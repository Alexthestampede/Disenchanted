#!/usr/bin/env python3
"""
Disenchanted Chat Window - PyQt5 GUI for conversational AI interaction

Disenchanted is a KDE Plasma chat interface inspired by Enchanted,
providing autonomous web research and multi-provider AI support.
"""
import sys
import base64
from pathlib import Path
from typing import Optional, List, Dict
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QLabel, QScrollArea, QFrame,
    QMessageBox, QSplitter, QFileDialog
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt5.QtGui import QFont, QTextCursor, QKeySequence, QPixmap, QIcon

from modulle import create_ai_client
from modulle.base import BaseTextProcessor, BaseVisionProcessor
from modulle.web import WebAccessor
from modulle.web.tools import SearchWebTool, FetchPageTool
from modulle.tools import ToolRegistry
from gui.settings_dialog import SettingsDialog
from config.app_config import AppConfig


class AIWorkerThread(QThread):
    """Background thread for AI processing to keep UI responsive"""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    tool_called = pyqtSignal(str, dict)  # Signal for tool usage (tool_name, args)

    def __init__(self, processor, messages: List[Dict], temperature: Optional[float],
                 image_data: Optional[str] = None, use_vision: bool = False,
                 client=None, model: Optional[str] = None, provider: Optional[str] = None,
                 tool_registry: Optional[ToolRegistry] = None, web_search_enabled: bool = False):
        super().__init__()
        self.processor = processor
        self.messages = messages
        self.temperature = temperature
        self.image_data = image_data
        self.use_vision = use_vision
        self.client = client
        self.model = model
        self.provider = provider
        self.tool_registry = tool_registry
        self.web_search_enabled = web_search_enabled

    def run(self):
        try:
            # Prepare kwargs with optional temperature
            kwargs = {}
            if self.temperature is not None:
                kwargs['temperature'] = self.temperature

            # If we have an image and a vision processor, use analyze_image
            if self.use_vision and self.image_data and hasattr(self.processor, 'analyze_image'):
                # Get the last user message as the prompt
                prompt = self.messages[-1]['content'] if self.messages else "Analyze this image"
                response = self.processor.analyze_image(
                    image_data=self.image_data,
                    prompt=prompt,
                    **kwargs
                )
                if response:
                    self.finished.emit(response)
                else:
                    self.error.emit("AI returned empty response")

            # Web search enabled - use tool calling
            elif self.web_search_enabled and self.client and self.tool_registry and hasattr(self.client, 'chat_with_tools'):
                response_text = self._handle_tool_calling(kwargs)
                if response_text:
                    self.finished.emit(response_text)
                else:
                    self.error.emit("AI returned empty response")

            # Standard chat without tools
            else:
                response = self.processor.chat(
                    messages=self.messages,
                    **kwargs
                )
                if response:
                    self.finished.emit(response)
                else:
                    self.error.emit("AI returned empty response")

        except Exception as e:
            self.error.emit(f"Error: {str(e)}")

    def _handle_tool_calling(self, kwargs):
        """Handle tool calling workflow with web search"""
        MAX_ITERATIONS = 10
        messages = self.messages.copy()

        # Get tool format method based on provider
        tool_format_map = {
            'ollama': 'to_ollama_format',
            'openai': 'to_openai_format',
            'claude': 'to_claude_format',
            'gemini': 'to_gemini_format',
            'lm_studio': 'to_openai_format'
        }
        tool_format = tool_format_map.get(self.provider, 'to_openai_format')
        tools_formatted = getattr(self.tool_registry, tool_format)()

        for iteration in range(MAX_ITERATIONS):
            # Call LLM with tools
            response = self.client.chat_with_tools(
                model=self.model,
                messages=messages,
                tools=tools_formatted,
                **kwargs
            )

            if response['finish_reason'] == 'error':
                raise Exception("Error communicating with LLM")

            # Check if LLM wants to use tools
            if response.get('tool_calls'):
                # Execute each tool call
                for tool_call in response['tool_calls']:
                    tool_name = tool_call['name']
                    tool_args = tool_call['arguments']

                    # Emit signal for UI update
                    self.tool_called.emit(tool_name, tool_args)

                    # Execute the tool
                    try:
                        result = self.tool_registry.execute(tool_name, **tool_args)

                        # Add assistant message with tool call
                        messages.append({
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [{
                                "id": tool_call['id'],
                                "type": "function",
                                "function": {
                                    "name": tool_name,
                                    "arguments": tool_args
                                }
                            }]
                        })

                        # Add tool result message
                        tool_result_msg = {
                            "role": "tool",
                            "content": result,
                            "name": tool_name
                        }

                        # Claude needs tool_use_id
                        if self.provider == 'claude':
                            tool_result_msg['tool_use_id'] = tool_call['id']

                        messages.append(tool_result_msg)

                    except Exception as e:
                        # Add error message
                        messages.append({
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [{
                                "id": tool_call['id'],
                                "type": "function",
                                "function": {
                                    "name": tool_name,
                                    "arguments": tool_args
                                }
                            }]
                        })
                        messages.append({
                            "role": "tool",
                            "content": f"Error: {str(e)}",
                            "name": tool_name
                        })
            else:
                # LLM provided final answer
                return response.get('content', '')

        # Max iterations reached
        return response.get('content', '') or "Research incomplete (max iterations reached)"


