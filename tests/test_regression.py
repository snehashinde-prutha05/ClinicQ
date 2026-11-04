"""ClinicQ regression suite (Selenium WebDriver, Python).

Run the whole suite after every bug fix: that re-run IS the regression test.
Each test name starts with the test case id used in docs/TEST_CASES.csv.
"""
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

from helpers import *   # noqa: F401,F403  (URL, helper functions)


# ------------------------------------------------------------------ TC01
def test_tc01_home_dashboard_has_all_entries(driver):
    driver.get(URL + "/")
    assert "ClinicQ" in driver.title
    for element_id in ("book-link", "find-phone", "find-btn", "open-display",
                       "open-reception", "open-doctor", "open-login",
                       "nav-home", "nav-book", "nav-track", "nav-login"):
        assert has(driver, element_id), f"missing #{element_id} on the home page"


# ------------------------------------------------------------------ TC02 (equivalence partitions)
@pytest.mark.parametrize("name, phone, error_ids", [
    ("", "", ["name-err", "phone-err"]),                  # both empty
    ("Ravi123", "9876543210", ["name-err"]),              # digits in name
    ("<b>Ravi</b>", "9876543210", ["name-err"]),          # markup in name
    ("R", "9876543210", ["name-err"]),                    # name too short
    ("Ravi Kumar", "12345", ["phone-err"]),               # phone too short
    ("Ravi Kumar", "5876543210", ["phone-err"]),          # does not start with 6-9
    ("Ravi Kumar", "98765abcde", ["phone-err"]),          # letters in phone
])
def test_tc02_booking_validation(driver, name, phone, error_ids):
    submit_booking(driver, name, phone)
    for error_id in error_ids:
        # wait for the page to reload with the error (the form posts to the server)
        wait(driver).until(lambda d, e=error_id: has(d, e), f"expected #{error_id} for {name!r} / {phone!r}")
    assert "/t/" not in driver.current_url


# ------------------------------------------------------------------ TC03 (valid names in other scripts)
@pytest.mark.parametrize("name, phone", [
    ("Anne-Marie D'Souza", "9876500001"),
    ("रवि कुमार", "9876500002"),          # Hindi / Marathi (Devanagari)
    ("José Álvarez", "9876500003"),
])
def test_tc03_valid_names_in_any_script_are_accepted(driver, name, phone):
    book_online(driver, name, phone)
    assert text_of(driver, "token-status") == "Booked"


# ------------------------------------------------------------------ TC04
def test_tc04_valid_booking_creates_booked_ticket(driver):
    book_online(driver, "Ravi Kumar", "98765 43210")
    assert text_of(driver, "token-no") == "01"
    assert text_of(driver, "token-status") == "Booked"
    assert "Ravi" in text_of(driver, "status-body")


# ------------------------------------------------------------------ TC05  (R6)
def test_tc05_one_active_token_per_phone_in_any_format(driver):
    book_online(driver, "Ravi Kumar", "9876543210")
    for same_number in ("+91 98765 43210", "098765-43210", "98765 43210"):
        submit_booking(driver, "Ravi Again", same_number)
        assert "already has an active token" in text_of(driver, "form-error")


# ------------------------------------------------------------------ TC06  (R1)
def test_tc06_online_and_walkin_share_one_sequence(driver):
    book_online(driver, "Online One", "9876543210")
    assert text_of(driver, "token-no") == "01"
    login(driver, "receptionist")
    issue_walkin(driver, "Walk Two", "9123456780")
    assert "02" in queue_order(driver)
    book_online(driver, "Online Three", "9000000003")
    assert text_of(driver, "token-no") == "03"


# ------------------------------------------------------------------ TC07  (R2)
def test_tc07_booked_patient_is_not_called_until_arrived(driver):
    book_online(driver, "Online One", "9876543210")             # token 01, Booked
    login(driver, "receptionist")
    issue_walkin(driver, "Walk Two", "9123456780")              # token 02, Waiting
    login(driver, "doctor")
    doctor_call_next(driver)
    assert text_of(driver, "current-no") == "02"                # the walk-in, not the booked one


