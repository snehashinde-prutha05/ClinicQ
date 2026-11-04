# ClinicQ: Exploratory Testing Log

Exploratory testing means learning, designing and executing tests at the same time, guided by a short **charter**. Time-box each session (about 30 minutes) and write notes while you test. Replace the blanks with your own results.

**Tester:** ____________  **App version / date:** ____________  **Browser:** Chrome ____

---
## Session 1: Break the queue order
**Charter:** Explore the calling order using walk-ins, online bookings, emergencies, no-shows and cancellations, to discover any case where the wrong patient is called.
**Start / end time:** ______ / ______  **Duration:** ____ min

**Ideas to try**
- Several online bookings, check them in in a different order from their token numbers
- Emergency flagged on a Booked (not yet arrived) token
- Cancel the patient who is currently being called
- Skip, rejoin, and flag the rejoined patient as emergency
- Estimate shown after many quick consultations (average time of 1 minute)

| # | What I did | What I expected | What happened | Bug? (ID) |
|---|-----------|-----------------|---------------|-----------|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |

**Questions / observations:**

---
## Session 2: Two receptionists at once, and double actions
**Charter:** Explore simultaneous actions, repeated clicks and stale pages, to discover duplicate or inconsistent data.
**Start / end time:** ______ / ______  **Duration:** ____ min

**Ideas to try**
- Two browsers (normal and incognito) both logged in as receptionist, press Issue token together
- Double-click Issue token, Call next, Complete
- Two doctors' browsers: call next in both
- Cancel a token in one browser while the other still shows it
- Press Back and re-submit forms

| # | What I did | What I expected | What happened | Bug? (ID) |
|---|-----------|-----------------|---------------|-----------|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |

**Questions / observations:**

---
## Session 3: Abuse the forms and URLs
**Charter:** Explore inputs, URLs and sessions with unexpected data, to discover validation, security and error-handling problems.
**Start / end time:** ______ / ______  **Duration:** ____ min

**Ideas to try**
- Very long names, emoji, spaces only, `<script>alert(1)</script>`, `' OR 1=1 --`
- Phone numbers: letters, +91 with brackets, 12 digits, repeated digits
- Open `/reception` while logged out; change the token code in `/t/<code>`; try `/token/1/arrive` in the address bar
- Clear cookies and submit a form
- Look at the page at 390 px width and with browser zoom at 200%

| # | What I did | What I expected | What happened | Bug? (ID) |
|---|-----------|-----------------|---------------|-----------|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |

**Questions / observations:**

---
## Summary
| Session | Duration | Bugs found | Most important finding |
|---------|----------|-----------|------------------------|
| 1 | | | |
| 2 | | | |
| 3 | | | |
