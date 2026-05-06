#!/bin/bash
cd "$(dirname "$0")"

echo "=============================================="
echo "  RSC Cloud Native Workload Dashboard"
echo "  Configuration"
echo "=============================================="
echo ""

if [ -f .env ]; then
    echo "Existing .env found. Overwrite? (y/N)"
    read -r answer
    if [ "$answer" != "y" ] && [ "$answer" != "Y" ]; then
        echo "Keeping existing configuration."
        exit 0
    fi
fi

echo "Enter your RSC connection details."
echo "(Get these from RSC > Settings > Service Accounts)"
echo ""
read -p "RSC Base URL (e.g., https://your-org.my.rubrik.com): " RSC_URL
read -p "Service Account Client ID: " RSC_ID
read -sp "Service Account Secret: " RSC_SECRET
echo ""

cat > .env << ENVFILE
RSC_SERVICE_ACCOUNT_ID=${RSC_ID}
RSC_SERVICE_ACCOUNT_SECRET=${RSC_SECRET}
RSC_BASE_URL=${RSC_URL}
ENVFILE

chmod 600 .env

echo ""
echo "Configuration saved to .env"
echo ""
echo "Next steps:"
echo "  ./test.sh    - Validate connectivity"
echo "  ./run.sh     - Launch the dashboard"
