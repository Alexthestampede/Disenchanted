#!/usr/bin/env python3
"""
Speech (text-to-speech) support for Disenchanted.

Rendering goes through ModuLLe's Ollama speech processor
(``/v1/audio/speech``, Ollama >= 0.40.9). That call is a blocking HTTP
request, so it runs in a QThread; playback is handed to the first system
player found (paplay, pw-play, ffplay, aplay) through QProcess and stays on
the main thread.

No Qt widgets live here: the chat window owns the UI and only asks for
render/play/stop. Audio files are temporary and deleted when playback ends.
"""
import os
import shutil
import tempfile
from typing import Optional, Tuple

from PyQt5.QtCore import QObject, QProcess, QThread, pyqtSignal

# System players, tried in order. (binary, extra args)
PLAYERS = (
    ("paplay", ()),
    ("pw-play", ()),
    ("ffplay", ("-nodisp", "-autoexit", "-loglevel", "quiet")),
    ("aplay", ("-q",)),
)


def available() -> bool:
    """True when an audio player this module can drive is installed."""
    return any(shutil.which(binary) for binary, _ in PLAYERS)


def create_processor(model: Optional[str] = None,
                     base_url: Optional[str] = None,
                     api_key: Optional[str] = None):
    """Build a ModuLLe Ollama speech processor.

    ``model=None`` falls back to the library default (``OLLAMA_SPEECH_MODEL``,
    i.e. ``lfm3-omni``). Provider errors surface as RuntimeError so callers can
    show them without importing PyQt-specific exceptions.
    """
    try:
        from modulle import create_speech_processor
    except Exception as e:  # pragma: no cover - library is always installed
        raise RuntimeError(f"Speech support unavailable in ModuLLe: {e}")
    try:
        return create_speech_processor(
            "ollama", model=model or None, base_url=base_url or None,
            api_key=api_key or None)
    except ValueError as e:
        raise RuntimeError(str(e))


class SpeechWorker(QThread):
    """Renders text to a temporary WAV file in the background."""

    done = pyqtSignal(str)   # path to the rendered wav
    error = pyqtSignal(str)

    def __init__(self, processor, text: str, voice: str = "default",
                 parent=None):
        super().__init__(parent)
        self.processor = processor
        self.text = text
        self.voice = voice or "default"

    def run(self):
        path = None
        try:
            fd, path = tempfile.mkstemp(prefix='disenchanted-speech-',
                                        suffix='.wav')
            os.close(fd)
            written = self.processor.speak_to_file(
                self.text, path, voice=self.voice)
            if not written:
                self._discard(path)
                self.error.emit("The speech model returned no audio")
                return
            self.done.emit(written)
        except Exception as e:
            if path:
                self._discard(path)
            self.error.emit(str(e))

    @staticmethod
    def _discard(path: str):
        try:
            os.unlink(path)
        except OSError:
            pass


class VoiceListWorker(QThread):
    """Fetches the voices supported by the configured speech model."""

    done = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, processor, parent=None):
        super().__init__(parent)
        self.processor = processor

    def run(self):
        try:
            self.done.emit(list(self.processor.list_voices() or []))
        except Exception as e:
            self.error.emit(str(e))


class SpeechPlayer(QObject):
    """Plays one WAV file at a time via an external player."""

    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, parent=None, player: Optional[Tuple[str, Tuple[str, ...]]] = None):
        super().__init__(parent)
        self._proc: Optional[QProcess] = None
        self._stopping = False
        self._player = player if player is not None else self._find_player()

    @staticmethod
    def _find_player() -> Optional[Tuple[str, Tuple[str, ...]]]:
        for binary, args in PLAYERS:
            exe = shutil.which(binary)
            if exe:
                return (exe, args)
        return None

    @property
    def player_name(self) -> str:
        return os.path.basename(self._player[0]) if self._player else ""

    def is_playing(self) -> bool:
        return self._proc is not None

    def play(self, path: str) -> bool:
        self.stop()
        if self._player is None:
            self.error.emit(
                "No audio player found — install paplay (PulseAudio), "
                "pw-play (PipeWire), ffplay or aplay")
            return False
        exe, args = self._player
        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.MergedChannels)
        proc.finished.connect(lambda *_: self._on_finished(proc))
        proc.errorOccurred.connect(lambda *_: self._on_error(proc))
        self._proc = proc
        self._stopping = False
        proc.start(exe, list(args) + [str(path)])
        if not proc.waitForStarted(2000):
            self._proc = None
            proc.deleteLater()
            self.error.emit(f"Could not start {self.player_name}")
            return False
        return True

    def stop(self):
        proc, self._proc = self._proc, None
        if proc is None:
            return
        self._stopping = True
        if proc.state() != QProcess.NotRunning:
            proc.kill()
            proc.waitForFinished(500)
        proc.deleteLater()

    # -- QProcess callbacks -------------------------------------------------
    def _on_finished(self, proc):
        if self._proc is proc:
            self._proc = None
            if not self._stopping:
                self.finished.emit()
        self._stopping = False
        proc.deleteLater()

    def _on_error(self, proc):
        if self._proc is proc:
            self._proc = None
            if not self._stopping:
                self.error.emit(
                    f"{self.player_name} could not play the audio "
                    f"({proc.errorString()})")


