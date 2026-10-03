#!/usr/bin/env python3
"""
Disenchanted GUI Configuration Management
Handles loading and saving settings for the KDE GUI application

Config is a nested dict persisted to ~/.disenchanted.json. Top-level keys
are the legacy flat provider settings; feature settings live under
namespaced keys (tasks, compression, searxng, mcp, hrr, dtline, ui).
Unknown keys in the file are preserved on save (merge-on-write).
"""
import json
import copy
from pathlib import Path
from typing import Dict, Any, Optional


class AppConfig:
    """Configuration manager for Disenchanted GUI"""

    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize config manager

        Args:
            config_file: Path to config file (defaults to ~/.disenchanted.json)
        """
        if config_file:
            self.config_file = Path(config_file)
        else:
            self.config_file = Path.home() / '.disenchanted.json'

    def load_settings(self) -> Dict[str, Any]:
        """Load settings from config file, merged over defaults."""
        defaults = self._get_defaults()
        if not self.config_file.exists():
            return defaults
        try:
            with open(self.config_file, 'r') as f:
                stored = json.load(f)
            return self._deep_merge(defaults, stored)
        except Exception as e:
            print(f"Error loading config: {e}")
            return defaults

    def save_settings(self, settings: Dict[str, Any]):
        """Save settings, preserving unknown keys already in the file."""
        current: Dict[str, Any] = {}
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    current = json.load(f)
            # guarantee new nested sections exist in freshly-saved files
            current = self._deep_merge(self._get_defaults(), current)
        except Exception:
            current = self._get_defaults()
        merged = self._deep_merge(current, settings)
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(merged, f, indent=2)
        except Exception as e:
            raise Exception(f"Failed to save settings: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get one setting (top-level key)."""
        return self.load_settings().get(key, default)

    def get_section(self, name: str) -> Dict[str, Any]:
        """Get a nested section as a dict (empty dict if missing)."""
        val = self.load_settings().get(name)
        return dict(val) if isinstance(val, dict) else {}

    def reset_settings(self):
        """Reset settings to defaults"""
        self.save_settings(self._get_defaults())

    def get_config_path(self) -> str:
        """Get the path to the config file"""
        return str(self.config_file)

    # -- internals -----------------------------------------------------------
    @staticmethod
    def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """merge override into base recursively; override wins, base keys kept."""
        out = copy.deepcopy(base)
        for k, v in (override or {}).items():
            if isinstance(v, dict) and isinstance(out.get(k), dict):
                out[k] = AppConfig._deep_merge(out[k], v)
            else:
                out[k] = copy.deepcopy(v)
        return out

    def _get_defaults(self) -> Dict[str, Any]:
        """
        Get default settings
        """
        return {
            # -- legacy provider settings (unchanged shape) --
            'provider': 'ollama',
            'text_model': 'llama2',
            'vision_model': None,
            'base_url': 'http://localhost:11434',
            'api_key': None,
            'temperature': None,        # None = use server default
            'max_tokens': None,
            'system_prompt': '',        # Empty = no system prompt
            'screenshot_prompt': 'Analyze this screenshot',

            # -- task-specific model routing (main model = top-level keys) --
            'tasks': {
                # each: {provider, model, api_key, base_url} or {} = main
                'title': {},
                'compress': {},
                'vision': {},
            },

            # -- context compression --
            'compression': {
                'enabled': True,
                'context_tokens': 8192,     # model's context window
                'threshold_pct': 70,        # compress at >= this % of window
                'keep_recent': 6,           # recent turns kept verbatim
                'prompt': None,             # None = built-in default prompt
            },

            # -- file attachments --
            'attachments': {
                'max_chars_inline': 60000,  # per-file injection budget
                'strategy': 'inject',       # inject | summarize | attach
            },

            # -- SearXNG (dummy default; user configures their instance) --
            'searxng': {
                'enabled': False,
                'base_url': 'http://localhost:8888',
                'categories': 'general',
                'language': '',
                'safesearch': 1,
                'max_results': 5,
            },

            # -- MCP servers --
            'mcp': {
                'enabled': False,
                'servers': []   # [{name, transport, command/url, args, env, ...}]
            },

            # -- HRR memory --
            'hrr': {
                'enabled': False,
                'dim': 2048,
                'top_k': 3,
                'auto_write': True,   # store exchanges automatically
            },

            # -- dtline image generation --
            'dtline': {
                'enabled': True,
                'model': None,        # None = dtline config default
                'preset': None,
                'size': None,         # e.g. "1:1 1024x1024"
                'steps': None,
                'seed': None,
                'output_dir': None,   # None = dtline default
            },

            # -- timestamps / time injection --
            'timestamps': {
                'show_on_bubbles': True,
                'inject_into_prompt': True,   # date/time line in system prompt
            },

            # -- conversations storage --
            'conversations': {
                'autosave': True,
                'dir': None,          # None = ~/.disenchanted/conversations
            },
        }