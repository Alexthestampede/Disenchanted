#!/bin/bash
# Disenchanted KDE Global Shortcut Wrapper
#
# This script integrates Disenchanted with KDE Plasma global shortcuts.
# It captures selected text, prompts for an AI task, and displays results in a chat GUI.
#
# Setup Instructions:
# 1. Run setup.sh to install dependencies
# 2. Make this script executable: chmod +x disenchanted-wrapper.sh
# 3. In KDE System Settings → Shortcuts → Custom Shortcuts:
#    - Create new "Command/URL" shortcut
#    - Set trigger key (e.g., Meta+Shift+A)
#    - Set command to full path of this script
#
# Requirements: kdialog, xsel (X11) or wl-paste (Wayland)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
LAUNCHER="$SCRIPT_DIR/disenchanted-chat.sh"

# --- Grab selected text ---
if [ "$XDG_SESSION_TYPE" = "wayland" ]; then
    SELECTED_TEXT=$(wl-paste -p 2>/dev/null)
else
    SELECTED_TEXT=$(xsel -o 2>/dev/null)
fi

# If no text selected, show error and exit
if [ -z "$SELECTED_TEXT" ]; then
    kdialog --error "No text selected. Please highlight some text first."
    exit 1
fi

# --- Get user's prompt ---
USER_PROMPT=$(kdialog --inputbox "What would you like to do with the selected text?" \
    "Disenchanted AI Prompt" \
    "Summarize this")

# If user cancelled, exit
if [ $? -ne 0 ]; then
    exit 0
fi

# If prompt is empty, use a default
if [ -z "$USER_PROMPT" ]; then
    USER_PROMPT="Analyze this text"
fi

# --- Launch the chat GUI with context ---
# The GUI will open with the initial prompt and text already loaded

# Check if venv exists
if [ ! -d "$VENV_DIR" ]; then
    kdialog --error "Disenchanted is not set up. Please run:\n\ncd $SCRIPT_DIR\n./setup.sh"
    exit 1
fi

# Activate venv and launch GUI
source "$VENV_DIR/bin/activate"
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

# Launch GUI with initial text and prompt as arguments
# We'll pass them as environment variables to avoid shell escaping issues
export DISENCHANTED_INITIAL_TEXT="$SELECTED_TEXT"
export DISENCHANTED_INITIAL_PROMPT="$USER_PROMPT"

python3 "$SCRIPT_DIR/gui/chat_window.py" --from-kde &

# Detach from the terminal so the script can exit
# The GUI will continue running in the background
