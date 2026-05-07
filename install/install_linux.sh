#!/bin/bash
set -e

echo "=============================================="
echo "  RSC Cloud Native Workload Dashboard"
echo "  Linux Installer (v1.0.1 - Security Hardened)"
echo "=============================================="
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
echo "Detected: ${PRETTY_NAME:-$DISTRO} ($(uname -m))"

# ── Install Python ──
echo ""
echo "Checking Python..."
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
    echo "  Installing Python..."
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
            echo "Unsupported distro: $DISTRO"
            echo "Install Python 3.9+ manually, then re-run."
            exit 1
            ;;
    esac
    PYTHON_CMD="python3"
fi
echo "  Using: $PYTHON_CMD ($($PYTHON_CMD --version))"

# ── Install directory ──
echo ""
echo "Installing to ${INSTALL_DIR}..."
mkdir -p "${INSTALL_DIR}/assets" "${INSTALL_DIR}/.streamlit"
mkdir -p "${INSTALL_DIR}/tests" "${INSTALL_DIR}/docs"

cp "${SCRIPT_DIR}/"*.py "${INSTALL_DIR}/" 2>/dev/null || true
cp "${SCRIPT_DIR}/requirements.txt" "${INSTALL_DIR}/"
cp "${SCRIPT_DIR}/.env.example" "${INSTALL_DIR}/"
cp "${SCRIPT_DIR}/.streamlit/config.toml" "${INSTALL_DIR}/.streamlit/"
[[ -d "${SCRIPT_DIR}/assets" ]] && cp "${SCRIPT_DIR}/assets/"* "${INSTALL_DIR}/assets/" 2>/dev/null || true
[[ -d "${SCRIPT_DIR}/tests" ]] && cp "${SCRIPT_DIR}/tests/"*.py "${INSTALL_DIR}/tests/" 2>/dev/null || true
[[ -d "${SCRIPT_DIR}/docs" ]] && cp "${SCRIPT_DIR}/docs/"* "${INSTALL_DIR}/docs/" 2>/dev/null || true

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

# ── Launchers (F-006: localhost only) ──
cat > "${INSTALL_DIR}/run.sh" << 'LAUNCHER'
#!/bin/bash
set -e
cd "$(dirname "$0")"
source .venv/bin/activate
if [[ ! -f .env ]]; then
    echo "Missing .env — run ./configure.sh first"
    exit 1
fi
kill -9 $(lsof -t -i :8501) 2>/dev/null || true
echo ""
echo "  RSC Cloud Native Workload Dashboard"
echo "  Binding: localhost:8501 only (security hardened)"
echo "  Open http://localhost:8501"
echo "  Press Ctrl+C to stop"
echo ""
# F-006: Bind to 127.0.0.1 only — NOT 0.0.0.0
# For remote access, use a reverse proxy with authentication
streamlit run dashboard.py \
    --server.port 8501 \
    --server.address 127.0.0.1 \
    --server.headless true \
    --browser.gatherUsageStats false
LAUNCHER
chmod +x "${INSTALL_DIR}/run.sh"

cat > "${INSTALL_DIR}/configure.sh" << 'CONFIGURE'
#!/bin/bash
cd "$(dirname "$0")"
echo "RSC Dashboard Configuration"
echo "============================"
echo ""
echo "NOTE: URL must match https://*.my.rubrik.com"
echo ""
read -p "RSC Base URL (https://your-org.my.rubrik.com): " RSC_URL
read -p "Service Account Client ID: " RSC_ID
read -sp "Service Account Secret: " RSC_SECRET
echo ""
if [[ ! "$RSC_URL" =~ ^https://.*\.my\.rubrik\.com$ ]]; then
    echo "WARNING: URL does not match expected pattern."
fi
cat > .env << EOF
RSC_SERVICE_ACCOUNT_ID=${RSC_ID}
RSC_SERVICE_ACCOUNT_SECRET=${RSC_SECRET}
RSC_BASE_URL=${RSC_URL}
EOF
chmod 600 .env
echo ""
echo "Saved to .env (permissions: 600)"
echo "Optional: echo 'DASHBOARD_PASSWORD=pass' >> .env"
echo "Next: ./test.sh then ./run.sh"
CONFIGURE
chmod +x "${INSTALL_DIR}/configure.sh"

cat > "${INSTALL_DIR}/test.sh" << 'EOF'
#!/bin/bash
set -e
cd "$(dirname "$0")"
source .venv/bin/activate
if [[ ! -f .env ]]; then echo "Run ./configure.sh first"; exit 1; fi
python test_monitoring.py
EOF
chmod +x "${INSTALL_DIR}/test.sh"

cat > "${INSTALL_DIR}/.gitignore" << 'EOF'
.env
.venv/
__pycache__/
*.pyc
.event_cache.json
.event_cache.bin
.cache.key
.DS_Store
EOF

echo ""
echo "=============================================="
echo "  Installation Complete!"
echo "=============================================="
echo ""
echo "  cd ${INSTALL_DIR}"
echo "  ./configure.sh && ./test.sh && ./run.sh"
echo ""
echo "  Security: localhost only, encrypted cache, credential validation"
echo ""
