"""Tkinter panel UI (stdlib — always works).

Persistent desktop panel: always-on-top (toggleable), collapsible,
scrolling news ticker, live CPU/RAM/disk monitors, timestamped activity
log, and a LISTENING / SPEAKING / IDLE status indicator.

Every control is wired to real behavior; there are no decorative buttons.
Voice and typed input both flow through handle_text -> speaker.speak,
so the single speak path is identical either way. Background threads
(ticker, monitors, timers) never touch tkinter directly — they schedule
UI updates with after().
"""
import threading
import time
from datetime import datetime

import tkinter as tk
from tkinter import scrolledtext

from . import monitors
from .news import NewsError, fetch_headlines
from .voice.listen import ListenError, WakeWordListener, capture_once

_STATUS_COLORS = {"IDLE": "gray", "LISTENING": "dodger blue", "SPEAKING": "orange"}
_TICKER_WIDTH = 90


class JarvisUI:
    def __init__(self, brain, speaker, mic_ok, config):
        self.brain = brain
        self.speaker = speaker
        self.mic_ok = mic_ok
        self.config = config
        self._busy = False
        self._wake = None
        self._collapsed = False
        self._ticker_raw = "TOP WORLD NEWS TODAY: loading headlines…"
        self._ticker_pos = 0

        self.root = tk.Tk()
        self.root.title("Jarvis")
        self.root.geometry("520x720")
        self.root.minsize(400, 320)
        self.root.attributes("-topmost", bool(config.get("always_on_top", True)))

        # Header row: status indicator + collapse button.
        header = tk.Frame(self.root)
        header.pack(fill=tk.X, padx=10, pady=(8, 2))
        self.status_dot = tk.Label(header, text="●", font=("Segoe UI", 14),
                                   fg=_STATUS_COLORS["IDLE"])
        self.status_dot.pack(side=tk.LEFT)
        self.status_text = tk.Label(header, text="IDLE", font=("Segoe UI", 10, "bold"),
                                    fg=_STATUS_COLORS["IDLE"])
        self.status_text.pack(side=tk.LEFT, padx=(4, 0))
        self.collapse_btn = tk.Button(header, text="—", width=3,
                                      command=self.toggle_collapse)
        self.collapse_btn.pack(side=tk.RIGHT)

        # News ticker.
        self.ticker_var = tk.StringVar(value=self._ticker_raw[:_TICKER_WIDTH])
        ticker = tk.Label(self.root, textvariable=self.ticker_var,
                          font=("Segoe UI", 9), fg="dark blue", anchor="w",
                          justify=tk.LEFT)
        ticker.pack(fill=tk.X, padx=10, pady=(2, 2))

        # System monitors.
        self.monitors_var = tk.StringVar(value=monitors.format_stats(None))
        mon = tk.Label(self.root, textvariable=self.monitors_var,
                       font=("Segoe UI", 9), fg="gray", anchor="w")
        mon.pack(fill=tk.X, padx=10, pady=(0, 4))

        # Activity log (read-only, timestamped). Collapsible.
        self.log = scrolledtext.ScrolledText(
            self.root, wrap=tk.WORD, state=tk.DISABLED, font=("Segoe UI", 11)
        )
        self.log.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4, 6))

        # Type-in row: entry + Send (Return also sends).
        self.entry_frame = tk.Frame(self.root)
        self.entry_frame.pack(fill=tk.X, padx=10, pady=6)
        self.entry = tk.Entry(self.entry_frame, font=("Segoe UI", 11))
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry.bind("<Return>", lambda _e: self.send_typed())
        self.send_btn = tk.Button(self.entry_frame, text="Send", width=8,
                                  command=self.send_typed)
        self.send_btn.pack(side=tk.LEFT, padx=(6, 0))

        # Push-to-talk row.
        talk_frame = tk.Frame(self.root)
        talk_frame.pack(fill=tk.X, padx=10, pady=6)
        self.talk_btn = tk.Button(
            talk_frame, text="🎤 Push to Talk", font=("Segoe UI", 12, "bold"),
            height=2, command=self.push_to_talk,
        )
        self.talk_btn.pack(fill=tk.X)
        if not mic_ok:
            self.talk_btn.config(state=tk.DISABLED, text="🎤 No microphone — type instead")

        # Options row: voice toggle, always-on-top, mic info, quit.
        opt_frame = tk.Frame(self.root)
        opt_frame.pack(fill=tk.X, padx=10, pady=6)
        self.voice_var = tk.BooleanVar(value=speaker.enabled)
        self.voice_toggle = tk.Checkbutton(
            opt_frame, text="Voice on", variable=self.voice_var, command=self.toggle_voice
        )
        self.voice_toggle.pack(side=tk.LEFT)
        self._sync_voice_toggle()
        self.topmost_var = tk.BooleanVar(
            value=bool(config.get("always_on_top", True)))
        self.topmost_toggle = tk.Checkbutton(
            opt_frame, text="On top", variable=self.topmost_var,
            command=self.toggle_topmost,
        )
        self.topmost_toggle.pack(side=tk.LEFT, padx=(8, 0))
        self.mic_label = tk.Label(opt_frame, text="", fg="gray", font=("Segoe UI", 9))
        self.mic_label.pack(side=tk.LEFT, padx=(12, 0))
        self.quit_btn = tk.Button(opt_frame, text="Quit", command=self._on_close)
        self.quit_btn.pack(side=tk.RIGHT)
        self._refresh_mic_label()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Background workers.
        self._start_ticker()
        self._start_monitors()
        if mic_ok and config.get("wake_word"):
            self._start_wake_word()

    # ----- status indicator -------------------------------------------------

    def _set_status(self, state):
        color = _STATUS_COLORS.get(state, "gray")
        self.status_dot.config(fg=color)
        self.status_text.config(text=state, fg=color)

    # ----- collapse ----------------------------------------------------------

    def toggle_collapse(self):
        if self._collapsed:
            self.log.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4, 6),
                          before=self.entry_frame)
            self.collapse_btn.config(text="—")
            self._collapsed = False
        else:
            self.log.pack_forget()
            self.collapse_btn.config(text="+")
            self._collapsed = True

    def toggle_topmost(self):
        self.root.attributes("-topmost", bool(self.topmost_var.get()))

    # ----- activity log -------------------------------------------------------

    def log_line(self, who, text):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log.config(state=tk.NORMAL)
        self.log.insert(tk.END, f"[{stamp}] {who}: {text}\n")
        self.log.see(tk.END)
        self.log.config(state=tk.DISABLED)

    # ----- background: news ticker -------------------------------------------

    def _start_ticker(self):
        threading.Thread(target=self._ticker_worker, daemon=True,
                         name="jarvis-ticker").start()
        self.root.after(180, self._scroll_ticker)

    def _ticker_worker(self):
        refresh = self.config.get("ticker_refresh_minutes", 15) or 15
        while True:
            try:
                titles = fetch_headlines(limit=8)
                raw = "TOP WORLD NEWS TODAY: " + "   •   ".join(titles)
            except NewsError:
                raw = "TOP WORLD NEWS TODAY: headlines unavailable (offline?)"
            except Exception:
                raw = "TOP WORLD NEWS TODAY: headlines unavailable"
            self.root.after(0, self._ticker_update, raw)
            time.sleep(refresh * 60)

    def _ticker_update(self, raw):
        self._ticker_raw = raw
        self._ticker_pos = 0

    def _scroll_ticker(self):
        s = (self._ticker_raw + "   •   ")
        pos = self._ticker_pos % len(s)
        shown = (s[pos:] + s[:pos])[:_TICKER_WIDTH]
        self.ticker_var.set(shown)
        self._ticker_pos = pos + 1
        self.root.after(180, self._scroll_ticker)

    # ----- background: system monitors ---------------------------------------

    def _start_monitors(self):
        threading.Thread(target=self._monitors_worker, daemon=True,
                         name="jarvis-monitors").start()

    def _monitors_worker(self):
        while True:
            stats = monitors.read_stats()
            self.root.after(0, self.monitors_var.set, monitors.format_stats(stats))
            time.sleep(2)

    # ----- timer/reminder alerts ----------------------------------------------

    def announce_alert(self, text):
        """Thread-safe: called by brain.alert() from timer threads."""
        self.root.after(0, self._announce_alert_ui, text)

    def _announce_alert_ui(self, text):
        self.log_line("⏰ Reminder", text)
        self._set_status("SPEAKING")
        self.root.update_idletasks()
        if not self.speaker.speak(text) and self.speaker.last_error:
            self.log_line("Jarvis", f"(voice failed: {self.speaker.last_error})")
        self._set_status("IDLE")
        self._popup(text)

    def _popup(self, text):
        pop = tk.Toplevel(self.root)
        pop.title("Jarvis")
        pop.attributes("-topmost", True)
        tk.Label(pop, text=text, wraplength=320, font=("Segoe UI", 11),
                 padx=16, pady=12).pack()
        tk.Button(pop, text="OK", width=10, command=pop.destroy).pack(pady=(0, 12))
        pop.after(30000, lambda: pop.winfo_exists() and pop.destroy())

    # ----- small helpers -------------------------------------------------------

    def _refresh_mic_label(self):
        mic = "Mic ready" if self.mic_ok else "No mic — type-in mode"
        voice = "Voice on" if self.speaker.enabled else "Voice off"
        self.mic_label.config(text=f"{mic}  •  {voice}")

    def _sync_voice_toggle(self):
        self.voice_toggle.config(text="Voice on" if self.voice_var.get() else "Voice off")

    def _on_close(self):
        if self._wake is not None:
            self._wake.stop()
        self.root.destroy()

    # ----- the single input path ------------------------------------------

    def handle_text(self, text, source="typed"):
        """One path for voice and typed input: log, think, log, speak."""
        text = (text or "").strip()
        if not text:
            if source == "voice":
                self.log_line("Jarvis", "I didn't hear anything.")
            return
        self.log_line("You", text)
        try:
            reply = self.brain.respond(text)
        except Exception as exc:
            reply = f"Something went wrong in my brain: {exc}"
        self.log_line("Jarvis", reply)
        self._set_status("SPEAKING")
        self.root.update_idletasks()
        if not self.speaker.speak(reply) and self.speaker.last_error:
            self.log_line("Jarvis", f"(voice failed: {self.speaker.last_error})")
        self._set_status("IDLE")

    def send_typed(self):
        text = self.entry.get()
        self.entry.delete(0, tk.END)
        self.handle_text(text, source="typed")

    # ----- voice input -----------------------------------------------------

    def toggle_voice(self):
        self.speaker.enabled = self.voice_var.get()
        self._sync_voice_toggle()
        self._refresh_mic_label()

    def push_to_talk(self):
        if self._busy or not self.mic_ok:
            return
        self._busy = True
        self._set_status("LISTENING")
        self.talk_btn.config(state=tk.DISABLED, text="🎤 Listening…")
        threading.Thread(target=self._listen_worker, daemon=True).start()

    def _listen_worker(self):
        try:
            text = capture_once(timeout=self.config.get("mic_timeout", 8))
        except ListenError as exc:
            text, err = None, str(exc)
        else:
            err = None
        self.root.after(0, self._listen_done, text, err)

    def _listen_done(self, text, err):
        self._busy = False
        self._set_status("IDLE")
        self.talk_btn.config(state=tk.NORMAL, text="🎤 Push to Talk")
        if err:
            self.log_line("Jarvis", err)
            return
        self.handle_text(text or "", source="voice")

    def _start_wake_word(self):
        phrase = self.config.get("wake_phrase", "hey jarvis")
        self._wake = WakeWordListener(on_wake=self._wake_heard, phrase=phrase)
        self._wake.start()
        self.log_line("Jarvis", f"Wake word on — say '{phrase}'.")

    def _wake_heard(self):
        self.root.after(0, self._on_wake_ui)

    def _on_wake_ui(self):
        self.log_line("Jarvis", "Yes? Listening…")
        self.push_to_talk()

    # ----- main loop ---------------------------------------------------------

    def run(self):
        self.root.mainloop()
