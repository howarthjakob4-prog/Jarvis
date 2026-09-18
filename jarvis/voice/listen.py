"""Offline speech-to-text with Vosk.

The mic is optional: if it is missing (or its packages are), every function
fails with a clear message and the app keeps running in type-in mode.
Third-party imports are lazy so importing this module never crashes.
"""
import io
import json
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
MODEL_DIRNAME = "vosk-model-small-en-us-0.15"
SAMPLE_RATE = 16000


class ListenError(Exception):
    """Mic/model/STT problems, always with a human-readable message."""


def models_base() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "models"


def model_path(base=None) -> Path:
    return Path(base) if base else models_base() / MODEL_DIRNAME


def ensure_model(base=None) -> Path:
    """Return the model dir, downloading (~40MB) and unzipping on first use."""
    dest = model_path(base)
    if (dest / ".ready").is_file():
        return dest
    try:
        with urllib.request.urlopen(MODEL_URL, timeout=180) as resp:
            data = resp.read()
    except Exception as exc:
        raise ListenError(f"Could not download the speech model: {exc}") from exc
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            zf.extractall(dest.parent)
        (dest / ".ready").write_text("ok", encoding="utf-8")
    except Exception as exc:
        raise ListenError(f"Could not unpack the speech model: {exc}") from exc
    return dest


def mic_available() -> bool:
    """True if sounddevice sees at least one input device. Never raises."""
    try:
        import sounddevice as sd
    except ImportError:
        return False
    try:
        return any(d.get("max_input_channels", 0) > 0 for d in sd.query_devices())
    except Exception:
        return False


def capture_once(timeout=8, base=None) -> str:
    """Record from the mic for up to `timeout` seconds. Returns the text heard."""
    try:
        import sounddevice as sd
    except ImportError as exc:
        raise ListenError("Microphone input needs the 'sounddevice' package.") from exc
    try:
        from vosk import KaldiRecognizer, Model
    except ImportError as exc:
        raise ListenError("Speech recognition needs the 'vosk' package.") from exc

    try:
        model = Model(str(ensure_model(base)))
    except ListenError:
        raise
    except Exception as exc:
        raise ListenError(f"Could not load the speech model: {exc}") from exc

    rec = KaldiRecognizer(model, SAMPLE_RATE)
    rec.SetWords(False)
    final = ""
    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                            dtype="int16", blocksize=8000) as stream:
            end = time.time() + timeout
            while time.time() < end:
                data, _ = stream.read(8000)
                raw = data.tobytes()
                if rec.AcceptWaveform(raw):
                    final = json.loads(rec.Result()).get("text", "")
                    if final:
                        break
            if not final:
                final = json.loads(rec.FinalResult()).get("text", "")
    except ListenError:
        raise
    except Exception as exc:
        raise ListenError(f"Microphone error: {exc}") from exc
    return final.strip()


class WakeWordListener(threading.Thread):
    """Background thread. Calls on_wake() each time the wake phrase is heard."""

    def __init__(self, on_wake, phrase="hey jarvis", base=None):
        super().__init__(daemon=True, name="jarvis-wake")
        self.on_wake = on_wake
        self.phrase = phrase.lower()
        self.base = base
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        try:
            import sounddevice as sd
            from vosk import KaldiRecognizer, Model
        except ImportError:
            return
        try:
            model = Model(str(ensure_model(self.base)))
        except ListenError:
            return
        rec = KaldiRecognizer(model, SAMPLE_RATE)
        try:
            with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                                dtype="int16", blocksize=4000) as stream:
                while not self._stop.is_set():
                    data, _ = stream.read(4000)
                    raw = data.tobytes()
                    if rec.AcceptWaveform(raw):
                        text = json.loads(rec.Result()).get("text", "").lower()
                    else:
                        text = json.loads(rec.PartialResult()).get("partial", "").lower()
                    if self.phrase in text:
                        try:
                            self.on_wake()
                        except Exception:
                            pass
                        rec.Reset()
        except Exception:
            return
