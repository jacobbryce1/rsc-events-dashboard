#Requires -Version 5.1
$ErrorActionPreference = "Stop"

Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  RSC Cloud Native Workload Dashboard — Windows Installer    ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

$InstallDir = "$env:USERPROFILE\rsc-dashboard"
$ScriptDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

# ── Check Python ──
Write-Host "🔍 Checking Python..." -ForegroundColor Yellow
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
    Write-Host "   Installing Python 3.12..." -ForegroundColor Yellow
    try {
        winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
        $PythonCmd = "python"
    } catch {
        Write-Host "❌ Install Python 3.9+ from https://python.org/downloads/" -ForegroundColor Red
        exit 1
    }
}
Write-Host "   ✅ $PythonCmd ($(& $PythonCmd --version))" -ForegroundColor Green

# ── Install ──
Write-Host "`n📁 Installing to $InstallDir..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
New-Item -ItemType Directory -Force -Path "$InstallDir\assets" | Out-Null
New-Item -ItemType Directory -Force -Path "$InstallDir\.streamlit" | Out-Null
New-Item -ItemType Directory -Force -Path "$InstallDir\tests" | Out-Null
New-Item -ItemType Directory -Force -Path "$InstallDir\docs" | Out-Null

Copy-Item "$ScriptDir\src\*" -Destination $InstallDir -Force
Copy-Item "$ScriptDir\requirements.txt" -Destination $InstallDir -Force
Copy-Item "$ScriptDir\.streamlit\config.toml" -Destination "$InstallDir\.streamlit\" -Force
Copy-Item "$ScriptDir\.env.example" -Destination $InstallDir -Force
Copy-Item "$ScriptDir\assets\*" -Destination "$InstallDir\assets\" -Force -ErrorAction SilentlyContinue
Copy-Item "$ScriptDir\tests\*" -Destination "$InstallDir\tests\" -Force -ErrorAction SilentlyContinue
Copy-Item "$ScriptDir\docs\*" -Destination "$InstallDir\docs\" -Force -ErrorAction SilentlyContinue

# ── Venv ──
Write-Host "`n🐍 Creating virtual environment..." -ForegroundColor Yellow
Set-Location $InstallDir
& $PythonCmd -m venv .venv
& "$InstallDir\.venv\Scripts\Activate.ps1"

Write-Host "📦 Installing dependencies..." -ForegroundColor Yellow
pip install --upgrade pip setuptools wheel -q
pip install -r requirements.txt -q

# ── Launchers ──
@"
@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
if not exist .env (
    echo [ERROR] Missing .env — run configure.bat first
    pause & exit /b 1
)
echo Starting RSC Cloud Native Workload Dashboard...
echo Open http://localhost:8501
streamlit run dashboard.py --server.port 8501 --server.address localhost --server.headless true
"@ | Out-File -FilePath "$InstallDir\run.bat" -Encoding ASCII

@"
@echo off
cd /d "%~dp0"
echo RSC Dashboard Configuration
echo ============================
set /p RSC_URL="RSC Base URL (https://your-org.my.rubrik.com): "
set /p RSC_ID="Service Account Client ID: "
set /p RSC_SECRET="Service Account Secret: "
(
echo RSC_SERVICE_ACCOUNT_ID=%RSC_ID%
echo RSC_SERVICE_ACCOUNT_SECRET=%RSC_SECRET%
echo RSC_BASE_URL=%RSC_URL%
) > .env
echo.
echo Saved to .env
echo Next: run.bat
pause
"@ | Out-File -FilePath "$InstallDir\configure.bat" -Encoding ASCII

@"
@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
if not exist .env ( echo [ERROR] Run configure.bat first & pause & exit /b 1 )
python tests\test_monitoring.py
pause
"@ | Out-File -FilePath "$InstallDir\test.bat" -Encoding ASCII

Write-Host "`n╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  ✅ Installation Complete!                                    ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host "`n  Location: $InstallDir"
Write-Host "`n  Next: cd $InstallDir"
Write-Host "        .\configure.bat"
Write-Host "        .\test.bat"
Write-Host "        .\run.bat`n"
