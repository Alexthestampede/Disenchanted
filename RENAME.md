# Disenchanted - Renaming Summary

## Project Rename: ModuLLe GUI → Disenchanted

The KDE Plasma chat interface has been renamed from "ModuLLe GUI" to **Disenchanted** to better reflect its inspiration from the excellent [Enchanted](https://github.com/AugustDev/enchanted) project for macOS/iOS.

### Why "Disenchanted"?

A playful nod to Enchanted while emphasizing the Linux/KDE focus. The name also reflects the project's goal to "disenchant" the complexity of using multiple AI providers by providing a unified, flexible interface.

## What Changed

### Application Identity
- **Window Title**: "ModuLLe Chat" → "Disenchanted"
- **Application Name**: ModuLLe Chat → Disenchanted
- **Settings Dialog**: "ModuLLe Settings" → "Disenchanted Settings"

### Configuration
- **Config File**: `~/.modulle-gui.json` → `~/.disenchanted.json`
- Old config files will NOT be automatically migrated

### Scripts & Launchers
- **GUI Launcher**: `modulle-chat.sh` → `disenchanted-chat.sh`
- **KDE Wrapper**: `kdemodule_wrapper_new.sh` → `disenchanted-wrapper.sh`
- **Environment Variables**:
  - `MODULLE_INITIAL_TEXT` → `DISENCHANTED_INITIAL_TEXT`
  - `MODULLE_INITIAL_PROMPT` → `DISENCHANTED_INITIAL_PROMPT`

### Documentation
- **README.md**: Fully updated with Disenchanted branding and Enchanted acknowledgment
- **SETUP.md**: Updated with new names throughout
- All references to "ModuLLe GUI" changed to "Disenchanted"

### What Stayed the Same
- **Directory Name**: `dev/ModuLLe/` (kept for compatibility)
- **Library Name**: ModuLLe library in `deps/ModuLLe/` (unchanged)
- **Python Package Imports**: Still uses `from modulle import ...`
- **Core Functionality**: All features work exactly the same

## Migration Guide

If you were using the old version:

### 1. Configuration Migration (Optional)

```bash
# Copy your old config to the new name
cp ~/.modulle-gui.json ~/.disenchanted.json
```

### 2. Update KDE Shortcut

If you had a KDE global shortcut configured:

1. Open **System Settings** → **Shortcuts** → **Custom Shortcuts**
2. Find your old ModuLLe shortcut
3. Update the command path:
   - Old: `/path/to/dev/ModuLLe/kdemodule_wrapper_new.sh`
   - New: `/path/to/dev/ModuLLe/disenchanted-wrapper.sh`
4. Optionally rename the shortcut to "Disenchanted" or "Disenchanted AI Chat"

### 3. Use New Launcher

```bash
# Old way (still works but deprecated)
./modulle-chat.sh

# New way
./disenchanted-chat.sh
```

### 4. Remove Old Files (Optional)

The old scripts still exist for backward compatibility but can be removed:

```bash
# Remove deprecated launcher scripts (after verifying new ones work)
rm modulle-chat.sh
rm kdemodule_wrapper.sh
rm kdemodule_wrapper_new.sh
```

## Fresh Installation

For new users, just follow the updated [SETUP.md](SETUP.md):

```bash
cd /path/to/dev/ModuLLe
./setup.sh
./disenchanted-chat.sh  # Test the GUI
```

Then configure the KDE shortcut using `disenchanted-wrapper.sh`.

## Credits & Inspiration

**Disenchanted** is inspired by [Enchanted](https://github.com/AugustDev/enchanted), an excellent conversational AI app for macOS/iOS by August Leppänen. Disenchanted aims to bring similar functionality to Linux/KDE users with additional features like:

- Autonomous web research with tool calling
- Support for local AI providers (Ollama, LM Studio)
- Multi-provider flexibility (OpenAI, Claude, Gemini)
- KDE Plasma integration

Built on top of the [ModuLLe](../../deps/ModuLLe/) library for provider abstraction.
