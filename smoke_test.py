import os, re, sys, tempfile  # quick developer check, not your Selenium suite
os.environ["CLINICQ_DB"] = tempfile.mktemp(suffix=".db")
os.environ["CLINICQ_TEST"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A

ok = fail = 0
def check(name, cond):
    global ok, fail
    if cond: ok += 1; print("PASS", name)
    else: fail += 1; print("FAIL", name)

def client(role=None):
    c = A.app.test_client()
    with c.session_transaction() as s:
        s["csrf"] = "x"
        if role: s["role"] = role; s["user"] = role
    return c
def post(c, url, **d): return c.post(url, data={"csrf": "x", **d}, follow_redirects=True)
def row(sql, *a):
    with A.app.app_context(): return A.get_db().execute(sql, a).fetchone()
def sql(q, *a):
    if len(a) == 1 and isinstance(a[0], tuple): a = a[0]
    with A.app.app_context(): A.get_db().execute(q, a)

rec, doc, pat = client("receptionist"), client("doctor"), client()

# pure rules
check("phone +91 normalised", A.normalize_phone("+91 98765-43210") == "9876543210")
check("phone 0-prefix normalised", A.normalize_phone("098765 43210") == "9876543210")
check("phone bad rejected", A.normalize_phone("12345") is None and A.normalize_phone("5876543210") is None)
from datetime import datetime, timedelta
e = datetime(2026,1,1,10,0)
check("grace 15:00 not late", not A.is_late(e, e+timedelta(minutes=15)))
check("grace 15:01 late", A.is_late(e, e+timedelta(minutes=15, seconds=1)))

# pages render
check("home 200", pat.get("/").status_code == 200)
check("book 200", pat.get("/book").status_code == 200)
check("login 200", pat.get("/login").status_code == 200)
check("reception blocked when logged out", pat.get("/reception").status_code == 302)
check("doctor blocked for receptionist", rec.get("/doctor").status_code == 302)
check("csrf enforced", A.app.test_client().post("/book", data={"name":"A B","phone":"9876543210"}).status_code == 400)

# R1 online booking + R6 one token per phone
r = post(pat, "/book", name="Ravi Kumar", phone="98765 43210")
check("online booking shows ticket", b"You are booked" in r.data)
r = post(pat, "/book", name="Ravi Again", phone="+91 9876543210")
check("R6 same phone (+91 variant) blocked", b"already has an active token" in r.data)
r = post(pat, "/book", name="X", phone="123")
check("validation errors shown", b"valid 10-digit" in r.data and b"letters only" in r.data)

# walk-in shares sequence
post(rec, "/reception/issue", name="Meena Shah", phone="9123456780")
check("R1 shared sequence 1,2", [r["token_no"] for r in [row("SELECT token_no FROM tokens WHERE name='Ravi Kumar'"), row("SELECT token_no FROM tokens WHERE name='Meena Shah'")]] == [1, 2])
check("walk-in is Arrived", row("SELECT status s FROM tokens WHERE token_no=2")["s"] == "Arrived")
check("online is Booked", row("SELECT status s FROM tokens WHERE token_no=1")["s"] == "Booked")

# R2 booked cannot be called
r = post(doc, "/doctor/call-next")
check("R2 call-next picks walk-in (booked not present)", row("SELECT status s FROM tokens WHERE token_no=2")["s"] == "Called")
check("R4 cannot call second while one is active", b"Finish the current patient" in post(doc, "/doctor/call-next").data)

# invalid transition
tid2 = row("SELECT id FROM tokens WHERE token_no=2")["id"]
check("R8 cannot complete a Called token", b"cannot become Completed" in post(doc, f"/token/{tid2}/complete").data)
post(doc, f"/token/{tid2}/start"); post(doc, f"/token/{tid2}/complete")
check("complete works", row("SELECT status s FROM tokens WHERE token_no=2")["s"] == "Completed")

# on-time arrival keeps token order; two more walk-ins
tid1 = row("SELECT id FROM tokens WHERE token_no=1")["id"]
post(rec, "/reception/issue", name="Asha Rao", phone="9000000001")   # token 3
post(rec, f"/token/{tid1}/arrive")
q = [r["token_no"] for r in A.app.app_context() and []] or None
with A.app.app_context(): order = [x["token_no"] for x in A.waiting(A.get_db())]
check("on-time online keeps place (1 before 3)", order == [1, 3])

# R4 emergency jumps queue
post(rec, "/reception/issue", name="Zed Khan", phone="9000000002", emergency="on")  # token 4
with A.app.app_context(): order = [x["token_no"] for x in A.waiting(A.get_db())]
check("R4 emergency first", order == [4, 1, 3])
# second emergency goes after first emergency
tid3 = row("SELECT id FROM tokens WHERE token_no=3")["id"]
post(rec, f"/token/{tid3}/emergency")
with A.app.app_context(): order = [x["token_no"] for x in A.waiting(A.get_db())]
check("two emergencies keep flag order", order[:2] == [4, 3])
check("double emergency refused", b"already marked" in post(rec, f"/token/{tid3}/emergency").data)

# R5 no-show + rejoin once
post(doc, "/doctor/call-next")  # calls 4
tid4 = row("SELECT id FROM tokens WHERE token_no=4")["id"]
sql("UPDATE tokens SET called_at=? WHERE id=?", (A.ts(A.now()-timedelta(minutes=6)), tid4))
doc.get("/doctor")
check("R5 auto-skip after 5+ min", row("SELECT status s FROM tokens WHERE id=?", tid4)["s"] == "Skipped")
code4 = row("SELECT code c FROM tokens WHERE id=?", tid4)["c"]
r = post(pat, f"/t/{code4}/rejoin")
check("rejoin once works", row("SELECT status s, rejoined r FROM tokens WHERE id=?", tid4)["r"] == 1)
post(doc, "/doctor/call-next")   # 4 again? emergency flag still set -> first
tid = row("SELECT id FROM tokens WHERE status='Called'")["id"]
post(doc, f"/token/{tid}/skip")
r = post(pat, f"/t/{row('SELECT code c FROM tokens WHERE id=?', tid)['c']}/rejoin")
check("R5 second rejoin refused", b"already rejoined once" in r.data or b"already rejoined" in r.data)

# R3 late arrival goes behind waiting
post(pat, "/book", name="Late Larry", phone="9111111111")
tl = row("SELECT id, code FROM tokens WHERE name='Late Larry'")
post(rec, "/reception/issue", name="Walk Wendy", phone="9222222222")
sql("UPDATE tokens SET expected_arrival=? WHERE id=?", (A.ts(A.now()-timedelta(minutes=16)), tl["id"]))
post(rec, f"/token/{tl['id']}/arrive")
with A.app.app_context(): order = [x["token_no"] for x in A.waiting(A.get_db())]
late_no = row("SELECT token_no n FROM tokens WHERE id=?", tl["id"])["n"]
check("R3 late arrival is last", order[-1] == late_no and row("SELECT was_late w FROM tokens WHERE id=?", tl["id"])["w"] == 1)
post(pat, "/book", name="Edge Eddie", phone="9333333333")
te = row("SELECT id FROM tokens WHERE name='Edge Eddie'")["id"]
sql("UPDATE tokens SET expected_arrival=? WHERE id=?", (A.ts(A.now()-timedelta(minutes=14)), te))
post(rec, f"/token/{te}/arrive")
check("R3 14 min late is still on time", row("SELECT was_late w FROM tokens WHERE id=?", te)["w"] == 0)

# cancel frees the slot; terminal states
tc = row("SELECT id FROM tokens WHERE name='Walk Wendy'")["id"]
post(rec, f"/token/{tc}/cancel")
check("cancel works", row("SELECT status s FROM tokens WHERE id=?", tc)["s"] == "Cancelled")
check("cancelled cannot be cancelled again", b"cannot become Cancelled" in post(rec, f"/token/{tc}/cancel").data)
check("doctor cannot arrive (403)", doc.post(f"/token/{tc}/arrive", data={"csrf":"x"}).status_code == 403)

# status page + panel + display + estimate
code = row("SELECT code c FROM tokens WHERE name='Edge Eddie'")["c"]
check("status page", b"Your token" in pat.get(f"/t/{code}").data)
check("panel fragment", b"ticket" in pat.get(f"/t/{code}/panel").data)
check("display board", b"Now serving" in pat.get("/display").data)
check("find by phone", b"Your token" in post(pat, "/find", phone="+91 93333 33333").data)
check("find unknown phone", b"No active token" in post(pat, "/find", phone="9444444444").data)
check("unknown token 404", pat.get("/t/nope").status_code == 404)

# DB-level uniqueness backstop (R1)
import sqlite3
try:
    with A.app.app_context():
        A.get_db().execute("INSERT INTO tokens (code,day,token_no,name,phone,source,status,created_at) VALUES ('zz',?,1,'D','9555555555','walk-in','Arrived','x')", (A.today(),))
    check("R1 DB blocks duplicate token_no", False)
except sqlite3.IntegrityError:
    check("R1 DB blocks duplicate token_no", True)

# login
c = client()
r = c.post("/login", data={"csrf":"x","username":"doctor","password":"doctor123"}, follow_redirects=True)
check("doctor login", b"Doctor view" in r.data)
r = client().post("/login", data={"csrf":"x","username":"doctor","password":"bad"}, follow_redirects=True)
check("bad login rejected", b"Wrong username" in r.data)
check("open redirect blocked", client().post("/login?next=//evil.com", data={"csrf":"x","username":"doctor","password":"doctor123"}).headers["Location"].endswith("/doctor"))

# R9 / R10 / R11 (settings are per-database, reset after each check)
sql("INSERT OR REPLACE INTO settings (key, value) VALUES ('online_limit', '0')")
check("R10 quota full blocks online booking", b"are full" in post(pat, "/book", name="Quota Q", phone="9555555551").data)
sql("INSERT OR REPLACE INTO settings (key, value) VALUES ('online_limit', '24')")
sql("INSERT OR REPLACE INTO settings (key, value) VALUES ('online_open', '0')")
check("R11 paused blocks online booking", b"paused" in post(pat, "/book", name="Pause P", phone="9555555552").data)
sql("INSERT OR REPLACE INTO settings (key, value) VALUES ('online_open', '1')")
post(pat, "/book", name="Early Erin", phone="9555555553")
code_e = row("SELECT code c FROM tokens WHERE name='Early Erin'")["c"]
check("R9 self check-in refused before window", b"Check-in opens at" in post(pat, f"/t/{code_e}/checkin").data)
tid_e = row("SELECT id FROM tokens WHERE name='Early Erin'")["id"]
sql("UPDATE tokens SET expected_arrival=? WHERE id=?", (A.ts(A.now()), tid_e))
post(pat, f"/t/{code_e}/checkin")
check("R9 self check-in works when window open", row("SELECT status s FROM tokens WHERE id=?", tid_e)["s"] == "Arrived")
check("activity page lists actions", b"issued online token" in rec.get("/activity").data)
check("slip page renders for receptionist", b"slip-token-no" in rec.get("/slip/%d" % tid_e).data)
check("slip blocked when logged out", pat.get("/slip/%d" % tid_e).status_code == 302)

print(f"\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
