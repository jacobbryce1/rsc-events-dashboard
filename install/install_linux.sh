#!/bin/bash
set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  RSC Cloud Native Workload Dashboard — Linux Installer      ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

INSTALL_DIR="${HOME}/rsc-dashboard"
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# ── Detect distro ──
if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO=$ID
else
    DISTRO="unknown"
fi
echo "🐧 Detected: ${PRETTY_NAME:-$DISTRO} ($(uname -m))"

# ── Install Python ──
echo ""
echo "🔍 Checking Python..."
PYTHON_CMD=""
for cmd in python3.12 python3.11 python3; do
    if command -v "$cmd" &>/dev/null; then
        PY_MINOR=$($cmd --version 2>&1 | awk '{print $2}' | cut -d. -f2)
        if [[ "$PY_MINOR" -ge 9 ]]; then
            PYTHON_CMD="$cmd"
            break
        fi
    fi
done

if [[ -z "$PYTHON_CMD" ]]; then
    echo "   Installing Python..."
    case "$DISTRO" in
        ubuntu|debian|pop)
            sudo apt-get update -qq
            sudo apt-get install -y python3 python3-venv python3-pip -qq
            ;;
        rhel|centos|fedora|rocky|alma)
            sudo dnf install -y python3 python3-pip
            ;;
        suse|opensuse*)
            sudo zypper install -y python3 python3-pip python3-venv
            ;;
        arch|manjaro)
            sudo pacman -S --noconfirm python python-pip
            ;;
        *)
            echo "❌ Unsupported distro: $DISTRO"
            echo "   Install Python 3.9+ manually, then re-run."
            exit 1
            ;;
    esac
    PYTHON_CMD="python3"
fi
echo "   ✅ Using: $PYTHON_CMD ($($PYTHON_CMD --version))"

# ── Install directory ──
echo ""
echo "📁 Installing to ${INSTALL_DIR}..."
mkdir -p "${INSTALL_DIR}/assets" "${INSTALL_DIR}/.streamlit"

cp "${SCRIPT_DIR}/src/"*.py "${INSTALL_DIR}/"
cp "${SCRIPT_DIR}/requirements.txt" "${INSTALL_DIR}/"
cp "${SCRIPT_DIR}/.streamlit/config.toml" "${INSTALL_DIR}/.streamlit/"
cp "${SCRIPT_DIR}/.env.example" "${INSTALL_DIR}/"
[[ -d "${SCRIPT_DIR}/assets" ]] && cp "${SCRIPT_DIR}/assets/"* "${INSTALL_DIR}/assets/" 2>/dev/null || true
[[ -d "${SCRIPT_DIR}/tests" ]] && mkdir -p "${INSTALL_DIR}/tests" && cp "${SCRIPT_DIR}/tests/"*.py "${INSTALL_DIR}/tests/" 2>/dev/null || true
[[ -d "${SCRIPT_DIR}/docs" ]] && mkdir -p "${INSTALL_DIR}/docs" && cp "${SCRIPT_DIR}/docs/"* "${INSTALL_DIR}/docs/" 2>/dev/null || true

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

# ── Launchers ──
cat > "${INSTALL_DIR}/run.sh" << 'LAUNCHER'
#!/bin/bash
set -e
cd "$(dirname "$0")"
source .venv/bin/activate
if [[ ! -f .env ]]; then echo "❌ Run ./configure.sh first"; exit 1; fi
kill -9 $(lsof -t -i :8501) 2>/dev/null || true
echo "🛡️  Starting RSC Cloud Native Workload Dashboard..."
echo "   Open http://localhost:8501"
streamlit run dashboard.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
LAUNCHER
chmod +x "${INSTALL_DIR}/run.sh"

cat > "${INSTALL_DIR}/configure.sh" << 'CONFIGURE'
#!/bin/bash
cd "$(dirname "$0")"
echo "RSC Dashboard Configuration"
echo "════════════════════════════"
read -p "RSC Base URL (https://your-org.my.rubrik.com): " RSC_URL
read -p "Service Account Client ID: " RSC_ID
read -sp "Service Account Secret: " RSC_SECRET
echo ""
cat > .env << EOF
RSC_SERVICE_ACCOUNT_ID=${RSC_ID}
RSC_SERVICE_ACCOUNT_SECRET=${RSC_SECRET}
RSC_BASE_URL=${RSC_URL}
EOF
chmod 600 .env
echo "✅ Saved. Next: ./test.sh then ./run.sh"
CONFIGURE
chmod +x "${INSTALL_DIR}/configure.sh"

cat > "${INSTALL_DIR}/test.sh" << 'EOF'
#!/bin/bash
set -e
cd "$(dirname "$0")"
source .venv/bin/activate
if [[ ! -f .env ]]; then echo "❌ Run ./configure.sh first"; exit 1; fi
python tests/test_monitoring.py
EOF
chmod +x "${INSTALL_DIR}/test.sh"

echo ""
echo "✅ Installation complete!"
echo "   cd ${INSTALL_DIR} && ./configure.sh && ./run.sh"
