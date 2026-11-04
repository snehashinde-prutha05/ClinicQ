"""ClinicQ - a fair queue and token system for small clinics (Flask + SQLite)."""
import math
import os
import re
import secrets
import socket
import sqlite3
import unicodedata
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from functools import wraps
from dotenv import load_dotenv

from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   session, url_for)
from markupsafe import Markup
try:
    import segno          # optional: QR code on the walk-in slip
except ImportError:       # the app works without it
    segno = None
from werkzeug.security import check_password_hash, generate_password_hash

# ----------------------------------------------------------------- config
BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get(
    "CLINICQ_DB",
    "/tmp/clinicq.db" if os.environ.get("VERCEL") else os.path.join(BASE, "clinicq.db")
)
BIND_HOST = os.environ.get("CLINICQ_HOST", "127.0.0.1")
TEST_MODE = os.environ.get("CLINICQ_TEST") == "1"   # enables /__test__ helpers

GRACE_MIN = 15            # R3: minutes late an online patient may arrive
NOSHOW_MIN = 5            # R5: minutes a called patient has to show up
BOOKING_LEAD_MIN = 20     # minimum time given to reach the clinic after booking
CHECKIN_OPEN_MIN = 15     # R9: patient self check-in opens this long before the 'reach by' time
ONLINE_LIMIT_DEFAULT = int(os.environ.get("CLINICQ_ONLINE_LIMIT", 24))   # R10: online tokens per day
DEFAULT_CONSULT_MIN = 8   # R7: used until real consultations are recorded
REJOIN_AFTER = 3          # R5: a skipped patient rejoins behind this many people
ACTIVE = ("Booked", "Arrived", "Called", "In consultation")

# R8: the only legal state changes (used for state-transition testing)
ALLOWED = {
    "Booked": {"Arrived", "Cancelled"},
    "Arrived": {"Called", "Cancelled"},
    "Called": {"In consultation", "Skipped"},
    "In consultation": {"Completed"},
    "Skipped": {"Arrived", "Cancelled"},
}

load_dotenv()
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")
app.config.update(SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_HTTPONLY=True)

SCHEMA = """
CREATE TABLE IF NOT EXISTS staff (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('receptionist', 'doctor'))
);
CREATE TABLE IF NOT EXISTS tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    day TEXT NOT NULL,
    token_no INTEGER NOT NULL,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('online', 'walk-in')),
    status TEXT NOT NULL,
    is_emergency INTEGER NOT NULL DEFAULT 0,
    emergency_at TEXT,
    queue_pos REAL,
    rejoined INTEGER NOT NULL DEFAULT 0,
    was_late INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    expected_arrival TEXT,
    arrived_at TEXT, called_at TEXT, started_at TEXT, completed_at TEXT,
    UNIQUE (day, token_no)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_phone ON tokens (day, phone)
    WHERE status IN ('Booked', 'Arrived', 'Called', 'In consultation');
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, token_no INTEGER
);
"""


def init_db():
    con = sqlite3.connect(DB_PATH)
    con.executescript(SCHEMA)
    if con.execute("SELECT COUNT(*) FROM staff").fetchone()[0] == 0:
        con.executemany(
            "INSERT INTO staff (username, password_hash, role) VALUES (?, ?, ?)",
            [("reception", generate_password_hash("reception123"), "receptionist"),
             ("doctor", generate_password_hash("doctor123"), "doctor")])
    con.commit()
    con.close()


# ------------------------------------------------------------- db helpers
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@contextmanager
def tx(db):
    """One write transaction. BEGIN IMMEDIATE makes two receptionists queue up
    instead of both reading the same 'last token number' (R1)."""
    db.execute("BEGIN IMMEDIATE")
    try:
        yield
        db.execute("COMMIT")
    except Exception:
        db.execute("ROLLBACK")
        raise


class RuleError(Exception):
    """A business rule was broken; the message is safe to show to the user."""


def now():
    return datetime.now().replace(microsecond=0)


def ts(dt):
    return dt.isoformat(sep=" ")


def ts_precise():
    """Microsecond timestamp: two emergencies flagged in the same second keep their order."""
    return datetime.now().isoformat(sep=" ", timespec="microseconds")


def parse(s):
    return datetime.fromisoformat(s)


def today():
    return date.today().isoformat()


def log(db, actor, action, token_no=None):
    db.execute("INSERT INTO events (at, actor, action, token_no) VALUES (?,?,?,?)",
               (ts(now()), actor, action, token_no))


