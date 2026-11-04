"""Small helper functions shared by the Selenium regression tests."""
import os
import re
import urllib.error
import urllib.parse
import urllib.request

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

URL = os.environ.get("CLINICQ_URL", "http://127.0.0.1:5000").rstrip("/")
ACCOUNTS = {"receptionist": ("reception", "reception123"), "doctor": ("doctor", "doctor123")}


# ---- plain HTTP calls to the test-mode helpers of the app --------------------
def post(path, data=None):
    body = urllib.parse.urlencode(data or {}).encode()
    req = urllib.request.Request(URL + path, data=body, method="POST")
    return urllib.request.urlopen(req, timeout=10).status


def shift(db_id, field, minutes):
    """Move a stored time earlier (used for the 5-minute no-show rule)."""
    post(f"/__test__/shift/{db_id}", {"field": field, "minutes": minutes})


def set_limit(limit):
    """Set today's online-token limit (rule R10)."""
    post("/__test__/set-limit", {"limit": limit})


def set_late(db_id, minutes):
    """Pretend an online patient was due `minutes` ago (used for the 15-minute grace rule)."""
    post(f"/__test__/set-late/{db_id}", {"minutes": minutes})


# ---- waiting + clicking ------------------------------------------------------
def wait(d, seconds=10):
    return WebDriverWait(d, seconds)


def el(d, element_id):
    return wait(d).until(EC.presence_of_element_located((By.ID, element_id)))


def click(d, element_id):
    wait(d).until(EC.element_to_be_clickable((By.ID, element_id))).click()


def type_into(d, element_id, text):
    box = el(d, element_id)
    box.clear()
    box.send_keys(text)


def has(d, element_id):
    return len(d.find_elements(By.ID, element_id)) > 0


def text_of(d, element_id):
    return el(d, element_id).text.strip()


def flash_text(d):
    return wait(d).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".flash"))).text


# ---- staff actions -----------------------------------------------------------
def login(d, role):
    """Log in as a staff role. Retries once: a stale page or cookie left over from the
    previous test can occasionally swallow the first attempt (found in the Windows run)."""
    user, pw = ACCOUNTS[role]
    target = "/reception" if role == "receptionist" else "/doctor"
    for attempt in (1, 2):
        d.delete_all_cookies() if attempt == 2 else None
        d.get(URL + "/login")
        type_into(d, "username", user)
        type_into(d, "password", pw)
        click(d, "login-btn")
        try:
            wait(d, 8).until(EC.url_contains(target))
            return
        except TimeoutException:
            if attempt == 2:
                raise


def issue_walkin(d, name, phone, emergency=False):
    """Receptionist must be logged in."""
    d.get(URL + "/reception")
    type_into(d, "walk-name", name)
    type_into(d, "walk-phone", phone)
    if emergency:
        click(d, "walk-emergency")
    click(d, "issue-btn")
    return text_of(d, "slip-token-no")   # the token slip opens after a successful issue


def row_xpath(table_id, token_no):
    return (f"//table[@id='{table_id}']//tr[td[contains(@class,'tok') "
            f"and normalize-space()='{token_no:02d}']]")


def row_button(d, table_id, token_no, prefix):
    xp = row_xpath(table_id, token_no) + f"//button[starts-with(@id,'{prefix}-')]"
    return wait(d).until(EC.element_to_be_clickable((By.XPATH, xp)))


def db_id(button):
    return int(button.get_attribute("id").rsplit("-", 1)[1])


def queue_order(d):
    """Token numbers in the reception 'Waiting' table, top to bottom."""
    d.get(URL + "/reception")
    return [c.text.strip() for c in d.find_elements(By.CSS_SELECTOR, "#queue-table td.tok")]


def queue_row_text(d, token_no):
    return d.find_element(By.XPATH, row_xpath("queue-table", token_no)).text


def reception_action(d, table_id, token_no, prefix):
    d.get(URL + "/reception")
    row_button(d, table_id, token_no, prefix).click()
    wait(d).until(EC.presence_of_element_located((By.ID, "issue-btn")))


def doctor_call_next(d):
    d.get(URL + "/doctor")
    click(d, "call-next-btn")
    el(d, "current-no")


def doctor_serving_db_id(d):
    for bid in ("start-btn", "complete-btn"):
        found = d.find_elements(By.ID, bid)
        if found:
            action = found[0].find_element(By.XPATH, "./ancestor::form").get_attribute("action")
            return int(re.search(r"/token/(\d+)/", action).group(1))
    raise AssertionError("No patient is in the doctor's room")


def doctor_finish_current(d):
    """Start and complete the patient who is currently called."""
    click(d, "start-btn")
    click(d, "complete-btn")
    el(d, "call-next-btn")


# ---- patient actions ---------------------------------------------------------
def submit_booking(d, name, phone):
    d.get(URL + "/book")
    type_into(d, "name", name)
    type_into(d, "phone", phone)
    click(d, "book-btn")


def book_online(d, name, phone):
    submit_booking(d, name, phone)
    wait(d).until(EC.url_contains("/t/"))
    el(d, "token-no")


def find_my_token(d, phone):
    d.get(URL + "/")
    type_into(d, "find-phone", phone)
    click(d, "find-btn")