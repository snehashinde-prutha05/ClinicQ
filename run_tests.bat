@echo off
REM Run this in a SECOND window while run_app_test_mode.bat is running.
python -m pytest --html=docs\test_report.html --self-contained-html
echo.
echo Report saved to docs\test_report.html
pause
