# Disenchanted - Setup Guide

A PyQt5 chat interface for KDE Plasma inspired by Enchanted, featuring autonomous web research and multi-provider AI support. Process selected text with AI using global keyboard shortcuts.

## Features

- 🎨 **Native KDE Chat Interface** - Beautiful PyQt5 GUI with dark theme
- 💬 **Conversational AI** - Full conversation history with context
- ⚙️ **Settings Panel** - Configure AI provider, models, and parameters
- ⌨️ **Global Shortcuts** - Trigger AI processing from anywhere in KDE
- 🔌 **Multi-Provider Support** - Ollama, OpenAI, Gemini, Claude, LM Studio
- 🔒 **Isolated Environment** - Uses Python virtual environment for clean installation

## Prerequisites

### System Requirements
- KDE Plasma desktop environment
- Python 3.8 or higher
- Wayland or X11 display server

### Required System Tools

Install these with your package manager:

```bash
# Fedora/RHEL
sudo dnf install python3 python3-pip kdialog wl-clipboard xsel

# Debian/Ubuntu
sudo apt install python3 python3-pip python3-venv kdialog wl-clipboard xsel

# Arch
sudo pacman -S python python-pip kdialog wl-clipboard xsel
```

**Note**: You only need `wl-clipboard` (Wayland) OR `xsel` (X11), but having both is fine.

## Installation

### Step 1: Run Setup Script

The setup script creates a virtual environment and installs all dependencies:

```bash
cd /home/alexthestampede/Aish/linuxintelligence/dev/ModuLLe
./setup.sh
```

This will:
- Create a Python virtual environment in `venv/`
- Install PyQt5 and other GUI dependencies
- Install ModuLLe library with all AI provider support
- Make launcher scripts executable

### Step 2: Test the GUI

Launch the chat interface manually to verify installation:

```bash
./disenchanted-chat.sh
```

On first run:
1. Click "⚙ Settings" button
2. Select your AI provider (Ollama recommended for testing)
3. Enter model name (e.g., `llama2` for Ollama)
4. Click "🔌 Test Connection" to verify
5. Click "Save"

### Step 3: Configure KDE Global Shortcut

Now set up the keyboard shortcut to trigger the AI from anywhere:

1. Open **KDE System Settings**
2. Navigate to **Shortcuts** → **Custom Shortcuts**
3. Right-click in the empty area and select: **New** → **Global Shortcut** → **Command/URL**
4. Name it something like "Disenchanted AI Chat"
5. In the **Trigger** tab:
   - Click the button to set a key combination
   - Press your desired shortcut (e.g., `Meta+Shift+A` or `Ctrl+Alt+M`)
6. In the **Action** tab:
   - Set **Command/URL** to the full path:
     ```
     /home/alexthestampede/Aish/linuxintelligence/dev/ModuLLe/disenchanted-wrapper.sh
     ```
7. Click **Apply**

## Usage

### From Global Shortcut (Recommended)

1. **Highlight any text** in any application (browser, editor, terminal, etc.)
2. **Press your configured shortcut** (e.g., `Meta+Shift+A`)
3. **Enter a prompt** in the dialog (e.g., "Summarize", "Translate to Spanish", "Explain this")
4. **Chat window appears** with AI response
5. **Continue the conversation** by typing follow-up questions

### From Command Line

Launch the GUI directly:

```bash
cd /home/alexthestampede/Aish/linuxintelligence/dev/ModuLLe
./disenchanted-chat.sh
```

## Configuration

### GUI Settings Panel

Access via the **⚙ Settings** button in the chat window.

#### Provider Tab
- **Provider Selection**: Choose between Ollama, LM Studio, OpenAI, Gemini, or Claude
- **Model Configuration**:
  - Text Model (required): e.g., `llama2`, `gpt-4o-mini`, `gemini-1.5-flash`
  - Vision Model (optional): For image analysis
- **Connection Settings**:
  - Base URL (local providers): e.g., `http://localhost:11434`
  - API Key (cloud providers): Your API key

#### Parameters Tab
- **Temperature** (0.0 - 2.0): Controls randomness
  - Lower (0.1-0.3): More focused, deterministic
  - Medium (0.7): Balanced
  - Higher (1.0-2.0): More creative, varied
- **Max Tokens**: Limit response length (optional)

### Configuration File

Settings are saved to `~/.disenchanted.json`:

```json
{
  "provider": "ollama",
  "text_model": "llama2",
  "vision_model": null,
  "base_url": "http://localhost:11434",
  "api_key": null,
  "temperature": 0.7,
  "max_tokens": null
}
```

You can edit this file directly if needed.

## Provider-Specific Setup

### Ollama (Local - Recommended for Privacy)

