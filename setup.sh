#!/bin/bash
# Setup script for Disenchanted - KDE AI Chat GUI

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
DEPS_DIR="$SCRIPT_DIR/deps"
MODULLE_LIB="$DEPS_DIR/ModuLLe"

echo "================================================"
echo "Disenchanted - KDE AI Chat Setup"
echo "================================================"

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Found Python $PYTHON_VERSION"

# Check for git (needed to clone ModuLLe)
if ! command -v git &> /dev/null; then
    echo "✗ Error: git is not installed"
    echo "Please install git first: sudo dnf install git"
    exit 1
fi

# Clone ModuLLe library if not present
if [ ! -d "$MODULLE_LIB" ]; then
    echo ""
    echo "ModuLLe library not found, cloning from GitHub..."
    mkdir -p "$DEPS_DIR"

    if git clone https://github.com/Alexthestampede/ModuLLe.git "$MODULLE_LIB"; then
        echo "✓ ModuLLe cloned successfully"
    else
        echo "✗ Failed to clone ModuLLe"
        echo "Please check your internet connection or clone manually:"
        echo "  mkdir -p $DEPS_DIR"
        echo "  git clone https://github.com/Alexthestampede/ModuLLe.git $MODULLE_LIB"
        exit 1
    fi
else
    echo "✓ ModuLLe library found at $MODULLE_LIB"
fi

# Create virtual environment
if [ ! -d "$VENV_DIR" ]; then
    echo ""
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate venv and install dependencies
echo ""
echo "Installing dependencies..."
source "$VENV_DIR/bin/activate"

# Upgrade pip
pip install --upgrade pip > /dev/null 2>&1

# Install PyQt5 and other GUI dependencies
pip install -r "$SCRIPT_DIR/requirements.txt"

# Install ModuLLe library with all providers
echo ""
echo "Installing ModuLLe library..."
pip install -e "$MODULLE_LIB[all]"

# Make launcher scripts executable
echo ""
echo "Making launcher scripts executable..."
chmod +x "$SCRIPT_DIR/disenchanted-chat.sh"
chmod +x "$SCRIPT_DIR/disenchanted-wrapper.sh"

echo ""
echo "================================================"
echo "✓ Setup complete!"
echo "================================================"
echo ""
echo "Next steps:"
echo "1. Run manually to test:"
echo "   $SCRIPT_DIR/disenchanted-chat.sh"
echo ""
echo "2. Set up KDE global shortcut:"
echo "   System Settings → Shortcuts → Custom Shortcuts"
echo "   Command: $SCRIPT_DIR/disenchanted-wrapper.sh"
echo ""
echo "3. Read the full setup guide:"
echo "   cat $SCRIPT_DIR/SETUP.md"
echo ""