# ------------------------------------------------------------ pure rules
def valid_name(name):
    """2-60 characters: letters (any script, including Devanagari vowel signs), spaces . ' -"""
    if not 2 <= len(name) <= 60 or not unicodedata.category(name[0]).startswith("L"):
        return False
    return all(unicodedata.category(c)[0] in "LM" or c in " .'-\u200c\u200d" for c in name)


def normalize_phone(raw):
    """'+91 98765-43210', '098765 43210', '9876543210' -> '9876543210' (else None)."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits if re.fullmatch(r"[6-9]\d{9}", digits) else None


def is_late(expected, arrived, grace=GRACE_MIN):
    """R3: late only when MORE than `grace` minutes after the expected time."""
    return (arrived - expected) > timedelta(minutes=grace)


def clean_person(form):
    errors = {}
    name = " ".join((form.get("name") or "").split())
    if not valid_name(name):
        errors["name"] = "Enter the full name using letters only (2 to 60 characters)."
    phone = normalize_phone(form.get("phone"))
    if not phone:
        errors["phone"] = "Enter a valid 10-digit mobile number, for example 98765 43210."
    return name, phone, errors


# --------------------------------------------------------------- settings
def get_setting(db, key, default=None):
    r = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default


def set_setting(db, key, value):
    db.execute("INSERT INTO settings (key, value) VALUES (?, ?) "
               "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))


def online_open(db):
    return get_setting(db, "online_open", "1") == "1"


def online_limit(db):
    return int(get_setting(db, "online_limit", ONLINE_LIMIT_DEFAULT))


def online_count(db):
    return db.execute("SELECT COUNT(*) FROM tokens WHERE day=? AND source='online' "
                      "AND status != 'Cancelled'", (today(),)).fetchone()[0]


def booking_block(db):
    """R10 / R11: why online booking is unavailable right now (None when it is open)."""
    if not online_open(db):
        return "Online booking is paused for now. Please visit the clinic and take a walk-in token."
    if online_count(db) >= online_limit(db):
        return "Online tokens for today are full. Please visit the clinic and take a walk-in token."
    return None


# ------------------------------------------------------------ queue reads
def waiting(db):
    """Patients present and waiting, in the order they will be called."""
    return db.execute(
        """SELECT * FROM tokens WHERE day=? AND status='Arrived'
           ORDER BY is_emergency DESC,
                    CASE WHEN is_emergency=1 THEN emergency_at END ASC,
                    queue_pos ASC, token_no ASC""", (today(),)).fetchall()


def current(db):
    return db.execute(
        "SELECT * FROM tokens WHERE day=? AND status IN ('Called','In consultation') "
        "ORDER BY called_at LIMIT 1", (today(),)).fetchone()


def avg_consult(db):
    rows = db.execute(
        "SELECT started_at, completed_at FROM tokens WHERE day=? AND status='Completed' "
        "AND started_at IS NOT NULL AND completed_at IS NOT NULL "
        "ORDER BY completed_at DESC LIMIT 5", (today(),)).fetchall()
    mins = [(parse(r["completed_at"]) - parse(r["started_at"])).total_seconds() / 60
            for r in rows]
    mins = [m for m in mins if m > 0]
    return max(sum(mins) / len(mins), 1.0) if mins else float(DEFAULT_CONSULT_MIN)


def estimate(db, t):
    """R7: minutes = people ahead x average consultation time."""
    w = waiting(db)
    ids = [x["id"] for x in w]
    if t["id"] not in ids:
        return None
    k = ids.index(t["id"])
    busy = 1 if current(db) else 0
    return {"position": k + 1, "waiting_ahead": k, "busy": busy,
            "minutes": math.ceil((k + busy) * avg_consult(db))}


def max_token_no(db):
    return db.execute("SELECT COALESCE(MAX(token_no),0) FROM tokens WHERE day=?",
                      (today(),)).fetchone()[0]


def expire_noshows(db):
    """R5: a token called more than NOSHOW_MIN minutes ago is skipped."""
    cutoff = ts(now() - timedelta(minutes=NOSHOW_MIN))
    stale = db.execute("SELECT id FROM tokens WHERE day=? AND status='Called' AND called_at < ?",
                       (today(), cutoff)).fetchall()
    if not stale:
        return
    with tx(db):
        for r in stale:
            row = db.execute("SELECT token_no FROM tokens WHERE id=? AND status='Called'",
                             (r["id"],)).fetchone()
            if row:
                db.execute("UPDATE tokens SET status='Skipped' WHERE id=?", (r["id"],))
                log(db, "system", "auto-skipped (no-show)", row["token_no"])


# ----------------------------------------------------------- queue writes
def fetch(db, tid):
    t = db.execute("SELECT * FROM tokens WHERE id=?", (tid,)).fetchone()
    if not t:
        raise RuleError("That token does not exist.")
    if t["day"] != today():
        raise RuleError("That token is from a previous day.")
    return t


def check(t, new):
    if new not in ALLOWED.get(t["status"], set()):
        raise RuleError(f"Token {t['token_no']} is {t['status']} and cannot become {new}.")


def issue_token(db, actor, name, phone, source, emergency=False):
    n = now()
    try:
        with tx(db):
            if db.execute(
                "SELECT 1 FROM tokens WHERE day=? AND phone=? AND status IN "
                "('Booked','Arrived','Called','In consultation')", (today(), phone)).fetchone():
                raise RuleError("This phone number already has an active token today.")   # R6
            if source == "online":
                blocked = booking_block(db)                                                # R10, R11
                if blocked:
                    raise RuleError(blocked)
            no = max_token_no(db) + 1                                                      # R1
            code = secrets.token_urlsafe(6)
            if source == "walk-in":
                status, pos, arrived, expected = "Arrived", float(no), ts(n), None
            else:
                status, pos, arrived = "Booked", None, None
                busy = 1 if current(db) else 0
                wait = math.ceil((len(waiting(db)) + busy) * avg_consult(db))
                expected = ts(n + timedelta(minutes=max(wait, BOOKING_LEAD_MIN)))
            cur = db.execute(
                "INSERT INTO tokens (code, day, token_no, name, phone, source, status, "
                "is_emergency, emergency_at, queue_pos, created_at, expected_arrival, arrived_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (code, today(), no, name, phone, source, status,
                 1 if emergency else 0, ts_precise() if emergency else None, pos,
                 ts(n), expected, arrived))
            tid = cur.lastrowid
            log(db, actor, "issued emergency token" if emergency else f"issued {source} token", no)
    except sqlite3.IntegrityError:
        raise RuleError("Could not issue the token. Please try again.")
    return code, tid


def act_arrive(db, actor, tid):
    with tx(db):
        t = fetch(db, tid)
        if t["status"] != "Booked":
            raise RuleError(f"Token {t['token_no']} is {t['status']}; only booked tokens can check in.")
        n, w = now(), waiting(db)
        late = bool(t["source"] == "online" and t["expected_arrival"]
                    and is_late(parse(t["expected_arrival"]), n))
        if late and w:   # R3: behind everyone already waiting
            pos = max(max(x["queue_pos"] for x in w), max_token_no(db)) + 0.5
        else:
            pos = float(t["token_no"])
        db.execute("UPDATE tokens SET status='Arrived', arrived_at=?, queue_pos=?, was_late=? WHERE id=?",
                   (ts(n), pos, 1 if (late and w) else 0, tid))
        log(db, actor, "checked in late" if (late and w) else "checked in", t["token_no"])


def act_checkin(db, actor, tid):
    """R9: a patient may check themselves in once the window opens."""
    t = fetch(db, tid)
    if t["status"] != "Booked":
        raise RuleError("Only booked tokens can check in.")
    opens = parse(t["expected_arrival"]) - timedelta(minutes=CHECKIN_OPEN_MIN)
    if now() < opens:
        raise RuleError(f"Check-in opens at {opens.strftime('%I:%M %p').lstrip('0')}. "
                        "You can also tell reception when you arrive.")
    act_arrive(db, actor, tid)


def act_emergency(db, actor, tid):
    with tx(db):
        t = fetch(db, tid)
        if t["status"] not in ("Booked", "Arrived"):
            raise RuleError("Only booked or waiting patients can be marked as emergency.")
        if t["is_emergency"]:
            raise RuleError("This patient is already marked as emergency.")
        if t["status"] == "Booked":      # an emergency is physically present
            db.execute("UPDATE tokens SET status='Arrived', arrived_at=?, queue_pos=? WHERE id=?",
                       (ts(now()), float(t["token_no"]), tid))
        db.execute("UPDATE tokens SET is_emergency=1, emergency_at=? WHERE id=?", (ts_precise(), tid))
        log(db, actor, "marked EMERGENCY", t["token_no"])


def act_call_next(db, actor):
    with tx(db):
        if current(db):
            raise RuleError("Finish the current patient before calling the next one.")   # R4
        w = waiting(db)
        if not w:
            raise RuleError("No patients are waiting.")
        t = w[0]
        db.execute("UPDATE tokens SET status='Called', called_at=? WHERE id=?", (ts(now()), t["id"]))
        log(db, actor, "called", t["token_no"])


def act_move(db, actor, tid, new, stamp=None, verb=None):
    with tx(db):
        t = fetch(db, tid)
        check(t, new)
        if stamp:
            db.execute(f"UPDATE tokens SET status=?, {stamp}=? WHERE id=?", (new, ts(now()), tid))
        else:
            db.execute("UPDATE tokens SET status=? WHERE id=?", (new, tid))
        log(db, actor, verb or new.lower(), t["token_no"])


def act_rejoin(db, actor, tid):
    with tx(db):
        t = fetch(db, tid)
        if t["status"] != "Skipped":
            raise RuleError("Only skipped tokens can rejoin the queue.")
        if t["rejoined"]:
            raise RuleError("This token has already rejoined once. Please ask reception.")
        nw = [x for x in waiting(db) if not x["is_emergency"]]
        if len(nw) <= REJOIN_AFTER:
            pos = max(x["queue_pos"] for x in nw) + 0.5 if nw else float(t["token_no"])
        else:   # slot in behind the first REJOIN_AFTER patients
            pos = (nw[REJOIN_AFTER - 1]["queue_pos"] + nw[REJOIN_AFTER]["queue_pos"]) / 2
        db.execute("UPDATE tokens SET status='Arrived', rejoined=1, arrived_at=?, queue_pos=?, "
                   "called_at=NULL WHERE id=?", (ts(now()), pos, tid))
        log(db, actor, "rejoined the queue", t["token_no"])


# ------------------------------------------------------- auth + security
def home_for(role):
    return url_for("reception") if role == "receptionist" else url_for("doctor")


def staff_required(*roles):
    def deco(f):
        @wraps(f)
        def wrapper(*a, **kw):
            if "role" not in session:
                return redirect(url_for("login", next=request.path))
            if roles and session["role"] not in roles:
                flash("You do not have access to that page.", "error")
                return redirect(home_for(session["role"]))
            return f(*a, **kw)
        return wrapper
    return deco


@app.before_request
def csrf_protect():
    if request.method == "POST" and not request.path.startswith("/__test__"):
        sent, real = request.form.get("csrf", ""), session.get("csrf", "")
        if not real or not secrets.compare_digest(sent, real):
            abort(400)


@app.context_processor
def inject():
    def csrf_field():
        session.setdefault("csrf", secrets.token_hex(16))
        return Markup(f'<input type="hidden" name="csrf" value="{session["csrf"]}">')
    return dict(csrf_field=csrf_field, GRACE_MIN=GRACE_MIN, NOSHOW_MIN=NOSHOW_MIN,
                BOOKING_LEAD_MIN=BOOKING_LEAD_MIN, CHECKIN_OPEN_MIN=CHECKIN_OPEN_MIN)


@app.template_filter("hm")
def hm(s):
    return parse(s).strftime("%I:%M %p").lstrip("0") if s else ""


@app.template_filter("maskphone")
def maskphone(p):
    return p[:2] + "\u2022" * 6 + p[-2:] if p and len(p) == 10 else p


@app.template_filter("shortname")
def shortname(n):
    """'Ravi Kumar' -> 'Ravi K.' (the status page can be opened by phone number, so show less)."""
    parts = (n or "").split()
    return parts[0] + (f" {parts[1][0]}." if len(parts) > 1 else "") if parts else ""


@app.template_filter("label")
def label(status):
    return "Waiting" if status == "Arrived" else status


@app.template_filter("slug")
def slug(status):
    return status.lower().replace(" ", "-")


# -------------------------------------------------------- patient routes
@app.route("/")
def index():
    my, code = None, session.get("last_code")
    if code:
        db = get_db()
        expire_noshows(db)
        row = db.execute("SELECT * FROM tokens WHERE code=? AND day=?", (code, today())).fetchone()
        if row and row["status"] in ("Booked", "Arrived", "Called", "In consultation", "Skipped"):
            my = row
    return render_template("index.html", my=my)

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/book", methods=["GET", "POST"])
def book():
    db, errors, form = get_db(), {}, request.form
    if request.method == "POST":
        name, phone, errors = clean_person(form)
        if not errors:
            try:
                code, _ = issue_token(db, "patient", name, phone, "online")
                session["last_code"] = code
                return redirect(url_for("status", code=code))
            except RuleError as e:
                errors["_"] = str(e)
    return render_template("book.html", errors=errors, form=form, closed=booking_block(db))


@app.route("/track")
def track():
    return render_template("track.html")


@app.post("/find")
def find():
    phone = normalize_phone(request.form.get("phone"))
    row = None
    if phone:
        row = get_db().execute(
            "SELECT code FROM tokens WHERE day=? AND phone=? AND status IN "
            "('Booked','Arrived','Called','In consultation','Skipped') ORDER BY id DESC LIMIT 1",
            (today(), phone)).fetchone()
    if row:
        session["last_code"] = row["code"]
        return redirect(url_for("status", code=row["code"]))
    flash("No active token found for that number today. Check the number or get a new token.", "error")
    return redirect(url_for("track"))


def panel_ctx(db, code):
    expire_noshows(db)
    t = db.execute("SELECT * FROM tokens WHERE code=?", (code,)).fetchone()
    if not t:
        abort(404)
    est = estimate(db, t)
    ctx = dict(t=t, est=est, serving=current(db), noshow_left=None, deadline=None,
               turn_at=ts(now() + timedelta(minutes=est["minutes"])) if est else None)
    if t["status"] == "Called" and t["called_at"]:
        left = parse(t["called_at"]) + timedelta(minutes=NOSHOW_MIN) - now()
        ctx["noshow_left"] = max(0, math.ceil(left.total_seconds() / 60))
    if t["status"] == "Booked" and t["expected_arrival"]:
        ctx["deadline"] = ts(parse(t["expected_arrival"]) + timedelta(minutes=GRACE_MIN))
        opens = parse(t["expected_arrival"]) - timedelta(minutes=CHECKIN_OPEN_MIN)
        ctx["checkin_open_at"], ctx["checkin_open"] = ts(opens), now() >= opens
    return ctx


@app.route("/t/<code>")
def status(code):
    return render_template("status.html", **panel_ctx(get_db(), code))


@app.route("/t/<code>/panel")
def status_panel(code):
    return render_template("_panel.html", **panel_ctx(get_db(), code))


@app.post("/t/<code>/<action>")
def patient_action(code, action):
    db = get_db()
    t = db.execute("SELECT id FROM tokens WHERE code=?", (code,)).fetchone()
    if not t or action not in ("cancel", "rejoin", "checkin"):
        abort(404)
    try:
        if action == "checkin":
            act_checkin(db, "patient", t["id"])
            flash("You are checked in. Please wait nearby.", "ok")
        elif action == "cancel":
            act_move(db, "patient", t["id"], "Cancelled", verb="cancelled by patient")
            flash("Your token has been cancelled.", "ok")
        else:
            act_rejoin(db, "patient", t["id"])
            flash("You are back in the queue.", "ok")
    except (RuleError, sqlite3.IntegrityError) as e:
        flash(str(e) if isinstance(e, RuleError) else "This phone number already has another active token.", "error")
    return redirect(url_for("status", code=code))


@app.route("/display")
def display():
    db = get_db()
    expire_noshows(db)
    return render_template("display.html", serving=current(db), nxt=waiting(db)[:4])


# ----------------------------------------------------------- staff routes
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u, p = (request.form.get("username") or "").strip(), request.form.get("password") or ""
        row = get_db().execute("SELECT * FROM staff WHERE username=?", (u,)).fetchone()
        if row and check_password_hash(row["password_hash"], p):
            session.clear()
            session.update(user=row["username"], role=row["role"], csrf=secrets.token_hex(16))
            nxt = request.args.get("next", "")
            if nxt.startswith("/") and not nxt.startswith("//"):
                return redirect(nxt)
            return redirect(home_for(row["role"]))
        flash("Wrong username or password.", "error")
    return render_template("login.html")


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/reception")
@staff_required("receptionist")
def reception():
    db = get_db()
    expire_noshows(db)
    t = today()
    q = lambda sql: db.execute(sql, (t,)).fetchall()
    stats = dict(
        waiting=len(waiting(db)),
        booked=db.execute("SELECT COUNT(*) FROM tokens WHERE day=? AND status='Booked'", (t,)).fetchone()[0],
        inroom=1 if current(db) else 0,
        done=db.execute("SELECT COUNT(*) FROM tokens WHERE day=? AND status='Completed'", (t,)).fetchone()[0])
    online = dict(open=online_open(db), used=online_count(db), limit=online_limit(db))
    return render_template(
        "reception.html", stats=stats, queue=waiting(db), serving=current(db), online=online,
        booked=q("SELECT * FROM tokens WHERE day=? AND status='Booked' ORDER BY token_no"),
        skipped=q("SELECT * FROM tokens WHERE day=? AND status='Skipped' ORDER BY token_no"),
        events=db.execute("SELECT * FROM events WHERE substr(at,1,10)=? ORDER BY id DESC LIMIT 8", (t,)).fetchall())


@app.post("/reception/issue")
@staff_required("receptionist")
def reception_issue():
    name, phone, errors = clean_person(request.form)
    if errors:
        flash(" ".join(errors.values()), "error")
    else:
        try:
            _, tid = issue_token(get_db(), session["user"], name, phone, "walk-in",
                                 emergency=request.form.get("emergency") == "on")
            return redirect(url_for("slip", tid=tid))
        except RuleError as e:
            flash(str(e), "error")
    return redirect(url_for("reception"))


def lan_ip():
    """This computer's address on the local network (None if it has no network)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("10.255.255.255", 1))     # nothing is sent; this only picks the network card
        ip = sock.getsockname()[0]
        return None if ip.startswith("127.") else ip
    except OSError:
        return None
    finally:
        sock.close()


