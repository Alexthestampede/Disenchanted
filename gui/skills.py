#!/usr/bin/env python3
"""
Disenchanted skills: SKILL.md folders in ~/.disenchanted/skills/<name>/.

Each skill folder contains a SKILL.md (plain markdown). Enabled skills are
appended to the system prompt at conversation start. Users edit the files
directly (open folder) — no parsing beyond frontmatter-ish title.
"""
import re
from pathlib import Path
from typing import Dict, List, Optional


def skills_root() -> Path:
    return Path.home() / '.disenchanted' / 'skills'


class Skill:
    def __init__(self, name: str, path: Path, text: str, description: str = ''):
        self.name = name
        self.path = path
        self.text = text
        self.description = description

    def system_block(self) -> str:
        """SKILL.md content ready for system-prompt inclusion."""
        return f"### Skill: {self.name}\n{self.text.strip()}"


class SkillStore:
    """Discovers skills from $HOME/.disenchanted/skills/<name>/SKILL.md."""

    def __init__(self, root: Optional[str] = None):
        self.root = Path(root).expanduser() if root else skills_root()
        self._cache: Dict[str, Skill] = {}
        self.refresh()

    def refresh(self):
        self._cache = {}
        if not self.root.exists():
            return
        for d in sorted(self.root.iterdir()):
            if not d.is_dir():
                continue
            skill_md = d / 'SKILL.md'
            if not skill_md.exists():
                continue
            try:
                text = skill_md.read_text(encoding='utf-8')
            except Exception:
                continue
            desc = ''
            m = re.search(r'^description:\s*(.+)$', text, re.M)
            if m:
                desc = m.group(1).strip()
            self._cache[d.name] = Skill(d.name, skill_md, text, desc)

    def list_skills(self) -> List[Skill]:
        return list(self._cache.values())

    def names(self) -> List[str]:
        return sorted(self._cache)

    def get(self, name: str) -> Optional[Skill]:
        return self._cache.get(name)

    def create(self, name: str, text: str = '') -> Optional[Skill]:
        """Create a skill folder + SKILL.md; sanitized name."""
        safe = re.sub(r'[^\w\-]', '_', name.strip())
        if not safe:
            return None
        d = self.root / safe
        d.mkdir(parents=True, exist_ok=True)
        skill_md = d / 'SKILL.md'
        if not skill_md.exists():
            skill_md.write_text(f"description: {safe}\n\n{text or '(edit this skill)'}",
                                encoding='utf-8')
        self.refresh()
        return self.get(safe)

    def enabled_skills(self, enabled: List[str]) -> List[Skill]:
        return [self._cache[n] for n in enabled if n in self._cache]

    @staticmethod
    def skills_system_block(skills: List[Skill]) -> str:
        """Combine enabled skills into one system-prompt appendix."""
        if not skills:
            return ''
        return "\n\n".join(s.system_block() for s in skills)