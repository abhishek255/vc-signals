#!/bin/bash
# VC Signals — one-line installer
# Usage: curl -sL https://raw.githubusercontent.com/abhishek255/vc-signals/main/install.sh | bash

set -e

SKILL_NAME="vc-signals"
SKILL_DIR="$HOME/.claude/skills/$SKILL_NAME"
REPO_URL="https://github.com/abhishek255/vc-signals.git"
TMP_DIR=$(mktemp -d)

echo ""
echo "  VC Signals Installer"
echo "  ===================="
echo ""

# Check Python
echo "  Checking Python..."
PYTHON=""
for py in python3.14 python3.13 python3.12 python3; do
    if command -v "$py" >/dev/null 2>&1; then
        version=$("$py" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
        major=$(echo "$version" | cut -d. -f1)
        minor=$(echo "$version" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 12 ]; then
            PYTHON="$py"
            echo "  Found $py ($version)"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo ""
    echo "  Python 3.12+ is required but not found."
    echo "  Install it with: brew install python@3.13"
    echo ""
    exit 1
fi

# Clone repo to temp dir
echo "  Downloading VC Signals..."
git clone --quiet --depth 1 "$REPO_URL" "$TMP_DIR/vc-signals" 2>/dev/null

# Copy skill to global location
echo "  Installing skill to $SKILL_DIR..."
mkdir -p "$HOME/.claude/skills"
rm -rf "$SKILL_DIR"
cp -r "$TMP_DIR/vc-signals/.claude/skills/vc-signals" "$SKILL_DIR"

# Pre-create vendor directory for last30days (cloned during setup wizard)
mkdir -p "$HOME/.claude/vendor"
echo "  Vendor directory ready at $HOME/.claude/vendor/"

# Try to install requests (optional — skill works without it)
echo "  Installing Python dependencies..."
$PYTHON -m pip install requests >/dev/null 2>&1 || \
$PYTHON -m pip install --user requests >/dev/null 2>&1 || \
echo "  Note: Could not install 'requests' library. GitHub trending will be limited."

# Clean up
rm -rf "$TMP_DIR"

echo ""
echo "  Done! VC Signals is installed."
echo ""
echo "  Open Claude Code or Co-Work and type:"
echo "    /vc-signals weekly devtools"
echo ""
echo "  The skill will guide you through setup on first run."
echo ""