def public_base():
    """Address a PHONE can open. 127.0.0.1 only means 'this device', so swap in the network address."""
    override = os.environ.get("CLINICQ_PUBLIC_URL")
    if override:
        return override.rstrip("/")
    host, _, port = request.host.partition(":")
    if host in ("127.0.0.1", "localhost", "[::1]"):
        ip = lan_ip()
        if ip:
            return f"{request.scheme}://{ip}" + (f":{port}" if port else "")
    return request.host_url.rstrip("/")


def qr_svg(text):
    if segno is None:
        return None
    # quiet zone of 4 modules and a solid white background make the code easy to scan
    return Markup(segno.make(text, error="m").svg_inline(scale=5, border=4, dark="#0e2a47", light="#ffffff"))


@app.route("/slip/<int:tid>")
@staff_required("receptionist")
def slip(tid):
    """Printable token slip for a walk-in patient, with a QR code to follow the queue live."""
    db = get_db()
    expire_noshows(db)
    t = db.execute("SELECT * FROM tokens WHERE id=? AND day=?", (tid, today())).fetchone()
    if not t:
        abort(404)
    est = estimate(db, t)
    track = public_base() + url_for("status", code=t["code"])
    return render_template(
        "slip.html", t=t, est=est, track_url=track, qr=qr_svg(track),
        phone_ready=BIND_HOST != "127.0.0.1" or bool(os.environ.get("CLINICQ_PUBLIC_URL")),
        turn_at=ts(now() + timedelta(minutes=est["minutes"])) if est else None)


