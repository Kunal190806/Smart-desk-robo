# pi_robo.py – Mimobot: Single-file Voice Assistant for Raspberry Pi
"""Mimobot – A smart, responsive, and slightly expressive AI assistant.
Runs entirely on Raspberry Pi 3B with ILI9341 TFT display.

Features:
- Wake-word activation ("Mimobot", "Robo", "Mimo")
- Persistent smart memory with fuzzy matching
- Time / Date queries
- Weather + AQI (via wttr.in)
- Reminder system
- Natural, conversational personality
- TFT animated face (luma.lcd)
"""

import json
import threading
import time
import datetime
import math
import random
import speech_recognition as sr
import pyttsx3
from difflib import get_close_matches
import os
import logging
import re
import subprocess
import wave
import io
import numpy as np
import pyaudio
import shutil
from PIL import Image, ImageDraw

# Optional imports
try:
    import winsound
except ImportError:
    winsound = None

try:
    import serial
except Exception:
    serial = None

try:
    import urllib.request
    import urllib.error
    _HAS_URLLIB = True
except ImportError:
    _HAS_URLLIB = False

# ---------------------------------------------------------------------------
# Configuration & Global State
# ---------------------------------------------------------------------------
MEMORY_FILE = "memory.json"

# Safe TTS engine initialization
engine = None
for _driver in [None, 'espeak', 'nsss', 'sapi5']:
    try:
        engine = pyttsx3.init(driverName=_driver)
        _voices = engine.getProperty('voices')
        for _v in _voices:
            if 'en' in _v.id.lower():
                engine.setProperty('voice', _v.id)
                break
        print(f"TTS Engine initialized successfully (driver: {_driver or 'default'})")
        break
    except Exception as _e:
        print(f"TTS init failed with driver '{_driver}': {_e}")
        engine = None
        continue

if engine is None:
    print("WARNING: Could not initialize any TTS engine. Speech will be disabled.")

recognizer = sr.Recognizer()
recognizer.energy_threshold = 300
recognizer.dynamic_energy_threshold = True

# TTS thread-safety
_speak_lock = threading.Lock()
_state_callback = None

# Memory store
_memory = {}
_memory_lock = threading.Lock()

# Multi-step conversation context
_pending = {
    "handler": None,
    "data": {},
    "step": 0,
}

# Bluetooth (disabled for Pi by default)
_bt = None
print("Bluetooth Connection Disabled (Pi Mode)")

# Conversation Tracking (Continuous Conversation)
_last_interaction_time = 0.0
CONVERSATION_WINDOW = 10.0  # seconds

# TTS Capability Detection
_HAS_ESPEAK = shutil.which("espeak-ng") is not None

# Audio mapping for mouth sync
_audio_level = 0.0
_audio_lock = threading.Lock()
_mouth_multiplier = 50
_current_mouth_h = 0.0
_pyaudio_instance = pyaudio.PyAudio()

# Platform Detection
IS_PI = False
tk = None         # Emulator only
ImageTk = None   # Emulator only

try:
    from luma.core.interface.serial import spi
    from luma.core.render import canvas
    from luma.lcd.device import ili9341
    IS_PI = True
except ImportError:
    IS_PI = False
    print("--- INFO: Pi Hardware not found. Attempting Windows Emulator... ---")
    try:
        import tkinter as tk
        from PIL import ImageTk
    except ImportError:
        print("--- WARNING: Emulator GUI libraries (Tkinter/PIL) missing. ---")

# ---------- WINDOWS EMULATOR CLASSES ----------
class MockDevice:
    """Simulates a luma.lcd device using a Tkinter window."""
    def __init__(self, width=320, height=240):
        self.width = width
        self.height = height
        self.root = tk.Tk()
        self.root.title("Mimobot Emulator")
        self.root.resizable(False, False)
        self.canvas_widget = tk.Canvas(self.root, width=width, height=height, bg="black")
        self.canvas_widget.pack()
        self.image_label = None
        self.current_frame = None

    def display(self, image):
        """Update the Tkinter window with the PIL image."""
        self.current_frame = ImageTk.PhotoImage(image)
        if self.image_label is None:
            self.image_label = self.canvas_widget.create_image(0, 0, anchor="nw", image=self.current_frame)
        else:
            self.canvas_widget.itemconfig(self.image_label, image=self.current_frame)
        self.root.update()

