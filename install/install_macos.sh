#!/bin/bash
set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  RSC Cloud Native Workload Dashboard — macOS Installer      ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

INSTALL_DIR="${HOME}/rsc-dashboard"
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [[ "$(uname)" != "Darwin" ]]; then
    echo "❌ This script is for macOS only."
    exit 1
fi

# ── Homebrew ──
echo "🔍 Checking Homebrew..."
if ! command -v brew &>/dev/null; then
    echo "   Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    if [[ -f /opt/homebrew/bin/brew ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
else
    echo "   ✅ Homebrew found"
fi

# ── Python ──
echo "🔍 Checking Python..."
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
    echo "   Installing Python 3.12..."
    brew install python@3.12
    PYTHON_CMD="/opt/homebrew/bin/python3.12"
fi
echo "   ✅ Using: $PYTHON_CMD ($($PYTHON_CMD --version))"

# ── Install directory ──
echo ""
echo "📁 Installing to ${INSTALL_DIR}..."
mkdir -p "${INSTALL_DIR}/assets"
mkdir -p "${INSTALL_DIR}/.streamlit"

# Copy source
cp "${SCRIPT_DIR}/src/"*.py "${INSTALL_DIR}/"
cp "${SCRIPT_DIR}/requirements.txt" "${INSTALL_DIR}/"
cp "${SCRIPT_DIR}/.streamlit/config.toml" "${INSTALL_DIR}/.streamlit/"
cp "${SCRIPT_DIR}/.env.example" "${INSTALL_DIR}/"

# Copy assets
if [[ -d "${SCRIPT_DIR}/assets" ]]; then
    cp "${SCRIPT_DIR}/assets/"* "${INSTALL_DIR}/assets/" 2>/dev/null || true
fi

# Copy tests
if [[ -d "${SCRIPT_DIR}/tests" ]]; then
    mkdir -p "${INSTALL_DIR}/tests"
    cp "${SCRIPT_DIR}/tests/"*.py "${INSTALL_DIR}/tests/" 2>/dev/null || true
fi

# Copy docs
if [[ -d "${SCRIPT_DIR}/docs" ]]; then
    mkdir -p "${INSTALL_DIR}/docs"
    cp "${SCRIPT_DIR}/docs/"* "${INSTALL_DIR}/docs/" 2>/dev/null || true
fi

# ── Virtual environment ──
echo ""
echo "🐍 Creating virtual environment..."
cd "${INSTALL_DIR}"
$PYTHON_CMD -m venv .venv
source .venv/bin/activate

echo "📦 Installing dependencies..."
pip install --upgrade pip setuptools wheel -q
pip install -r requirements.txt -q
echo "   ✅ All packages installed"

# ── Create launchers ──
cat > "${INSTALL_DIR}/run.sh" << 'LAUNCHER'
#!/bin/bash
set -e
cd "$(dirname "$0")"
source .venv/bin/activate
if [[ ! -f .env ]]; then
    echo "❌ Missing .env file."
    echo "   Run: ./configure.sh"
    exit 1
fi
# Kill existing instance on same port
kill -9 $(lsof -t -i :8501) 2>/dev/null || true
echo "🛡️  Starting RSC Cloud Native Workload Dashboard..."
echo "   Open http://localhost:8501"
echo "   Press Ctrl+C to stop"
echo ""
streamlit run dashboard.py --server.port 8501 --server.address localhost --server.headless true --browser.gatherUsageStats false
LAUNCHER
chmod +x "${INSTALL_DIR}/run.sh"

cat > "${INSTALL_DIR}/test.sh" << 'TESTLAUNCHER'
#!/bin/bash
set -e
cd "$(dirname "$0")"
source .venv/bin/activate
if [[ ! -f .env ]]; then
    echo "❌ Missing .env — run ./configure.sh first"
    exit 1
fi
echo "🧪 Running validation tests..."
python tests/test_monitoring.py
TESTLAUNCHER
chmod +x "${INSTALL_DIR}/test.sh"

cat > "${INSTALL_DIR}/configure.sh" << 'CONFIGURE'
#!/bin/bash
cd "$(dirname "$0")"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  RSC Cloud Native Workload Dashboard — Configuration        ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

if [[ -f .env ]]; then
    echo "⚠️  Existing .env found. Overwrite? (y/N)"
    read -r answer
    if [[ "$answer" != "y" && "$answer" != "Y" ]]; then
        echo "Keeping existing configuration."
        exit 0
    fi
fi

echo "Enter your RSC connection details:"
echo "(Get these from RSC > Settings > Service Accounts)"
echo ""
read -p "RSC Base URL (e.g., https://your-org.my.rubrik.com): " RSC_URL
read -p "Service Account Client ID: " RSC_ID
read -sp "Service Account Secret: " RSC_SECRET
echo ""

# Validate URL format
if [[ ! "$RSC_URL" =~ ^https:// ]]; then
    echo "⚠️  URL should start with https://"
fi

cat > .env << ENVEOF
RSC_SERVICE_ACCOUNT_ID=${RSC_ID}
RSC_SERVICE_ACCOUNT_SECRET=${RSC_SECRET}
RSC_BASE_URL=${RSC_URL}
ENVEOF

chmod 600 .env
echo ""
echo "✅ Configuration saved to .env"
echo ""
echo "Next steps:"
echo "  ./test.sh    — Validate connectivity and data"
echo "  ./run.sh     — Launch the dashboard"
CONFIGURE
chmod +x "${INSTALL_DIR}/configure.sh"

# ── .gitignore ──
cat > "${INSTALL_DIR}/.gitignore" << 'GITIGNORE'
.env
.venv/
__pycache__/
*.pyc
.event_cache.json
.collection_state.json
.DS_Store
GITIGNORE

# ── Done ──
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ✅ Installation Complete!                                  ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "  Installed to: ${INSTALL_DIR}"
echo ""
echo "  Quick start:"
echo "    cd ${INSTALL_DIR}"
echo "    ./configure.sh     ← Enter RSC credentials"
echo "    ./test.sh          ← Validate connectivity"
echo "    ./run.sh           ← Launch dashboard"
echo ""
