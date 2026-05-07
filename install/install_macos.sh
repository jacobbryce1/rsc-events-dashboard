#!/bin/bash
set -e

echo "=============================================="
echo "  RSC Cloud Native Workload Dashboard"
echo "  macOS Installer (v1.0.1 - Security Hardened)"
echo "=============================================="
echo ""

INSTALL_DIR="${HOME}/rsc-dashboard"
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [[ "$(uname)" != "Darwin" ]]; then
    echo "This script is for macOS only."
    exit 1
fi

# ── Homebrew ──
echo "Checking Homebrew..."
if ! command -v brew &>/dev/null; then
    echo "  Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    if [[ -f /opt/homebrew/bin/brew ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
else
    echo "  Homebrew found"
fi

# ── Python ──
echo "Checking Python..."
PYTHON_CMD=""
for cmd in /opt/homebrew/bin/python3 python3.12 python3.11 python3; do
    if command -v "$cmd" &>/dev/null; then
        PY_VER=$($cmd --version 2>&1 | awk '{print $2}')
        PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
        if [[ "$PY_MINOR" -ge 9 ]]; then
            PYTHON_CMD="$cmd"
            break
        fi
    fi
done

if [[ -z "$PYTHON_CMD" ]]; then
    echo "  Installing Python 3.12..."
    brew install python@3.12
    PYTHON_CMD="/opt/homebrew/bin/python3.12"
fi
echo "  Using: $PYTHON_CMD ($($PYTHON_CMD --version))"

# ── Install directory ──
echo ""
echo "Installing to ${INSTALL_DIR}..."
mkdir -p "${INSTALL_DIR}/assets"
mkdir -p "${INSTALL_DIR}/.streamlit"
mkdir -p "${INSTALL_DIR}/tests"
mkdir -p "${INSTALL_DIR}/docs"

# Copy source
cp "${SCRIPT_DIR}/"*.py "${INSTALL_DIR}/" 2>/dev/null || true
cp "${SCRIPT_DIR}/requirements.txt" "${INSTALL_DIR}/"
cp "${SCRIPT_DIR}/.env.example" "${INSTALL_DIR}/"
cp "${SCRIPT_DIR}/.streamlit/config.toml" "${INSTALL_DIR}/.streamlit/"

# Copy assets, tests, docs
[[ -d "${SCRIPT_DIR}/assets" ]] && cp "${SCRIPT_DIR}/assets/"* "${INSTALL_DIR}/assets/" 2>/dev/null || true
[[ -d "${SCRIPT_DIR}/tests" ]] && cp "${SCRIPT_DIR}/tests/"*.py "${INSTALL_DIR}/tests/" 2>/dev/null || true
[[ -d "${SCRIPT_DIR}/docs" ]] && cp "${SCRIPT_DIR}/docs/"* "${INSTALL_DIR}/docs/" 2>/dev/null || true

# Copy launcher scripts
for f in run.sh test.sh configure.sh; do
    [[ -f "${SCRIPT_DIR}/$f" ]] && cp "${SCRIPT_DIR}/$f" "${INSTALL_DIR}/"
done

# ── Virtual environment ──
echo ""
echo "Creating virtual environment..."
cd "${INSTALL_DIR}"
$PYTHON_CMD -m venv .venv
source .venv/bin/activate

echo "Installing pinned dependencies..."
pip install --upgrade pip setuptools wheel -q
pip install -r requirements.txt -q
echo "  All packages installed"

# ── Create run.sh (localhost only per F-006) ──
cat > "${INSTALL_DIR}/run.sh" << 'LAUNCHER'
#!/bin/bash
set -e
cd "$(dirname "$0")"
source .venv/bin/activate
if [[ ! -f .env ]]; then
    echo "Missing .env file."
    echo "Run ./configure.sh to set up RSC credentials."
    exit 1
fi
# Security: kill any existing instance
kill -9 $(lsof -t -i :8501) 2>/dev/null || true
echo ""
echo "  RSC Cloud Native Workload Dashboard"
echo "  ===================================="
echo "  Binding: localhost:8501 only (security hardened)"
echo "  Open http://localhost:8501 in your browser"
echo "  Press Ctrl+C to stop"
echo ""
# F-006: Bind to localhost only — do not change to 0.0.0.0
# If remote access is needed, use a reverse proxy with authentication
streamlit run dashboard.py \
    --server.port 8501 \
    --server.address 127.0.0.1 \
    --server.headless true \
    --browser.gatherUsageStats false
