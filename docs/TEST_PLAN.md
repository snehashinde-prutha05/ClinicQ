# ClinicQ: Test Plan

**Course:** 410245(D) Software Testing and Quality Assurance, Mini Project 9
**Application under test:** ClinicQ (see PRD.md)
**Prepared by:** ______________________  **Date:** ____________  **Version:** 1.0

## 1. Objective
Verify that ClinicQ enforces its business rules (R1 to R8), validates input, restricts access by role, and stays correct after every bug fix. Find and classify defects using Selenium WebDriver, Selenium IDE and exploratory testing, and judge whether the application is acceptable.

## 2. Scope
**In scope:** online booking, walk-in tokens, check-in, call/start/complete/skip, emergency priority, no-show and rejoin, cancellation, wait estimate, patient status page, find-by-phone, staff login and roles, waiting-room screen, error pages, responsive layout.
**Out of scope:** load/performance testing, SMS, multi-clinic, browser compatibility beyond Chrome, deployment testing.

## 3. Features to be tested
| Feature | Rules | Priority |
|---------|-------|----------|
| Online booking and input validation | R1, R6 | High |
| Token numbering (shared sequence, no duplicates) | R1 | High |
| Check-in and calling order | R2, R3 | High |
| Emergency handling | R4 | High |
| No-show skip and single rejoin | R5 | High |
| Wait estimate | R7 | Medium |
| State transitions | R8 | High |
| Cancellation | R8 | Medium |
| Walk-in slip, token details and times, my-token shortcut | F13, F14, F17 | Medium |
| Patient self check-in window | R9 | High |
| Online daily limit and pause switch | R10, R11 | High |
| Activity log (who did what) | F12 | Medium |
| Login, roles, protected pages | NFR | High |
| Find my token, status page, waiting-room screen | F4, F9, F11 | Medium |
| Error pages, forged requests, responsive layout | NFR | Low |

## 4. Test approach
| Level or technique | How it is used here |
|--------------------|---------------------|
| Black-box, Equivalence Partitioning | Valid and invalid names and phone numbers (TC02, TC03) |
| Black-box, Boundary Value Analysis | Grace period at 14 and 16 minutes, no-show at 6 minutes, name length (TC02, TC12, TC13, TC14) |
| State Transition testing | Allowed and forbidden token status changes (TC08, TC14) |
| Decision-table style combination | Emergency + waiting + late + online combinations (TC09 to TC13, TC28 to TC31) |
| Error guessing | SQL-injection style login, markup in names, double clicks (TC19, TC31) |
| Automated regression | Selenium WebDriver (Python + pytest, 31 test functions covering 32 test cases), re-run after every fix |
| Record and replay | Selenium IDE recordings of key flows (see SELENIUM_IDE_GUIDE.md) |
| Exploratory testing | Time-boxed charters with a written log (EXPLORATORY_TESTING_LOG.md) |
| White-box (light) | `smoke_test.py` checks pure functions (phone normalisation, grace boundary) and database constraints |

## 5. Environment and tools
Windows laptop, Google Chrome, Python 3.10+, Flask 3, SQLite, Selenium 4 (WebDriver and IDE), pytest, pytest-html. App URL: http://127.0.0.1:5000. The application runs in **test mode** (`CLINICQ_TEST=1`) so tests can reset data and move time.

## 6. Test data
Staff accounts reception / reception123 and doctor / doctor123. Phone numbers 9123456780 to 9123456782 for walk-ins and 9876543210 for online bookings. Invalid data sets are listed in TEST_CASES.csv.

## 7. Entry criteria
Application runs without errors. Rules R1 to R8 are documented. Test mode works. Selenium and Chrome are installed.

## 8. Pass/fail and exit criteria
- A test **passes** when the actual result equals the expected result in TEST_CASES.csv. Otherwise it **fails** and a defect is logged.
- **Exit:** all planned test cases executed, no open Critical (S1) or Major (S2) defects, at least 95% of automated tests passing in the final regression run, and every fixed defect re-tested.
- **Acceptance verdict** is recorded in TEST_REPORT.md.

## 9. Bug taxonomy
**By type**
| Code | Type | Example |
|------|------|---------|
| FUN | Functional or business logic | Wrong calling order, wrong estimate |
| VAL | Input validation | Valid Hindi name rejected |
| STA | State or workflow | Completed a token that was only Called |
| CON | Concurrency or data integrity | Duplicate token numbers |
| SEC | Security or privacy | No login attempt limit, token lookup by phone |
| UI | Usability or display | Overlapping text, unclear message |
| RES | Responsive or compatibility | Broken layout on a phone |
| ERR | Error handling | Unfriendly error page |

**By severity**
| Level | Meaning |
|-------|---------|
| S1 Critical | Queue unusable, wrong patient called, data loss, serious security hole |
| S2 Major | A rule is broken but a workaround exists |
| S3 Minor | Small defect, wrong or confusing message |
| S4 Cosmetic | Spacing, colour, wording |

**Priority:** P1 fix now, P2 fix before release, P3 fix if time allows.
**Lifecycle:** New, Open, Fixed, Verified (re-tested and regression suite passed), Closed, or Deferred (known limitation).

## 10. Regression strategy
The automated suite in `tests/test_regression.py` covers the high-priority rules. After every defect fix the full suite is re-run, not only the test that failed. Each cycle is recorded in TEST_REPORT.md (cycle number, tests run, passed, failed, defects raised, defects fixed).

## 11. Exploratory testing
Three charters of about 30 minutes each (queue order, concurrency and double actions, abuse of forms and URLs). Notes, bugs and questions are recorded in EXPLORATORY_TESTING_LOG.md.

## 12. Risks
| Risk | Mitigation |
|------|------------|
| Time-based rules are slow to test | Test-mode helpers move times instantly |
| Tests depend on a clean database | The suite resets data before every test |
| Browser or driver mismatch | Selenium Manager downloads the right driver |
| Limited testing time | Prioritise high-priority features first |

## 13. Schedule
| Day | Activity |
|-----|----------|
| 1 | Run the app, review the PRD, write the plan |
| 2 | Finalise test cases, record Selenium IDE flows |
| 3 | Run the WebDriver suite (Cycle 1), log defects |
| 4 | Fix defects, re-run everything (Cycle 2) |
| 5 | Exploratory sessions, final regression, report |

## 14. Deliverables
Test plan (this file), TEST_CASES.csv, Selenium IDE recordings, WebDriver scripts, BUG_LOG.csv, EXPLORATORY_TESTING_LOG.md, pytest HTML report, TEST_REPORT.md.
