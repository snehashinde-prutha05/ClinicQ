@echo off
REM Starts ClinicQ in TEST MODE (needed by the Selenium suite). Keep this window open.
set CLINICQ_TEST=1
python app.py
