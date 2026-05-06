@echo off
cd /d "%~dp0"

echo ==============================================
echo   RSC Cloud Native Workload Dashboard
echo   Configuration
echo ==============================================
echo.

if exist .env (
    echo Existing .env found. Overwrite? (y/N)
    set /p answer=
    if /i not "%answer%"=="y" (
        echo Keeping existing configuration.
        exit /b 0
    )
)

echo Enter your RSC connection details.
echo (Get these from RSC ^> Settings ^> Service Accounts)
echo.
set /p RSC_URL="RSC Base URL (e.g., https://your-org.my.rubrik.com): "
set /p RSC_ID="Service Account Client ID: "
set /p RSC_SECRET="Service Account Secret: "

(
echo RSC_SERVICE_ACCOUNT_ID=%RSC_ID%
echo RSC_SERVICE_ACCOUNT_SECRET=%RSC_SECRET%
echo RSC_BASE_URL=%RSC_URL%
) > .env

echo.
echo Configuration saved to .env
echo.
echo Next steps:
echo   test.bat    - Validate connectivity
echo   run.bat     - Launch the dashboard
echo.
pause