1. Install Ollama: https://ollama.ai
2. Start the server: `ollama serve`
3. Pull a model: `ollama pull llama2`
4. In Disenchanted settings:
   - Provider: Ollama (Local)
   - Text Model: `llama2`
   - Base URL: `http://localhost:11434`

### LM Studio (Local - User-Friendly)

1. Install LM Studio: https://lmstudio.ai
2. Download and load a model
3. Start the server (default: `http://localhost:1234`)
4. In Disenchanted settings:
   - Provider: LM Studio (Local)
   - Text Model: Your loaded model name
   - Base URL: `http://localhost:1234`

### OpenAI (Cloud)

1. Get API key: https://platform.openai.com/api-keys
2. In Disenchanted settings:
   - Provider: OpenAI (Cloud)
   - Text Model: `gpt-4o-mini` (cost-effective) or `gpt-4o`
   - API Key: Your key

### Google Gemini (Cloud - Free Tier Available)

1. Get API key: https://aistudio.google.com/app/apikey
2. In Disenchanted settings:
   - Provider: Google Gemini (Cloud)
   - Text Model: `gemini-1.5-flash` (free tier) or `gemini-1.5-pro`
   - API Key: Your key

### Anthropic Claude (Cloud)

1. Get API key: https://console.anthropic.com/
2. In Disenchanted settings:
   - Provider: Anthropic Claude (Cloud)
   - Text Model: `claude-3-5-haiku-20241022` or `claude-3-5-sonnet-20241022`
   - API Key: Your key

## Troubleshooting

### "Virtual environment not found"
Run `./setup.sh` to create the virtual environment.

### "No text selected" error
Make sure to highlight text before pressing the keyboard shortcut. The text must be in the primary selection (highlighted with mouse).

### GUI doesn't open
1. Check if venv is properly set up: `ls -la venv/`
2. Test manually: `./disenchanted-chat.sh`
3. Check for errors in terminal

### "Failed to initialize AI" error
1. Verify your AI provider is running (for local providers)
2. Check your API key (for cloud providers)
3. Test connection in Settings panel
4. Check model name is correct

### Keyboard shortcut not working
1. Verify shortcut in System Settings → Shortcuts
2. Check the command path is correct (use absolute path)
3. Make sure `disenchanted-wrapper_new.sh` is executable
4. Test the wrapper directly: `./disenchanted-wrapper_new.sh` (after selecting text)

### Import errors
Make sure to activate the venv and set PYTHONPATH:
```bash
source venv/bin/activate
export PYTHONPATH="$(pwd):$PYTHONPATH"
python3 gui/chat_window.py
```

## Updating

To update Disenchanted library:

```bash
cd /home/alexthestampede/Aish/linuxintelligence/dev/ModuLLe
source venv/bin/activate
pip install -e ../../deps/ModuLLe[all] --upgrade
```

To update GUI dependencies:

```bash
source venv/bin/activate
pip install -r requirements.txt --upgrade
```

## Uninstallation

```bash
cd /home/alexthestampede/Aish/linuxintelligence/dev/ModuLLe

# Remove virtual environment
rm -rf venv/

# Remove configuration
rm ~/.disenchanted.json

# Remove KDE shortcut manually in System Settings
```

## Development

### Project Structure

```
dev/ModuLLe/
├── gui/
│   ├── __init__.py
│   ├── chat_window.py      # Main chat interface
│   └── settings_dialog.py  # Settings panel
├── config/
│   ├── __init__.py
│   └── app_config.py       # Configuration management
├── venv/                   # Virtual environment (created by setup.sh)
├── setup.sh               # Installation script
├── disenchanted-chat.sh        # GUI launcher
├── disenchanted-wrapper_new.sh  # KDE integration script
├── requirements.txt       # Python dependencies
└── SETUP.md              # This file
```

### Running in Development Mode

```bash
# Activate venv
source venv/bin/activate

# Set PYTHONPATH
export PYTHONPATH="$(pwd):$PYTHONPATH"

# Run directly
python3 gui/chat_window.py

# Or with initial context for testing
MODULLE_INITIAL_TEXT="Test text" MODULLE_INITIAL_PROMPT="Summarize" python3 gui/chat_window.py --from-kde
```

## Tips

1. **Privacy**: Use Ollama or LM Studio to keep all data local
2. **Cost**: Gemini has a generous free tier; GPT-4o-mini is affordable
3. **Speed**: Local models are faster (no network latency)
4. **Quality**: GPT-4o and Claude Sonnet provide best results
5. **Shortcuts**: Create multiple shortcuts for different tasks (summarize, translate, etc.)

## License

MIT License - Same as ModuLLe library

## Credits

Built on top of ModuLLe - A modular LLM provider abstraction layer
