# ClinicQ: fair queue and token system for small clinics

Flask + SQLite web app, built for **SPPU BE Computer, 410245(D) Software Testing and Quality Assurance, Mini Project 9** (web-based application, Test Plan with bug taxonomy, regression scripts, bugs found with Selenium WebDriver and IDE, test reports with exploratory testing).

## What is in this folder
| Path | What it is |
|------|-----------|
| `app.py`, `templates/`, `static/` | The application |
| `docs/PRD.md` | Product requirements, features, business rules R1 to R11, patient journey |
| `docs/TEST_PLAN.md` | Test plan with features, approach, criteria and **bug taxonomy** |
| `docs/TEST_CASES.csv` | 43 test cases (32 automated, 11 manual). Fill in Actual result and Status |
| `tests/` | Selenium WebDriver regression suite (Python + pytest) |
| `docs/SELENIUM_IDE_GUIDE.md` | How to record the three Selenium IDE flows |
| `docs/BUG_LOG.csv` | Bug log (6 starter entries, add your own) |
| `docs/EXPLORATORY_TESTING_LOG.md` | Three charters and a note-taking template |
| `docs/TEST_REPORT.md` | Test report template to fill from your runs |
| `smoke_test.py` | Quick developer check (white-box: functions, rules, database constraints) |

## 1. Install (once)
Needs Python 3.10+ and Google Chrome.
```
pip install -r requirements.txt
```

## 2. Run the app
**Windows:** double-click `run_app_test_mode.bat` (keep the window open), then open http://127.0.0.1:5000
**Mac/Linux:** `./run_app_test_mode.sh`

This starts the app in **test mode**, which lets the tests reset data and move time forward. For normal use run `python app.py`.

Demo accounts: `reception / reception123` and `doctor / doctor123`.

**Phone demo (to scan the QR code on the walk-in slip):** put the laptop and phone on the same Wi-Fi, set `CLINICQ_HOST=0.0.0.0`, start the app, and open it on the laptop using the laptop's network address (for example http://192.168.1.5:5000) instead of 127.0.0.1. The QR code then points to that address.

## 3. Run the Selenium regression suite
With the app running, open a **second** window in this folder:
**Windows:** double-click `run_tests.bat`  **Mac/Linux:** `./run_tests.sh`

It opens Chrome, runs 42 automated checks (31 test functions, several run with multiple data rows), and writes an HTML report to `docs/test_report.html` for your submission. Set `HEADLESS=1` to run without a visible browser.

**Regression cycle for your report:**
1. Run the suite, note failures, log them in `docs/BUG_LOG.csv` (Cycle 1).
2. Fix the defect in the code.
3. Run the **whole** suite again (Cycle 2). Record the result. Repeat until the exit criteria in the test plan are met.

If the suite stops straight away with "not in test mode", you started the app with `python app.py` instead of the test-mode script.

## Where does a patient see their token and time?
| Situation | Where | What is shown |
|-----------|-------|---------------|
| Booked online | Token page (opens automatically after booking) | Token number, progress bar, reach-by time, issued time, estimated turn time, "I'm here" button, cancel |
| Walk-in at the desk | Token slip after the receptionist issues it (print it, or scan the QR code) | Token number, name, issued time, estimated wait and turn time, link to follow live |
| Came back later | Home page "Your token" card, or **Track my token** with the phone number | Opens the same token page |
| In the waiting room | Waiting-room screen (`/display`) | Now serving and next tokens, no names |

## Business rules (all tests come from these)
| ID | Rule |
|----|------|
| R1 | Token numbers are sequential per day and never duplicated (online and walk-in share one sequence). |
| R2 | Only arrived (Waiting) patients can be called, in token order. Online tokens start as Booked. |
| R3 | An online patient who checks in MORE than 15 minutes after their "reach by" time joins behind everyone already waiting. |
| R4 | An emergency is called next but never interrupts a patient already called. Several emergencies keep their flagged order. |
| R5 | A called patient not seen within 5 minutes is skipped. A skipped token can rejoin once, behind 3 patients. |
| R6 | One active token per phone number per day (+91, 0-prefix, spaces, dashes are the same number). |
| R7 | Estimated wait = patients ahead (+1 if someone is in the room) x average of last 5 consultations (8 min default). |
| R8 | Only legal state changes: Booked, Waiting, Called, In consultation, Completed; plus Skipped and Cancelled. |
| R9 | A patient can check in themselves from 15 minutes before their reach-by time. The receptionist can check anyone in at any time. |
| R10 | At most 24 online tokens per day. A cancelled online token frees its place. Walk-ins are never limited. |
| R11 | The receptionist can pause and resume online booking. Walk-in tokens are never blocked. |

## Element ids (for Selenium)
Navigation: `nav-home` `nav-book` `nav-track` `nav-login` `nav-desk` `nav-doctor` `nav-activity` `nav-display` `logout-btn`.
Home: `book-link` `find-phone` `find-btn` `open-display` `open-reception` `open-doctor` `open-login` `my-token-card` `my-token-no` `my-token-link`.
Booking: `name` `phone` `book-btn` `form-error` `name-err` `phone-err` `booking-closed`.
Token page: `token-no` `token-status` `status-body` `eta` `ahead` `progress` `checkin-btn` `checkin-hint` `cancel-btn` `rejoin-btn` `now-serving` `copy-link`, details `info-name` `info-phone` `info-type` `info-issued` `info-reach-by` `info-turn-at` `info-called-at`.
Login: `username` `password` `login-btn`.
Reception: `walk-name` `walk-phone` `walk-emergency` `issue-btn` `online-state` `online-usage` `toggle-online`; per token `arrive-<id>` `emergency-<id>` `cancel-<id>` `rejoin-<id>` `slip-<id>`; tables `queue-table` `booked-table` `skipped-table`.
Slip: `slip-token-no` `slip-name` `slip-issued` `slip-turn-at` `slip-track-link` `print-btn` `slip-back`.
Doctor: `call-next-btn` `start-btn` `complete-btn` `skip-btn` `current-no` `upnext-table`. Activity: `activity-table`.

## Test-mode helpers (only when `CLINICQ_TEST=1`)
- `POST /__test__/reset` clears all tokens, the log and the settings.
- `POST /__test__/set-late/<token_id>` with `minutes`: sets an online token's "reach by" time to exactly that many minutes ago (rules R3 and R9).
- `POST /__test__/shift/<token_id>` with `field` (`called_at` or `expected_arrival`) and `minutes`: moves a time earlier (rule R5).
- `POST /__test__/set-limit` with `limit`: sets the online token limit (rule R10).

## Known limitations (logged as deferred in the bug log)
No login attempt limit; status lookup by phone number is not verified; online bookings do not verify phone ownership; self check-in has no location check; time rules are checked when a page loads, not by a background job; single clinic and single doctor.