# ------------------------------------------------------------------ TC08  (R8)
def test_tc08_consultation_flow_and_state_transitions(driver):
    login(driver, "receptionist")
    issue_walkin(driver, "Walk One", "9123456780")
    login(driver, "doctor")
    doctor_call_next(driver)
    assert has(driver, "start-btn") and has(driver, "skip-btn")
    assert not has(driver, "complete-btn"), "a Called token must not be completable"
    click(driver, "start-btn")
    assert has(driver, "complete-btn") and not has(driver, "start-btn")
    click(driver, "complete-btn")
    assert has(driver, "call-next-btn")
    assert not driver.find_element(By.ID, "call-next-btn").is_enabled()    # nobody left


# ------------------------------------------------------------------ TC09  (R4)
def test_tc09_emergency_is_called_first(driver):
    login(driver, "receptionist")
    issue_walkin(driver, "Walk One", "9123456780")
    issue_walkin(driver, "Walk Two", "9123456781")
    issue_walkin(driver, "Emergency Three", "9123456782", emergency=True)
    assert queue_order(driver) == ["03", "01", "02"]
    login(driver, "doctor")
    doctor_call_next(driver)
    assert text_of(driver, "current-no") == "03"


# ------------------------------------------------------------------ TC10  (R4)
def test_tc10_emergency_does_not_interrupt_current_patient(driver):
    login(driver, "receptionist")
    issue_walkin(driver, "Walk One", "9123456780")
    issue_walkin(driver, "Walk Two", "9123456781")
    login(driver, "doctor")
    doctor_call_next(driver)                                    # 01 is now called
    login(driver, "receptionist")
    reception_action(driver, "queue-table", 2, "emergency")     # 02 becomes an emergency
    login(driver, "doctor")
    assert text_of(driver, "current-no") == "01"                # still 01
    assert not has(driver, "call-next-btn")                     # cannot call a second patient
    doctor_finish_current(driver)
    click(driver, "call-next-btn")
    assert text_of(driver, "current-no") == "02"


# ------------------------------------------------------------------ TC11  (R4)
def test_tc11_two_emergencies_keep_the_order_they_were_flagged(driver):
    login(driver, "receptionist")
    for i, phone in enumerate(("9123456780", "9123456781", "9123456782"), start=1):
        issue_walkin(driver, f"Walk {'ABC'[i-1]}", phone)
    reception_action(driver, "queue-table", 3, "emergency")
    reception_action(driver, "queue-table", 2, "emergency")
    assert queue_order(driver) == ["03", "02", "01"]


# ------------------------------------------------------------------ TC12  (R3, boundary 14 min)
def test_tc12_arriving_14_minutes_late_keeps_original_place(driver):
    book_online(driver, "Online One", "9876543210")             # 01, Booked
    login(driver, "receptionist")
    issue_walkin(driver, "Walk Two", "9123456780")              # 02, Waiting
    driver.get(URL + "/reception")
    online_id = db_id(row_button(driver, "booked-table", 1, "arrive"))
    set_late(online_id, 14)
    reception_action(driver, "booked-table", 1, "arrive")
    assert queue_order(driver) == ["01", "02"]
    assert "late" not in queue_row_text(driver, 1)


# ------------------------------------------------------------------ TC13  (R3, boundary 16 min)
def test_tc13_arriving_16_minutes_late_goes_behind_waiting_patients(driver):
    book_online(driver, "Late Larry", "9876543210")             # 01, Booked
    login(driver, "receptionist")
    issue_walkin(driver, "Walk Two", "9123456780")              # 02
    issue_walkin(driver, "Walk Three", "9123456781")            # 03
    driver.get(URL + "/reception")
    online_id = db_id(row_button(driver, "booked-table", 1, "arrive"))
    set_late(online_id, 16)
    reception_action(driver, "booked-table", 1, "arrive")
    assert queue_order(driver) == ["02", "03", "01"]
    assert "late" in queue_row_text(driver, 1)


