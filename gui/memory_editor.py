#!/usr/bin/env python3
"""
Disenchanted HRR memory viewer/editor dialog.

Shows every stored memory entry (text, timestamp, similarity metadata left
out), lets the user edit text, delete entries, or wipe the store.
"""
from typing import Optional

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QTextEdit, QLineEdit, QLabel, QMessageBox, QWidget
)
from PyQt5.QtCore import Qt
from datetime import datetime

from modulle.memory import HRRMemoryStore
from config.app_config import AppConfig


class MemoryEditorDialog(QDialog):
    """View/edit/delete HRR memory entries."""

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        hrr = config.get_section('hrr')
        try:
            self.store = HRRMemoryStore(dim=int(hrr.get('dim', 2048) or 2048))
        except Exception as e:
            self.store = None
            self._err = str(e)

        self.setWindowTitle("HRR Memory")
        self.setModal(True)
        self.setMinimumSize(650, 450)
        self._current_id: Optional[str] = None

        layout = QVBoxLayout(self)

        info = QLabel("Episodic memories injected into conversations when relevant.")
        info.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(info)

        row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search memories (try recall)...")
        self.search_input.textChanged.connect(self.refresh_list)
        row.addWidget(self.search_input, stretch=1)
        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedWidth(30)
        refresh_btn.clicked.connect(self.refresh_list)
        row.addWidget(refresh_btn)
        layout.addLayout(row)

        list_row = QHBoxLayout()
        self.list_widget = QListWidget()
        self.list_widget.currentRowChanged.connect(self.on_select)
        list_row.addWidget(self.list_widget, stretch=1)

        editor_col = QVBoxLayout()
        self.timestamp_label = QLabel('')
        self.timestamp_label.setStyleSheet('color: #7f8c8d; font-size: 9pt;')
        editor_col.addWidget(self.timestamp_label)
        self.text_edit = QTextEdit()
        editor_col.addWidget(self.text_edit, stretch=1)
        save_btn = QPushButton("💾 Save changes")
        save_btn.clicked.connect(self.save_entry)
        editor_col.addWidget(save_btn)
        list_row.addLayout(editor_col, stretch=2)
        layout.addLayout(list_row, stretch=1)

        btn_row = QHBoxLayout()
        delete_btn = QPushButton("🗑 Delete selected")
        delete_btn.clicked.connect(self.delete_entry)
        wipe_btn = QPushButton("Wipe all memory")
        wipe_btn.clicked.connect(self.wipe_all)
        btn_row.addWidget(delete_btn)
        btn_row.addStretch()
        btn_row.addWidget(wipe_btn)
        layout.addLayout(btn_row)

        self.refresh_list()

    def refresh_list(self):
        self.list_widget.clear()
        if self.store is None:
            self.list_widget.addItem(f"Memory unavailable: {getattr(self, '_err', '?')}")
            return
        query = self.search_input.text().strip()
        entries = self.store.list_entries()
        if query:
            hits = self.store.recall(query, top_k=20, min_similarity=0.0)
            hit_ids = [h['id'] for h in hits]
            by_id = {e['id']: e for e in entries}
            entries = [by_id[i] for i in hit_ids if i in by_id]
        for e in entries:
            ts = datetime.fromtimestamp(e['timestamp']).strftime('%Y-%m-%d %H:%M')
            item = QListWidgetItem(f"{ts}  {e['text'][:60]}")
            item.setData(Qt.UserRole, e['id'])
            self.list_widget.addItem(item)

    def on_select(self, row):
        item = self.list_widget.item(row)
        if not item or self.store is None:
            return
        entry_id = item.data(Qt.UserRole)
        for e in self.store.list_entries():
            if e['id'] == entry_id:
                self._current_id = entry_id
                self.timestamp_label.setText(
                    f"Stored {datetime.fromtimestamp(e['timestamp']).strftime('%Y-%m-%d %H:%M:%S')} "
                    f"· topics: {', '.join(e['topics']) or '—'}")
                self.text_edit.setPlainText(e['text'])
                return

    def save_entry(self):
        if self.store is None or not self._current_id:
            return
        new_text = self.text_edit.toPlainText().strip()
        if not new_text:
            QMessageBox.warning(self, "Empty", "Memory text cannot be empty.")
            return
        self.store.edit(self._current_id, new_text=new_text)
        self.store.save()
        self.refresh_list()

    def delete_entry(self):
        if self.store is None or not self._current_id:
            return
        self.store.delete(self._current_id)
        self.store.save()
        self._current_id = None
        self.text_edit.clear()
        self.refresh_list()

    def wipe_all(self):
        if self.store is None:
            return
        reply = QMessageBox.question(
            self, "Wipe memory", "Delete ALL stored memories?",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.store.clear()
            self.store.save()
            self.refresh_list()