class MockCanvas:
    """Mimics luma canvas context manager."""
    def __init__(self, device):
        self.device = device
        self.image = Image.new("RGB", (device.width, device.height), "black")
        self.draw = ImageDraw.Draw(self.image)
    def __enter__(self):
        return self.draw
    def __exit__(self, type, value, traceback):
        self.device.display(self.image)

# ---------------------------------------------------------------------------
# Wake words & natural responses
# ---------------------------------------------------------------------------
WAKE_WORDS = [
    "mimobot", "mimo bot", "hey mimo", "hey mimobot",
    "robo", "hey robo", "robot", "hey robot",
    "mimo", "memo", "demo", "heyy mimo", "heyy robo", "mimo mimo"
]

# Response pools per intent (micro-variation for personality)
ACK_RESPONSES = ["yeah?", "hmm?", "go ahead", "yes?", "I'm listening", "what's up?", "tell me"]
CONFUSED_RESPONSES = ["huh?", "say that again?", "didn't catch that", "what was that?", "come again?", "sorry?"]
THANK_RESPONSES = ["no problem", "anytime", "got you", "sure thing", "happy to help", "you're welcome"]
GREETING_RESPONSES = ["hey!", "hello!", "what's up?", "hi there!", "yo!", "hey, how can I help?"]
MEMORY_CONFIRM = ["got it.", "noted.", "I'll remember that.", "stored.", "okay, remembered."]
FALLBACK_RESPONSES = [
    "hmm, I'm not sure what to do with that.",
    "I didn't quite get that. Try saying help.",
    "sorry, I don't know how to handle that yet.",
    "that's new to me. Try something else?",
]

def pick(lst):
    """Pick a random response from a pool."""
    return random.choice(lst)

def format_item(item):
    """Fix grammar for items (singular vs plural)."""
    # Check the last word for pluralization (e.g., "my keys" -> "keys")
    words = item.lower().split()
    last_word = words[-1] if words else ""
    if last_word.endswith("s") and not last_word.endswith("ss"): # Basic check for keys but not glass
        return f"your {item} are"
    else:
        return f"your {item} is"

CITY = "Pune"  # Default city for weather

# Conversation memory — tracks last topic for pronoun resolution
_last_topic = None  # e.g. "keys"

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
    global _state_callback
    _state_callback = fn

def _set_state(state: str):
    if _state_callback:
        try:
            _state_callback(state)
        except Exception as e:
            logging.exception("State callback error: %s", e)
    _send_bt(f"STATE:{state}")

def _beep(freq=800, duration=150):
    if winsound:
        try:
            winsound.Beep(freq, duration)
        except Exception:
            pass