# ------------------------------------------------------------------ TC14 + TC15  (R5)
def test_tc14_noshow_is_skipped_and_can_rejoin_once(driver):
    login(driver, "receptionist")
    issue_walkin(driver, "Walk One", "9123456780")
    login(driver, "doctor")
    doctor_call_next(driver)
    shift(doctor_serving_db_id(driver), "called_at", 6)         # called 6 minutes ago
    driver.get(URL + "/doctor")                                 # page load applies the rule
    assert "No patient in the room" in driver.page_source

    find_my_token(driver, "9123456780")                         # patient looks for the token
    wait(driver).until(EC.url_contains("/t/"))
    assert "skipped" in text_of(driver, "status-body").lower()
    click(driver, "rejoin-btn")                                 # first rejoin works
    assert text_of(driver, "token-status") == "Waiting"

    login(driver, "doctor")
    doctor_call_next(driver)
    shift(doctor_serving_db_id(driver), "called_at", 6)
    driver.get(URL + "/doctor")
    find_my_token(driver, "9123456780")
    wait(driver).until(EC.url_contains("/t/"))
    assert "skipped" in text_of(driver, "status-body").lower()
    assert not has(driver, "rejoin-btn"), "a token may rejoin only once"
    assert "already rejoined once" in text_of(driver, "status-body")


# ------------------------------------------------------------------ TC16  (R7)
def test_tc16_wait_estimate_uses_default_average(driver):
    login(driver, "receptionist")
    for i, phone in enumerate(("9123456780", "9123456781", "9123456782")):
        issue_walkin(driver, f"Walk {'ABC'[i]}", phone)
    find_my_token(driver, "9123456780")
    assert text_of(driver, "eta") == "You are next."
    find_my_token(driver, "9123456782")
    assert text_of(driver, "eta") == "About 16 min"             # 2 ahead x 8 min default
    assert text_of(driver, "ahead") == "2"


# ------------------------------------------------------------------ TC17
def test_tc17_patient_can_cancel_and_book_again(driver):
    book_online(driver, "Ravi Kumar", "9876543210")
    click(driver, "cancel-btn")
    wait(driver).until(EC.alert_is_present())
    driver.switch_to.alert.accept()
    wait(driver).until(lambda d: text_of(d, "token-status") == "Cancelled")
    book_online(driver, "Ravi Kumar", "9876543210")             # cancelled token no longer blocks
    assert text_of(driver, "token-no") == "02"


# ------------------------------------------------------------------ TC18
def test_tc18_reception_cancel_removes_patient_from_queue(driver):
    login(driver, "receptionist")
    for i, phone in enumerate(("9123456780", "9123456781", "9123456782")):
        issue_walkin(driver, f"Walk {'ABC'[i]}", phone)
    reception_action(driver, "queue-table", 2, "cancel")
    assert queue_order(driver) == ["01", "03"]


# ------------------------------------------------------------------ TC19 (invalid + injection logins)
@pytest.mark.parametrize("user, password", [
    ("reception", "wrong-password"),
    ("nobody", "reception123"),
    ("' OR '1'='1", "' OR '1'='1"),
    ("", ""),
])
def test_tc19_bad_logins_are_rejected(driver, user, password):
    driver.get(URL + "/login")
    if user:
        type_into(driver, "username", user)
    if password:
        type_into(driver, "password", password)
    click(driver, "login-btn")
    assert "/reception" not in driver.current_url and "/doctor" not in driver.current_url


# ------------------------------------------------------------------ TC20
def test_tc20_role_based_access(driver):
    login(driver, "receptionist")
    driver.get(URL + "/doctor")
    assert "/reception" in driver.current_url
    assert "do not have access" in flash_text(driver)


# ------------------------------------------------------------------ TC21
def test_tc21_staff_pages_need_login(driver):
    for path in ("/reception", "/doctor"):
        driver.get(URL + path)
        assert "/login" in driver.current_url


# ------------------------------------------------------------------ TC22 + TC23
def test_tc22_find_my_token_accepts_any_phone_format(driver):
    book_online(driver, "Ravi Kumar", "9876543210")
    find_my_token(driver, "+91 98765-43210")
    assert text_of(driver, "token-no") == "01"


def test_tc23_find_my_token_unknown_number(driver):
    find_my_token(driver, "9444444444")
    assert "No active token" in flash_text(driver)


# ------------------------------------------------------------------ TC24  (walk-in slip)
def test_tc24_walkin_slip_shows_token_and_times(driver):
    login(driver, "receptionist")
    issue_walkin(driver, "Walk One", "9123456780")
    assert text_of(driver, "slip-token-no") == "01"
    assert text_of(driver, "slip-name") == "Walk One"
    assert text_of(driver, "slip-issued") != ""
    assert "/t/" in el(driver, "slip-track-link").get_attribute("href")
    assert has(driver, "print-btn")
    click(driver, "slip-back")
    assert "/reception" in driver.current_url


