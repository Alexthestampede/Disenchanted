#!/usr/bin/env python3
"""
Disenchanted Settings Dialog - Configure AI provider and parameters
"""
from typing import Dict, Optional, List
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QComboBox,
    QLineEdit, QDoubleSpinBox, QPushButton, QLabel, QMessageBox,
    QGroupBox, QTabWidget, QWidget, QProgressBar, QTextEdit
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

from modulle import create_ai_client


class ModelFetcherThread(QThread):
    """Background thread for fetching available models"""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, provider: str, base_url: Optional[str] = None, api_key: Optional[str] = None):
        super().__init__()
        self.provider = provider
        self.base_url = base_url
        self.api_key = api_key

    def run(self):
        try:
            # Create client to fetch models
            client, _, _ = create_ai_client(
                provider=self.provider,
                base_url=self.base_url,
                api_key=self.api_key,
                text_model='placeholder'  # Dummy model for client creation
            )

            models = client.list_models()
            if models:
                self.finished.emit(models)
            else:
                self.error.emit("No models found on server")
        except Exception as e:
            self.error.emit(str(e))


class SettingsDialog(QDialog):
    """Settings dialog for configuring Disenchanted"""

    PROVIDERS = {
        'ollama': 'Ollama (Local)',
        'lm_studio': 'LM Studio (Local)',
        'openai': 'OpenAI (Cloud)',
        'gemini': 'Google Gemini (Cloud)',
        'claude': 'Anthropic Claude (Cloud)'
    }

    # Cloud provider models (predefined lists since they don't have a list API)
    CLOUD_MODELS = {
        'openai': [
            'gpt-4o',
            'gpt-4o-mini',
            'gpt-4-turbo',
            'gpt-4',
            'gpt-3.5-turbo',
            'o1-preview',
            'o1-mini'
        ],
        'gemini': [
            'gemini-1.5-pro',
            'gemini-1.5-flash',
            'gemini-1.5-flash-8b',
            'gemini-1.0-pro'
        ],
        'claude': [
            'claude-3-5-sonnet-20241022',
            'claude-3-5-haiku-20241022',
            'claude-3-opus-20240229',
            'claude-3-sonnet-20240229',
            'claude-3-haiku-20240307'
        ]
    }

    DEFAULT_MODELS = {
        'ollama': 'llama2',
        'lm_studio': 'local-model',
        'openai': 'gpt-4o-mini',
        'gemini': 'gemini-1.5-flash',
        'claude': 'claude-3-5-haiku-20241022'
    }

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.current_settings = self.config.load_settings()
        self.model_fetcher: Optional[ModelFetcherThread] = None

        self.setWindowTitle("Disenchanted Settings")
        self.setModal(True)
        self.setMinimumWidth(600)

        self.init_ui()
        self.load_current_settings()

    def init_ui(self):
        """Initialize the settings UI"""
        layout = QVBoxLayout(self)

        # Tab widget for organization
        tabs = QTabWidget()

        # Provider tab
        provider_tab = QWidget()
        provider_layout = QVBoxLayout(provider_tab)

        # Provider selection
        provider_group = QGroupBox("AI Provider")
        provider_form = QFormLayout()

        self.provider_combo = QComboBox()
        for key, name in self.PROVIDERS.items():
            self.provider_combo.addItem(name, key)
        self.provider_combo.currentIndexChanged.connect(self.on_provider_changed)
        provider_form.addRow("Provider:", self.provider_combo)

        provider_group.setLayout(provider_form)
        provider_layout.addWidget(provider_group)

        # Model configuration
        model_group = QGroupBox("Model Configuration")
        model_layout = QVBoxLayout()

        # Model fetch controls
        model_controls = QHBoxLayout()

        self.model_status_label = QLabel("Select a provider and click Refresh")
        self.model_status_label.setStyleSheet("color: #888; font-size: 9pt; font-style: italic;")
        model_controls.addWidget(self.model_status_label)

        model_controls.addStretch()

        self.refresh_models_btn = QPushButton("🔄 Refresh Models")
        self.refresh_models_btn.clicked.connect(self.fetch_models)
        model_controls.addWidget(self.refresh_models_btn)

        model_layout.addLayout(model_controls)

        # Model selection form
        model_form = QFormLayout()

        self.text_model_combo = QComboBox()
        self.text_model_combo.setEditable(True)
        self.text_model_combo.setPlaceholderText("Select or type model name...")
        model_form.addRow("Text Model:", self.text_model_combo)

        self.vision_model_combo = QComboBox()
        self.vision_model_combo.setEditable(True)
        self.vision_model_combo.setPlaceholderText("Select or type model name...")
        model_form.addRow("Vision Model:", self.vision_model_combo)

        model_layout.addLayout(model_form)
        model_group.setLayout(model_layout)
        provider_layout.addWidget(model_group)

        # Connection settings
        connection_group = QGroupBox("Connection Settings")
        connection_form = QFormLayout()

        self.base_url_input = QLineEdit()
        self.base_url_input.setPlaceholderText("http://localhost:11434")
        self.base_url_label = QLabel("Base URL:")
        connection_form.addRow(self.base_url_label, self.base_url_input)

        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setPlaceholderText("Enter API key...")
        self.api_key_label = QLabel("API Key:")
        connection_form.addRow(self.api_key_label, self.api_key_input)

        connection_group.setLayout(connection_form)
        provider_layout.addWidget(connection_group)

        # Test connection button
        test_btn = QPushButton("🔌 Test Connection")
        test_btn.clicked.connect(self.test_connection)
        provider_layout.addWidget(test_btn)

        provider_layout.addStretch()
        tabs.addTab(provider_tab, "Provider")

        # Parameters tab
        params_tab = QWidget()
        params_layout = QVBoxLayout(params_tab)

        params_group = QGroupBox("Generation Parameters")
        params_form = QFormLayout()

        # Temperature
        temp_layout = QHBoxLayout()
        self.temperature_input = QLineEdit()
        self.temperature_input.setPlaceholderText("Empty = server default (recommended)")
        temp_layout.addWidget(self.temperature_input)
        params_form.addRow("Temperature:", temp_layout)

        temp_help = QLabel("Range: 0.0-2.0 (lower = focused, higher = creative). Leave empty to use server default.")
        temp_help.setStyleSheet("color: #888; font-size: 9pt; font-style: italic;")
        temp_help.setWordWrap(True)
        params_form.addRow("", temp_help)

        # Max tokens
        self.max_tokens_input = QLineEdit()
        self.max_tokens_input.setPlaceholderText("Leave empty for server default")
        params_form.addRow("Max Tokens:", self.max_tokens_input)

        params_group.setLayout(params_form)
        params_layout.addWidget(params_group)

        # System prompt group
        system_group = QGroupBox("System Prompt")
        system_layout = QVBoxLayout()

        system_help = QLabel("Define the AI's behavior and personality. Leave empty for default behavior.")
        system_help.setStyleSheet("color: #888; font-size: 9pt; font-style: italic;")
        system_help.setWordWrap(True)
        system_layout.addWidget(system_help)

        self.system_prompt_input = QTextEdit()
        self.system_prompt_input.setPlaceholderText(
            "Example: You are a helpful assistant that provides accurate, factual information. "
            "You admit when you don't know something rather than guessing."
        )
        self.system_prompt_input.setMaximumHeight(100)
        system_layout.addWidget(self.system_prompt_input)

        system_group.setLayout(system_layout)
        params_layout.addWidget(system_group)

        # Screenshot settings group
        screenshot_group = QGroupBox("Screenshot Settings")
        screenshot_layout = QVBoxLayout()

        screenshot_help = QLabel(
            "Prompt sent automatically when using the screenshot shortcut. "
            "Write detailed instructions for analyzing screenshots (e.g., radar screens, game HUDs)."
        )
        screenshot_help.setStyleSheet("color: #888; font-size: 9pt; font-style: italic;")
        screenshot_help.setWordWrap(True)
        screenshot_layout.addWidget(screenshot_help)

        self.screenshot_prompt_input = QTextEdit()
        self.screenshot_prompt_input.setPlaceholderText(
            "Example: Analyze this velocity radar screen and describe any notable weather patterns, "
            "rotation signatures, or severe weather indicators you can identify."
        )
        self.screenshot_prompt_input.setMaximumHeight(100)
        screenshot_layout.addWidget(self.screenshot_prompt_input)

        screenshot_group.setLayout(screenshot_layout)
        params_layout.addWidget(screenshot_group)

        params_layout.addStretch()
        tabs.addTab(params_tab, "Parameters")

        layout.addWidget(tabs)

        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_settings)
        save_btn.setDefault(True)
        button_layout.addWidget(save_btn)

        layout.addLayout(button_layout)

        # Apply styling
        self.setStyleSheet("""
            QDialog {
                background-color: #232629;
            }
            QGroupBox {
                color: #eff0f1;
                border: 1px solid #4d4d4d;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QLabel {
                color: #eff0f1;
            }
            QLineEdit, QComboBox, QDoubleSpinBox {
                background-color: #31363b;
                color: #eff0f1;
                border: 1px solid #4d4d4d;
                border-radius: 3px;
                padding: 5px;
            }
            QPushButton {
                background-color: #3daee9;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
            }
            QPushButton:hover {
                background-color: #4db8f0;
            }
            QTabWidget::pane {
                border: 1px solid #4d4d4d;
                background-color: #232629;
            }
            QTabBar::tab {
                background-color: #31363b;
                color: #eff0f1;
                padding: 8px 15px;
                border: 1px solid #4d4d4d;
            }
            QTabBar::tab:selected {
                background-color: #3daee9;
            }
        """)

    def load_current_settings(self):
        """Load current settings into the form"""
        provider = self.current_settings.get('provider', 'ollama')

        # Set provider
        index = self.provider_combo.findData(provider)
        if index >= 0:
            self.provider_combo.setCurrentIndex(index)

        # Set connection settings first
        self.base_url_input.setText(
            self.current_settings.get('base_url', '')
        )
        self.api_key_input.setText(
            self.current_settings.get('api_key', '')
        )

        # Set parameters
        # Handle temperature - don't convert None to string "None"
        temperature = self.current_settings.get('temperature')
        self.temperature_input.setText(str(temperature) if temperature is not None else '')

        # Handle max_tokens properly - don't convert None to string "None"
        max_tokens = self.current_settings.get('max_tokens')
        self.max_tokens_input.setText(str(max_tokens) if max_tokens is not None else '')

        # Set system prompt
        system_prompt = self.current_settings.get('system_prompt', '')
        self.system_prompt_input.setPlainText(system_prompt)

        # Set screenshot prompt
        screenshot_prompt = self.current_settings.get('screenshot_prompt', 'Analyze this screenshot')
        self.screenshot_prompt_input.setPlainText(screenshot_prompt)

        # Update UI based on provider
        self.on_provider_changed()

        # Set models (as editable text - will be in combo if models are fetched)
        text_model = self.current_settings.get('text_model', '')
        vision_model = self.current_settings.get('vision_model', '')

        if text_model:
            self.text_model_combo.setCurrentText(text_model)
        if vision_model:
            self.vision_model_combo.setCurrentText(vision_model)

    def on_provider_changed(self):
        """Handle provider selection change"""
        provider = self.provider_combo.currentData()
        is_local = provider in ['ollama', 'lm_studio']

        # Show/hide relevant fields
        self.base_url_label.setVisible(is_local)
        self.base_url_input.setVisible(is_local)
        self.api_key_label.setVisible(not is_local)
        self.api_key_input.setVisible(not is_local)

        # Clear model combos
        self.text_model_combo.clear()
        self.vision_model_combo.clear()

        # For cloud providers, populate with known models
        if provider in self.CLOUD_MODELS:
            models = self.CLOUD_MODELS[provider]
            self.text_model_combo.addItems(models)
            self.vision_model_combo.addItems(models)

            # Set default
            default_model = self.DEFAULT_MODELS.get(provider, '')
            if default_model:
                self.text_model_combo.setCurrentText(default_model)

            self.model_status_label.setText(f"✓ {len(models)} models available")
            self.model_status_label.setStyleSheet("color: #27ae60; font-size: 9pt;")
        else:
            # For local providers, show prompt to refresh
            self.model_status_label.setText("Click 'Refresh Models' to fetch from server")
            self.model_status_label.setStyleSheet("color: #f67400; font-size: 9pt;")

    def fetch_models(self):
        """Fetch available models from the selected provider"""
        provider = self.provider_combo.currentData()

        # For cloud providers, models are already populated
        if provider in self.CLOUD_MODELS:
            QMessageBox.information(self, "Models Available",
                                  f"Models for {provider} are already listed in the dropdown.")
            return

        # For local providers, fetch from server
        base_url = self.base_url_input.text().strip() or None

        if not base_url:
            QMessageBox.warning(self, "Missing URL",
                              "Please enter the base URL for the server first.")
            return

        # Disable button and show progress
        self.refresh_models_btn.setEnabled(False)
        self.model_status_label.setText("Fetching models from server...")
        self.model_status_label.setStyleSheet("color: #f67400; font-size: 9pt;")

        # Start background thread
        self.model_fetcher = ModelFetcherThread(provider, base_url)
        self.model_fetcher.finished.connect(self.on_models_fetched)
        self.model_fetcher.error.connect(self.on_models_fetch_error)
        self.model_fetcher.start()

    def on_models_fetched(self, models: List[str]):
        """Handle successfully fetched models"""
        # Re-enable button
        self.refresh_models_btn.setEnabled(True)

        # Clear and populate combos
        current_text = self.text_model_combo.currentText()
        current_vision = self.vision_model_combo.currentText()

        self.text_model_combo.clear()
        self.vision_model_combo.clear()

        self.text_model_combo.addItems(models)
        self.vision_model_combo.addItems(models)

        # Restore previous selection if it exists in the list
        if current_text in models:
            self.text_model_combo.setCurrentText(current_text)
        if current_vision in models:
            self.vision_model_combo.setCurrentText(current_vision)

        self.model_status_label.setText(f"✓ Found {len(models)} models")
        self.model_status_label.setStyleSheet("color: #27ae60; font-size: 9pt;")

    def on_models_fetch_error(self, error: str):
        """Handle error fetching models"""
        self.refresh_models_btn.setEnabled(True)
        self.model_status_label.setText(f"✗ Error: {error}")
        self.model_status_label.setStyleSheet("color: #da4453; font-size: 9pt;")

        QMessageBox.warning(self, "Failed to Fetch Models",
                          f"Could not fetch models from server:\n{error}\n\n"
                          f"You can still type a model name manually.")

    def test_connection(self):
        """Test connection to AI provider"""
        try:
            provider = self.provider_combo.currentData()
            text_model = self.text_model_combo.currentText().strip()
            api_key = self.api_key_input.text().strip() or None
            base_url = self.base_url_input.text().strip() or None

            if not text_model:
                QMessageBox.warning(self, "Missing Model",
                                  "Please specify a text model.")
                return

            # Try to create client
            client, processor, _ = create_ai_client(
                provider=provider,
                text_model=text_model,
                api_key=api_key,
                base_url=base_url
            )

            # Test with health check
            if hasattr(client, 'health_check'):
                if client.health_check():
                    # Also try to list models as a bonus
                    models = client.list_models()
                    if models:
                        QMessageBox.information(self, "Connection Successful",
                                              f"✓ Successfully connected to {provider}!\n\n"
                                              f"Found {len(models)} available models.")
                    else:
                        QMessageBox.information(self, "Connection Successful",
                                              f"✓ Successfully connected to {provider}!")
                else:
                    QMessageBox.warning(self, "Connection Failed",
                                      f"Could not connect to {provider}.\n"
                                      f"Please check your settings.")
            else:
                QMessageBox.information(self, "Client Created",
                                      f"Client created for {provider}.\n"
                                      f"(Health check not available for this provider)")

        except Exception as e:
            QMessageBox.critical(self, "Connection Error",
                               f"Error connecting to AI:\n{str(e)}")

    def save_settings(self):
        """Save settings to config file"""
        try:
            provider = self.provider_combo.currentData()
            text_model = self.text_model_combo.currentText().strip()

            if not text_model:
                QMessageBox.warning(self, "Missing Model",
                                  "Please specify a text model.")
                return

            # Parse temperature safely
            temperature_text = self.temperature_input.text().strip()
            temperature = None
            if temperature_text and temperature_text.lower() != 'none':
                try:
                    temperature = float(temperature_text)
                    if temperature < 0.0 or temperature > 2.0:
                        QMessageBox.warning(self, "Invalid Temperature",
                                          f"Temperature must be between 0.0 and 2.0. Got: {temperature}")
                        return
                except ValueError:
                    QMessageBox.warning(self, "Invalid Temperature",
                                      f"Temperature must be a number or empty. Got: '{temperature_text}'")
                    return

            # Parse max_tokens safely
            max_tokens_text = self.max_tokens_input.text().strip()
            max_tokens = None
            if max_tokens_text and max_tokens_text.lower() != 'none':
                try:
                    max_tokens = int(max_tokens_text)
                except ValueError:
                    QMessageBox.warning(self, "Invalid Max Tokens",
                                      f"Max tokens must be a number or empty. Got: '{max_tokens_text}'")
                    return

            settings = {
                'provider': provider,
                'text_model': text_model,
                'vision_model': self.vision_model_combo.currentText().strip() or None,
                'base_url': self.base_url_input.text().strip() or None,
                'api_key': self.api_key_input.text().strip() or None,
                'temperature': temperature,
                'max_tokens': max_tokens,
                'system_prompt': self.system_prompt_input.toPlainText().strip(),
                'screenshot_prompt': self.screenshot_prompt_input.toPlainText().strip() or 'Analyze this screenshot'
            }

            self.config.save_settings(settings)
            QMessageBox.information(self, "Settings Saved",
                                  "Settings have been saved successfully!")
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Save Error",
                               f"Error saving settings:\n{str(e)}")
