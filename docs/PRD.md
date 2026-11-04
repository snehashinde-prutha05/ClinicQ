# ClinicQ: Product Requirements Document

**Project:** SPPU BE Computer Engineering, LP-IV, 410245(D) Software Testing and Quality Assurance, Mini Project 9
**Product:** ClinicQ, a fair queue and token system for small clinics
**Stack:** Python 3, Flask, SQLite, HTML/CSS/JavaScript. Tested with Selenium WebDriver (Python) and Selenium IDE.

## 1. Problem statement
At small clinics, patients wait for hours with no idea of their turn. The receptionist manages walk-ins, relatives asking to go first, emergencies and no-shows from memory. The doctor cannot see how heavy the day is. When clinics also accept online bookings, a new question appears: how can online and walk-in patients be treated fairly?

## 2. Goal
One shared, transparent queue for online and walk-in patients, with explicit, enforced rules and a live estimated wait.

## 3. Users
| User | Needs |
|------|-------|
| Patient | Get a token, see place in queue and estimated wait, cancel, rejoin once if skipped |
| Receptionist | Issue walk-in tokens, mark online patients as arrived, flag emergencies, cancel, rejoin skipped patients |
| Doctor | See who is next, call the next patient, start and complete consultations, mark no-shows, see the day's load |

## 4. Features (MVP)
| ID | Feature | Who |
|----|---------|-----|
| F1 | Online booking (name, phone) producing a token and a "reach by" time | Patient |
| F2 | Walk-in token issue (optionally flagged emergency) | Receptionist |
| F3 | Check-in of online patients (Booked to Waiting) | Receptionist |
| F4 | Live patient status page with estimated wait (refreshes every 10 s) | Patient |
| F5 | Call next, start consultation, complete, mark not present | Doctor |
| F6 | Emergency flag with priority | Receptionist |
| F7 | Automatic no-show skip and single rejoin | System, Patient, Receptionist |
| F8 | Cancel token | Patient, Receptionist |
| F9 | Find my token by phone number | Patient |
| F10 | Staff login with two roles | Receptionist, Doctor |
| F11 | Waiting-room "Now serving" screen (no names shown) | Public |
| F12 | Activity log page: every queue action with who and when (audit trail) | Receptionist, Doctor |
| F13 | Printable walk-in token slip with QR code to follow the queue on a phone | Receptionist, Patient |
| F14 | Token details and times on the patient page: progress bar, issued time, reach-by time, estimated turn time, called time, masked phone | Patient |
| F15 | Patient self check-in ("I'm here"), opens 15 minutes before the reach-by time | Patient |
| F16 | Online booking daily limit and receptionist pause/resume switch | Receptionist |
| F17 | "My token" shortcut on the home page, dedicated Track my token page, copy-link button | Patient |

## 5. Business rules
| ID | Rule |
|----|------|
| R1 | Token numbers are sequential per day and never duplicated. Online and walk-in tokens share one sequence. |
| R2 | Only patients who have arrived (Waiting) can be called, in token order. |
| R3 | An online patient who checks in MORE than 15 minutes after their "reach by" time joins behind everyone already waiting. |
| R4 | An emergency is called next but never interrupts a patient already called or in consultation. Several emergencies keep the order in which they were flagged. |
| R5 | A called patient not seen within 5 minutes is skipped. A skipped token can rejoin once, behind the first 3 non-emergency patients. |
| R6 | One active token per phone number per day (+91, 0-prefix, spaces and dashes are the same number). |
| R7 | Estimated wait = patients ahead (+1 if someone is in the room) x average of the last 5 consultations today (8 minutes by default). |
| R8 | Legal state changes only (see diagram). Completed and Cancelled are final. |
| R9 | A patient can check in themselves only from 15 minutes before their "reach by" time. The receptionist can check anyone in at any time. |
| R10 | At most 24 online tokens per day (a share of daily capacity, so walk-ins always have room). A cancelled online token frees its place. |
| R11 | The receptionist can pause online booking (for example when the clinic is closing). Walk-in tokens are never blocked. |

```
Booked --> Arrived(Waiting) --> Called --> In consultation --> Completed
   |             |               |
   |             |               +--> Skipped --> Arrived (once) / Cancelled
   +--> Cancelled <--+
```

## 5a. Where does the patient see their token and time?
| Situation | Where | What is shown |
|-----------|-------|---------------|
| Just booked online | Token page `/t/<code>` (opens automatically) | Token number, status, progress bar, reach-by time, issued time, estimated turn time, I'm here button |
| Walk-in at the desk | Printed or on-screen slip with QR code; the same token page by scanning it | Token number, name, issued time, estimated wait and turn time, link to follow live |
| Came back later | Home page "Your token" card, or Track my token with the phone number | Opens the same token page |
| Waiting room | Waiting-room screen `/display` | Now serving and next tokens (no names) |

## 6. Data (SQLite)
- `tokens`: id, code, day, token_no, name, phone, source (online / walk-in), status, is_emergency, emergency_at, queue_pos, rejoined, was_late, created_at, expected_arrival, arrived_at, called_at, started_at, completed_at. Unique on (day, token_no). Unique active phone per day.
- `staff`: username, password hash, role.
- `settings`: online booking open/paused and the daily online limit.
- `events`: timestamp, actor, action, token number (audit trail).
Only name, phone and token are stored. No medical data.

## 7. Non-functional requirements
- Usable on a phone (responsive down to 390 px width).
- Forms protected against forged submissions (CSRF token).
- Passwords stored hashed. Staff pages need login and the correct role.
- Friendly error pages (400, 403, 404, 405).
- Keyboard focus visible, labelled form fields, high-contrast text.

## 8. Out of scope (future scope)
SMS or WhatsApp alerts, multi-clinic accounts, payments, analytics, patient self check-in by location, medical records, multiple doctors.

## 9. SaaS path
Per-clinic monthly subscription. Roadmap: multi-clinic tenancy, SMS alerts, multiple doctors and rooms, wait-time analytics, a tablet kiosk for walk-ins.

## 10. Success criteria
All business rules R1 to R8 verified by automated regression tests. No open Critical or Major defects at release. A patient can book and see an estimate in under 30 seconds.
