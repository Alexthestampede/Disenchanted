#!/usr/bin/env python3
"""
Disenchanted GUI Configuration Management
Handles loading and saving settings for the KDE GUI application
"""
import json
import os
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
        """
        Load settings from config file

        Returns:
            Dictionary of settings, or defaults if file doesn't exist
        """
        if not self.config_file.exists():
            return self._get_defaults()

        try:
            with open(self.config_file, 'r') as f:
                settings = json.load(f)
                # Merge with defaults to ensure all keys exist
                defaults = self._get_defaults()
                defaults.update(settings)
                return defaults
        except Exception as e:
            print(f"Error loading config: {e}")
            return self._get_defaults()

    def save_settings(self, settings: Dict[str, Any]):
        """
        Save settings to config file

        Args:
            settings: Dictionary of settings to save
        """
        try:
            # Create parent directory if it doesn't exist
            self.config_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self.config_file, 'w') as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            raise Exception(f"Failed to save settings: {e}")

    def _get_defaults(self) -> Dict[str, Any]:
        """
        Get default settings

        Returns:
            Dictionary of default settings
        """
        return {
            'provider': 'ollama',
            'text_model': 'llama2',
            'vision_model': None,
            'base_url': 'http://localhost:11434',
            'api_key': None,
            'temperature': None,  # None = use server default
            'max_tokens': None,
            'system_prompt': ''  # Empty = no system prompt
        }

    def reset_settings(self):
        """Reset settings to defaults"""
        self.save_settings(self._get_defaults())

    def get_config_path(self) -> str:
        """Get the path to the config file"""
        return str(self.config_file)
