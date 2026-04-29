# robo_brain.py – Modular Voice Assistant Engine
"""Robo Brain – core engine for the Dasai Mochi voice assistant.
Provides:
- Continuous listening with wake‑word detection
- Thread‑safe TTS via pyttsx3
- Smart memory (store/retrieve) with fuzzy matching
- Reminder system (background threads)
- Google Calendar integration (lazy init)
- Multi‑step conversation flow handling
- Optional Bluetooth communication (dev mode if no device)
"""

import json
import threading
import time
import datetime
import math
import speech_recognition as sr
import pyttsx3
from difflib import get_close_matches
import os
import logging

try:
    import winsound
except ImportError:
    winsound = None

# Optional Bluetooth – safe import
try:
    import serial
except Exception:
    serial = None

# ---------------------------------------------------------------------------
# Configuration & Global State
# ---------------------------------------------------------------------------
MEMORY_FILE = "memory.json"
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"

engine = pyttsx3.init()
recognizer = sr.Recognizer()
recognizer.energy_threshold = 300  # Adjust for better sensitivity
recognizer.dynamic_energy_threshold = True

# TTS thread‑safety
_speak_lock = threading.Lock()
_state_callback = None  # UI can register a callback(state:str)

# Memory store (loaded lazily)
_memory = {}
_memory_lock = threading.Lock()

# Conversation context for multi‑step commands
_pending = {
    "handler": None,  # function to call when next user utterance arrives
    "data": {},
    "step": 0,
}

# Bluetooth (dev mode if unavailable)
_bt = None
if serial:
    try:
        _bt = serial.Serial("COM5", 9600, timeout=1)
        print("Bluetooth Connected")
    except Exception:
        _bt = None
        print("Bluetooth Not Connected (Dev Mode)")
else:
    _bt = None
    print("serial module missing – Bluetooth disabled")

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------
def _send_bt(msg: str):
    if _bt:
        try:
            _bt.write((msg + "\n").encode())
        except Exception:
            pass

def set_state_callback(fn):
    """Register a UI callback that receives state strings such as
    'idle', 'listening', 'speaking', 'thinking', 'alert', 'error'."""
    global _state_callback
    _state_callback = fn

def _set_state(state: str):
    """Internal state setter – notifies UI and Bluetooth."""
    if _state_callback:
        try:
            _state_callback(state)
        except Exception as e:
            logging.exception("State callback error: %s", e)
    _send_bt(f"STATE:{state}")

def _beep(freq=800, duration=150):
    """Play a short beep sound (Windows only)."""
    if winsound:
        try:
            winsound.Beep(freq, duration)
        except Exception:
            pass

# ---------------------------------------------------------------------------
# Text‑to‑Speech (thread‑safe)
# ---------------------------------------------------------------------------
def speak(text: str, rate: int = 175, volume: float = 1.0, voice_idx: int = 0, block: bool = False):
    """Speak *text*. By default, runs in a background thread.
    If *block* is True, it blocks the current thread until finished.
    """
    def _run():
        with _speak_lock:
            _set_state("speaking")
            engine.setProperty('rate', rate)
            engine.setProperty('volume', volume)
            voices = engine.getProperty('voices')
            if voices:
                engine.setProperty('voice', voices[voice_idx].id)
            engine.say(text)
            engine.runAndWait()
            _set_state("idle")

    if block:
        _run()
    else:
        threading.Thread(target=_run, daemon=True).start()

# ---------------------------------------------------------------------------
# Memory persistence (smart memory)
# ---------------------------------------------------------------------------
def _load_memory():
    global _memory
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                _memory = json.load(f)
        except Exception:
            _memory = {}
    else:
        _memory = {}

_load_memory()

def _save_memory():
    with _memory_lock:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(_memory, f, ensure_ascii=False, indent=2)

def remember(item: str, location: str):
    """Store *item* → *location* in memory and persist to disk."""
    with _memory_lock:
        _memory[item.lower()] = location
        _save_memory()
    _send_bt(f"MEMORY:{item}|{location}")
    speak(f"I remember your {item} is in {location}")

def recall(query: str):
    """Attempt to find the best‑matching memory entry for *query*.
    Returns a tuple (item, location) or (None, None).
    """
    words = query.lower().split()
    # simple heuristic – look for the word after "my" or the last word
    candidate = None
    if "my" in words:
        idx = words.index("my")
        if idx + 1 < len(words):
            candidate = words[idx + 1]
    if not candidate:
        candidate = words[-1]
    
    with _memory_lock:
        matches = get_close_matches(candidate, _memory.keys(), n=1, cutoff=0.5)
        if matches:
            key = matches[0]
            loc = _memory[key]
            speak(f"Your {key} is in {loc}")
            return key, loc
        else:
            speak("I don't know where that is")
            return None, None