@app.post("/reception/online-toggle")
@staff_required("receptionist")
def online_toggle():
    db = get_db()
    new = "0" if online_open(db) else "1"
    set_setting(db, "online_open", new)
    log(db, session["user"], "paused online booking" if new == "0" else "resumed online booking")
    flash("Online booking paused." if new == "0" else "Online booking resumed.", "ok")
    return redirect(url_for("reception"))


@app.route("/activity")
@staff_required()
def activity():
    rows = get_db().execute("SELECT * FROM events WHERE substr(at,1,10)=? ORDER BY id DESC LIMIT 300",
                            (today(),)).fetchall()
    return render_template("activity.html", rows=rows)


@app.route("/doctor")
@staff_required("doctor")
def doctor():
    db = get_db()
    expire_noshows(db)
    t, w, avg = today(), waiting(db), avg_consult(db)
    return render_template(
        "doctor.html", serving=current(db), queue=w[:6], waiting_count=len(w), avg=round(avg),
        clear_minutes=math.ceil(len(w) * avg),
        booked=db.execute("SELECT COUNT(*) FROM tokens WHERE day=? AND status='Booked'", (t,)).fetchone()[0],
        done=db.execute("SELECT COUNT(*) FROM tokens WHERE day=? AND status='Completed'", (t,)).fetchone()[0])


