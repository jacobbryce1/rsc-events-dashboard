#Requires -Version 5.1
$ErrorActionPreference = "Stop"

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  RSC Cloud Native Workload Dashboard" -ForegroundColor Cyan
Write-Host "  Windows Installer (v1.0.1 - Security Hardened)" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

$InstallDir = "$env:USERPROFILE\rsc-dashboard"
$ScriptDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

# ── Check Python ──
Write-Host "Checking Python..." -ForegroundColor Yellow
$PythonCmd = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python 3\.(\d+)") {
            if ([int]$Matches[1] -ge 9) { $PythonCmd = $cmd; break }
        }
    } catch { }
}

if (-not $PythonCmd) {
    Write-Host "  Installing Python 3.12..." -ForegroundColor Yellow
    try {
        winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
        $PythonCmd = "python"
    } catch {
        Write-Host "Install Python 3.9+ from https://python.org/downloads/" -ForegroundColor Red
        exit 1
    }
}
Write-Host "  Using: $PythonCmd ($(& $PythonCmd --version))" -ForegroundColor Green

# ── Install ──
Write-Host "`nInstalling to $InstallDir..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
New-Item -ItemType Directory -Force -Path "$InstallDir\assets" | Out-Null
New-Item -ItemType Directory -Force -Path "$InstallDir\.streamlit" | Out-Null
New-Item -ItemType Directory -Force -Path "$InstallDir\tests" | Out-Null
New-Item -ItemType Directory -Force -Path "$InstallDir\docs" | Out-Null

Copy-Item "$ScriptDir\*.py" -Destination $InstallDir -Force -ErrorAction SilentlyContinue
Copy-Item "$ScriptDir\requirements.txt" -Destination $InstallDir -Force
Copy-Item "$ScriptDir\.env.example" -Destination $InstallDir -Force
Copy-Item "$ScriptDir\.streamlit\config.toml" -Destination "$InstallDir\.streamlit\" -Force
Copy-Item "$ScriptDir\assets\*" -Destination "$InstallDir\assets\" -Force -ErrorAction SilentlyContinue
Copy-Item "$ScriptDir\tests\*" -Destination "$InstallDir\tests\" -Force -ErrorAction SilentlyContinue
Copy-Item "$ScriptDir\docs\*" -Destination "$InstallDir\docs\" -Force -ErrorAction SilentlyContinue

# ── Venv ──
Write-Host "`nCreating virtual environment..." -ForegroundColor Yellow
Set-Location $InstallDir
& $PythonCmd -m venv .venv
& "$InstallDir\.venv\Scripts\Activate.ps1"

Write-Host "Installing pinned dependencies..." -ForegroundColor Yellow
pip install --upgrade pip setuptools wheel -q
pip install -r requirements.txt -q

# ── Launchers (F-006: localhost binding) ──
@"
@echo off
cd /d "%~dp0"

if not exist .venv (
    echo Virtual environment not found.
    echo Run install script first.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

if not exist .env (
    echo Missing .env file.
    echo Run configure.bat to set up RSC credentials.
    pause
    exit /b 1
)

echo.
echo   RSC Cloud Native Workload Dashboard
echo   ====================================
echo   Binding: localhost:8501 only (security hardened)
echo   Open http://localhost:8501
echo   Press Ctrl+C to stop
echo.

REM F-006: Bind to 127.0.0.1 only
REM For remote access, use a reverse proxy with authentication
streamlit run dashboard.py --server.port 8501 --server.address 127.0.0.1 --server.headless true --browser.gatherUsageStats false
"@ | Out-File -FilePath "$InstallDir\run.bat" -Encoding ASCII

@"
@echo off
cd /d "%~dp0"
echo ==============================================
echo   RSC Dashboard Configuration
echo ==============================================
echo.
echo NOTE: URL must match https://*.my.rubrik.com
echo.
set /p RSC_URL="RSC Base URL (https://your-org.my.rubrik.com): "
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
echo Optional: Add DASHBOARD_PASSWORD=yourpass to .env for shared machines
echo.
echo Next: test.bat then run.bat
pause
"@ | Out-File -FilePath "$InstallDir\configure.bat" -Encoding ASCII

@"
@echo off
cd /d "%~dp0"
if not exist .venv (
    echo Run install script first.
    pause
    exit /b 1
)
call .venv\Scripts\activate.bat
if not exist .env (
    echo Run configure.bat first.
    pause
    exit /b 1
)
echo.
echo   RSC Dashboard - Validation Tests
echo   ==================================
echo.
python test_monitoring.py
pause
"@ | Out-File -FilePath "$InstallDir\test.bat" -Encoding ASCII

Write-Host "`n==============================================" -ForegroundColor Green
Write-Host "  Installation Complete!" -ForegroundColor Green
Write-Host "==============================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Location: $InstallDir"
Write-Host "  Security: localhost only, encrypted cache, credential validation"
Write-Host ""
Write-Host "  Next:" -ForegroundColor Yellow
Write-Host "    cd $InstallDir"
Write-Host "    .\configure.bat"
Write-Host "    .\test.bat"
Write-Host "    .\run.bat"
Write-Host ""
