#!/bin/bash
# Disenchanted Screenshot-to-AI Wrapper
#
# Captures the current monitor (where the cursor is) and sends it to the AI vision processor.
# No dialogs or popups during capture — press the shortcut, get analysis in the chat GUI.
#
# Setup Instructions:
# 1. Run setup.sh to install dependencies
# 2. Make this script executable: chmod +x disenchanted-screenshot-wrapper.sh
# 3. In KDE System Settings → Shortcuts → Custom Shortcuts:
#    - Create new "Command/URL" shortcut
#    - Set trigger key (e.g., Meta+Shift+S)
#    - Set command to full path of this script
#
# Requirements: grim (Wayland) or spectacle (KDE/X11)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SCREENSHOT_PATH="/tmp/disenchanted_screenshot_${TIMESTAMP}.png"

# --- Take screenshot of current monitor (no dialogs) ---
# Uses -m (current monitor where cursor is) instead of -f (all monitors)
if command -v spectacle &>/dev/null; then
    # KDE native — works on both Wayland and X11
    spectacle -b -n -m -o "$SCREENSHOT_PATH"
elif command -v grim &>/dev/null; then
    # grim fallback (Wayland/wlroots) — captures focused output if possible
    FOCUSED_OUTPUT=$(wlr-randr 2>/dev/null | awk '/^[^ ]/ {name=$1} /current/ {print name; exit}')
    if [ -n "$FOCUSED_OUTPUT" ]; then
        grim -o "$FOCUSED_OUTPUT" "$SCREENSHOT_PATH"
    else
        grim "$SCREENSHOT_PATH"
    fi
else
    notify-send "Disenchanted" "No screenshot tool found. Install spectacle or grim." --icon=dialog-error
    exit 1
fi

# Verify screenshot was captured
if [ ! -f "$SCREENSHOT_PATH" ]; then
    notify-send "Disenchanted" "Failed to capture screenshot." --icon=dialog-error
    exit 1
fi

# --- Check venv ---
if [ ! -d "$VENV_DIR" ]; then
    notify-send "Disenchanted" "Not set up. Please run setup.sh first." --icon=dialog-error
    exit 1
fi

# --- Launch the chat GUI with screenshot ---
source "$VENV_DIR/bin/activate"
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"
export DISENCHANTED_INITIAL_SCREENSHOT="$SCREENSHOT_PATH"

python3 "$SCRIPT_DIR/gui/chat_window.py" --from-screenshot &

# Detach from the terminal so the script can exit
# The GUI will continue running in the background