# ---------------------------------------------------------------------------
# Reminder system
# ---------------------------------------------------------------------------
def _parse_time(text: str) -> float:
    """Parse *text* into a delay in seconds.
    Supports formats like "in 5 minutes", "in 10 seconds", "at 14:30".
    Falls back to 10 seconds.
    """
    now = datetime.datetime.now()
    txt = text.lower().strip()
    # "in X minutes" or "in X seconds"
    if txt.startswith("in "):
        parts = txt[3:].split()
        try:
            num = int(parts[0])
            unit = parts[1] if len(parts) > 1 else "seconds"
            if "min" in unit:
                return num * 60
            else:
                return num
        except Exception:
            pass
    # "at HH:MM"
    if txt.startswith("at "):
        try:
            t = txt[3:]
            hour, minute = map(int, t.split(":"))
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target < now:
                target += datetime.timedelta(days=1)
            return (target - now).total_seconds()
        except Exception:
            pass
    # default
    return 10.0

def set_reminder(task: str, when: str):
    """Create a background reminder that will speak *task* after *when*.
    *when* is a natural‑language string parsed by ``_parse_time``.
    """
    delay = _parse_time(when)
    _send_bt(f"REMINDER:{task}|{when}")
    speak("Reminder set")

    def _reminder_thread():
        time.sleep(delay)
        _set_state("alert")
        speak(f"Reminder: {task}")

    threading.Thread(target=_reminder_thread, daemon=True).start()

# ---------------------------------------------------------------------------
# Android Calendar integration via Bluetooth (no direct Google API)
# ---------------------------------------------------------------------------
def add_calendar_event(summary: str, when: str):
    """Send a calendar add request to the connected Android device via Bluetooth.
    The Android app is responsible for creating the event.
    """
    if _bt:
        # Format: CAL_ADD:summary|when
        _send_bt(f"CAL_ADD:{summary}|{when}")
        speak(f"Sending event '{summary}' to Android calendar")
    else:
        speak("Android device not connected; cannot add calendar event")

def list_upcoming_events(max_results: int = 5):
    """Request the Android device to list upcoming events via Bluetooth.
    The Android app should respond with a NOTIF or CMD that can be spoken.
    """
    if _bt:
        _send_bt("CAL_LIST")
        speak("Requesting upcoming events from Android")
    else:
        speak("Android device not connected; cannot fetch events")

# ---------------------------------------------------------------------------
# Conversation flow handling (multi‑step)
# ---------------------------------------------------------------------------
def _reset_pending():
    _pending["handler"] = None
    _pending["data"] = {}
    _pending["step"] = 0

def handle_command(text: str):
    """Main entry point for a user command (post‑wake‑word)."""
    # If we are in the middle of a multi‑step flow, delegate
    if _pending["handler"]:
        _pending["handler"](text)
        return

    # Simple one‑shot commands
    txt = text.lower()
    print(f"--- DEBUG: Routing command: '{txt}' ---", flush=True)

    if "kept" in txt and "in" in txt:
        # Memory store
        try:
            parts = txt.split("my")[1].split("in")
            item = parts[0].strip()
            loc = parts[1].strip()
            remember(item, loc)
        except Exception:
            speak("I didn't understand the memory command")
        return
    if "where" in txt:
        # Memory recall
        try:
            item = txt.split("my")[1].strip()
            recall(item)
        except Exception:
            speak("I couldn't figure out what you asked")
        return
    if "remind" in txt:
        # Start multi‑step reminder flow
        speak("What should I remind you about?")
        _pending["handler"] = _reminder_step_task
        _pending["step"] = 1
        return
    if ("add" in txt or "schedule" in txt) and ("event" in txt):
        # Flexible match for "add event", "add a event", "schedule event", etc.
        speak("What is the event title?")
        _pending["handler"] = _calendar_step_title
        _pending["step"] = 1
        return
    if ("today" in txt or "todays" in txt) and "schedule" in txt:
        # Specialized response for user's specific schedule
        speak("Your schedule for today is: One. You have an event named Technologia. Two. You have to submit your NNFL assignment. And three. You have a PPT.")
        return
    if ("my" in txt or "what" in txt) and "events" in txt:
        list_upcoming_events()
        return
    if "help" in txt:
        speak("I can remember where you kept things, set reminders, manage your schedule, and check your calendar. Try saying, where are my keys, or, remind me to drink water.")
        return
    # Fallback
    print(f"--- DEBUG: No command route found for '{txt}' ---", flush=True)
    speak(f"I'm sorry, I don't know the command {txt} yet.")
    return False # Not handled

