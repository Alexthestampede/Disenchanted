#!/usr/bin/env python3
"""
Disenchanted Chat Window - PyQt5 GUI for conversational AI interaction

Disenchanted is a KDE Plasma chat interface inspired by Enchanted,
providing autonomous web research and multi-provider AI support.

This module is the window shell; supporting logic lives in:
- gui/bubbles.py    (message widgets)
- gui/workers.py    (background threads)
- gui/session.py    (conversation persistence)
- gui/settings_dialog.py (settings UI)
- config/app_config.py   (settings storage)
"""
import os
import sys
import base64
from pathlib import Path
from typing import Optional, List, Dict

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QScrollArea, QFrame,
    QMessageBox, QFileDialog, QListWidget, QListWidgetItem,
    QSplitter, QMenu, QAction
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont

from modulle import create_ai_client
from modulle.base import BaseTextProcessor, BaseVisionProcessor
from modulle.web import WebAccessor
from modulle.web.tools import SearchWebTool, FetchPageTool
from modulle.web.searxng_tools import SearchSearxngTool
from modulle.web.searxng import SearxngSearcher
from modulle.tools import ToolRegistry
from modulle.context import (
    ContextCompressor, estimate_messages_tokens,
    inject_time, DEFAULT_COMPRESSION_PROMPT,
)
from modulle.files import FileIngestor, IngestStrategy
from modulle.memory import HRRMemoryStore

from gui.settings_dialog import SettingsDialog
from gui.version import VERSION, APP_NAME
from gui.bubbles import ChatBubble
from gui.workers import AIWorkerThread, SimpleTaskThread
from gui.session import (
    ConversationSession, list_sessions, load_session, sessions_dir,
)
from gui.system_prompts import SystemPromptStore
from gui.update_checker import UpdateChecker
from config.app_config import AppConfig


