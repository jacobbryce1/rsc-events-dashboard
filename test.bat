@echo off
cd /d "%~dp0"

if not exist .venv (
    echo Virtual environment not found.
    echo Run install script first or create one:
    echo   python -m venv .venv
    echo   .venv\Scripts\activate.bat
    echo   pip install -r requirements.txt
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

if not exist .env (
    echo Missing .env file.
    echo Run configure.bat first to set up RSC credentials.
    pause
    exit /b 1
)

echo.
echo   RSC Cloud Native Workload Dashboard
echo   Validation Tests
echo   ====================================
echo.

python test_monitoring.py
pause