# ---------------------------------------------------------------------------
# Text-to-Speech (Streaming + Mouth Sync)
# ---------------------------------------------------------------------------
def speak(text: str, rate: int = 160, volume: float = 1.0, block: bool = False):
    """
    Speaks text using espeak-ng pipeline to capture real-time amplitude.
    Streams audio to PyAudio while updating _audio_level.
    """
    def _run():
        global _audio_level, _last_interaction_time
        time.sleep(random.uniform(0.3, 0.8))

        with _speak_lock:
            _set_state("speaking")
            try:
                # 1. Start espeak-ng process ONLY if available
                if not _HAS_ESPEAK:
                    raise FileNotFoundError("espeak-ng not found")

                cmd = ["espeak-ng", "-s", str(rate), "-a", str(int(volume * 100)), "--stdout", text]
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                
                # 2. Open WAV header from pipe (it's brief, usually 44 bytes)
                # We read a small buffer first to handle the header
                header = proc.stdout.read(44)
                if not header:
                    raise Exception("No audio data generated by espeak-ng")

                with wave.open(io.BytesIO(header + proc.stdout.read(1024)), 'rb') as wf:
                    chunk_size = 1024
                    stream = _pyaudio_instance.open(
                        format=_pyaudio_instance.get_format_from_width(wf.getsampwidth()),
                        channels=wf.getnchannels(),
                        rate=wf.getframerate(),
                        output=True
                    )

                    # 3. Stream from pipe in chunks
                    while True:
                        data = proc.stdout.read(chunk_size)
                        if not data:
                            break
                        
                        # Calculate RMS for Mouth Sync
                        samples = np.frombuffer(data, dtype=np.int16)
                        if len(samples) > 0:
                            rms = np.sqrt(np.mean(np.square(samples.astype(np.float32))))
                            with _audio_lock:
                                _audio_level = min(1.0, rms / 8000.0)
                        
                        stream.write(data)

                    stream.stop_stream()
                    stream.close()
                    with _audio_lock:
                        _audio_level = 0.0

            except Exception as e:
                print(f"--- DEBUG: Streaming TTS Error: {e} ---", flush=True)
                with _audio_lock:
                    _audio_level = 0.0
                if engine:
                    # Simulate mouth movement for Windows fallback
                    def _jitter():
                        start_time = time.time()
                        while current_expression == "speaking":
                            with _audio_lock:
                                # Random jitter between 0.1 and 0.6 to simulate volume
                                random_vol = random.uniform(0.1, 0.6)
                                _audio_level = random_vol
                            time.sleep(0.05)
                            if time.time() - start_time > 15: break # Max 15s catch-all
                        with _audio_lock: _audio_level = 0.0

                    threading.Thread(target=_jitter, daemon=True).start()
                    
                    engine.setProperty('rate', rate)
                    engine.setProperty('volume', volume)
                    engine.say(text)
                    engine.runAndWait()
            
            _set_state("idle")
            _last_interaction_time = time.time()

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
    """Store item with location and timestamp. Overwrites if exists."""
    global _last_topic
    item_key = item.lower().strip()
    loc_clean = location.strip()
    
    # Avoid 'the the car' — check if already prefixed
    prefixes = ("the ", "my ", "your ", "a ", "an ", "in ", "on ", "at ")
    if not loc_clean.lower().startswith(prefixes):
        loc_clean = f"the {loc_clean}"
        
    with _memory_lock:
        _memory[item_key] = {
            "location": loc_clean,
            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        _save_memory()
    _last_topic = item_key
    speak(f"{pick(MEMORY_CONFIRM)} {format_item(item_key)} in {loc_clean}.")

def recall(query: str):
    """Smart recall with fuzzy matching and pronoun resolution."""
    global _last_topic
    words = query.lower().split()

    # Pronoun resolution: "where are they?" -> use last topic
    pronouns = {"they", "them", "it", "that", "those", "this"}
    if any(p in words for p in pronouns) and _last_topic:
        candidate = _last_topic
    else:
        # Try to extract the item after "my"
        candidate = None
        if "my" in words:
            idx = words.index("my")
            remaining = words[idx + 1:]
            fillers = {"is", "are", "the", "a", "an", "somewhere", "anywhere", "at", "in", "on"}
            remaining = [w for w in remaining if w not in fillers]
            if remaining:
                candidate = " ".join(remaining)
        if not candidate:
            fillers = {"where", "is", "are", "my", "the", "did", "i", "leave", "put", "keep", "kept", "find"}
            meaningful = [w for w in words if w not in fillers]
            candidate = meaningful[-1] if meaningful else words[-1]

    with _memory_lock:
        # Extract location from multi-entity memory format
        def _get_loc(val):
            if isinstance(val, dict):
                return val.get("location", "unknown")
            return val  # backward compat with old flat format

        # Exact match first
        if candidate in _memory:
            data = _memory[candidate]
            loc = _get_loc(data)
            _last_topic = candidate
            
            # Use timestamp for context
            timestr = ""
            if isinstance(data, dict) and "time" in data:
                entry_time = datetime.datetime.strptime(data["time"], "%Y-%m-%d %H:%M")
                now = datetime.datetime.now()
                if entry_time.date() == now.date():
                    timestr = " earlier today"
                else:
                    timestr = " recently"
            
            speak(f"{format_item(candidate)} in {loc}{timestr}.")
            return candidate, loc
        # Fuzzy match
        matches = get_close_matches(candidate, _memory.keys(), n=1, cutoff=0.5)
        if matches:
            key = matches[0]
            data = _memory[key]
            loc = _get_loc(data)
            _last_topic = key
            
            timestr = ""
            if isinstance(data, dict) and "time" in data:
                entry_time = datetime.datetime.strptime(data["time"], "%Y-%m-%d %H:%M")
                now = datetime.datetime.now()
                if entry_time.date() == now.date():
                    timestr = " earlier today"
                else:
                    timestr = " recently"
                    
            speak(f"{format_item(key)} in {loc}{timestr}.")
            return key, loc
        else:
            speak(f"Hmm, I don't remember where your {candidate} is.")
            return None, None

def _parse_memory_store(txt: str):
    """Parse natural memory storage phrases.
    Catches: kept, left, put, placed, is, are, think
    """
    patterns = [
        r"(?:i\s+)?(?:think\s+)?(?:i\s+)?(?:kept|left|put|placed)\s+(?:my\s+)?(.+?)\s+(?:in|on|at|under|near|behind|beside|next to|inside)\s+(?:the\s+)?([a-zA-Z\s]{1,20})",
        r"my\s+(.+?)\s+(?:is|are)\s+(?:in|on|at|under|near|behind|beside|next to|inside)\s+(?:the\s+)?([a-zA-Z\s]{1,20})",
        r"(.+?)\s+(?:is|are)\s+(?:in|on|at|under|near|behind|beside|next to|inside)\s+(?:the\s+)?([a-zA-Z\s]{1,20})",
        r"(?:my\s+)?(.+?)\s+in\s+(?:the\s+)?([a-zA-Z\s]{1,20})", # Relaxed: "keys in the car"
    ]
    for pattern in patterns:
        match = re.search(pattern, txt)
        if match:
            item = match.group(1).strip()
            location = match.group(2).strip()
            # Filter out obviously wrong parses
            if len(item) > 0 and len(location) > 0 and len(item) < 30:
                # Basic cleaning of leading 'it' or 'they'
                item = re.sub(r"^(it|they|them|that|those)\s+", "", item)
                return item, location
    return None, None

# ---------------------------------------------------------------------------
# Reminder system
# ---------------------------------------------------------------------------
def _parse_time(text: str) -> float:
    now = datetime.datetime.now()
    txt = text.lower().strip()
    if txt.startswith("in "):
        parts = txt[3:].split()
        try:
            num = int(parts[0])
            unit = parts[1] if len(parts) > 1 else "seconds"
            if "min" in unit:
                return num * 60
            elif "hour" in unit:
                return num * 3600
            else:
                return num
        except Exception:
            pass
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
    return 10.0

def set_reminder(task: str, when: str):
    delay = _parse_time(when)
    speak(f"Alright, I'll remind you about {task}.")

    def _reminder_thread():
        time.sleep(delay)
        _set_state("alert")
        speak(f"Hey! Reminder: {task}")

    threading.Thread(target=_reminder_thread, daemon=True).start()

# ---------------------------------------------------------------------------
# Time & Date
# ---------------------------------------------------------------------------
def tell_time():
    now = datetime.datetime.now()
    hour = now.strftime("%I").lstrip("0")
    minute = now.strftime("%M")
    ampm = now.strftime("%p")
    speak(f"It's {hour}:{minute} {ampm}.")

def tell_date():
    now = datetime.datetime.now()
    speak(f"Today is {now.strftime('%A, %B %d, %Y')}.")

# ---------------------------------------------------------------------------
# Weather & AQI (via wttr.in — no API key needed)
# ---------------------------------------------------------------------------
def tell_weather():
    if not _HAS_URLLIB:
        speak("Sorry, I can't check the weather right now.")
        return

    def _fetch():
        _set_state("thinking")
        try:
            url = f"https://wttr.in/{CITY}?format=j1"
            req = urllib.request.Request(url, headers={"User-Agent": "Mimobot/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            
            current = data['current_condition'][0]
            temp = current['temp_C']
            desc = current['weatherDesc'][0]['value']
            speak(f"It's {temp} degrees and {desc.lower()} in {CITY}.")
        except Exception as e:
            print(f"--- DEBUG: Weather fetch error: {e} ---", flush=True)
            speak("Sorry, I couldn't get the weather right now.")

    threading.Thread(target=_fetch, daemon=True).start()

def tell_air_conditions():
    if not _HAS_URLLIB:
        speak("Sorry, I can't check the air conditions right now.")
        return

    def _fetch():
        _set_state("thinking")
        try:
            url = f"https://wttr.in/{CITY}?format=j1"
            req = urllib.request.Request(url, headers={"User-Agent": "Mimobot/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                
            current = data['current_condition'][0]
            humidity = current['humidity']
            h_val = int(humidity)
            
            if h_val < 40:
                feel = "dry and clear"
            elif h_val < 70:
                feel = "moderate"
            else:
                feel = "quite humid"
                
            speak(f"Air conditions in {CITY} feel {feel} with {humidity} percent humidity.")
        except Exception as e:
            print(f"--- DEBUG: Air conditions fetch error: {e} ---", flush=True)
            speak("Sorry, I couldn't check the air conditions right now.")

    threading.Thread(target=_fetch, daemon=True).start()

# ---------------------------------------------------------------------------
# Conversation flow handling (multi-step)
# ---------------------------------------------------------------------------
def _reset_pending():
    _pending["handler"] = None
    _pending["data"] = {}
    _pending["step"] = 0

# ----- Reminder multi-step -----
def _reminder_step_task(task_text: str):
    _pending["data"]["task"] = task_text
    speak("When should I remind you?")
    _pending["handler"] = _reminder_step_time

def _reminder_step_time(time_text: str):
    task = _pending["data"].get("task", "")
    set_reminder(task, time_text)
    _reset_pending()

# ---------------------------------------------------------------------------
# Main command router (Mimobot personality)
# ---------------------------------------------------------------------------
def handle_command(text: str):
    """Route a command after wake-word activation."""
    if _pending["handler"]:
        _pending["handler"](text)
        return

    txt = text.lower().strip()
    print(f"--- DEBUG: Routing command: '{txt}' ---", flush=True)

    # --- PRIORITY 1: Memory ---
    # Store memory
    item, location = _parse_memory_store(txt)
    if item and location:
        _set_state("happy")
        remember(item, location)
        return

    # Recall memory (including pronoun: "where are they?")
    if ("where" in txt and ("my" in txt or any(p in txt for p in ["they", "them", "it"]))) or \
       ("did" in txt and "leave" in txt) or \
       ("find" in txt and "my" in txt):
        recall(txt)
        return

    # --- PRIORITY 2: System info ---
    if "time" in txt and ("what" in txt or "tell" in txt or "current" in txt):
        tell_time()
        return

    if "date" in txt and ("what" in txt or "tell" in txt or "today" in txt):
        tell_date()
        return

    if "day" in txt and ("what" in txt or "today" in txt):
        tell_date()
        return

    # --- PRIORITY 3: External info ---
    if "weather" in txt:
        tell_weather()
        return

    if "aqi" in txt or "air quality" in txt or "pollution" in txt or "air condition" in txt:
        tell_air_conditions()
        return

    # --- Reminders ---
    if "remind" in txt:
        speak("Sure. What should I remind you about?")
        _pending["handler"] = _reminder_step_task
        _pending["step"] = 1
        return

     # --- Help ---
    if "help" in txt or "what can you do" in txt:
        speak("I can remember things, tell you the time, check the weather, and set reminders. Just ask naturally!")
        return

    # --- Small Talk / Conversations ---
    if "what are you doing" in txt or "what r u doing" in txt:
        speak("Just hanging out in the wires, ready to help you!")
        return

    if "how are you" in txt or "how r u" in txt:
        speak("I'm doing great! My circuits are nice and warm.")
        return

    if "who are you" in txt:
        speak("I am Mimobot, your smart assistant.")
        return

    # --- Greetings ---
    if txt in ("hello", "hi", "hey", "sup", "what's up", "howdy"):
        speak(pick(GREETING_RESPONSES))
        return

    # --- Thank you ---
    if "thank" in txt or "thanks" in txt:
        speak(pick(THANK_RESPONSES))
        return

    # --- Fallback ---
    print(f"--- DEBUG: No command route found for '{txt}' ---", flush=True)
    speak(pick(FALLBACK_RESPONSES))

# ---------------------------------------------------------------------------
# Voice loop – runs in its own daemon thread
# ---------------------------------------------------------------------------
def _listen_once(timeout: int = 5):
    try:
        with sr.Microphone() as source:
            print("--- DEBUG: Listening... ---", flush=True)
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            try:
                audio = recognizer.listen(source, phrase_time_limit=5, timeout=timeout)
                text = recognizer.recognize_google(audio).lower()
                print(f"--- DEBUG: Recognized: '{text}' ---", flush=True)
                return text
            except sr.WaitTimeoutError:
                return ""
            except Exception as e:
                print(f"--- DEBUG: Recognition Error: {type(e).__name__} ---", flush=True)
                return ""
    except Exception as e:
        print(f"--- DEBUG: Microphone Init Error: {e} ---", flush=True)
        return ""

def _contains_wake_word(text: str) -> bool:
    """Check if text contains any wake word using regex for word boundaries."""
    txt = text.lower()
    # Prevents triggering on 'mimosa' or 'robotics'
    return bool(re.search(r"\b(mimo|mimobot|robo|robot|memo|demo)\b", txt))

def _strip_wake_word(text: str) -> str:
    """Remove wake word from text to get the actual command."""
    txt = text.lower()
    # Use re.sub with word boundaries to cleanly remove wake words
    txt = re.sub(r"\b(mimobot|mimo bot|hey mimo|hey mimobot|robo|hey robo|robot|hey robot|mimo|memo|demo|heyy mimo|heyy robo|mimo mimo)\b", "", txt).strip()
    return txt.strip()

def _voice_loop():
    print("--- DEBUG: Voice Loop Started ---", flush=True)
    while True:
        try:
            # --- SAFETY GUARD --- 
            # Wait if the bot is still speaking to prevent hearing its own echo
            while current_expression == "speaking":
                time.sleep(0.1)
                
            # Small buffer after speaking to let the room settle
            if time.time() - _last_interaction_time < 0.5:
                time.sleep(0.5)

            # PRIORITY 1: Multi-step pending command
            if _pending["handler"]:
                print(f"--- DEBUG: Listening for pending step {_pending['step']} ---", flush=True)
                _set_state("listening")
                text = _listen_once(timeout=10)
                if text:
                    handle_command(text)
                else:
                    speak(pick(CONFUSED_RESPONSES), block=True)
                    _reset_pending()
                continue

            # PRIORITY 2: Check for active conversation (Continuous Mode)
            # If we just interacted within the window, skip wake word
            in_conversation = (time.time() - _last_interaction_time < CONVERSATION_WINDOW)

            if in_conversation:
                print("--- DEBUG: In Active Conversation (Skipping wake word) ---", flush=True)
                _set_state("listening")
                text = _listen_once(timeout=5)
            else:
                _set_state("idle")
                text = _listen_once(timeout=3)

            if not text:
                continue

            # Logic: If already in conversation, we process immediately.
            # Otherwise, check for wake word.
            is_wake = _contains_wake_word(text)
            
            if in_conversation or is_wake:
                if is_wake:
                    print("--- DEBUG: Wake Word Detected! ---", flush=True)
                    command = _strip_wake_word(text)
                else:
                    command = text

                if command and len(command) > 2:
                    print(f"--- DEBUG: Processing command: '{command}' ---", flush=True)
                    if is_wake: _beep(1000, 100)
                    handle_command(command)
                elif is_wake:
                    # Just the wake word: Acknowledge and wait for the actual command
                    speak(pick(ACK_RESPONSES), block=True)
                    _set_state("listening")
                    command = _listen_once(timeout=4)
                    if command:
                        _beep(1000, 100)
                        handle_command(command)
                    else:
                        speak(pick(CONFUSED_RESPONSES), block=True)

        except Exception as e:
            print(f"--- DEBUG: Voice Loop Iteration Error: {e} ---", flush=True)
            time.sleep(1)


def start():
    """Launch background voice loop."""
    threading.Thread(target=_voice_loop, daemon=True).start()



# ---------- DISPLAY SETTINGS ----------
# ILI9341 Screen Resolution
WIDTH = 320
HEIGHT = 240
BG = "black"
FG = "white"

# ---------- SPI / EMULATOR CONFIGURATION ----------
# Wiring specifically requested for the Raspberry Pi 3B
# DC -> GPIO25 (Pin 22), RST -> GPIO24 (Pin 18)
device = None
if IS_PI:
    try:
        serial_iface = spi(port=0, device=0, gpio_DC=25, gpio_RST=24)
        device = ili9341(serial_iface, width=WIDTH, height=HEIGHT)
    except Exception as e:
        print(f"Hardware Error: {e}. Falling back to Emulator.")
        IS_PI = False

if not IS_PI:
    device = MockDevice(WIDTH, HEIGHT)

# Mock 'canvas' function for Emulator
if not IS_PI:
    def canvas(dev):
        return MockCanvas(dev)

# ---------- UI STATE ----------
current_expression = "idle"
left_eye_height = 50
right_eye_height = 50
is_speaking = False
talk_phase = 0

target_eye_shift_x = 0
current_eye_shift_x = 0
last_shift_time = time.time()

def set_state(state: str):
    """Callback invoked by robo_brain to update physical TFT state."""
    global current_expression, is_speaking
    current_expression = state
    if state == "speaking":
        is_speaking = True
    else:
        is_speaking = False


# ---------- DRAW FACE ----------
def draw_face(draw, offset):
    global left_eye_height, right_eye_height, talk_phase
    global target_eye_shift_x, current_eye_shift_x, last_shift_time
    global _current_mouth_h

    current_time = time.time()

    # 1. Adapt Face Expression Targets
    left_target = 50
    right_target = 50

    if current_expression == "listening":
        left_target = 35 # Slightly raised / focused
        right_target = 35
    elif current_expression == "thinking":
        left_target = 45 
        right_target = 20 # Asymmetrical look
    elif current_expression == "error":
        left_target = 25 # Squinting / hurt
        right_target = 25
    elif current_expression == "happy":
        left_target = 10 # Happy squint / arched eyes
        right_target = 10
    else:
        left_target = 50
        right_target = 50
        
        # Idle Blink logic: blink rapidly every ~4 seconds
        if int(current_time) % 4 == 0 and (current_time * 10) % 10 > 8:
            left_target = 5
            right_target = 5

    # Smooth easing for animations
    left_eye_height += (left_target - left_eye_height) * 0.3
    right_eye_height += (right_target - right_eye_height) * 0.3

    # Background Fill to prevent ghosting
    draw.rectangle((0, 0, WIDTH, HEIGHT), fill=BG)

    # 2. Base positions perfectly scaled and centered for 320x240
    eye_width = 25
    
    # Horizontal eye movement with random pauses ("looking around")
    if current_time - last_shift_time > random.uniform(1.5, 4.5):
        target_eye_shift_x = random.randint(-18, 18)
        last_shift_time = current_time

    # Easing perfectly mimics a sudden dart of the eyes and slow settle
    current_eye_shift_x += (target_eye_shift_x - current_eye_shift_x) * 0.15
    
    left_x = 100 + current_eye_shift_x
    right_x = 220 + current_eye_shift_x
    base_eye_y = 100
    
    # Left eye
    try:
        # rounded_rectangle is cleaner, exists in newer PIL
        draw.rounded_rectangle(
            [left_x, base_eye_y + offset, left_x + eye_width, base_eye_y + offset + left_eye_height], 
            radius=10, fill=FG
        )
        # Right eye
        draw.rounded_rectangle(
            [right_x - eye_width, base_eye_y + offset, right_x, base_eye_y + offset + right_eye_height], 
            radius=10, fill=FG
        )
    except AttributeError:
        # Fallback for very old Pillow installations
        draw.rectangle([left_x, base_eye_y + offset, left_x + eye_width, base_eye_y + offset + left_eye_height], fill=FG)
        draw.rectangle([right_x - eye_width, base_eye_y + offset, right_x, base_eye_y + offset + right_eye_height], fill=FG)

    # 3. Draw Mouth (Centered underneath eyes)
    mouth_center_x = 160
    mouth_y = 170

    if is_speaking: # Real-time Audio Sync
        # Dynamic scaling based on amplitude (Read with lock for thread-safety)
        with _audio_lock:
            level = _audio_level
        target_h = level * _mouth_multiplier
        # Ease into the new height for smoothness
        _current_mouth_h += (target_h - _current_mouth_h) * 0.4
        
        draw.ellipse([mouth_center_x - 15, mouth_y + offset - _current_mouth_h/2, 
                      mouth_center_x + 15, mouth_y + offset + _current_mouth_h/2 + 7], fill=FG)
    elif current_expression == "alert": # Alert/Exclamation
        draw.ellipse([mouth_center_x - 8, mouth_y + offset - 8, 
                      mouth_center_x + 8, mouth_y + offset + 8], fill=FG)
    elif current_expression == "error": # Frown (Arc upper curve)
        # PIL arcs measure from 3 o'clock, increasing clockwise. 180->360 is top half.
        draw.arc([mouth_center_x - 30, mouth_y + offset - 15, 
                  mouth_center_x + 30, mouth_y + offset + 15], start=180, end=360, fill=FG, width=4)
    elif current_expression == "happy": # Giant Smile
        draw.arc([mouth_center_x - 35, mouth_y + offset - 10, 
                  mouth_center_x + 35, mouth_y + offset + 25], start=0, end=180, fill=FG, width=6)
    else: # Smile (Arc lower curve) with subtle mouth breathing
        mouth_breath = math.sin(current_time * 2) * 4
        # 0->180 is bottom half.
        draw.arc([mouth_center_x - 30, mouth_y + offset - 15, 
                  mouth_center_x + 30, mouth_y + offset + 15 + mouth_breath], start=0, end=180, fill=FG, width=4)

# ---------- BOOT SEQUENCE ----------
# 1. Connect UI state to brain
set_state_callback(set_state)
# 2. Start the background daemon loop inside the brain from the background to the front
start()

# ---------- MAIN UI LOOP ----------
print("Starting TFT Rendering Engine on ILI9341...")

try:
    while True:
        # Slight bobbing offset for "breathing" effect
        offset = math.sin(time.time() * 1.5) * 3
        
        # Opens canvas. Background implicitly cleared every frame.
        with canvas(device) as draw:
            draw_face(draw, offset)
            
        time.sleep(0.03) # Lower CPU overhead while keeping it smooth (~33 fps)
except KeyboardInterrupt:
    print("\nExiting UI loop cleanly.")
finally:
    _pyaudio_instance.terminate()