def _handle_direct_command(text: str) -> bool:
    """Check if the text matches a known command without requiring a wake word.
    Used for the 'always respond' feature.
    """
    txt = text.lower()
    # High-confidence command triggers
    if (("today" in txt or "todays" in txt) and "schedule" in txt) or \
       ("kept" in txt and "in" in txt) or \
       ("where" in txt and "my" in txt) or \
       ("remind" in txt) or \
       (("add" in txt or "schedule" in txt) and "event" in txt):
        
        # Beep first to show we caught it
        _beep(1000, 100)
        handle_command(text)
        return True
    return False

# ----- Reminder multi‑step -----
def _reminder_step_task(task_text: str):
    # Received task description, ask for time
    _pending["data"]["task"] = task_text
    speak("When should I remind you?")
    _pending["handler"] = _reminder_step_time

def _reminder_step_time(time_text: str):
    task = _pending["data"].get("task", "")
    set_reminder(task, time_text)
    _reset_pending()

# ----- Calendar multi‑step -----
def _calendar_step_title(title_text: str):
    _pending["data"]["title"] = title_text
    speak("When is the event? (e.g., at 14:30)")
    _pending["handler"] = _calendar_step_time

def _calendar_step_time(time_text: str):
    title = _pending["data"].get("title", "Untitled Event")
    add_calendar_event(title, time_text)
    _reset_pending()

# ---------------------------------------------------------------------------
# Bluetooth inbound command listener (optional)
# ---------------------------------------------------------------------------
def _bluetooth_listener():
    if not _bt:
        return
    while True:
        try:
            line = _bt.readline().decode().strip()
            if not line:
                continue
            if line.startswith("CMD:"):
                cmd = line[4:]
                handle_command(cmd)
        except Exception:
            pass

if _bt:
    threading.Thread(target=_bluetooth_listener, daemon=True).start()

# ---------------------------------------------------------------------------
# Voice loop – runs in its own daemon thread
# ---------------------------------------------------------------------------
def _listen_once(timeout: int = 5):
    """Listens for a single phrase and returns the text, or an empty string on error/timeout."""
    try:
        with sr.Microphone() as source:
            print("--- DEBUG: Listening... ---", flush=True)
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            try:
                # Added timeout of 3s to wait for speech to start
                audio = recognizer.listen(source, phrase_time_limit=5, timeout=timeout)
                text = recognizer.recognize_google(audio).lower()
                print(f"--- DEBUG: Recognized: '{text}' ---", flush=True)
                return text
            except sr.WaitTimeoutError:
                # Just silent timeout, no error
                return ""
            except Exception as e:
                print(f"--- DEBUG: Recognition Error: {type(e).__name__} ---", flush=True)
                return ""
    except Exception as e:
        print(f"--- DEBUG: Microphone Init Error: {e} ---", flush=True)
        return ""

def _voice_loop():
    print("--- DEBUG: Voice Loop Started ---", flush=True)
    while True:
        try:
            # IMPORTANT: If we have a pending multi-step command, prioritize it
            if _pending["handler"]:
                print(f"--- DEBUG: Listening for pending step {_pending['step']} ---", flush=True)
                _set_state("listening")
                text = _listen_once(timeout=10)
                if text:
                    handle_command(text)
                else:
                    print("--- DEBUG: Pending step timed out ---", flush=True)
                    _reset_pending()
                continue

            # NORMAL FLOW
            _set_state("idle")
            text = _listen_once(timeout=3)
            
            if not text:
                continue
                
            # 1. ALWAYS RESPOND: Check if it's a direct command first
            if _handle_direct_command(text):
                continue

            # 2. WAKE WORD: If it wasn't a direct command, check for wake words
            wake_words = ["hey robo", "robo", "hey mimo", "mimo", "hey robot", "mimo mimo", "heyy mimo", "heyy robo"]
            if any(word in text.lower() for word in wake_words):
                print("--- DEBUG: Wake Word Detected! ---", flush=True)
                speak("Huh?", block=True) 
                
                # Now listening for the actual command
                _set_state("listening")
                print("--- DEBUG: Waiting for command... ---", flush=True)
                command = _listen_once(timeout=5)
                if command:
                    _beep(1000, 100)
                    handle_command(command)
                else:
                    print("--- DEBUG: No command detected after wake word ---", flush=True)
            # If no wake word, just ignore
        except Exception as e:
            print(f"--- DEBUG: Voice Loop Iteration Error: {e} ---", flush=True)
            time.sleep(1)


def start():
    """Public entry point – launches background voice loop.
    UI should call this once after initializing the UI and optionally
    registering a state callback via ``set_state_callback``.
    """
    threading.Thread(target=_voice_loop, daemon=True).start()

# End of robo_brain.py