@app.post("/doctor/call-next")
@staff_required("doctor")
def doctor_call_next():
    try:
        act_call_next(get_db(), session["user"])
    except RuleError as e:
        flash(str(e), "error")
    return redirect(url_for("doctor"))


PERMS = {"arrive": {"receptionist"}, "emergency": {"receptionist"}, "cancel": {"receptionist"},
         "rejoin": {"receptionist"}, "skip": {"receptionist", "doctor"},
         "start": {"doctor"}, "complete": {"doctor"}}


@app.post("/token/<int:tid>/<action>")
@staff_required()
def token_action(tid, action):
    if action not in PERMS:
        abort(404)
    if session["role"] not in PERMS[action]:
        abort(403)
    db, actor = get_db(), session["user"]
    try:
        if action == "arrive":
            act_arrive(db, actor, tid)
        elif action == "emergency":
            act_emergency(db, actor, tid)
        elif action == "rejoin":
            act_rejoin(db, actor, tid)
        elif action == "cancel":
            act_move(db, actor, tid, "Cancelled", verb="cancelled")
        elif action == "skip":
            act_move(db, actor, tid, "Skipped", verb="marked not present")
        elif action == "start":
            act_move(db, actor, tid, "In consultation", stamp="started_at", verb="started consultation")
        elif action == "complete":
            act_move(db, actor, tid, "Completed", stamp="completed_at", verb="completed")
    except RuleError as e:
        flash(str(e), "error")
    except sqlite3.IntegrityError:
        flash("This phone number already has another active token today.", "error")
    return redirect(home_for(session["role"]))


