#!/bin/bash
# Disenchanted Chat Launcher
# Launches the Disenchanted chat GUI with proper venv activation

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
PYTHON_SCRIPT="$SCRIPT_DIR/gui/chat_window.py"

# Check if venv exists
if [ ! -d "$VENV_DIR" ]; then
    echo "Error: Virtual environment not found!"
    echo "Please run setup.sh first:"
    echo "  cd $SCRIPT_DIR"
    echo "  ./setup.sh"
    exit 1
fi

# Activate venv and run the GUI
source "$VENV_DIR/bin/activate"

# Add current directory to PYTHONPATH so imports work
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

# Run with any arguments passed to the script
python3 "$PYTHON_SCRIPT" "$@"
