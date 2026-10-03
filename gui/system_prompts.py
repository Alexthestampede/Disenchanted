#!/usr/bin/env python3
"""
Disenchanted system prompt database: user-editable named prompts.

Stored at ~/.disenchanted/system_prompts.json as:
[{"name": ..., "text": ..., "created": ..., "updated": ...}]
Selecting one at conversation start copies its text into settings'
system_prompt (which is what gets seeded into a new chat).
"""
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional


def prompts_file() -> Path:
    return Path.home() / '.disenchanted' / 'system_prompts.json'


class SystemPromptStore:
    """CRUD for named system prompts."""

    def __init__(self, path: Optional[str] = None):
        self.path = Path(path) if path else prompts_file()
        self.prompts: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        if not self.path.exists():
            self.prompts = []
            return
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            self.prompts = data.get('prompts', []) if isinstance(data, dict) else data
        except Exception:
            self.prompts = []

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({'prompts': self.prompts}, ensure_ascii=False, indent=1),
            encoding='utf-8')

    def list(self) -> List[Dict[str, Any]]:
        return sorted(self.prompts, key=lambda p: p.get('name', '').lower())

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        for p in self.prompts:
            if p.get('name') == name:
                return p
        return None

    def upsert(self, name: str, text: str) -> bool:
        """Create or update a prompt by name."""
        name = name.strip()
        text = text.rstrip()
        if not name:
            return False
        for p in self.prompts:
            if p.get('name') == name:
                p['text'] = text
                p['updated'] = time.time()
                self.save()
                return True
        self.prompts.append({
            'name': name, 'text': text,
            'created': time.time(), 'updated': time.time(),
        })
        self.save()
        return True

    def delete(self, name: str) -> bool:
        before = len(self.prompts)
        self.prompts = [p for p in self.prompts if p.get('name') != name]
        if len(self.prompts) < before:
            self.save()
            return True
        return False

    def names(self) -> List[str]:
        return [p['name'] for p in self.list()]