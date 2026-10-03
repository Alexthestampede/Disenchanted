#!/usr/bin/env python3
"""
Disenchanted conversation sessions: history model + JSON persistence.

A ConversationSession holds one chat: ordered messages with roles, content
and timestamps. Sessions autosave to ~/.disenchanted/conversations/*.json.
"""

import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any


def sessions_dir(configured: Optional[str] = None) -> Path:
    """Directory where conversation JSON files are stored."""
    if configured:
        d = Path(configured).expanduser()
    else:
        d = Path.home() / '.disenchanted' / 'conversations'
    d.mkdir(parents=True, exist_ok=True)
    return d


class ConversationSession:
    """One chat conversation with timestamped messages and persistence."""

    def __init__(self, session_id: Optional[str] = None,
                 title: str = "New conversation",
                 messages: Optional[List[Dict[str, Any]]] = None,
                 created_at: Optional[float] = None):
        self.id = session_id or uuid.uuid4().hex[:12]
        self.title = title
        self.messages: List[Dict[str, Any]] = messages or []
        self.created_at = created_at or time.time()

    # -- message operations ----------------------------------------------------
    def add_message(self, role: str, content: str,
                    timestamp: Optional[float] = None,
                    extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Append a message; returns it."""
        msg = {
            'role': role,
            'content': content,
            'timestamp': timestamp if timestamp is not None else time.time(),
        }
        if extra:
            msg.update(extra)
        self.messages.append(msg)
        return msg

    def llm_messages(self) -> List[Dict[str, str]]:
        """Message list in the plain role/content form LLMs expect."""
        return [{'role': m['role'], 'content': m['content']}
                for m in self.messages
                if m.get('role') in ('system', 'user', 'assistant')]

    @property
    def is_empty(self) -> bool:
        return not self.messages

    def last_exchange_text(self, max_len: int = 400) -> str:
        """Trailing conversation snippet — used for title generation."""
        parts = []
        for m in self.messages:
            if m['role'] in ('user', 'assistant'):
                parts.append(f"{m['role']}: {m['content'][:200]}")
        text = "\n".join(parts)
        return text[:max_len]

    def first_user_text(self, max_len: int = 60) -> str:
        for m in self.messages:
            if m['role'] == 'user':
                text = ' '.join(m['content'].split())
                return text[:max_len]
        return self.title

    # -- persistence --------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'title': self.title,
            'created_at': self.created_at,
            'messages': self.messages,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationSession":
        return cls(
            session_id=data.get('id'),
            title=data.get('title') or 'New conversation',
            messages=data.get('messages') or [],
            created_at=data.get('created_at'),
        )

    def save(self, directory: Optional[str] = None) -> Path:
        """Write this session to its JSON file; returns the path."""
        d = sessions_dir(directory)
        path = d / f"{self.id}.json"
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=1),
                        encoding='utf-8')
        return path

    @classmethod
    def load(cls, path: Path) -> "ConversationSession":
        return cls.from_dict(json.loads(path.read_text(encoding='utf-8')))

    def delete_file(self, directory: Optional[str] = None):
        d = sessions_dir(directory)
        path = d / f"{self.id}.json"
        if path.exists():
            path.unlink()

    def export_markdown(self, path: Path):
        """Export the conversation as readable markdown."""
        lines = [f"# {self.title}",
                 f"*{datetime.fromtimestamp(self.created_at).strftime('%Y-%m-%d %H:%M')}*",
                 ""]
        for m in self.messages:
            ts = datetime.fromtimestamp(m.get('timestamp', 0)).strftime('%H:%M')
            who = {'user': 'You', 'assistant': 'AI'}.get(m['role'], m['role'])
            lines.append(f"**{who}** ({ts})")
            lines.append('')
            lines.append(m.get('content', ''))
            lines.append('')
        path.write_text("\n".join(lines), encoding='utf-8')


def list_sessions(directory: Optional[str] = None) -> List[Dict[str, Any]]:
    """All saved sessions, most-recently-active first.

    Returns dicts with id/title/updated/size (no full messages).
    """
    d = sessions_dir(directory)
    out = []
    for p in d.glob('*.json'):
        try:
            data = json.loads(p.read_text(encoding='utf-8'))
            out.append({
                'id': data.get('id') or p.stem,
                'title': data.get('title') or 'Untitled',
                'updated': p.stat().st_mtime,
                'file': p,
                'count': len(data.get('messages', [])),
            })
        except Exception:
            continue  # skip corrupt files
    out.sort(key=lambda s: s['updated'], reverse=True)
    return out


def load_session(session_id: str, directory: Optional[str] = None
                 ) -> Optional[ConversationSession]:
    d = sessions_dir(directory)
    path = d / f"{session_id}.json"
    if not path.exists():
        return None
    try:
        return ConversationSession.load(path)
    except Exception:
        return None