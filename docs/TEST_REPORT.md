# ClinicQ: Test Report

**Project:** ClinicQ, 410245(D) Mini Project 9  **Tester:** ____________  **Date:** ____________
**Application version:** 1.0  **Environment:** Windows, Chrome ____, Python ____, Selenium ____

## 1. Objective
Verify business rules R1 to R11, validation, roles and error handling of ClinicQ, and decide whether it is acceptable.

## 2. What was tested
Features and techniques are listed in TEST_PLAN.md. Test cases are in TEST_CASES.csv. Defects are in BUG_LOG.csv. Exploratory sessions are in EXPLORATORY_TESTING_LOG.md. The HTML report from pytest is `docs/test_report.html`.

## 3. Execution summary (final cycle)
| Item | Count |
|------|-------|
| Test cases planned | 43 |
| Automated (WebDriver) | 32 cases (31 test functions, 42 test runs) |
| Manual / exploratory | 11 cases + 3 exploratory sessions |
| Passed | ___ |
| Failed | ___ |
| Blocked / not run | ___ |
| Pass percentage | ___ % |

## 4. Regression cycles
| Cycle | Build | Tests run | Passed | Failed | Defects raised | Defects fixed |
|-------|-------|-----------|--------|--------|----------------|---------------|
| 1 | initial | | | | | |
| 2 | after fixes | | | | | |
| 3 | final | | | | | |

Regression rule: after every fix the **whole** suite was re-run, not only the failed test.

## 5. Defect summary
| Severity | Raised | Fixed | Open / Deferred |
|----------|--------|-------|-----------------|
| S1 Critical | | | |
| S2 Major | | | |
| S3 Minor | | | |
| S4 Cosmetic | | | |

| Type (taxonomy) | Count |
|-----------------|-------|
| FUN, VAL, STA, CON, SEC, UI, RES, ERR | |

## 6. Selenium IDE and WebDriver
Flows recorded in Selenium IDE: ______________________. Flows scripted in WebDriver: see `tests/test_regression.py`. Differences noticed between the two (for example: IDE cannot move time or reset data): ______________________.

## 7. Exploratory testing summary
Sessions held: ___ . Total time: ___ min. Key findings: ______________________.

## 8. Known limitations (deferred)
No login attempt limit, token lookup by phone number is not verified, online bookings do not verify phone ownership, time rules are checked at page load (no background job).

## 9. Test pass/fail criteria and verdict
Exit criteria: all planned cases executed, no open S1 or S2 defects, at least 95% of automated tests passing in the final cycle.

**Verdict:** [ ] Accepted  [ ] Accepted with conditions  [ ] Not accepted
**Justification:** ______________________________________________

Tester: ____________  Guide: ____________
