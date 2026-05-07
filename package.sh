#!/bin/bash
set -e
cd "$(dirname "$0")"

VERSION="1.0.0"
PACKAGE_NAME="rsc-cloud-native-dashboard"
DIST_DIR="dist"
BUILD_DIR="${DIST_DIR}/${PACKAGE_NAME}-${VERSION}"

echo "=============================================="
echo "  Packaging RSC Cloud Native Workload Dashboard v${VERSION}"
echo "=============================================="
echo ""

# Clean previous builds
rm -rf "${DIST_DIR}"
mkdir -p "${BUILD_DIR}/assets"
mkdir -p "${BUILD_DIR}/docs"
mkdir -p "${BUILD_DIR}/install"
mkdir -p "${BUILD_DIR}/tests"
mkdir -p "${BUILD_DIR}/.streamlit"

# Source files
echo "Copying source files..."
for f in config.py rsc_client.py data_collector.py token_monitor.py \
         incremental_cache.py utils.py dashboard.py; do
    if [ -f "$f" ]; then
        cp "$f" "${BUILD_DIR}/"
        echo "  [OK] $f"
    else
        echo "  [MISSING] $f"
        exit 1
    fi
done

# Launcher scripts
echo ""
echo "Copying launcher scripts..."
for f in run.sh test.sh configure.sh run.bat test.bat configure.bat; do
    if [ -f "$f" ]; then
        cp "$f" "${BUILD_DIR}/"
        echo "  [OK] $f"
    else
        echo "  [SKIP] $f (not found)"
    fi
done

# Install scripts
echo ""
echo "Copying install scripts..."
for f in install/install_macos.sh install/install_linux.sh install/install_windows.ps1; do
    if [ -f "$f" ]; then
        cp "$f" "${BUILD_DIR}/install/"
        echo "  [OK] $f"
    else
        echo "  [SKIP] $f (not found)"
    fi
done

# Tests
echo ""
echo "Copying tests..."
if [ -f "test_monitoring.py" ]; then
    cp test_monitoring.py "${BUILD_DIR}/"
    cp test_monitoring.py "${BUILD_DIR}/tests/"
    echo "  [OK] test_monitoring.py"
fi

# Assets
echo ""
echo "Copying assets..."
if [ -d "assets" ]; then
    cp assets/* "${BUILD_DIR}/assets/" 2>/dev/null && echo "  [OK] assets/" || echo "  [SKIP] assets/ (empty)"
else
    echo "  [SKIP] assets/ (not found)"
fi

# Docs
echo ""
echo "Copying docs..."
for f in docs/SETUP_GUIDE.md docs/TROUBLESHOOTING.md; do
    if [ -f "$f" ]; then
        cp "$f" "${BUILD_DIR}/docs/"
        echo "  [OK] $f"
    else
        echo "  [SKIP] $f (not found)"
    fi
done

# Config files
echo ""
echo "Copying config files..."
cp requirements.txt "${BUILD_DIR}/"
echo "  [OK] requirements.txt"

if [ -f ".env.example" ]; then
    cp .env.example "${BUILD_DIR}/"
    echo "  [OK] .env.example"
fi

if [ -f "README.md" ]; then
    cp README.md "${BUILD_DIR}/"
    echo "  [OK] README.md"
fi

if [ -f ".streamlit/config.toml" ]; then
    cp .streamlit/config.toml "${BUILD_DIR}/.streamlit/"
    echo "  [OK] .streamlit/config.toml"
fi

# .gitignore for the package
cat > "${BUILD_DIR}/.gitignore" << 'GITIGNORE'
.env
.venv/
__pycache__/
*.pyc
.event_cache.json
.collection_state.json
.DS_Store
dist/
docs/*.docx
docs/*.pdf
GITIGNORE
echo "  [OK] .gitignore"

# Create archives
echo ""
echo "Creating archives..."
cd "${DIST_DIR}"
tar -czf "${PACKAGE_NAME}-${VERSION}.tar.gz" "${PACKAGE_NAME}-${VERSION}/"
zip -qr "${PACKAGE_NAME}-${VERSION}.zip" "${PACKAGE_NAME}-${VERSION}/"
cd ..

echo ""
echo "=============================================="
echo "  Packaging complete!"
echo "=============================================="
echo ""
ls -lh "${DIST_DIR}/${PACKAGE_NAME}-${VERSION}.tar.gz"
ls -lh "${DIST_DIR}/${PACKAGE_NAME}-${VERSION}.zip"
echo ""
echo "Distribute to testers:"
echo "  macOS/Linux: tar -xzf ${PACKAGE_NAME}-${VERSION}.tar.gz"
echo "               cd ${PACKAGE_NAME}-${VERSION}"
echo "               bash install/install_macos.sh"
echo ""
echo "  Windows:     Expand-Archive ${PACKAGE_NAME}-${VERSION}.zip ."
echo "               cd ${PACKAGE_NAME}-${VERSION}"
echo "               .\\install\\install_windows.ps1"
