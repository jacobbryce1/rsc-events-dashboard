#!/bin/bash
set -e
cd "$(dirname "$0")"

TODAY=$(date +%Y-%m-%d)

echo "📄 Generating documentation..."
echo "   Date: ${TODAY}"
echo ""

# Check for pandoc
if ! command -v pandoc &>/dev/null; then
    echo "⚠️  pandoc not found. Installing..."
    if [[ "$(uname)" == "Darwin" ]]; then
        if command -v brew &>/dev/null; then
            brew install pandoc
        else
            echo "❌ Install Homebrew first, or install pandoc manually:"
            echo "   https://pandoc.org/installing.html"
            exit 1
        fi
    elif command -v apt-get &>/dev/null; then
        sudo apt-get install -y pandoc
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y pandoc
    else
        echo "❌ Install pandoc manually: https://pandoc.org/installing.html"
        exit 1
    fi
fi

echo "   Using pandoc $(pandoc --version | head -1)"
echo ""

# ── Generate Setup Guide ──
echo "   📝 Generating Setup Guide..."
if [[ ! -f SETUP_GUIDE.md ]]; then
    echo "   ❌ SETUP_GUIDE.md not found"
    exit 1
fi

pandoc SETUP_GUIDE.md \
    -f markdown \
    -t docx \
    --toc \
    --toc-depth=3 \
    --metadata title="RSC Cloud Native Workload Dashboard - Setup Guide" \
    --metadata subtitle="Installation, Configuration & Usage" \
    --metadata author="Jacob Bryce — Advisory SE, Strategic Accounts" \
    --metadata date="${TODAY}" \
    -o "RSC_Cloud_Native_Dashboard_Setup_Guide.docx"

echo "   ✅ RSC_Cloud_Native_Dashboard_Setup_Guide.docx"

# ── Generate Troubleshooting Guide ──
echo "   📝 Generating Troubleshooting Guide..."
if [[ ! -f TROUBLESHOOTING.md ]]; then
    echo "   ❌ TROUBLESHOOTING.md not found"
    exit 1
fi

pandoc TROUBLESHOOTING.md \
    -f markdown \
    -t docx \
    --toc \
    --metadata title="RSC Cloud Native Workload Dashboard - Troubleshooting" \
    --metadata subtitle="Common Issues & Solutions" \
    --metadata author="Jacob Bryce — Advisory SE, Strategic Accounts" \
    --metadata date="${TODAY}" \
    -o "RSC_Cloud_Native_Dashboard_Troubleshooting.docx"

echo "   ✅ RSC_Cloud_Native_Dashboard_Troubleshooting.docx"

# ── Generate Combined Document ──
echo "   📝 Generating Combined Guide..."

COMBINED_FILE="_combined_temp.md"

cat > "${COMBINED_FILE}" << HEADER
---
title: "RSC Cloud Native Workload Dashboard"
subtitle: "Complete Documentation"
author: "Jacob Bryce — Advisory SE, Strategic Accounts"
date: "${TODAY}"
---

HEADER

cat SETUP_GUIDE.md >> "${COMBINED_FILE}"
printf '\n\n---\n\n# Troubleshooting\n\n' >> "${COMBINED_FILE}"
# Skip the H1 title from troubleshooting since we added our own
tail -n +3 TROUBLESHOOTING.md >> "${COMBINED_FILE}"

pandoc "${COMBINED_FILE}" \
    -f markdown \
    -t docx \
    --toc \
    --toc-depth=3 \
    -o "RSC_Cloud_Native_Dashboard_Complete_Guide.docx"

rm -f "${COMBINED_FILE}"

echo "   ✅ RSC_Cloud_Native_Dashboard_Complete_Guide.docx"

# ── Summary ──
echo ""
echo "═══════════════════════════════════════════════════"
echo "  ✅ All documents generated:"
echo "═══════════════════════════════════════════════════"
echo ""
ls -lh *.docx
echo ""
echo "  Ready to distribute to testers."