class DisenchantedChatWindow(QMainWindow):
    """Main chat window for Disenchanted"""

    def __init__(self, initial_text: Optional[str] = None, initial_prompt: Optional[str] = None,
                 initial_screenshot: Optional[str] = None):
        super().__init__()

        self.config = AppConfig()
        self.session = ConversationSession()
        self.ai_processor: Optional[BaseTextProcessor] = None
        self.vision_processor: Optional[BaseVisionProcessor] = None
        self.ai_client = None
        self.current_model: Optional[str] = None
        self.current_provider: Optional[str] = None
        self.worker_thread: Optional[AIWorkerThread] = None
        self.task_thread: Optional[SimpleTaskThread] = None
        self.attached_image_path: Optional[str] = None
        self.attached_image_base64: Optional[str] = None

        # File attachments (non-image)
        self.ingestor = FileIngestor()
        self.attached_files: List[dict] = []   # [{path, block(ContextFile)}]

        # Web search components
        self.web_accessor: Optional[WebAccessor] = None
        self.tool_registry: Optional[ToolRegistry] = None
        self.tool_registry_searxng: Optional[SearxngSearcher] = None
        self.web_search_enabled = False

        # Context compression
        self.compressor: Optional[ContextCompressor] = None
        self.original_history_before_compression: List[Dict] = []
        self.compress_thread: Optional[SimpleTaskThread] = None

        # HRR memory
        self.memory: Optional[HRRMemoryStore] = None

        # System prompts DB
        self.prompt_store = SystemPromptStore()

        # Update checker
        self.update_checker = UpdateChecker(self.config, VERSION)

        self.init_ui()
        self.init_web_components()
        self.init_ai()
        self.init_memory()

        # Update check (once/day, silent unless update found)
        self.update_checker.check_soon(self)

        # If initial text provided, add it to the conversation
        if initial_text and initial_prompt:
            self.start_conversation(initial_prompt, initial_text)
        elif initial_screenshot:
            self.start_screenshot_conversation(initial_screenshot)

    # ------------------------------------------------------------------ UI --
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle(f"{APP_NAME} {VERSION}")
        self.setGeometry(100, 100, 1000, 650)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)

        # Top bar with status and settings
        top_bar = QHBoxLayout()

        self.btn_sidebar = QPushButton("☰")
        self.btn_sidebar.setFixedWidth(36)
        self.btn_sidebar.setToolTip("Toggle conversation list")
        self.btn_sidebar.clicked.connect(self.toggle_sidebar)
        top_bar.addWidget(self.btn_sidebar)

        self.status_label = QLabel("Initializing...")
        self.status_label.setStyleSheet("color: #888; font-style: italic;")
        top_bar.addWidget(self.status_label)

        top_bar.addStretch()

        # Context meter
        self.context_label = QLabel("ctx 0%")
        self.context_label.setToolTip("Estimated context usage")
        self.context_label.setStyleSheet("color: #7f8c8d; font-size: 9pt;")
        top_bar.addWidget(self.context_label)

        # Web search toggle button
        self.web_search_btn = QPushButton("🌐 Web: OFF")
        self.web_search_btn.setCheckable(True)
        self.web_search_btn.setToolTip("Enable web search for AI research")
        self.web_search_btn.clicked.connect(self.toggle_web_search)
        top_bar.addWidget(self.web_search_btn)

        # MCP popover button
        self.mcp_btn = QPushButton("🔌 MCP")
        self.mcp_btn.setToolTip("Per-chat MCP server toggles")
        self.mcp_btn.clicked.connect(self.open_mcp_menu)
        top_bar.addWidget(self.mcp_btn)

        settings_btn = QPushButton("⚙ Settings")
        settings_btn.clicked.connect(self.open_settings)
        top_bar.addWidget(settings_btn)

        clear_btn = QPushButton("🗑 Clear")
        clear_btn.clicked.connect(self.clear_conversation)
        top_bar.addWidget(clear_btn)

        main_layout.addLayout(top_bar)

        # Middle: sidebar + chat area in a splitter
        self.splitter = QSplitter(Qt.Horizontal)

        # Sidebar: conversation list
        sidebar_widget = QWidget()
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        self.session_list = QListWidget()
        self.session_list.itemDoubleClicked.connect(self.on_session_clicked)
        self.session_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.session_list.customContextMenuRequested.connect(
            self.on_session_context_menu)
        sidebar_layout.addWidget(self.session_list, stretch=1)
        new_chat_btn = QPushButton("+ New chat")
        new_chat_btn.clicked.connect(self.new_chat)
        sidebar_layout.addWidget(new_chat_btn)
        self.splitter.addWidget(sidebar_widget)

        # Chat display area (scrollable)
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.addStretch()

        self.chat_scroll.setWidget(self.chat_container)
        self.splitter.addWidget(self.chat_scroll)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([220, 780])

        main_layout.addWidget(self.splitter, stretch=1)

        # Attached-files chips row (hidden by default)
        self.files_row = QHBoxLayout()
        self.files_row.setContentsMargins(0, 0, 0, 0)
        main_layout.addLayout(self.files_row)

        # Input area
        input_layout = QHBoxLayout()

        # Image preview label (hidden by default)
        self.image_preview = QLabel()
        self.image_preview.setVisible(False)
        self.image_preview.setMaximumHeight(60)
        main_layout.addWidget(self.image_preview)

        self.attach_button = QPushButton("📎 Attach")
        self.attach_button.setToolTip("Attach image or document (text, code, PDF...)")
        self.attach_button.clicked.connect(self.attach_file)
        input_layout.addWidget(self.attach_button)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type your message...")
        self.input_field.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.input_field, stretch=1)

        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_message)
        input_layout.addWidget(self.send_button)

        main_layout.addLayout(input_layout)

        self.apply_theme()
        self.refresh_sidebar()

    def apply_theme(self):
        self.setStyleSheet("""
            QMainWindow, QDialog {
                background-color: #232629;
            }
            QLineEdit {
                background-color: #31363b;
                color: #eff0f1;
                border: 1px solid #4d4d4d;
                border-radius: 5px;
                padding: 8px;
                font-size: 11pt;
            }
            QPushButton {
                background-color: #3daee9;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #4db8f0;
            }
            QPushButton:pressed {
                background-color: #2c9cd6;
            }
            QScrollArea {
                border: none;
                background-color: #232629;
            }
            QListWidget {
                background-color: #1b1e20;
                color: #eff0f1;
                border: none;
                font-size: 9pt;
            }
            QListWidget::item:selected {
                background-color: #3daee9;
            }
        """)

    # ------------------------------------------------------ sidebar / sessions --
    def toggle_sidebar(self):
        w = self.splitter.sizes()
        if w[0] > 0:
            self._sidebar_width = w[0]
            self.splitter.setSizes([0, w[0] + w[1]])
        else:
            self.splitter.setSizes([getattr(self, '_sidebar_width', 220), w[1] or 780])

    def refresh_sidebar(self):
        self.session_list.clear()
        conv_dir = self.config.get_section('conversations').get('dir')
        for s in list_sessions(conv_dir)[:200]:
            dt = __import__('datetime').datetime.fromtimestamp(s['updated'])
            label = f"{s['title'][:40]}\n{dt.strftime('%m-%d %H:%M')} · {s['count']} msg"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, s['id'])
            self.session_list.addItem(item)

    def on_session_clicked(self, item):
        session_id = item.data(Qt.UserRole)
        if session_id == getattr(self, '_current_session_id', None):
            return
        self._load_session(session_id)

    def on_session_context_menu(self, pos):
        item = self.session_list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        act_open = QAction("Open", self)
        act_export = QAction("Export markdown...", self)
        act_delete = QAction("Delete", self)
        menu.addAction(act_open)
        menu.addAction(act_export)
        menu.addSeparator()
        menu.addAction(act_delete)
        chosen = menu.exec_(self.session_list.mapToGlobal(pos))
        session_id = item.data(Qt.UserRole)
        if chosen == act_open:
            self._load_session(session_id)
        elif chosen == act_export:
            self.export_session(session_id)
        elif chosen == act_delete:
            sess = load_session(session_id)
            if sess:
                sess.delete_file()
                if session_id == getattr(self, '_current_session_id', None):
                    self.new_chat(confirm=False)
                self.refresh_sidebar()

    def _load_session(self, session_id: str):
        conv_dir = self.config.get_section('conversations').get('dir')
        sess = load_session(session_id, conv_dir)
        if not sess:
            return
        self._autosave_current()
        self.session = sess
        self._current_session_id = sess.id
        self._render_session()
        self.refresh_sidebar()

    def _render_session(self):
        # clear chat area
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        show_ts = self.config.get_section('timestamps').get(
            'show_on_bubbles', True)
        for m in self.session.messages:
            if m['role'] in ('user', 'assistant'):
                self.add_bubble(m['content'], m['role'] == 'user',
                                image_path=m.get('image_path'),
                                timestamp=m.get('timestamp'),
                                show_timestamp=show_ts,
                                record=False)
        QTimer.singleShot(50, self.scroll_to_bottom)

    def new_chat(self, confirm=True):
        if confirm and not self.session.is_empty:
            reply = QMessageBox.question(self, "New chat",
                                         "Start a new conversation?",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply != QMessageBox.Yes:
                return
        self._autosave_current()
        self.session = ConversationSession()
        self._current_session_id = None
        # clear chat UI
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.conversation_history = []
        self.clear_attached_image()
        self.clear_attached_files()
        self.input_field.setFocus()

    def export_session(self, session_id: str):
        sess = load_session(session_id)
        if not sess:
            return
        default = f"{sess.title[:40].replace(' ', '_') or 'chat'}.md"
        path, _ = QFileDialog.getSaveFileName(self, "Export conversation",
                                              default, "Markdown (*.md)")
        if path:
            try:
                sess.export_markdown(Path(path))
                self.status_label.setText(f"Exported to {path}")
            except Exception as e:
                QMessageBox.warning(self, "Export failed", str(e))

    # ------------------------------------------------------- system prompt DB --
    def prompt_for_new_conversation(self) -> str:
        """System prompt to seed a new conversation (global or DB-selected)."""
        settings = self.config.load_settings()
        return settings.get('system_prompt', '').strip()

    # ---------------------------------------------------------------- AI init --
    def init_web_components(self):
        """Initialize web search components (DDG + configured SearXNG)"""
        try:
            self.web_accessor = WebAccessor()
            self.tool_registry = ToolRegistry()
            self.tool_registry.register(SearchWebTool(self.web_accessor))
            self.tool_registry.register(FetchPageTool(self.web_accessor))
        except Exception as e:
            print(f"Warning: Failed to initialize web components: {e}")
            self.web_accessor = None
            self.tool_registry = None

        # SearXNG (only when configured; default URL is a dummy)
        try:
            sx = self.config.get_section('searxng')
            url = (sx.get('base_url') or '').strip()
            if sx.get('enabled') and url:
                self.searxng_searcher = SearxngSearcher(
                    base_url=url,
                    categories=sx.get('categories', 'general'),
                    language=sx.get('language', ''),
                    safesearch=sx.get('safesearch', 1),
                )
            else:
                self.searxng_searcher = None
        except Exception as e:
            print(f"Warning: SearXNG init failed: {e}")
            self.searxng_searcher = None

    def init_ai(self):
        """Initialize AI client with current settings"""
        try:
            settings = self.config.load_settings()
            provider = settings.get('provider', 'ollama')
            text_model = settings.get('text_model')
            vision_model = settings.get('vision_model')
            api_key = settings.get('api_key')
            base_url = settings.get('base_url')

            self.ai_client, self.ai_processor, self.vision_processor = create_ai_client(
                provider=provider,
                text_model=text_model,
                vision_model=vision_model,
                api_key=api_key,
                base_url=base_url
            )

            self.current_provider = provider
            self.current_model = text_model

            # Compression setup
            comp = self.config.get_section('compression')
            if comp.get('enabled', True):
                self.compressor = ContextCompressor(
                    processor=self.ai_processor,
                    max_tokens=int(comp.get('context_tokens', 8192) or 8192),
                    threshold_pct=int(comp.get('threshold_pct', 70) or 70),
                    summary_prompt=comp.get('prompt') or DEFAULT_COMPRESSION_PROMPT,
                    keep_recent=int(comp.get('keep_recent', 6) or 6),
                    summarizer=self._compressor_summarizer,
                )
            else:
                self.compressor = None

            # Check if provider supports tool calling
            tool_calling_supported = hasattr(self.ai_client, 'chat_with_tools')
            if tool_calling_supported and self.tool_registry:
                self.web_search_btn.setEnabled(True)
                self.web_search_btn.setToolTip("Enable web search for AI research (uses tool calling)")
            else:
                self.web_search_btn.setEnabled(False)
                if not tool_calling_supported:
                    self.web_search_btn.setToolTip("Web search not available: model doesn't support tool calling")
                else:
                    self.web_search_btn.setToolTip("Web search not available: web components failed to initialize")

            # Update button state based on vision processor availability
            if self.vision_processor:
                self.attach_button.setEnabled(True)
                self.attach_button.setToolTip("Attach image or document")
            else:
                self.attach_button.setEnabled(False)
                self.attach_button.setToolTip("Vision model not configured. Set one in Settings.")

            self.status_label.setText(f"Connected: {provider} ({text_model})")
            self.status_label.setStyleSheet("color: #27ae60;")
            self.update_context_meter()
        except Exception as e:
            self.status_label.setText(f"Error: {str(e)}")
            self.status_label.setStyleSheet("color: #da4453;")
            QMessageBox.warning(self, "AI Initialization Error",
                              f"Failed to initialize AI:\n{str(e)}\n\nPlease check settings.")

    def init_memory(self):
        """Initialize HRR memory store if enabled."""
        hrr = self.config.get_section('hrr')
        if not hrr.get('enabled', False):
            self.memory = None
            return
        try:
            self.memory = HRRMemoryStore(dim=int(hrr.get('dim', 2048) or 2048))
        except Exception as e:
            print(f"Warning: HRR memory init failed: {e}")
            self.memory = None

    # ------------------------------------------------------------- compression --
    @staticmethod
    def _compressor_summarizer(prompt: str) -> str:
        """Fallback summarizer used when no dedicated thread is wired.

        Runs synchronously via the library processor — the GUI calls
        compression asynchronously (see _maybe_compress_async), so this path
        is only used by tests/CLI.
        """
        raise NotImplementedError("sync summarizer not used by the GUI")

    def _maybe_compress(self):
        """If over threshold: summarize old turns with a background task."""
        if not self.compressor or self.session.is_empty:
            return
        llm_msgs = self._llm_messages_with_system()
        if not self.compressor.should_compress(llm_msgs):
            return
        if len(llm_msgs) <= self.compressor.keep_recent + 2:
            return
        if self.compress_thread and self.compress_thread.isRunning():
            return  # already compressing

        _, compressible, _ = self.compressor._split(llm_msgs)
        transcript = "\n".join(
            f"{m['role'].upper()}: {m.get('content', '')}" for m in compressible)
        prompt = f"{self.compressor.summary_prompt}\n\nConversation to compress:\n{transcript}"

        self.status_label.setText("Compressing context...")
        settings = self.config.load_settings()
        compress_model = (self.config.get_section('tasks')
                          .get('compress') or {}).get('model')
        processor, temperature = self.ai_processor, None
        if compress_model:
            # dedicated compression model requested
            self.compress_thread = self._make_task_thread_with_model(
                'compress', prompt, settings, compress_model)
        else:
            self.compress_thread = SimpleTaskThread(
                'compress', processor, prompt, temperature)
        self.compress_thread.finished.connect(self.on_compressed)
        self.compress_thread.error.connect(self.on_compress_error)
        self.compress_thread.start()

    def _make_task_thread_with_model(self, task: str, prompt: str,
                                     settings: dict, model: str) -> SimpleTaskThread:
        """Build a SimpleTaskThread using a (possibly other-provider) model."""
        from modulle.tasks import ModelRole
        role_cfg = (self.config.get_section('tasks').get(task) or {})
        provider = role_cfg.get('provider') or settings.get('provider')
        api_key = role_cfg.get('api_key') or settings.get('api_key')
        base_url = role_cfg.get('base_url') or settings.get('base_url')
        try:
            _, processor, _ = create_ai_client(
                provider=provider, text_model=model,
                api_key=api_key, base_url=base_url)
            return SimpleTaskThread(task, processor, prompt)
        except Exception:
            return SimpleTaskThread(task, self.ai_processor, prompt)

    def on_compressed(self, task: str, summary: str):
        """Apply compression result to session history."""
        if task != 'compress' or not summary:
            return
        keep = self.compressor.keep_recent
        msgs = self.session.messages
        # messages to keep: system entries at head + last `keep` messages
        head = []
        idx = 0
        while idx < len(msgs) and msgs[idx]['role'] == 'system':
            head.append(msgs[idx]); idx += 1
        tail = msgs[-keep:]
        compressible_count = len(msgs) - len(head) - len(tail)
        if compressible_count <= 0:
            return
        summary_msg = self.session.add_message(
            'assistant',
            f"{self.compressor.trigger_mark}\n{summary.strip()}",
            extra={'kind': 'compression'})
        self.session.messages = head + [summary_msg] + tail
        self._autosave_current()
        self.update_context_meter()
        self.status_label.setText("Context compressed")
        self.status_label.setStyleSheet("color: #27ae60;")

    def on_compress_error(self, task: str, error: str):
        print(f"Compression failed: {error}")
        self._set_ready_status()

    def _llm_messages_with_system(self):
        """Session messages as LLM list, with time-injection."""
        settings = self.config.load_settings()
        msgs = []
        # system prompt (from session if present, else global)
        sys_prompt = ''
        for m in self.session.messages:
            if m['role'] == 'system' and m.get('kind') != 'compression':
                sys_prompt = m['content']
                break
        if not sys_prompt:
            sys_prompt = settings.get('system_prompt', '')
        if settings.get('timestamps', {}).get('inject_into_prompt', True):
            if sys_prompt:
                msgs = inject_time([{'role': 'system', 'content': sys_prompt}])
            else:
                msgs = inject_time([])
        else:
            if sys_prompt:
                msgs.append({'role': 'system', 'content': sys_prompt})
        msgs.extend(self.session.llm_messages())
        # HRR memory note
        if self.memory and self.session.messages:
            try:
                last_user = next((m['content'] for m in reversed(self.session.messages)
                                  if m['role'] == 'user'), None)
                if last_user:
                    note = self.memory.as_context_note(last_user)
                    if note:
                        msgs.append({'role': 'system', 'content': note})
            except Exception:
                pass
        return msgs

    # ---------------------------------------------------------- context meter --
    def update_context_meter(self):
        if not self.compressor:
            self.context_label.setText("ctx off")
            return
        pct = self.compressor.usage_pct(self._llm_messages_with_system())
        self.context_label.setText(f"ctx {pct:.0f}%")
        if pct >= 90:
            color = '#da4453'
        elif pct >= self.compressor.threshold_pct:
            color = '#f67400'
        else:
            color = '#7f8c8d'
        self.context_label.setStyleSheet(f"color: {color}; font-size: 9pt;")
        tip = (f"~{estimate_messages_tokens(self._llm_messages_with_system())} / "
               f"{self.compressor.max_tokens} tokens "
               f"({pct:.0f}% of window)")
        self.context_label.setToolTip(tip)

    # ------------------------------------------------------------- attachments --
    def attach_file(self):
        """Attach an image or document for the next message"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Attach file", "",
            "All files (*);;Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp);;"
            "Documents (*.md *.txt *.pdf *.py *.html *.json *.csv *.log)"
        )
        if not file_path:
            return

        ext = Path(file_path).suffix.lower()
        if ext in ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'):
            if not self.vision_processor:
                QMessageBox.warning(self, "Vision Not Available",
                                  "No vision model configured.\n\n"
                                  "Go to Settings and configure a vision model.")
                return
            try:
                with open(file_path, 'rb') as f:
                    self.attached_image_base64 = base64.b64encode(f.read()).decode('utf-8')
                    self.attached_image_path = file_path
                pixmap = _pixmap_for(file_path)
                if pixmap:
                    scaled = pixmap.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.image_preview.setPixmap(scaled)
                    self.image_preview.setVisible(True)
                self.attach_button.setText("🖼️ Image attached")
                self.attach_button.setStyleSheet("background-color: #27ae60;")
                self.input_field.setPlaceholderText("Describe what you want to know about the image...")
            except Exception as e:
                QMessageBox.critical(self, "Image Load Error", str(e))
            return

        # Non-image file: ingest now, attach block to next message
        att = self.config.get_section('attachments')
        strategy = IngestStrategy(att.get('strategy', 'inject'))
        cf = self.ingestor.ingest(
            file_path, strategy=strategy,
            max_chars=int(att.get('max_chars_inline', 60000) or 60000))
        if cf.error and Path(file_path).exists() and not cf.size_bytes:
            QMessageBox.warning(self, "Attach failed", cf.error)
            return
        self.attached_files.append({'path': file_path, 'block': cf})
        self._add_file_chip(cf)
        self.attach_button.setText(f"📎 {len(self.attached_files)} attached")
        self.attach_button.setStyleSheet("background-color: #27ae60;")

    def _add_file_chip(self, cf):
        chip = QFrame()
        chip.setStyleSheet("QFrame { background-color: #31363b; border-radius: 4px; }")
        chip_layout = QHBoxLayout(chip)
        chip_layout.setContentsMargins(6, 2, 6, 2)
        label = QLabel(f"📄 {cf.name} ({cf.size_bytes:,}B"
                       f"{', ' + cf.strategy.value if cf.strategy != IngestStrategy.INJECT else ''})")
        label.setStyleSheet("font-size: 9pt;")
        chip_layout.addWidget(label)
        remove_btn = QPushButton("✕")
        remove_btn.setFixedSize(18, 18)
        remove_btn.setStyleSheet("padding: 0; font-size: 8pt;")
        def _rm():
            self.attached_files = [a for a in self.attached_files
                                   if a['block'] is not cf]
            self.files_row.removeWidget(chip)
            chip.deleteLater()
            if not self.attached_files and not self.attached_image_path:
                self.attach_button.setText("📎 Attach")
                self.attach_button.setStyleSheet("")
        remove_btn.clicked.connect(_rm)
        chip_layout.addWidget(remove_btn)
        self.files_row.addWidget(chip)
        self.files_row.addStretch()

    def clear_attached_files(self):
        self.attached_files = []
        while self.files_row.count():
            item = self.files_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def clear_attached_image(self):
        self.attached_image_path = None
        self.attached_image_base64 = None
        self.image_preview.setVisible(False)
        self.attach_button.setText("📎 Attach")
        self.attach_button.setStyleSheet("")
        self.input_field.setPlaceholderText("Type your message...")

    # ---------------------------------------------------------------- sending --
    def start_conversation(self, prompt: str, text: str):
        """Start conversation with initial context"""
        self._maybe_seed_system_prompt()
        initial_message = f"{prompt}:\n\n{text}"
        self.session.add_message('user', initial_message)
        self.add_bubble(initial_message, is_user=True)
        self.process_ai_response()

    def start_screenshot_conversation(self, screenshot_path: str):
        """Start conversation by analyzing a screenshot"""
        if not self.vision_processor:
            QMessageBox.warning(self, "Vision Not Available",
                              "No vision model configured.\n\n"
                              "Go to Settings and configure a vision model to use screenshot analysis.")
            return

        if not Path(screenshot_path).is_file():
            QMessageBox.warning(self, "Screenshot Not Found",
                              f"Screenshot file not found:\n{screenshot_path}")
            return

        self._maybe_seed_system_prompt()

        # Read and base64-encode the screenshot
        try:
            with open(screenshot_path, 'rb') as f:
                image_bytes = f.read()
                self.attached_image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                self.attached_image_path = screenshot_path
        except Exception as e:
            QMessageBox.critical(self, "Screenshot Load Error", str(e))
            return

        settings = self.config.load_settings()
        prompt = settings.get('screenshot_prompt') or 'Analyze this screenshot'

        self.session.add_message('user', prompt, extra={'image_path': screenshot_path})
        self.add_bubble(prompt, is_user=True, image_path=screenshot_path)
        self.process_ai_response()

    def _maybe_seed_system_prompt(self):
        """Add the active system prompt to a fresh conversation."""
        if not self.session.is_empty:
            return
        settings = self.config.load_settings()
        sys_prompt = settings.get('system_prompt', '').strip()
        if sys_prompt:
            self.session.add_message('system', sys_prompt, extra={'kind': 'system'})

    def send_message(self):
        """Send user message"""
        message = self.input_field.text().strip()
        if not message and not self.attached_image_path and not self.attached_files:
            return

        if not self.ai_processor:
            QMessageBox.warning(self, "Not Connected",
                              "AI is not connected. Please check settings.")
            return

        # Check if vision is needed but not available
        if self.attached_image_path and not self.vision_processor:
            QMessageBox.warning(self, "Vision Not Available",
                              "You attached an image but no vision model is configured.\n\n"
                              "Go to Settings and configure a vision model.")
            return

        # Default message if only image/files are sent
        if not message and self.attached_image_path:
            message = "What's in this image?"
        elif not message and self.attached_files:
            message = "Summarize the attached file(s)."

        self.input_field.clear()

        self._maybe_seed_system_prompt()

        # Build the user-visible content (with file blocks for the LLM)
        show_ts = self.config.get_section('timestamps').get('show_on_bubbles', True)
        llm_content = message
        if self.attached_files:
            blocks = "\n\n".join(a['block'].to_context_string()
                                 for a in self.attached_files)
            llm_content = f"{message}\n\n{blocks}"

        now_ts = __import__('time').time()
        self.session.add_message('user', llm_content,
                                 extra={'display': message,
                                        'files': [a['path'] for a in self.attached_files]})
        self.add_bubble(message, is_user=True,
                        image_path=self.attached_image_path,
                        timestamp=now_ts, show_timestamp=show_ts)

        self.process_ai_response()

    def process_ai_response(self):
        """Process AI response in background thread"""
        if self.worker_thread and self.worker_thread.isRunning():
            return  # Already processing

        self.send_button.setEnabled(False)
        self.input_field.setEnabled(False)
        self.attach_button.setEnabled(False)
        self.web_search_btn.setEnabled(False)
        self.status_label.setText("AI is thinking...")
        self.status_label.setStyleSheet("color: #f67400;")

        settings = self.config.load_settings()
        temperature = settings.get('temperature')

        # Determine which processor to use
        use_vision = bool(self.attached_image_path and self.vision_processor)
        processor = self.vision_processor if use_vision else self.ai_processor

        # Check for local /image command (dtline) — handled inline, no LLM call
        if self._try_inline_image_generation():
            self._set_ready_status()
            return

        # Tool registry: web DDG + optional searxng
        registry = None
        if self.tool_registry:
            registry = self.tool_registry
            if self.searxng_searcher:
                try:
                    registry.register(SearchSearxngTool(self.searxng_searcher))
                except Exception:
                    pass

        self.worker_thread = AIWorkerThread(
            processor,
            self._llm_messages_with_system(),
            temperature,
            image_data=self.attached_image_base64,
            use_vision=use_vision,
            client=self.ai_client,
            model=self.current_model,
            provider=self.current_provider,
            tool_registry=registry,
            web_search_enabled=self.web_search_enabled
        )
        self.worker_thread.finished.connect(self.on_ai_response)
        self.worker_thread.error.connect(self.on_ai_error)
        self.worker_thread.tool_called.connect(self.on_tool_called)
        self.worker_thread.start()

    def _try_inline_image_generation(self) -> bool:
        """Handle '/image <prompt>' with dtline; True if handled."""
        message = self.input_field.text().strip()
        if not message.lower().startswith('/image '):
            return False
        prompt = message[len('/image '):].strip()
        self.input_field.clear()
        try:
            from gui.dtline_runner import run_dtline, DtlineError
            settings = self.config.load_settings()
            result = run_dtline(prompt, self.config.get_section('dtline'))
            shown = (result.get('images') or [{}])[0].get('path', '')
            content = f"🖼 Generated: `{shown}`\n\n*{prompt}*"
            self.session.add_message('assistant', content,
                                     extra={'kind': 'image', 'image_path': shown})
            self.add_bubble(content, is_user=False, image_path=shown)
            self._autosave_current()
        except Exception as e:
            self.add_bubble(f"⚠ Image generation failed: {e}", is_user=False)
        return True

    def on_tool_called(self, tool_name: str, tool_args: dict):
        """Handle tool call notification"""
        if tool_name in ('search_web', 'search_web_searxng'):
            query = tool_args.get('query', 'N/A')
            tool_msg = f"🔍 Searching web for: {query}"
        elif tool_name == 'fetch_page':
            url = tool_args.get('url', 'N/A')
            # Truncate long URLs
            display_url = url if len(url) < 60 else url[:57] + "..."
            tool_msg = f"📄 Fetching page: {display_url}"
        elif tool_name.startswith('mcp_'):
            tool_msg = f"🔌 MCP tool: {tool_name[4:]}"
        else:
            tool_msg = f"🔧 Using tool: {tool_name}"

        self.add_bubble(tool_msg, is_user=False)
        self.status_label.setText(f"Using tool: {tool_name}...")

    def on_ai_response(self, response: str):
        """Handle AI response"""
        now_ts = __import__('time').time()
        show_ts = self.config.get_section('timestamps').get('show_on_bubbles', True)
        self.session.add_message('assistant', response)
        self.add_bubble(response, is_user=False, timestamp=now_ts,
                        show_timestamp=show_ts)

        # Clear attached files/image after successful response
        self.clear_attached_image()
        self.clear_attached_files()

        self._autosave_current()
        self.update_context_meter()

        # HRR memory write
        if self.memory and self.config.get_section('hrr').get('auto_write', True):
            try:
                last_user = next((m['content'] for m in reversed(self.session.messages)
                                  if m['role'] == 'user'), None)
                if last_user:
                    self.memory.store(_memory_note(last_user, response))
                    self.memory.save()
            except Exception:
                pass

        # Compression check + async title generation on first exchange
        self._maybe_compress()
        self._maybe_generate_title()

        self._set_ready_status()
        self.input_field.setFocus()

    def on_ai_error(self, error: str):
        """Handle AI error"""
        show_ts = self.config.get_section('timestamps').get('show_on_bubbles', True)
        self.add_bubble(f"⚠ {error}", is_user=False,
                        timestamp=None if not show_ts else __import__('time').time(),
                        show_timestamp=show_ts)
        self.clear_attached_image()
        self._set_ready_status()
        self.input_field.setFocus()

    def _set_ready_status(self):
        self.send_button.setEnabled(True)
        self.input_field.setEnabled(True)
        self.attach_button.setEnabled(bool(self.vision_processor) or True)
        if hasattr(self.ai_client, 'chat_with_tools') and self.tool_registry:
            self.web_search_btn.setEnabled(True)
        settings = self.config.load_settings()
        model = settings.get('text_model', 'unknown')
        self.status_label.setText(f"Ready: {settings.get('provider', 'ollama')} ({model})")
        self.status_label.setStyleSheet("color: #27ae60;")

    def _maybe_generate_title(self):
        """Generate a session title on the first exchange (async)."""
        if getattr(self.session, 'title_generated', False):
            return
        if len([m for m in self.session.messages
                if m['role'] in ('user', 'assistant')]) < 2:
            return
        self.session.title_generated = True  # set optimistically; fallback below
        snippet = self.session.last_exchange_text()
        settings = self.config.load_settings()
        title_model = (self.config.get_section('tasks').get('title') or {}).get('model')
        prompt = ("Generate a short (3-6 word) title for this conversation. "
                  "Reply with only the title text, no quotes.\n\n" + snippet)
        if title_model:
            self.task_thread = self._make_task_thread_with_model(
                'title', prompt, settings, title_model)
        else:
            self.task_thread = SimpleTaskThread('title', self.ai_processor, prompt)
        self.task_thread.finished.connect(self.on_title_generated)
        self.task_thread.start()

    def on_title_generated(self, task: str, title: str):
        if task != 'title':
            return
        title = ' '.join(title.strip().split())
        if not title:
            return
        if len(title) > 60:
            title = title[:57] + '…'
        self.session.title = title
        self.setWindowTitle(f"{APP_NAME} {VERSION} — {title}")
        self._autosave_current()
        self.refresh_sidebar()

    # ------------------------------------------------------------- utilities --
    def add_bubble(self, text: str, is_user: bool,
                   image_path: Optional[str] = None,
                   timestamp: Optional[float] = None,
                   show_timestamp: bool = True,
                   record: bool = False):
        """Add a message bubble to the chat"""
        bubble = ChatBubble(text, is_user, image_path=image_path,
                            timestamp=timestamp, show_timestamp=show_timestamp)
        # Insert before the stretch
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)
        QTimer.singleShot(100, self.scroll_to_bottom)

    def scroll_to_bottom(self):
        scrollbar = self.chat_scroll.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _autosave_current(self):
        conv = self.config.get_section('conversations')
        if conv.get('autosave', True) and not self.session.is_empty:
            try:
                conv_dir = conv.get('dir')
                self.session.save(conv_dir)
                self._current_session_id = self.session.id
            except Exception as e:
                print(f"Warning: autosave failed: {e}")

    def toggle_web_search(self):
        """Toggle web search functionality"""
        self.web_search_enabled = self.web_search_btn.isChecked()

        if self.web_search_enabled:
            self.web_search_btn.setText("🌐 Web: ON")
            self.web_search_btn.setStyleSheet("background-color: #27ae60;")
        else:
            self.web_search_btn.setText("🌐 Web: OFF")
            self.web_search_btn.setStyleSheet("")

    def open_mcp_menu(self):
        """Per-chat MCP server toggle menu."""
        menu = QMenu(self)
        servers = self.config.get_section('mcp').get('servers', [])
        enabled = getattr(self, '_mcp_chat_enabled', set())
        if not servers:
            act = QAction("No MCP servers configured (Settings → MCP)", self)
            act.setEnabled(False)
            menu.addAction(act)
        for s in servers:
            name = s.get('name', '?')
            act = QAction(f"{name}", self)
            act.setCheckable(True)
            act.setChecked(name in enabled)
            act.toggled.connect(lambda checked, n=name: self._toggle_mcp_server(n, checked))
            menu.addAction(act)
        menu.exec_(self.mcp_btn.mapToGlobal(self.mcp_btn.rect().bottomLeft()))

    def _toggle_mcp_server(self, name: str, checked: bool):
        enabled = getattr(self, '_mcp_chat_enabled', set())
        if checked:
            enabled.add(name)
        else:
            enabled.discard(name)
        self._mcp_chat_enabled = enabled
        # connect lazily if needed
        if checked and not getattr(self, 'mcp_manager', None):
            try:
                from modulle.tools.mcp_client import MCPClientManager
                self.mcp_manager = MCPClientManager()
            except Exception as e:
                QMessageBox.warning(self, "MCP unavailable",
                                    f"MCP support requires the 'mcp' package:\n{e}")
                return
        try:
            servers = self.config.get_section('mcp').get('servers', [])
            spec = next((s for s in servers if s.get('name') == name), None)
            if checked and spec and self.mcp_manager and \
                    not self.mcp_manager.is_connected(name):
                self.mcp_manager.connect(spec)
            if not checked and self.mcp_manager and self.mcp_manager.is_connected(name):
                self.mcp_manager.disconnect(name)
            # merge tools into live registry
            if self.tool_registry and self.mcp_manager:
                self.mcp_manager.import_registry_into(self.tool_registry)
        except Exception as e:
            QMessageBox.warning(self, "MCP connection failed", str(e))

    def clear_conversation(self):
        """Clear the conversation history"""
        reply = QMessageBox.question(self, "Clear Conversation",
                                    "Are you sure you want to clear the conversation?",
                                    QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.new_chat(confirm=False)

    def open_settings(self):
        """Open settings dialog"""
        dialog = SettingsDialog(self.config, self)
        if dialog.exec_():
            # Settings were saved, reinitialize AI
            self.init_ai()
            self.init_memory()
            self.init_web_components()

    def closeEvent(self, event):
        self._autosave_current()
        try:
            if getattr(self, 'mcp_manager', None):
                self.mcp_manager.close_all()
        except Exception:
            pass
        super().closeEvent(event)


def _pixmap_for(path: str):
    from PyQt5.QtGui import QPixmap
    return QPixmap(path)


def _memory_note(user_text: str, ai_text: str) -> str:
    """Compact memory note from an exchange (for HRR store)."""
    u = ' '.join(user_text.split())[:200]
    a = ' '.join(ai_text.split())[:200]
    return f"User asked: {u} | Assistant answered: {a}"


def main(initial_text: Optional[str] = None, initial_prompt: Optional[str] = None):
    """Main entry point"""
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(VERSION)

    initial_screenshot = None

    # Check for KDE launcher environment variables
    if '--from-kde' in sys.argv:
        initial_text = os.environ.get('DISENCHANTED_INITIAL_TEXT')
        initial_prompt = os.environ.get('DISENCHANTED_INITIAL_PROMPT')

    # Check for screenshot mode
    if '--from-screenshot' in sys.argv:
        initial_screenshot = os.environ.get('DISENCHANTED_INITIAL_SCREENSHOT')

    window = DisenchantedChatWindow(initial_text, initial_prompt, initial_screenshot)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()