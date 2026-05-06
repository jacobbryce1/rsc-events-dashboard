#!/bin/bash
set -e
cd "$(dirname "$0")"

# Activate virtual environment
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "Virtual environment not found."
    echo "Run the install script first or create one:"
    echo "  python3 -m venv .venv"
    echo "  source .venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Check .env
if [ ! -f .env ]; then
    echo "Missing .env file."
    echo "Run ./configure.sh first to set up RSC credentials."
    exit 1
fi

echo ""
echo "  RSC Cloud Native Workload Dashboard"
echo "  Validation Tests"
echo "  ===================================="
echo ""

python test_monitoring.py