LAUNCHER
chmod +x "${INSTALL_DIR}/run.sh"

# ── Create test.sh ──
cat > "${INSTALL_DIR}/test.sh" << 'TESTLAUNCHER'
#!/bin/bash
set -e
cd "$(dirname "$0")"
source .venv/bin/activate
if [[ ! -f .env ]]; then
    echo "Missing .env — run ./configure.sh first"
    exit 1
fi
echo ""
echo "  RSC Cloud Native Workload Dashboard"
echo "  Validation Tests"
echo "  ===================================="
echo ""
python test_monitoring.py
TESTLAUNCHER
chmod +x "${INSTALL_DIR}/test.sh"

# ── Create configure.sh ──
cat > "${INSTALL_DIR}/configure.sh" << 'CONFIGURE'
#!/bin/bash
cd "$(dirname "$0")"

echo "=============================================="
echo "  RSC Cloud Native Workload Dashboard"
echo "  Configuration"
echo "=============================================="
echo ""

if [[ -f .env ]]; then
    echo "Existing .env found. Overwrite? (y/N)"
    read -r answer
    if [[ "$answer" != "y" && "$answer" != "Y" ]]; then
        echo "Keeping existing configuration."
        exit 0
    fi
fi

echo "Enter your RSC connection details."
echo "(Get these from RSC > Settings > Service Accounts)"
echo ""
echo "NOTE: URL must match https://*.my.rubrik.com format"
echo ""
read -p "RSC Base URL (e.g., https://your-org.my.rubrik.com): " RSC_URL
read -p "Service Account Client ID: " RSC_ID
read -sp "Service Account Secret: " RSC_SECRET
echo ""
echo ""

# Basic URL validation
if [[ ! "$RSC_URL" =~ ^https://.*\.my\.rubrik\.com$ ]]; then
    echo "WARNING: URL does not match expected pattern (https://*.my.rubrik.com)"
    echo "The dashboard will reject URLs that don't match this pattern."
    echo "Continue anyway? (y/N)"
    read -r proceed
    if [[ "$proceed" != "y" && "$proceed" != "Y" ]]; then
        echo "Aborted."
        exit 1
    fi
fi

cat > .env << ENVFILE
RSC_SERVICE_ACCOUNT_ID=${RSC_ID}
RSC_SERVICE_ACCOUNT_SECRET=${RSC_SECRET}
RSC_BASE_URL=${RSC_URL}
ENVFILE

chmod 600 .env

echo "Configuration saved to .env (permissions: 600)"
echo ""
echo "Optional: Add password protection for shared environments:"
echo "  echo 'DASHBOARD_PASSWORD=your-password' >> .env"
echo ""
echo "Next steps:"
echo "  ./test.sh    - Validate connectivity"
echo "  ./run.sh     - Launch the dashboard"
CONFIGURE
chmod +x "${INSTALL_DIR}/configure.sh"

# ── .gitignore ──
cat > "${INSTALL_DIR}/.gitignore" << 'GITIGNORE'
.env
.venv/
__pycache__/
*.pyc
.event_cache.json
.event_cache.bin
.cache.key
.collection_state.json
.DS_Store
GITIGNORE

# ── Done ──
echo ""
echo "=============================================="
echo "  Installation Complete!"
echo "=============================================="
echo ""
echo "  Location:  ${INSTALL_DIR}"
echo "  Security:  localhost binding, encrypted cache, credential validation"
echo ""
echo "  Next steps:"
echo "    cd ${INSTALL_DIR}"
echo "    ./configure.sh     - Enter RSC credentials"
echo "    ./test.sh          - Validate connectivity"
echo "    ./run.sh           - Launch dashboard"
echo ""
echo "  Security notes:"
echo "    - Dashboard only accessible from localhost (127.0.0.1)"
echo "    - Event cache is AES encrypted on disk"
echo "    - Credentials validated at startup before UI renders"
echo "    - Set DASHBOARD_PASSWORD in .env for shared machines"
echo ""