# ---------------------------------------------------------- error pages
@app.errorhandler(400)
@app.errorhandler(403)
@app.errorhandler(404)
@app.errorhandler(405)
def error_page(e):
    msgs = {400: "That request could not be verified. Go back, refresh the page and try again.",
            403: "You do not have permission to do that.",
            404: "We could not find that page.",
            405: "That address cannot be opened directly. Please use the buttons in the app."}
    return render_template("error.html", code=e.code, msg=msgs.get(e.code, "Something went wrong.")), e.code


# ------------------------------------------------- test helpers (opt-in)
if TEST_MODE:
    @app.post("/__test__/reset")
    def test_reset():
        db = get_db()
        db.execute("DELETE FROM tokens")
        db.execute("DELETE FROM events")
        db.execute("DELETE FROM settings")
        return "reset", 200

    @app.post("/__test__/set-limit")
    def test_set_limit():
        set_setting(get_db(), "online_limit", int(request.form.get("limit", ONLINE_LIMIT_DEFAULT)))
        return "set", 200

    @app.post("/__test__/shift/<int:tid>")
    def test_shift(tid):
        """Move a timestamp earlier so time rules (grace, no-show) can be tested instantly."""
        field, minutes = request.form.get("field"), int(request.form.get("minutes", 0))
        if field not in ("expected_arrival", "called_at"):
            abort(400)
        db = get_db()
        row = db.execute(f"SELECT {field} FROM tokens WHERE id=?", (tid,)).fetchone()
        if not row or not row[field]:
            abort(404)
        db.execute(f"UPDATE tokens SET {field}=? WHERE id=?",
                   (ts(parse(row[field]) - timedelta(minutes=minutes)), tid))
        return "shifted", 200

    @app.post("/__test__/set-late/<int:tid>")
    def test_set_late(tid):
        """Make an online token's 'reach by' time exactly N minutes in the past (N = lateness)."""
        minutes = int(request.form.get("minutes", 0))
        get_db().execute("UPDATE tokens SET expected_arrival=? WHERE id=?",
                         (ts(now() - timedelta(minutes=minutes)), tid))
        return "set", 200


init_db()

if __name__ == "__main__":
    if BIND_HOST != "127.0.0.1" and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        print(f"\n  Phone demo: open http://{lan_ip() or '<this-computer-address>'}:5000 on this computer, "
              "then scan the QR code on a walk-in slip with a phone on the same Wi-Fi.\n")
    # the interactive debugger is only safe on this computer, so it is off when the app is shared on the network
    app.run(host=BIND_HOST, debug=True, use_debugger=(BIND_HOST == "127.0.0.1"))