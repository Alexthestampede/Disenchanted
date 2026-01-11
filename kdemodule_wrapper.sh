#!/bin/bash

# A wrapper script to use ModuLLe with KDE Plasma global shortcuts.
# 1. Grabs highlighted text.
# 2. Asks for a prompt via a dialog box.
# 3. Runs ModuLLe with the text and prompt.
# 4. Displays the output in a dialog box.

# --- Configuration ---
# Set the absolute path to your modulle.sh script
MODULLE_SCRIPT_PATH="/home/alexthestampede/Aish/linuxintelligence/dev/ModuLLe/modulle.sh" #<-- IMPORTANT: Verify this path!

# --- Main Logic ---

# Check for Wayland or X11 to grab clipboard content
if [ "$XDG_SESSION_TYPE" = "wayland" ]; then
    SELECTED_TEXT=$(wl-paste -p)
else
    SELECTED_TEXT=$(xsel -o)
fi

# If no text was selected, exit gracefully
if [ -z "$SELECTED_TEXT" ]; then
    kdialog --error "No text selected."
    exit 1
fi

# Get user's prompt via a kdialog input box
USER_PROMPT=$(kdialog --inputbox "Enter your prompt for the selected text:" "AI Prompt")

# If the user cancelled the dialog, exit
if [ $? -ne 0 ]; then
    exit 0
fi

# Combine the user prompt and the selected text to form the input for ModuLLe
# This assumes modulle.sh can take the combined text via standard input.
FULL_INPUT="${USER_PROMPT}:

${SELECTED_TEXT}"

# Run the ModuLLe script and capture its output
AI_OUTPUT=$(echo -e "${FULL_INPUT}" | "$MODULLE_SCRIPT_PATH")

# Display the output in a kdialog message box
kdialog --msgbox "$AI_OUTPUT"
