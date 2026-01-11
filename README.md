# Disenchanted - KDE Plasma AI Chat

A PyQt5-based conversational AI interface for KDE Plasma inspired by Enchanted. Features autonomous web research, multi-provider support, and global keyboard shortcuts. Process selected text from anywhere in KDE using AI, with full conversation history and advanced settings.

**Why "Disenchanted"?** Inspired by the excellent [Enchanted](https://github.com/AugustDev/enchanted) project, Disenchanted brings similar conversational AI capabilities to Linux/KDE with a focus on web research and provider flexibility.

## ✨ Features

- 🎨 **Native KDE Chat GUI** - Beautiful PyQt5 interface with KDE dark theme
- 💬 **Conversational AI** - Full conversation history with context awareness
- 🌐 **Web Search** - Enable autonomous web research with tool calling (DuckDuckGo)
- ⚙️ **Settings Panel** - Configure provider, models, temperature, and more
- ⌨️ **Global Shortcuts** - Trigger AI from anywhere with a hotkey
- 🔌 **Multi-Provider** - Supports Ollama, OpenAI, Gemini, Claude, LM Studio
- 🔒 **Isolated venv** - Clean installation using Python virtual environment

## 🚀 Quick Start

See **[SETUP.md](SETUP.md)** for complete installation and usage instructions.

### Installation

```bash
# Run the automated setup
./setup.sh

# Test the GUI
./disenchanted-chat.sh
```

### Usage

1. Highlight text anywhere in KDE
2. Press your configured shortcut (e.g., `Meta+Shift+A`)
3. Enter your prompt (e.g., "Summarize", "Translate to Spanish")
4. Chat window opens with AI response
5. Continue the conversation with follow-up questions

### Web Search Feature

The GUI now includes autonomous web search capabilities using tool calling:

1. Click the **🌐 Web Search** button in the top bar to enable/disable
2. When enabled, the AI can autonomously search the web and fetch pages
3. The AI will decide when to use web search based on your questions
4. You'll see indicators like "🔍 Searching web for: ..." in the chat

**Requirements:**
- Model must support tool calling (most modern models do)
- Supported providers: Ollama, OpenAI, Claude, Gemini
- Uses DuckDuckGo (free, no API key needed)

**Example queries:**
- "What's the latest news about Python 3.13?"
- "Compare the features of React vs Vue in 2026"
- "Find recent articles about quantum computing breakthroughs"

## 📁 Project Structure

```
dev/ModuLLe/  # Note: Directory name not changed to maintain compatibility
├── gui/                    # PyQt5 GUI components
│   ├── chat_window.py      # Main chat interface (Disenchanted)
│   └── settings_dialog.py  # Settings configuration
├── config/                 # Configuration management
│   └── app_config.py       # Settings persistence (~/.disenchanted.json)
├── venv/                   # Virtual environment (auto-created)
├── setup.sh               # Automated setup script
├── disenchanted-chat.sh   # GUI launcher
├── disenchanted-wrapper.sh  # KDE shortcut integration
├── requirements.txt       # Python dependencies
├── SETUP.md              # Detailed setup guide
└── README.md             # This file
```

## 🎯 Features & Inspiration

**Disenchanted** combines the best of local Linux AI tools with inspiration from [Enchanted](https://github.com/AugustDev/enchanted):

**Core Features**:
- 💬 Full PyQt5 chat interface with conversation history
- 🌐 Autonomous web research with tool calling
- 🔌 Multi-provider support (Ollama, OpenAI, Claude, Gemini, LM Studio)
- ⚙️ Advanced settings panel for fine-tuned control
- 🖼️ Vision model support for image analysis
- 🔒 Isolated virtual environment
- ⌨️ KDE global shortcuts integration

**Built on ModuLLe**:
Disenchanted uses the [ModuLLe](../../deps/ModuLLe/) library for provider abstraction, allowing seamless switching between local and cloud AI providers.

## 📚 Documentation & Credits

- **[SETUP.md](SETUP.md)** - Complete setup and usage guide
- **[../../deps/ModuLLe/README.md](../../deps/ModuLLe/README.md)** - ModuLLe library documentation
- **[Enchanted](https://github.com/AugustDev/enchanted)** - The inspiration for this project

## 🙏 Acknowledgments

Disenchanted is inspired by [Enchanted](https://github.com/AugustDev/enchanted), an excellent conversational AI app for macOS/iOS. Disenchanted aims to bring similar functionality to Linux/KDE users with additional features like autonomous web research.

## 🔧 Requirements

- KDE Plasma desktop
- Python 3.8+
- kdialog, wl-clipboard (Wayland) or xsel (X11)
- See SETUP.md for installation commands

## 💡 Tips

- Use **Ollama** for privacy (all local, no cloud)
- Use **Gemini** for free cloud AI (generous free tier)
- Configure multiple shortcuts for different tasks
- Edit `~/.modulle-gui.json` to change settings

## 📝 License

MIT License - Same as ModuLLe library
