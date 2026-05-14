#!/bin/bash
set -e
cd "$(dirname "$0")"

# Activate virtual environment
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "Virtual environment not found."
    echo "Run the install script first or create one:"
    echo "  python3 -m venv .venv"
    echo "  source .venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Ensure all dependencies are installed (safe to run on every launch)
echo "  Checking dependencies..."
pip install -r requirements.txt -q
pip install watchdog -q
echo "  Dependencies OK"

# Check .env
if [ ! -f .env ]; then
    echo "Missing .env file."
    echo "Run ./configure.sh to set up RSC credentials."
    exit 1
fi

# Kill any existing instance on port 8501
kill -9 $(lsof -t -i :8501) 2>/dev/null || true

echo ""
echo "  RSC Cloud Native Workload Dashboard"
echo "  ===================================="
echo ""
echo "  Open http://localhost:8501 in your browser"
echo "  Press Ctrl+C to stop"
echo ""

streamlit run dashboard.py \
    --server.port 8501 \
    --server.address localhost \
    --server.headless true \
    --browser.gatherUsageStats false
