# Selenium IDE: record three flows (about 20 minutes)

Selenium IDE is a browser extension that records your clicks and replays them. No coding is needed. Your syllabus asks you to find bugs with **both** WebDriver and the IDE, so record these three flows and keep the `.side` files in `docs/ide_recordings/`.

## Setup
1. In Chrome, search for "Selenium IDE" in the Chrome Web Store and add the extension.
2. Start the app: `run_app_test_mode.bat` (Windows) or see README.
3. Open Selenium IDE, choose **Record a new test in a new project**, name the project `ClinicQ`, and enter the base URL `http://127.0.0.1:5000/`.

## Flow A: book a token
1. Record: open `/book`, type a name in `#name`, a phone in `#phone`, click `#book-btn`.
2. Add checks with right-click, **Insert command**:
   - `assert text`  target `id=token-status`  value `Booked`
   - `assert text`  target `id=token-no`  value `01` (only on a clean database)
3. Stop recording and name the test `A_book_token`.

## Flow B: walk-in token and doctor calls
1. Log in as `reception / reception123`, issue a walk-in (`#walk-name`, `#walk-phone`, `#issue-btn`). The token slip opens; add `assert text` on `id=slip-token-no`.
2. Log out (`#logout-btn`), log in as `doctor / doctor123`, click `#call-next-btn`.
3. Add `assert element present` for `id=start-btn` and `assert text` `id=current-no` equal to `01`.
4. Name the test `B_walkin_and_call`.

## Flow C: failed login
1. Open `/login`, type a wrong password, click `#login-btn`.
2. Add `assert element present` for `css=.flash-error`.
3. Name the test `C_bad_login`.

## Run and save
- The recordings expect a clean queue. Before each run, stop the app, delete the file `clinicq.db`, and start the app again (or run the WebDriver suite once, because it resets the data for you).
- Click **Run all tests in suite**. Save the project with Ctrl+S (file type `.side`).
- Take a screenshot of the passing run for your report.

## What to note for the report
| Question | Your answer |
|----------|-------------|
| Which bugs or problems did the IDE find? | |
| Which things could the IDE not do? (move time, reset data, handle the confirm pop-up reliably, loops) | |
| Which is better for regression, IDE or WebDriver, and why? | |

## Tips
- Prefer `id=` locators. Every important element in ClinicQ has one.
- If a recorded click fails, the page may not have finished loading: add a `wait for element present` command before it.
- After a recording, edit the generated test and remove accidental clicks.