class ChatBubble(QFrame):
    """Individual chat message bubble"""
    def __init__(self, text: str, is_user: bool, image_path: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        # Label for role
        role_label = QLabel("You" if is_user else "AI")
        role_font = QFont()
        role_font.setBold(True)
        role_font.setPointSize(9)
        role_label.setFont(role_font)

        layout.addWidget(role_label)

        # If there's an image, display it
        if image_path:
            image_label = QLabel()
            pixmap = QPixmap(image_path)
            # Scale image to fit (max width 300px, maintain aspect ratio)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                image_label.setPixmap(scaled_pixmap)
                layout.addWidget(image_label)

        # Message text
        message_label = QLabel(text)
        message_label.setWordWrap(True)
        message_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        layout.addWidget(message_label)

        # Style the bubble
        if is_user:
            self.setStyleSheet("""
                ChatBubble {
                    background-color: #3daee9;
                    color: white;
                    border-radius: 10px;
                    margin: 5px 50px 5px 5px;
                }
            """)
        else:
            self.setStyleSheet("""
                ChatBubble {
                    background-color: #31363b;
                    color: #eff0f1;
                    border-radius: 10px;
                    margin: 5px 5px 5px 50px;
                }
            """)


class DisenchantedChatWindow(QMainWindow):
    """Main chat window for Disenchanted"""

    def __init__(self, initial_text: Optional[str] = None, initial_prompt: Optional[str] = None,
                 initial_screenshot: Optional[str] = None):
        super().__init__()

        self.config = AppConfig()
        self.conversation_history: List[Dict[str, str]] = []
        self.ai_processor: Optional[BaseTextProcessor] = None
        self.vision_processor: Optional[BaseVisionProcessor] = None
        self.ai_client = None
        self.current_model: Optional[str] = None
        self.current_provider: Optional[str] = None
        self.worker_thread: Optional[AIWorkerThread] = None
        self.attached_image_path: Optional[str] = None
        self.attached_image_base64: Optional[str] = None

        # Web search components
        self.web_accessor: Optional[WebAccessor] = None
        self.tool_registry: Optional[ToolRegistry] = None
        self.web_search_enabled = False

        self.init_ui()
        self.init_web_components()
        self.init_ai()

        # If initial text provided, add it to the conversation
        if initial_text and initial_prompt:
            self.start_conversation(initial_prompt, initial_text)
        elif initial_screenshot:
            self.start_screenshot_conversation(initial_screenshot)

    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Disenchanted")
        self.setGeometry(100, 100, 800, 600)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)

        # Top bar with status and settings
        top_bar = QHBoxLayout()

        self.status_label = QLabel("Initializing...")
        self.status_label.setStyleSheet("color: #888; font-style: italic;")
        top_bar.addWidget(self.status_label)

        top_bar.addStretch()

        # Web search toggle button
        self.web_search_btn = QPushButton("🌐 Web Search: OFF")
        self.web_search_btn.setCheckable(True)
        self.web_search_btn.setToolTip("Enable web search for AI research")
        self.web_search_btn.clicked.connect(self.toggle_web_search)
        top_bar.addWidget(self.web_search_btn)

        settings_btn = QPushButton("⚙ Settings")
        settings_btn.clicked.connect(self.open_settings)
        top_bar.addWidget(settings_btn)

        clear_btn = QPushButton("🗑 Clear")
        clear_btn.clicked.connect(self.clear_conversation)
        top_bar.addWidget(clear_btn)

        main_layout.addLayout(top_bar)

        # Chat display area (scrollable)
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.addStretch()

        self.chat_scroll.setWidget(self.chat_container)
        main_layout.addWidget(self.chat_scroll, stretch=1)

        # Input area
        input_layout = QHBoxLayout()

        # Image preview label (hidden by default)
        self.image_preview = QLabel()
        self.image_preview.setVisible(False)
        self.image_preview.setMaximumHeight(60)
        main_layout.addWidget(self.image_preview)

        # Buttons row
        self.attach_image_button = QPushButton("📎 Image")
        self.attach_image_button.setToolTip("Attach an image for vision analysis")
        self.attach_image_button.clicked.connect(self.attach_image)
        input_layout.addWidget(self.attach_image_button)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type your message...")
        self.input_field.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.input_field, stretch=1)

        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_message)
        input_layout.addWidget(self.send_button)

        main_layout.addLayout(input_layout)

        # Apply dark theme styling
        self.setStyleSheet("""
            QMainWindow {
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
        """)

    def init_web_components(self):
        """Initialize web search components"""
        try:
            self.web_accessor = WebAccessor()
            self.tool_registry = ToolRegistry()
            self.tool_registry.register(SearchWebTool(self.web_accessor))
            self.tool_registry.register(FetchPageTool(self.web_accessor))
        except Exception as e:
            print(f"Warning: Failed to initialize web components: {e}")
            self.web_accessor = None
            self.tool_registry = None

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
                self.attach_image_button.setEnabled(True)
                self.attach_image_button.setToolTip("Attach an image for vision analysis")
            else:
                self.attach_image_button.setEnabled(False)
                self.attach_image_button.setToolTip("Vision model not configured. Set one in Settings.")

            self.status_label.setText(f"Connected: {provider} ({text_model})")
            self.status_label.setStyleSheet("color: #27ae60;")
        except Exception as e:
            self.status_label.setText(f"Error: {str(e)}")
            self.status_label.setStyleSheet("color: #da4453;")
            QMessageBox.warning(self, "AI Initialization Error",
                              f"Failed to initialize AI:\n{str(e)}\n\nPlease check settings.")

    def start_conversation(self, prompt: str, text: str):
        """Start conversation with initial context"""
        # Add system prompt if configured
        settings = self.config.load_settings()
        system_prompt = settings.get('system_prompt', '').strip()
        if system_prompt:
            self.conversation_history.append({
                "role": "system",
                "content": system_prompt
            })

        initial_message = f"{prompt}:\n\n{text}"
        self.add_message(initial_message, is_user=True)
        self.conversation_history.append({
            "role": "user",
            "content": initial_message
        })
        self.process_ai_response()

    def start_screenshot_conversation(self, screenshot_path: str):
        """Start conversation by analyzing a screenshot"""
        if not self.vision_processor:
            QMessageBox.warning(self, "Vision Not Available",
                              "No vision model configured.\n\n"
                              "Go to Settings and configure a vision model to use screenshot analysis.")
            return

        # Verify screenshot file exists
        if not Path(screenshot_path).is_file():
            QMessageBox.warning(self, "Screenshot Not Found",
                              f"Screenshot file not found:\n{screenshot_path}")
            return

        # Add system prompt if configured
        settings = self.config.load_settings()
        system_prompt = settings.get('system_prompt', '').strip()
        if system_prompt:
            self.conversation_history.append({
                "role": "system",
                "content": system_prompt
            })

        # Read and base64-encode the screenshot
        try:
            with open(screenshot_path, 'rb') as f:
                image_bytes = f.read()
                self.attached_image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                self.attached_image_path = screenshot_path
        except Exception as e:
            QMessageBox.critical(self, "Screenshot Load Error",
                               f"Failed to load screenshot:\n{str(e)}")
            return

        # Get the screenshot prompt from settings
        prompt = settings.get('screenshot_prompt', 'Analyze this screenshot').strip()
        if not prompt:
            prompt = 'Analyze this screenshot'

        # Add message to chat with screenshot thumbnail
        self.add_message(prompt, is_user=True, image_path=screenshot_path)
        self.conversation_history.append({
            "role": "user",
            "content": prompt
        })

        # Send to AI vision processor
        self.process_ai_response()

    def add_message(self, text: str, is_user: bool, image_path: Optional[str] = None):
        """Add a message bubble to the chat"""
        bubble = ChatBubble(text, is_user, image_path)
        # Insert before the stretch
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)

        # Scroll to bottom
        QTimer.singleShot(100, self.scroll_to_bottom)

    def scroll_to_bottom(self):
        """Scroll chat to the bottom"""
        scrollbar = self.chat_scroll.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def attach_image(self):
        """Attach an image for vision analysis"""
        if not self.vision_processor:
            QMessageBox.warning(self, "Vision Not Available",
                              "No vision model configured.\n\n"
                              "Go to Settings and configure a vision model.")
            return

        # Open file dialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image",
            "",
            "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp);;All Files (*)"
        )

        if not file_path:
            return  # User cancelled

        try:
            # Read and encode image to base64
            with open(file_path, 'rb') as f:
                image_bytes = f.read()
                self.attached_image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                self.attached_image_path = file_path

            # Show preview
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.image_preview.setPixmap(scaled_pixmap)
                self.image_preview.setVisible(True)

            # Update UI
            self.attach_image_button.setText("🖼️ Image attached")
            self.attach_image_button.setStyleSheet("background-color: #27ae60;")
            self.input_field.setPlaceholderText("Describe what you want to know about the image...")

        except Exception as e:
            QMessageBox.critical(self, "Image Load Error",
                               f"Failed to load image:\n{str(e)}")

    def clear_attached_image(self):
        """Clear the attached image"""
        self.attached_image_path = None
        self.attached_image_base64 = None
        self.image_preview.setVisible(False)
        self.attach_image_button.setText("📎 Image")
        self.attach_image_button.setStyleSheet("")
        self.input_field.setPlaceholderText("Type your message...")

    def toggle_web_search(self):
        """Toggle web search functionality"""
        self.web_search_enabled = self.web_search_btn.isChecked()

        if self.web_search_enabled:
            self.web_search_btn.setText("🌐 Web Search: ON")
            self.web_search_btn.setStyleSheet("background-color: #27ae60;")

            # Update system prompt to inform AI about tools
            if not self.conversation_history or self.conversation_history[0].get('role') != 'system':
                tool_system_prompt = (
                    "You are an AI assistant with access to web search and page fetching tools. "
                    "When the user asks a question that requires current information or external knowledge, "
                    "use the search_web tool to find relevant information, then use fetch_page to read articles. "
                    "Synthesize information from multiple sources and provide comprehensive answers with citations."
                )
                self.conversation_history.insert(0, {
                    "role": "system",
                    "content": tool_system_prompt
                })
        else:
            self.web_search_btn.setText("🌐 Web Search: OFF")
            self.web_search_btn.setStyleSheet("")

            # Remove tool system prompt if it exists
            if self.conversation_history and self.conversation_history[0].get('role') == 'system':
                if 'web search' in self.conversation_history[0].get('content', '').lower():
                    self.conversation_history.pop(0)

    def send_message(self):
        """Send user message"""
        message = self.input_field.text().strip()
        if not message and not self.attached_image_path:
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

        # Default message if only image is sent
        if not message and self.attached_image_path:
            message = "What's in this image?"

        # Clear input
        self.input_field.clear()

        # If this is the first message, add system prompt
        if not self.conversation_history:
            settings = self.config.load_settings()
            system_prompt = settings.get('system_prompt', '').strip()
            if system_prompt:
                self.conversation_history.append({
                    "role": "system",
                    "content": system_prompt
                })

        # Add to chat with image if present
        self.add_message(message, is_user=True, image_path=self.attached_image_path)

        # Add to conversation history
        self.conversation_history.append({
            "role": "user",
            "content": message
        })

        # Process AI response
        self.process_ai_response()

    def process_ai_response(self):
        """Process AI response in background thread"""
        if self.worker_thread and self.worker_thread.isRunning():
            return  # Already processing

        self.send_button.setEnabled(False)
        self.input_field.setEnabled(False)
        self.attach_image_button.setEnabled(False)
        self.web_search_btn.setEnabled(False)
        self.status_label.setText("AI is thinking...")
        self.status_label.setStyleSheet("color: #f67400;")

        # Get temperature from settings (None = use server default)
        settings = self.config.load_settings()
        temperature = settings.get('temperature')  # Will be None if not set

        # Determine which processor to use
        use_vision = bool(self.attached_image_path and self.vision_processor)
        processor = self.vision_processor if use_vision else self.ai_processor

        # Create worker thread
        self.worker_thread = AIWorkerThread(
            processor,
            self.conversation_history.copy(),
            temperature,
            image_data=self.attached_image_base64,
            use_vision=use_vision,
            client=self.ai_client,
            model=self.current_model,
            provider=self.current_provider,
            tool_registry=self.tool_registry,
            web_search_enabled=self.web_search_enabled
        )
        self.worker_thread.finished.connect(self.on_ai_response)
        self.worker_thread.error.connect(self.on_ai_error)
        self.worker_thread.tool_called.connect(self.on_tool_called)
        self.worker_thread.start()

    def on_tool_called(self, tool_name: str, tool_args: dict):
        """Handle tool call notification"""
        # Display tool usage in chat
        if tool_name == 'search_web':
            query = tool_args.get('query', 'N/A')
            tool_msg = f"🔍 Searching web for: {query}"
        elif tool_name == 'fetch_page':
            url = tool_args.get('url', 'N/A')
            # Truncate long URLs
            display_url = url if len(url) < 60 else url[:57] + "..."
            tool_msg = f"📄 Fetching page: {display_url}"
        else:
            tool_msg = f"🔧 Using tool: {tool_name}"

        self.add_message(tool_msg, is_user=False)
        self.status_label.setText(f"Using tool: {tool_name}...")

    def on_ai_response(self, response: str):
        """Handle AI response"""
        self.add_message(response, is_user=False)
        self.conversation_history.append({
            "role": "assistant",
            "content": response
        })

        # Clear attached image after successful response
        self.clear_attached_image()

        self.send_button.setEnabled(True)
        self.input_field.setEnabled(True)
        self.attach_image_button.setEnabled(bool(self.vision_processor))

        # Re-enable web search button if tool calling is supported
        if hasattr(self.ai_client, 'chat_with_tools') and self.tool_registry:
            self.web_search_btn.setEnabled(True)

        self.input_field.setFocus()

        settings = self.config.load_settings()
        provider = settings.get('provider', 'ollama')
        model = settings.get('text_model', 'unknown')
        self.status_label.setText(f"Ready: {provider} ({model})")
        self.status_label.setStyleSheet("color: #27ae60;")

    def on_ai_error(self, error: str):
        """Handle AI error"""
        self.add_message(f"⚠ {error}", is_user=False)

        # Clear attached image on error
        self.clear_attached_image()

        self.send_button.setEnabled(True)
        self.input_field.setEnabled(True)
        self.attach_image_button.setEnabled(bool(self.vision_processor))

        # Re-enable web search button if tool calling is supported
        if hasattr(self.ai_client, 'chat_with_tools') and self.tool_registry:
            self.web_search_btn.setEnabled(True)

        self.input_field.setFocus()

        self.status_label.setText(f"Error occurred")
        self.status_label.setStyleSheet("color: #da4453;")

    def clear_conversation(self):
        """Clear the conversation history"""
        reply = QMessageBox.question(self, "Clear Conversation",
                                    "Are you sure you want to clear the conversation?",
                                    QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            # Remove all chat bubbles except the stretch
            while self.chat_layout.count() > 1:
                item = self.chat_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            self.conversation_history.clear()
            # Clear any attached image
            self.clear_attached_image()

    def open_settings(self):
        """Open settings dialog"""
        dialog = SettingsDialog(self.config, self)
        if dialog.exec_():
            # Settings were saved, reinitialize AI
            self.init_ai()
            self.clear_conversation()


def main(initial_text: Optional[str] = None, initial_prompt: Optional[str] = None):
    """Main entry point"""
    import os

    app = QApplication(sys.argv)
    app.setApplicationName("Disenchanted")

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