# ------------------------------------------------------------------ TC25  (token details + times)
def test_tc25_token_page_shows_details_and_times(driver):
    book_online(driver, "Ravi Kumar", "9876543210")
    assert text_of(driver, "info-name") == "Ravi K."
    assert text_of(driver, "info-phone") == "98" + "\u2022" * 6 + "10"
    assert text_of(driver, "info-type") == "Booked online"
    assert text_of(driver, "info-issued") != ""
    assert text_of(driver, "info-reach-by") != ""
    assert has(driver, "progress")


# ------------------------------------------------------------------ TC26  (estimated turn time)
def test_tc26_waiting_patient_sees_estimated_turn_time(driver):
    login(driver, "receptionist")
    issue_walkin(driver, "Walk One", "9123456780")
    issue_walkin(driver, "Walk Two", "9123456781")
    find_my_token(driver, "9123456781")
    assert text_of(driver, "info-turn-at").startswith("around")
    assert text_of(driver, "info-type") == "Walk-in"


# ------------------------------------------------------------------ TC27  (find the token again)
def test_tc27_home_remembers_my_token(driver):
    book_online(driver, "Ravi Kumar", "9876543210")
    driver.get(URL + "/")
    assert text_of(driver, "my-token-no") == "01"
    click(driver, "my-token-link")
    assert "/t/" in driver.current_url


# ------------------------------------------------------------------ TC28  (R9, window closed)
def test_tc28_self_checkin_is_closed_early(driver):
    book_online(driver, "Ravi Kumar", "9876543210")
    assert not driver.find_element(By.ID, "checkin-btn").is_enabled()
    assert "opens at" in text_of(driver, "checkin-hint")


# ------------------------------------------------------------------ TC29  (R9, window open)
def test_tc29_patient_can_check_in_when_window_opens(driver):
    book_online(driver, "Ravi Kumar", "9876543210")
    status_url = driver.current_url
    login(driver, "receptionist")
    driver.get(URL + "/reception")
    set_late(db_id(row_button(driver, "booked-table", 1, "arrive")), 0)   # reach-by time is now
    driver.get(status_url)
    assert driver.find_element(By.ID, "checkin-btn").is_enabled()
    click(driver, "checkin-btn")
    assert text_of(driver, "token-status") == "Waiting"


# ------------------------------------------------------------------ TC30  (R10)
def test_tc30_online_quota_and_cancel_frees_a_slot(driver):
    set_limit(2)
    book_online(driver, "Online One", "9876543210")
    book_online(driver, "Online Two", "9000000002")
    driver.get(URL + "/book")
    assert has(driver, "booking-closed") and not has(driver, "book-btn")
    login(driver, "receptionist")
    assert "2 of 2" in text_of(driver, "online-usage")
    reception_action(driver, "booked-table", 1, "cancel")
    driver.get(URL + "/book")
    assert has(driver, "book-btn")


# ------------------------------------------------------------------ TC31  (R11)
def test_tc31_receptionist_can_pause_and_resume_online_booking(driver):
    login(driver, "receptionist")
    driver.get(URL + "/reception")
    click(driver, "toggle-online")
    assert text_of(driver, "online-state") == "Paused"
    driver.get(URL + "/book")
    assert has(driver, "booking-closed")
    driver.get(URL + "/reception")
    click(driver, "toggle-online")
    assert text_of(driver, "online-state") == "Open"
    driver.get(URL + "/book")
    assert has(driver, "book-btn")


# ------------------------------------------------------------------ TC32  (audit trail)
def test_tc32_activity_log_records_who_flagged_an_emergency(driver):
    login(driver, "receptionist")
    issue_walkin(driver, "Walk One", "9123456780")
    issue_walkin(driver, "Walk Two", "9123456781")
    reception_action(driver, "queue-table", 2, "emergency")
    click(driver, "nav-activity")
    table = text_of(driver, "activity-table")
    assert "marked EMERGENCY" in table and "reception" in table