#!/usr/bin/env python3
"""
Disenchanted chat bubbles: message widgets with timestamps.
"""
from datetime import datetime
from typing import Optional

from PyQt5.QtWidgets import QFrame, QVBoxLayout, QLabel, QHBoxLayout
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPixmap


class ChatBubble(QFrame):
    """Individual chat message bubble"""

    def __init__(self, text: str, is_user: bool,
                 image_path: Optional[str] = None,
                 timestamp: Optional[float] = None,
                 show_timestamp: bool = True,
                 parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        # Header row: role + timestamp
        header = QHBoxLayout()
        role_label = QLabel("You" if is_user else "AI")
        role_font = QFont()
        role_font.setBold(True)
        role_font.setPointSize(9)
        role_label.setFont(role_font)
        header.addWidget(role_label)

        if show_timestamp and timestamp:
            ts_label = QLabel(datetime.fromtimestamp(timestamp).strftime('%H:%M'))
            ts_label.setStyleSheet("color: rgba(127,140,141,0.9); font-size: 8pt;")
            header.addStretch()
            header.addWidget(ts_label)
        layout.addLayout(header)

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