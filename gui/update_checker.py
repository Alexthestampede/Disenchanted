#!/usr/bin/env python3
"""
Disenchanted update checker.

Github-releases based: latest release tag must match yyyymmdd.v versioning.
Checks at most once per day (timestamp cached in the config file under
ui.last_update_check). Silent unless a newer version exists — then a
non-blocking banner offers "Update and restart".
"""
import json
import subprocess
import time
from pathlib import Path
from typing import Optional

import requests

from gui.version import VERSION, APP_NAME, GITHUB_REPO, is_newer

RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
CHECK_INTERVAL = 24 * 3600


def _state_file() -> Path:
    return Path.home() / '.disenchanted' / 'update_state.json'


def _read_state() -> dict:
    try:
        return json.loads(_state_file().read_text())
    except Exception:
        return {}


def _write_state(state: dict):
    try:
        _state_file().parent.mkdir(parents=True, exist_ok=True)
        _state_file().write_text(json.dumps(state))
    except Exception:
        pass


def fetch_latest_version(timeout: float = 5.0) -> Optional[str]:
    """Latest release tag from GitHub, or None."""
    try:
        resp = requests.get(RELEASES_API, timeout=timeout,
                            headers={'Accept': 'application/vnd.github+json'})
        if resp.status_code == 200:
            tag = (resp.json() or {}).get('tag_name', '')
            return tag.lstrip('v') or None
    except Exception:
        pass
    return None


class UpdateChecker:
    """Daily update checks + banner callback."""

    def __init__(self, config, current_version: str):
        self.config = config
        self.current_version = current_version

    def should_check_now(self) -> bool:
        state = _read_state()
        return (time.time() - state.get('last_check', 0)) > CHECK_INTERVAL

    def check_soon(self, window, delay_ms: int = 4000):
        """Schedule a silent check shortly after launch (GUI only)."""
        if not self.should_check_now():
            return
        from PyQt5.QtCore import QTimer, QThread, pyqtSignal

        class _FetchThread(QThread):
            done = pyqtSignal(object)
            def run(self):
                self.done.emit(fetch_latest_version())

        self._fetch_thread = _FetchThread()
        self._fetch_thread.done.connect(
            lambda latest: self._on_fetched(window, latest))
        self._fetch_thread.start()

    def _on_fetched(self, window, latest):
        from PyQt5.QtCore import QTimer
        if latest is None:
            return  # network error: silent
        _write_state({'last_check': time.time(),
                      'last_seen': latest or ''})
        if is_newer(latest, self.current_version):
            self._pending_version = latest
            QTimer.singleShot(0, lambda: self._notify(window))

    def _notify(self, window):
        try:
            self.show_update_banner(window, self._pending_version)
        except Exception:
            pass

    def show_update_banner(self, window, new_version: str):
        """Non-blocking banner with an Update-and-restart button."""
        from PyQt5.QtWidgets import QMessageBox
        box = QMessageBox(window)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle("Update available")
        box.setText(
            f"{APP_NAME} {new_version} is available (you have "
            f"{self.current_version}).")
        update_btn = box.addButton("Update and restart", QMessageBox.AcceptRole)
        box.addButton("Later", QMessageBox.RejectRole)
        box.exec_()
        if box.clickedButton() is update_btn:
            self.update_and_restart(window)

    def update_and_restart(self, window):
        """git pull in the GUI repo, then re-exec the launcher."""
        repo = self._gui_repo_path()
        if not repo:
            QMessageBox.warning(window, "Update failed",
                                "Could not locate the Disenchanted repo.")
            return
        try:
            result = subprocess.run(
                ['git', '-C', str(repo), 'pull', '--ff-only'],
                capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                QMessageBox.warning(window, "Update failed",
                                    result.stderr or result.stdout)
                return
            # venv deps may have changed; best-effort sync
            venv_pip = repo / 'venv' / 'bin' / 'pip'
            if venv_pip.exists():
                subprocess.run(
                    [str(venv_pip), 'install', '-r',
                     str(repo / 'requirements.txt'), '-q'],
                    capture_output=True, timeout=300)
            # relaunch and quit
            subprocess.Popen([str(repo / 'disenchanted-chat.sh')])
            window.close()
        except Exception as e:
            QMessageBox.warning(window, "Update failed", str(e))

    @staticmethod
    def _gui_repo_path() -> Optional[Path]:
        # repo root = parent of this file's gui/ dir
        return Path(__file__).resolve().parent.parent