class SpeechManager(QObject):
    """High-level read-aloud service: render (threaded) then play."""

    started = pyqtSignal()
    finished = pyqtSignal()
    error = pyqtSignal(str)
    voices_loaded = pyqtSignal(list)

    def __init__(self, parent=None, player: Optional[SpeechPlayer] = None):
        super().__init__(parent)
        self.settings = {}
        self.provider = "ollama"
        self.processor = None
        self.config_error: Optional[str] = None
        self._worker: Optional[SpeechWorker] = None
        self._voices_worker: Optional[VoiceListWorker] = None
        self._last_file: Optional[str] = None
        self.player = player or SpeechPlayer(self)
        self.player.finished.connect(self._on_playback_finished)
        self.player.error.connect(self._on_playback_error)

    # -- configuration ------------------------------------------------------
    def configure(self, speech: Optional[dict] = None, provider: str = "ollama",
                  base_url: Optional[str] = None, api_key: Optional[str] = None,
                  processor=None) -> Optional[str]:
        """(Re)build the processor from a config section.

        Returns an error string when speech stays unavailable, otherwise None.
        ``processor`` injects a ready-made processor (used by the settings
        dialog's Test button, which builds one from unsaved fields).
        """
        self.stop()
        self.settings = dict(speech or {})
        self.provider = (provider or "ollama").lower()
        self.processor = None
        self.config_error = None

        if not self.settings.get('enabled'):
            return None

        if processor is not None:
            self.processor = processor
            return None

        if self.provider != 'ollama':
            self.config_error = (
                "Read-aloud needs the Ollama provider: speech is served by "
                f"Ollama's /v1/audio/speech, not by '{self.provider}'.")
            return self.config_error

        try:
            self.processor = create_processor(
                model=self.settings.get('model'),
                base_url=self.settings.get('base_url') or base_url,
                api_key=api_key)
        except Exception as e:
            self.config_error = str(e)
            return self.config_error
        return None

    def enabled(self) -> bool:
        return self.processor is not None

    def busy(self) -> bool:
        return bool((self._worker and self._worker.isRunning())
                    or self.player.is_playing())

    # -- speaking -----------------------------------------------------------
    def speak(self, text: str, voice: Optional[str] = None) -> bool:
        text = (text or '').strip()
        if not text:
            return False
        if self.processor is None:
            self.error.emit(self.config_error
                            or "Read-aloud is off (Settings → Speech).")
            return False
        self.stop()
        worker = SpeechWorker(
            self.processor, text,
            voice=voice or self.settings.get('voice') or 'default',
            parent=self)
        worker.done.connect(self._on_rendered)
        worker.error.connect(self.error)
        worker.finished.connect(lambda w=worker: self._clear_worker(w))
        self._worker = worker
        worker.start()
        return True

    def stop(self):
        """Abort rendering/playback (used when closing or switching messages)."""
        worker, self._worker = self._worker, None
        if worker is not None:
            if worker.isRunning():
                worker.terminate()
                worker.wait(500)
            worker.deleteLater()
        self.player.stop()
        self._forget_file()

    def fetch_voices(self) -> bool:
        """Load the model's voices in the background; emits voices_loaded."""
        if self.processor is None:
            self.error.emit(self.config_error
                            or "Read-aloud is off (Settings → Speech).")
            return False
        if self._voices_worker and self._voices_worker.isRunning():
            return False
        worker = VoiceListWorker(self.processor, parent=self)
        worker.done.connect(self.voices_loaded)
        worker.error.connect(self.error)
        worker.finished.connect(lambda w=worker: self._clear_voices_worker(w))
        self._voices_worker = worker
        worker.start()
        return True

    # -- callbacks ----------------------------------------------------------
    def _on_rendered(self, path: str):
        if self._worker is None:
            # stop() ran after the render finished: drop the stale audio
            self._discard(path)
            return
        self._forget_file()
        self._last_file = path
        if self.player.play(path):
            self.started.emit()

    def _on_playback_finished(self):
        self._forget_file()
        self.finished.emit()

    def _on_playback_error(self, message: str):
        self._forget_file()
        self.error.emit(message)

    def _clear_worker(self, worker):
        if self._worker is worker:
            self._worker = None
        worker.deleteLater()

    def _clear_voices_worker(self, worker):
        if self._voices_worker is worker:
            self._voices_worker = None
        worker.deleteLater()

    def _forget_file(self):
        path, self._last_file = self._last_file, None
        if path:
            self._discard(path)

    @staticmethod
    def _discard(path: str):
        try:
            os.unlink(path)
        except OSError:
            pass
