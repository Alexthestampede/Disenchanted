#!/usr/bin/env python3
"""
Disenchanted Settings Dialog - Configure AI provider and parameters
"""
from typing import Dict, Optional, List
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QComboBox,
    QLineEdit, QDoubleSpinBox, QPushButton, QLabel, QMessageBox,
    QGroupBox, QTabWidget, QWidget, QProgressBar, QTextEdit,
    QCheckBox, QSpinBox, QListWidget, QInputDialog, QApplication
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

from modulle import create_ai_client
from gui.system_prompts import SystemPromptStore


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
        self.prompt_store = SystemPromptStore()

        self.setWindowTitle("Disenchanted Settings")
        self.setModal(True)
        self.setMinimumWidth(640)

        self.init_ui()
        self.load_current_settings()

    def init_ui(self):
        """Initialize the settings UI"""
        layout = QVBoxLayout(self)

        # Tab widget for organization
        self.tabs = QTabWidget()

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
        self.tabs.addTab(provider_tab, "Provider")

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
        self.tabs.addTab(params_tab, "Parameters")

        # ================= Tasks tab: per-task model routing =================
        tasks_tab = QWidget()
        tasks_layout = QVBoxLayout(tasks_tab)

        tasks_help = QLabel(
            "Assign a different model per task. Empty = use the main model. "
            "Model names follow the selected provider's naming (refresh on the "
            "Provider tab to see the list).")
        tasks_help.setWordWrap(True)
        tasks_help.setStyleSheet("color: #888; font-size: 9pt; font-style: italic;")
        tasks_layout.addWidget(tasks_help)

        tasks_group = QGroupBox("Task Models")
        tasks_form = QFormLayout()
        self.task_model_inputs = {}
        for role, label in (('title', 'Session Titles:'),
                            ('compress', 'Context Compression:'),
                            ('vision', 'Vision Fallback:')):
            inp = QComboBox()
            inp.setEditable(True)
            inp.setPlaceholderText("(use main model)")
            self.task_model_inputs[role] = inp
            tasks_form.addRow(label, inp)
        tasks_group.setLayout(tasks_form)
        tasks_layout.addWidget(tasks_group)

        # context window size for the main model (used by compression)
        ctx_group = QGroupBox("Main Model Context Window")
        ctx_form = QFormLayout()
        self.context_tokens_input = QLineEdit()
        self.context_tokens_input.setPlaceholderText("e.g. 8192, 32768, 131072")
        ctx_form.addRow("Context tokens:", self.context_tokens_input)
        ctx_group.setLayout(ctx_form)
        tasks_layout.addWidget(ctx_group)
        tasks_layout.addStretch()
        self.tabs.addTab(tasks_tab, "Tasks")

        # ================= Compression tab =================
        comp_tab = QWidget()
        comp_layout = QVBoxLayout(comp_tab)

        comp_group = QGroupBox("Context Compression")
        comp_form = QFormLayout()

        self.compression_enable = QCheckBox("Enable automatic compression")
        comp_form.addRow(self.compression_enable)

        self.threshold_spin = QSpinBox()
        self.threshold_spin.setRange(10, 95)
        self.threshold_spin.setSuffix("%")
        self.threshold_spin.setToolTip("Compress when estimated usage crosses this % of the context window")
        comp_form.addRow("Trigger at:", self.threshold_spin)

        self.keep_recent_spin = QSpinBox()
        self.keep_recent_spin.setRange(2, 50)
        comp_form.addRow("Keep recent messages:", self.keep_recent_spin)

        comp_group.setLayout(comp_form)
        comp_layout.addWidget(comp_group)

        prompt_group = QGroupBox("Compression Prompt")
        prompt_layout = QVBoxLayout()
        prompt_help = QLabel("Sent to the compression model to summarize older turns. "
                             "Reset restores the built-in default.")
        prompt_help.setWordWrap(True)
        prompt_help.setStyleSheet("color: #888; font-size: 9pt; font-style: italic;")
        prompt_layout.addWidget(prompt_help)

        self.compression_prompt_input = QTextEdit()
        self.compression_prompt_input.setMaximumHeight(120)
        prompt_layout.addWidget(self.compression_prompt_input)

        reset_prompt_btn = QPushButton("↺ Reset to default prompt")
        reset_prompt_btn.clicked.connect(self.reset_compression_prompt)
        prompt_layout.addWidget(reset_prompt_btn)
        prompt_group.setLayout(prompt_layout)
        comp_layout.addWidget(prompt_group)
        comp_layout.addStretch()
        self.tabs.addTab(comp_tab, "Compression")

        # ================= Search tab: SearXNG =================
        search_tab = QWidget()
        search_layout = QVBoxLayout(search_tab)

        sx_group = QGroupBox("SearXNG (self-hosted metasearch)")
        sx_form = QFormLayout()

        self.searxng_enable = QCheckBox("Enable SearXNG search tool")
        sx_form.addRow(self.searxng_enable)

        self.searxng_url_input = QLineEdit()
        self.searxng_url_input.setPlaceholderText("http://localhost:8888")
        sx_form.addRow("Instance URL:", self.searxng_url_input)

        self.searxng_categories_input = QLineEdit()
        self.searxng_categories_input.setPlaceholderText("general, news, it, science, images...")
        sx_form.addRow("Categories:", self.searxng_categories_input)

        self.searxng_language_input = QLineEdit()
        self.searxng_language_input.setPlaceholderText("e.g. en, it (empty = automatic)")
        sx_form.addRow("Language:", self.searxng_language_input)

        self.searxng_safesearch = QComboBox()
        self.searxng_safesearch.addItems(['0 (off)', '1 (moderate)', '2 (strict)'])
        sx_form.addRow("Safesearch:", self.searxng_safesearch)

        self.searxng_max_results = QSpinBox()
        self.searxng_max_results.setRange(1, 15)
        sx_form.addRow("Max results:", self.searxng_max_results)

        sx_group.setLayout(sx_form)
        search_layout.addWidget(sx_group)

        test_sx_btn = QPushButton("🔌 Test SearXNG")
        test_sx_btn.clicked.connect(self.test_searxng)
        search_layout.addWidget(test_sx_btn)

        sx_note = QLabel("The instance must allow JSON output: set 'formats: [html, json]' "
                         "in its settings.yml. Default URL is a dummy — set your own.")
        sx_note.setWordWrap(True)
        sx_note.setStyleSheet("color: #888; font-size: 9pt; font-style: italic;")
        search_layout.addWidget(sx_note)
        search_layout.addStretch()
        self.tabs.addTab(search_tab, "Search")

        # ================= MCP tab =================
        mcp_tab = QWidget()
        mcp_layout = QVBoxLayout(mcp_tab)

        self.mcp_enable = QCheckBox("Enable MCP (Model Context Protocol)")
        mcp_layout.addWidget(self.mcp_enable)

        mcp_help = QLabel(
            "Each server's tools become available for tool calling; enable/disable "
            "them per chat from the MCP button in the main window.")
        mcp_help.setWordWrap(True)
        mcp_help.setStyleSheet("color: #888; font-size: 9pt; font-style: italic;")
        mcp_layout.addWidget(mcp_help)

        self.mcp_servers_list = QListWidget()
        self.mcp_servers_list.setMinimumHeight(120)
        mcp_layout.addWidget(self.mcp_servers_list)

        mcp_btn_row = QHBoxLayout()
        mcp_add_btn = QPushButton("+ Add server")
        mcp_add_btn.clicked.connect(self.mcp_add_server)
        mcp_edit_btn = QPushButton("✎ Edit selected")
        mcp_edit_btn.clicked.connect(self.mcp_edit_server)
        mcp_del_btn = QPushButton("🗑 Remove selected")
        mcp_del_btn.clicked.connect(self.mcp_remove_server)
        mcp_btn_row.addWidget(mcp_add_btn)
        mcp_btn_row.addWidget(mcp_edit_btn)
        mcp_btn_row.addWidget(mcp_del_btn)
        mcp_layout.addLayout(mcp_btn_row)
        mcp_layout.addStretch()
        self.tabs.addTab(mcp_tab, "MCP")

        # ================= Attachments tab =================
        att_tab = QWidget()
        att_layout = QVBoxLayout(att_tab)
        att_group = QGroupBox("File attachments")
        att_form = QFormLayout()

        self.attach_strategy = QComboBox()
        self.attach_strategy.addItems(['inject', 'summarize', 'attach'])
        self.attach_strategy.setToolTip(
            "inject: file content inline · summarize: excerpts only · "
            "attach: reference only")
        att_form.addRow("Default strategy:", self.attach_strategy)

        self.attach_max_chars = QLineEdit()
        self.attach_max_chars.setPlaceholderText("60000")
        att_form.addRow("Max chars inline:", self.attach_max_chars)

        att_group.setLayout(att_form)
        att_layout.addWidget(att_group)

        # HRR memory group
        hrr_group = QGroupBox("HRR Memory (Holographic Reduced Representations)")
        hrr_form = QFormLayout()
        self.hrr_enable = QCheckBox("Enable episodic memory")
        self.hrr_enable.setToolTip("Stores exchanges as HRR vectors and injects relevant memories into context")
        hrr_form.addRow(self.hrr_enable)
        self.hrr_dim = QComboBox()
        self.hrr_dim.addItems(['512', '1024', '2048', '4096'])
        hrr_form.addRow("Vector dimension:", self.hrr_dim)
        self.hrr_topk = QSpinBox()
        self.hrr_topk.setRange(1, 10)
        hrr_form.addRow("Memories recalled:", self.hrr_topk)
        hrr_edit_btn = QPushButton("📝 View / edit memory...")
        hrr_edit_btn.clicked.connect(self.open_memory_editor)
        hrr_form.addRow("", hrr_edit_btn)
        hrr_group.setLayout(hrr_form)
        att_layout.addWidget(hrr_group)
        att_layout.addStretch()
        self.tabs.addTab(att_tab, "Attachments & Memory")

        # ================= Image gen (dtline) tab =================
        dt_tab = QWidget()
        dt_layout = QVBoxLayout(dt_tab)
        dt_group = QGroupBox("Inline image generation (dtline → Draw Things)")
        dt_form = QFormLayout()

        self.dt_enable = QCheckBox("Enable /image command")
        dt_form.addRow(self.dt_enable)

        self.dt_model = QComboBox()
        self.dt_model.setEditable(True)
        self.dt_model.setPlaceholderText("(dtline default)")
        dt_form.addRow("Model:", self.dt_model)

        dt_refresh_btn = QPushButton("🔄 List models")
        dt_refresh_btn.clicked.connect(self.dtline_refresh_models)
        dt_form.addRow("", dt_refresh_btn)

        self.dt_preset = QLineEdit()
        self.dt_preset.setPlaceholderText("(dtline default)")
        dt_form.addRow("Preset:", self.dt_preset)

        self.dt_size = QLineEdit()
        self.dt_size.setPlaceholderText("e.g. '1:1 1024x1024' (empty = default)")
        dt_form.addRow("Size (ratio WxH):", self.dt_size)

        self.dt_steps = QLineEdit()
        self.dt_steps.setPlaceholderText("(default)")
        dt_form.addRow("Steps:", self.dt_steps)

        self.dt_output = QLineEdit()
        self.dt_output.setPlaceholderText("(dtline default)")
        dt_form.addRow("Output dir:", self.dt_output)

        dt_group.setLayout(dt_form)
        dt_layout.addWidget(dt_group)
        dt_note = QLabel("Type '/image a red apple' in the chat to generate. "
                         "Requires the Draw Things gRPC server and dtline in PATH.")
        dt_note.setWordWrap(True)
        dt_note.setStyleSheet("color: #888; font-size: 9pt; font-style: italic;")
        dt_layout.addWidget(dt_note)
        dt_layout.addStretch()
        self.tabs.addTab(dt_tab, "Image Gen")

        # ================= System prompts tab =================
        sp_tab = QWidget()
        sp_layout = QVBoxLayout(sp_tab)
        sp_help = QLabel("Your database of system prompts. Pick one per conversation "
                         "from the prompt dropdown in the main window.")
        sp_help.setWordWrap(True)
        sp_help.setStyleSheet("color: #888; font-size: 9pt; font-style: italic;")
        sp_layout.addWidget(sp_help)

        sp_row = QHBoxLayout()
        self.sp_list = QListWidget()
        self.sp_list.setMinimumHeight(160)
        self.sp_list.currentRowChanged.connect(self.sp_selected)
        sp_row.addWidget(self.sp_list, stretch=1)

        sp_editor_col = QVBoxLayout()
        self.sp_name_input = QLineEdit()
        self.sp_name_input.setPlaceholderText("Prompt name")
        sp_editor_col.addWidget(self.sp_name_input)
        self.sp_text_input = QTextEdit()
        self.sp_text_input.setPlaceholderText("System prompt text...")
        sp_editor_col.addWidget(self.sp_text_input, stretch=1)
        sp_row.addLayout(sp_editor_col, stretch=2)
        sp_layout.addLayout(sp_row, stretch=1)

        sp_btn_row = QHBoxLayout()
        sp_new = QPushButton("+ New")
        sp_new.clicked.connect(self.sp_new)
        sp_save = QPushButton("💾 Save prompt")
        sp_save.clicked.connect(self.sp_save)
        sp_del = QPushButton("🗑 Delete")
        sp_del.clicked.connect(self.sp_delete)
        sp_use = QPushButton("→ Use as active prompt")
        sp_use.clicked.connect(self.sp_use)
        sp_btn_row.addWidget(sp_new)
        sp_btn_row.addWidget(sp_save)
        sp_btn_row.addWidget(sp_del)
        sp_btn_row.addWidget(sp_use)
        sp_layout.addLayout(sp_btn_row)
        self.tabs.addTab(sp_tab, "Prompts")

        # ================= Changelog tab =================
        cl_tab = QWidget()
        cl_layout = QVBoxLayout(cl_tab)
        from gui.changelog import CHANGELOG
        self.changelog_view = QTextEdit()
        self.changelog_view.setReadOnly(True)
        self.changelog_view.setPlainText(CHANGELOG)
        cl_layout.addWidget(self.changelog_view)
        self.tabs.addTab(cl_tab, "Changelog")

        layout.addWidget(self.tabs)

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

        # Tasks tab
        tasks = self.current_settings.get('tasks', {})
        for role, inp in self.task_model_inputs.items():
            cfg = tasks.get(role) or {}
            if cfg.get('model'):
                inp.setCurrentText(cfg['model'])
            else:
                inp.setCurrentText('')
        self.context_tokens_input.setText(
            str(self.current_settings.get('compression', {}).get('context_tokens', 8192) or ''))

        # Compression tab
        comp = self.current_settings.get('compression', {})
        self.compression_enable.setChecked(comp.get('enabled', True))
        self.threshold_spin.setValue(int(comp.get('threshold_pct', 70) or 70))
        self.keep_recent_spin.setValue(int(comp.get('keep_recent', 6) or 6))
        self.compression_prompt_input.setPlainText(comp.get('prompt') or '')

        # Search tab
        sx = self.current_settings.get('searxng', {})
        self.searxng_enable.setChecked(sx.get('enabled', False))
        self.searxng_url_input.setText(sx.get('base_url', '') or '')
        self.searxng_categories_input.setText(sx.get('categories', 'general') or '')
        self.searxng_language_input.setText(sx.get('language', '') or '')
        safesearch = int(sx.get('safesearch', 1) or 1)
        self.searxng_safesearch.setCurrentIndex(max(0, min(2, safesearch)))
        self.searxng_max_results.setValue(int(sx.get('max_results', 5) or 5))

        # MCP tab
        mcp = self.current_settings.get('mcp', {})
        self.mcp_enable.setChecked(mcp.get('enabled', False))
        self._mcp_servers = list(mcp.get('servers', []))
        self.refresh_mcp_list()

        # Attachments tab
        att = self.current_settings.get('attachments', {})
        strat_idx = self.attach_strategy.findText(att.get('strategy', 'inject'))
        self.attach_strategy.setCurrentIndex(max(0, strat_idx))
        self.attach_max_chars.setText(str(att.get('max_chars_inline', 60000) or ''))

        # HRR
        hrr = self.current_settings.get('hrr', {})
        self.hrr_enable.setChecked(hrr.get('enabled', False))
        dim = str(hrr.get('dim', 2048) or 2048)
        idx = self.hrr_dim.findText(dim)
        self.hrr_dim.setCurrentIndex(idx if idx >= 0 else 2)
        self.hrr_topk.setValue(int(hrr.get('top_k', 3) or 3))

        # Image gen tab
        dt = self.current_settings.get('dtline', {})
        self.dt_enable.setChecked(dt.get('enabled', True))
        if dt.get('model'):
            self.dt_model.setCurrentText(dt['model'])
        self.dt_preset.setText(dt.get('preset') or '')
        self.dt_size.setText(dt.get('size') or '')
        self.dt_steps.setText(str(dt.get('steps')) if dt.get('steps') else '')
        self.dt_output.setText(dt.get('output_dir') or '')

        # Prompts tab
        self.refresh_sp_list()

        # Update UI based on provider
        self.on_provider_changed()

        # Set models (as editable text - will be in combo if models are fetched)
        text_model = self.current_settings.get('text_model', '')
        vision_model = self.current_settings.get('vision_model', '')

        if text_model:
            self.text_model_combo.setCurrentText(text_model)
        if vision_model:
            self.vision_model_combo.setCurrentText(vision_model)

        # seed placeholder list for the tasks combos from current model list
        if hasattr(self, 'task_model_inputs'):
            pass



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

        # Populate task-model combos too
        for inp in self.task_model_inputs.values():
            current_task = inp.currentText()
            inp.clear()
            inp.addItems(models)
            if current_task:
                inp.setCurrentText(current_task)

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
                'screenshot_prompt': self.screenshot_prompt_input.toPlainText().strip() or 'Analyze this screenshot',
            }

            # Tasks
            tasks = {}
            for role, inp in self.task_model_inputs.items():
                model = inp.currentText().strip()
                tasks[role] = {'model': model} if model else {}
            settings['tasks'] = tasks

            # Compression
            try:
                ctx_tokens = int(self.context_tokens_input.text().strip())
            except ValueError:
                ctx_tokens = 8192
            settings['compression'] = {
                'enabled': self.compression_enable.isChecked(),
                'context_tokens': ctx_tokens,
                'threshold_pct': self.threshold_spin.value(),
                'keep_recent': self.keep_recent_spin.value(),
                'prompt': self.compression_prompt_input.toPlainText().strip() or None,
            }

            # SearXNG
            settings['searxng'] = {
                'enabled': self.searxng_enable.isChecked(),
                'base_url': self.searxng_url_input.text().strip() or 'http://localhost:8888',
                'categories': self.searxng_categories_input.text().strip() or 'general',
                'language': self.searxng_language_input.text().strip(),
                'safesearch': self.searxng_safesearch.currentIndex(),
                'max_results': self.searxng_max_results.value(),
            }

            # MCP
            settings['mcp'] = {
                'enabled': self.mcp_enable.isChecked(),
                'servers': self._mcp_servers,
            }

            # Attachments + HRR
            try:
                max_chars = int(self.attach_max_chars.text().strip() or 60000)
            except ValueError:
                max_chars = 60000
            settings['attachments'] = {
                'max_chars_inline': max_chars,
                'strategy': self.attach_strategy.currentText(),
            }
            settings['hrr'] = {
                'enabled': self.hrr_enable.isChecked(),
                'dim': int(self.hrr_dim.currentText()),
                'top_k': self.hrr_topk.value(),
                'auto_write': True,
            }

            # dtline
            try:
                steps = int(self.dt_steps.text().strip())
            except ValueError:
                steps = None
            settings['dtline'] = {
                'enabled': self.dt_enable.isChecked(),
                'model': self.dt_model.currentText().strip() or None,
                'preset': self.dt_preset.text().strip() or None,
                'size': self.dt_size.text().strip() or None,
                'steps': steps,
                'seed': None,
                'output_dir': self.dt_output.text().strip() or None,
            }

            self.config.save_settings(settings)
            QMessageBox.information(self, "Settings Saved",
                                  "Settings have been saved successfully!")
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Save Error",
                               f"Error saving settings:\n{str(e)}")

    # ============================================================ new tab logic ==
    def reset_compression_prompt(self):
        """Restore the built-in compression prompt (empty = default on save)."""
        from modulle.context import DEFAULT_COMPRESSION_PROMPT
        self.compression_prompt_input.setPlainText(DEFAULT_COMPRESSION_PROMPT)


    # -- SearXNG --------------------------------------------------------------
    def test_searxng(self):
        url = self.searxng_url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Missing URL", "Enter the SearXNG instance URL first.")
            return
        from modulle.web.searxng import SearxngSearcher
        searcher = SearxngSearcher(base_url=url)
        if not searcher.is_available():
            QMessageBox.warning(self, "Unreachable",
                                f"Could not reach {url}")
            return
        try:
            results = searcher.search('disenchanted test', max_results=1)
            if results:
                QMessageBox.information(self, "SearXNG OK",
                                        f"Connected. Sample result:\n{results[0]['title'][:80]}")
            else:
                QMessageBox.warning(self, "No results",
                                    "Reachable, but returned no results. Check that "
                                    "'formats: [html, json]' is set in settings.yml.")
        except ValueError as e:
            QMessageBox.warning(self, "JSON disabled", str(e))
        except Exception as e:
            QMessageBox.warning(self, "Search failed", str(e))

    # -- MCP ---------------------------------------------------------------------
    def refresh_mcp_list(self):
        self.mcp_servers_list.clear()
        for s in self._mcp_servers:
            transport = s.get('transport', 'stdio')
            where = s.get('url') or s.get('command', '')
            self.mcp_servers_list.addItem(f"{s.get('name', '?')} ({transport}) — {where}")

    def mcp_add_server(self):
        name, ok = QInputDialog.getText(self, "MCP server name", "Name:")
        if not ok or not name.strip():
            return
        transport, ok = QInputDialog.getItem(
            self, "Transport", "Type:", ['stdio', 'http'], 0, False)
        if not ok:
            return
        if transport == 'http':
            url, ok = QInputDialog.getText(self, "MCP HTTP URL", "URL:")
            if not ok or not url.strip():
                return
            self._mcp_servers.append({'name': name.strip(), 'transport': 'http',
                                      'url': url.strip()})
        else:
            command, ok = QInputDialog.getText(
                self, "MCP stdio command",
                "Command (with args, e.g. 'npx -y @modelcontextprotocol/server-filesystem /tmp'):")
            if not ok or not command.strip():
                return
            parts = command.strip().split()
            self._mcp_servers.append({'name': name.strip(), 'transport': 'stdio',
                                      'command': parts[0], 'args': parts[1:]})
        self.refresh_mcp_list()

    def mcp_edit_server(self):
        row = self.mcp_servers_list.currentRow()
        if row < 0 or row >= len(self._mcp_servers):
            return
        spec = self._mcp_servers[row]
        name, ok = QInputDialog.getText(self, "Edit name", "Name:", text=spec.get('name', ''))
        if ok and name.strip():
            spec['name'] = name.strip()
        if spec.get('transport') == 'http':
            url, ok = QInputDialog.getText(self, "Edit URL", "URL:", text=spec.get('url', ''))
            if ok and url.strip():
                spec['url'] = url.strip()
        else:
            joined = ' '.join([spec.get('command', '')] + spec.get('args', []))
            command, ok = QInputDialog.getText(self, "Edit command", "Command:", text=joined)
            if ok and command.strip():
                parts = command.strip().split()
                spec['command'] = parts[0]
                spec['args'] = parts[1:]
        self.refresh_mcp_list()

    def mcp_remove_server(self):
        row = self.mcp_servers_list.currentRow()
        if row < 0 or row >= len(self._mcp_servers):
            return
        del self._mcp_servers[row]
        self.refresh_mcp_list()

    # -- dtline ---------------------------------------------------------------
    def dtline_refresh_models(self):
        from gui.dtline_runner import list_models
        models = list_models()
        if not models:
            QMessageBox.information(self, "No models",
                                    "dtline not available or no models listed.\n"
                                    "You can still type a model name manually.")
            return
        current = self.dt_model.currentText()
        self.dt_model.clear()
        self.dt_model.addItems(models)
        if current:
            self.dt_model.setCurrentText(current)

    # -- system prompts DB ------------------------------------------------------
    def refresh_sp_list(self, select_name: Optional[str] = None):
        self.sp_list.clear()
        for p in self.prompt_store.list():
            label = f"{p['name']}  ({len(p.get('text', ''))} chars)"
            self.sp_list.addItem(label)
        if select_name:
            names = self.prompt_store.names()
            if select_name in names:
                self.sp_list.setCurrentRow(names.index(select_name))

    def sp_selected(self, row):
        names = [p['name'] for p in self.prompt_store.list()]
        if 0 <= row < len(names):
            p = self.prompt_store.get(names[row])
            if p:
                self.sp_name_input.setText(p['name'])
                self.sp_text_input.setPlainText(p.get('text', ''))

    def sp_new(self):
        self.sp_name_input.clear()
        self.sp_text_input.clear()
        self.sp_name_input.setFocus()

    def sp_save(self):
        name = self.sp_name_input.text().strip()
        text = self.sp_text_input.toPlainText()
        if not name or not text.strip():
            QMessageBox.warning(self, "Missing data",
                                "A prompt needs both a name and text.")
            return
        self.prompt_store.upsert(name, text)
        self.refresh_sp_list(name)

    def sp_delete(self):
        name = self.sp_name_input.text().strip()
        if name and self.prompt_store.delete(name):
            self.sp_new()
            self.refresh_sp_list()

    def sp_use(self):
        text = self.sp_text_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Empty prompt", "Nothing to set as active prompt.")
            return
        self.system_prompt_input.setPlainText(text)
        self.tabs.setCurrentIndex(0)

    def open_memory_editor(self):
        try:
            from gui.memory_editor import MemoryEditorDialog
            dlg = MemoryEditorDialog(self.config, self)
            dlg.exec_()
        except Exception as e:
            QMessageBox.warning(self, "Memory viewer", str(e))
