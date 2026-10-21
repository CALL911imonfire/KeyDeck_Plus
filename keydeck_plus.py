"""
KeyDeck - a customizable on-screen keyboard for Windows.

Run:   python keydeck_plus.py     (keep keydeck_words.py in the same folder)
Build: pip install pyinstaller && pyinstaller --noconsole --onefile --name KeyDeckPlus keydeck_plus.py
Optional: pip install pillow  (JPG and other picture types, smooth scaling, animated pictures)

Highlights
  * Never steals focus - it types into whatever program you were using.
  * Any key can be HELD DOWN (letters, numbers, F-keys, everything):
      - Right-click a key to hold it; click it again to release.
      - Or switch on the "Hold" toolbar button: every left-click then toggles hold.
      - "Release all" lets go of everything.
  * Modifier keys (Shift/Ctrl/Alt/Win) are one-shot by default (release after the
    next key); right-click them to lock them down.
  * Edit Layout: drag keys, drag the bottom-right corner to resize, pick which key
    each button sends, change labels and colors, add / duplicate / delete keys.
  * Loadouts: save as many layouts as you like and switch between them.
  * Keys are sent as hardware scan codes by default (works in most games).
  * Predictive text: a bar of 3 suggestions using a larger built-in vocabulary, starter
    phrase patterns, context-aware ranking, and words/phrases learned as you type. It
    saves them to predict.json in the KeyDeck folder under %APPDATA%. Click a suggestion to type it;
    right-click a suggestion to make it forget that word.

KEYDECK PLUS (this file) adds, on top of everything above:
  * Macro keys: one button types a phrase or runs a key sequence, e.g.
        Thanks for your help!{Enter}      or      {Ctrl+A}{Ctrl+C}{Wait 300}{Alt+Tab}{Ctrl+V}
    Edit Layout -> select a key -> "Program macro...".
  * Mouse keys (Sends list): Left / Right / Middle / Double click, Scroll Up / Down.
    Press one, move the pointer to the target and hold it still; the click fires.
  * Layer keys: a button that switches to another loadout, either for good or just for
    the next key press. Edit Layout -> select a key -> "Layer key...".
  * Dwell clicking: hover and hold still, and KeyDeck clicks for you (toolbar "Dwell" button;
    time, steadiness and repeat in Settings). Works on keys, toolbar, suggestions and menus.
  * Shortcut and macro buttons fire once instead of auto-repeating when held.
  * Swipe typing (hold and drag, or click-to-swipe) with contractions; right-click Backspace
    deletes the last swiped word.
  * Autocorrect, smart capitals and punctuation, adjustable number of suggestions.
  * Speak words aloud, Speak keys (a button that says a phrase) and a caption bar that shows
    what was said.
  * Pictures and animated GIFs on keys, saved inside the layout so shared layouts keep them.
  * Colour themes (including two high-contrast ones), keyboard background colour, per-key
    outline colour and thickness.
  * Switch scanning (row-column) driven by a plain left click, with scanning-friendly layouts.
  * Minimize to a small tab that reopens by resting the pointer on it (no click needed).
  * Import / export of layouts, and example loadouts in the repository.

Notes
  * Windows only. Layout of key codes assumes a US keyboard layout.
  * Windows blocks injected input into programs running as administrator, unless
    KeyDeck is also run as administrator.
"""

import atexit
import collections
import ctypes
import base64
import heapq
import io
import json
import math
import os
import queue
import re
import sys
import subprocess
import threading
import types
import time
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk

IS_WIN = sys.platform == "win32"

# --------------------------------------------------------------------------
# Windows input plumbing
# --------------------------------------------------------------------------
if IS_WIN:
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    ULONG_PTR = ctypes.c_size_t

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                    ("dwExtraInfo", ULONG_PTR)]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                    ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                    ("wParamH", wintypes.WORD)]

    class _INPUTUNION(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]

    user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    user32.SendInput.restype = wintypes.UINT
    user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
    user32.MapVirtualKeyW.restype = wintypes.UINT
    user32.GetParent.argtypes = [wintypes.HWND]
    user32.GetParent.restype = wintypes.HWND
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = ctypes.c_long
    user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
    user32.SetWindowLongW.restype = ctypes.c_long
    user32.GetKeyState.argtypes = [ctypes.c_int]
    user32.GetKeyState.restype = ctypes.c_short
    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    user32.GetCursorPos.restype = wintypes.BOOL
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.WindowFromPoint.argtypes = [wintypes.POINT]
    user32.WindowFromPoint.restype = wintypes.HWND
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.restype = ctypes.c_int
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    kernel32 = ctypes.windll.kernel32
    kernel32.GetCurrentProcessId.argtypes = []
    kernel32.GetCurrentProcessId.restype = wintypes.DWORD

INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
KEYEVENTF_UNICODE = 0x0004
INPUT_MOUSE = 0
MOUSEEVENTF_WHEEL = 0x0800
MOUSE_BUTTON_FLAGS = {"left": (0x0002, 0x0004), "right": (0x0008, 0x0010),
                      "middle": (0x0020, 0x0040)}      # (down, up)
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_APPWINDOW = 0x00040000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020


# --------------------------------------------------------------------------
# Key catalog: name -> (virtual-key code, needs extended flag)
# --------------------------------------------------------------------------
CATALOG = {}
LABELS = {}


def reg(name, vk, ext=False, label=None):
    CATALOG[name] = (vk, ext)
    LABELS[name] = label if label is not None else name


reg("Esc", 0x1B)
for i in range(1, 13):
    reg("F%d" % i, 0x6F + i)
for c in "`1234567890-=":
    reg(c, {"`": 0xC0, "-": 0xBD, "=": 0xBB}.get(c, ord(c) if c.isdigit() else 0))
reg("Backspace", 0x08)
reg("Tab", 0x09)
for c in "QWERTYUIOP":
    reg(c, ord(c))
reg("[", 0xDB)
reg("]", 0xDD)
reg("\\", 0xDC)
reg("Caps Lock", 0x14, label="Caps")
for c in "ASDFGHJKL":
    reg(c, ord(c))
reg(";", 0xBA)
reg("'", 0xDE)
reg("Enter", 0x0D)
reg("LShift", 0xA0, label="Shift")
for c in "ZXCVBNM":
    reg(c, ord(c))
reg(",", 0xBC)
reg(".", 0xBE)
reg("/", 0xBF)
reg("RShift", 0xA1, label="Shift")
reg("LCtrl", 0xA2, label="Ctrl")
reg("LWin", 0x5B, True, label="Win")
reg("LAlt", 0xA4, label="Alt")
reg("Space", 0x20, label="")
reg("RAlt", 0xA5, True, label="Alt")
reg("RWin", 0x5C, True, label="Win")
reg("Menu", 0x5D, True)
reg("RCtrl", 0xA3, True, label="Ctrl")
reg("PrtSc", 0x2C, True)
reg("ScrLk", 0x91)
reg("Pause", 0x13)
reg("Insert", 0x2D, True, label="Ins")
reg("Delete", 0x2E, True, label="Del")
reg("Home", 0x24, True)
reg("End", 0x23, True)
reg("PgUp", 0x21, True)
reg("PgDn", 0x22, True)
reg("Up", 0x26, True, label="\u25B2")
reg("Down", 0x28, True, label="\u25BC")
reg("Left", 0x25, True, label="\u25C0")
reg("Right", 0x27, True, label="\u25B6")
reg("Num Lock", 0x90, True, label="Num")
for d in "0123456789":
    reg("Num " + d, 0x60 + int(d), label=d)
reg("Num /", 0x6F, True, label="/")
reg("Num *", 0x6A, label="*")
reg("Num -", 0x6D, label="-")
reg("Num +", 0x6B, label="+")
reg("Num .", 0x6E, label=".")
reg("Num Enter", 0x0D, True, label="Enter")
for i in range(13, 25):
    reg("F%d" % i, 0x6F + i)
reg("Mute", 0xAD)
reg("Vol-", 0xAE)
reg("Vol+", 0xAF)
reg("Next", 0xB0)
reg("Prev", 0xB1)
reg("Stop", 0xB2)
reg("Play/Pause", 0xB3, label="Play")

# Keys that must be sent by virtual-key instead of scan code.
NO_SCAN = {0x13, 0x90, 0x2C, 0xAD, 0xAE, 0xAF, 0xB0, 0xB1, 0xB2, 0xB3}
MOD_VKS = {0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0x5B, 0x5C, 0x10, 0x11, 0x12}
SHIFT_VKS = {0xA0, 0xA1, 0x10}


class KeySender:
    def __init__(self, scancode_mode=True):
        self.scancode_mode = scancode_mode

    def send(self, name, down):
        vk, ext = CATALOG[name]
        if not IS_WIN:
            print("%s %s" % (name, "down" if down else "up"))
            return
        sc = 0
        if self.scancode_mode and vk not in NO_SCAN:
            r = user32.MapVirtualKeyW(vk, 4)  # MAPVK_VK_TO_VSC_EX
            sc = r & 0xFF
            if (r >> 8) in (0xE0, 0xE1):
                ext = True
        flags = 0
        if sc:
            wvk, wscan = 0, sc
            flags |= KEYEVENTF_SCANCODE
        else:
            wvk, wscan = vk, 0
        if ext:
            flags |= KEYEVENTF_EXTENDEDKEY
        if not down:
            flags |= KEYEVENTF_KEYUP
        inp = INPUT(type=INPUT_KEYBOARD)
        inp.u.ki = KEYBDINPUT(wVk=wvk, wScan=wscan, dwFlags=flags, time=0, dwExtraInfo=0)
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def unicode_char(self, ch):
        """Type any character (accents, symbols, emoji) as Unicode text."""
        if not IS_WIN:
            print("unicode %r" % ch)
            return
        data = ch.encode("utf-16-le")
        for i in range(0, len(data), 2):
            unit = data[i] | (data[i + 1] << 8)
            for up in (False, True):
                flags = KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if up else 0)
                inp = INPUT(type=INPUT_KEYBOARD)
                inp.u.ki = KEYBDINPUT(wVk=0, wScan=unit, dwFlags=flags, time=0, dwExtraInfo=0)
                user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def _mouse(self, flags, data=0):
        inp = INPUT(type=INPUT_MOUSE)
        inp.u.mi = MOUSEINPUT(dx=0, dy=0, mouseData=data & 0xFFFFFFFF, dwFlags=flags,
                              time=0, dwExtraInfo=0)
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def mouse_click(self, button, double=False):
        """Click at the current pointer position."""
        if not IS_WIN:
            print("mouse %s%s" % (button, " x2" if double else ""))
            return
        down, up = MOUSE_BUTTON_FLAGS[button]
        for _ in range(2 if double else 1):
            self._mouse(down)
            self._mouse(up)

    def mouse_wheel(self, direction):
        """One wheel notch at the current pointer position (+1 up, -1 down)."""
        if not IS_WIN:
            print("wheel %+d" % direction)
            return
        self._mouse(MOUSEEVENTF_WHEEL, 120 * direction)


# --------------------------------------------------------------------------
# Storage
# --------------------------------------------------------------------------
CONFIG_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~/.config"), "KeyDeck")
LOADOUT_DIR = os.path.join(CONFIG_DIR, "loadouts")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
PREDICT_FILE = os.path.join(CONFIG_DIR, "predict.json")
DEFAULT_SETTINGS = {"loadout": "", "unit": 38, "opacity": 1.0, "scancode": True,
                    "topmost": True, "oneshot": True, "repeat": True,
                    "predict": True, "learn": True, "mouse_delay": 0.7,
                    "dwell": False, "dwell_time": 1.0, "dwell_tol": 12,
                    "dwell_repeat": False, "dwell_ring": True, "dwell_button": True,
                    "autocorrect": "off", "swipe": False, "swipe_space": True,
                    "capitalize": True, "smart_punct": True,
                    "speak": False, "speak_rate": 0, "speak_volume": 100,
                    "theme": "dark", "swipe_style": "drag", "bg_color": "",
                    "scan": False, "scan_speed": 1.0, "scan_first": 0.5, "scan_loops": 3,
                    "suggest_count": 3, "animate_pictures": True,
                    "min_pos": "bc", "min_open": 0.0, "show_caption": True}


def load_settings():
    s = dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            s.update(json.load(f))
        for gone in ("tray", "hotkey_on", "hotkey"):      # removed features
            s.pop(gone, None)
    except Exception:
        pass
    return s


def save_settings(s):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(s, f, indent=2)
    except Exception:
        pass


def list_loadouts():
    try:
        return sorted(f[:-5] for f in os.listdir(LOADOUT_DIR) if f.lower().endswith(".json"))
    except Exception:
        return []


def safe_name(name):
    keep = "".join(ch for ch in name if ch.isalnum() or ch in " -_").strip()
    return keep


def new_key_dict(name, x, y, w=1.0, h=1.0, label=None, label2="", color="", fg="", edge="", edge_px=None):
    return {"key": name, "label": LABELS.get(name, name) if label is None else label,
            "label2": label2, "x": x, "y": y, "w": w, "h": h, "color": color, "fg": fg,
            "edge": edge, "edge_px": edge_px}


def default_layout():
    keys = []

    def add(name, x, y, w=1.0, h=1.0, label=None, label2=""):
        keys.append(new_key_dict(name, x, y, w, h, label, label2))

    add("Esc", 0, 0)
    for i in range(4):
        add("F%d" % (i + 1), 2 + i, 0)
    for i in range(4):
        add("F%d" % (i + 5), 6.5 + i, 0)
    for i in range(4):
        add("F%d" % (i + 9), 11 + i, 0)
    add("PrtSc", 15.25, 0)
    add("ScrLk", 16.25, 0)
    add("Pause", 17.25, 0)

    shifted = dict(zip("`1234567890-=", "~!@#$%^&*()_+"))
    for i, c in enumerate("`1234567890-="):
        add(c, i, 1.5, label2=shifted[c])
    add("Backspace", 13, 1.5, 2)
    add("Insert", 15.25, 1.5)
    add("Home", 16.25, 1.5)
    add("PgUp", 17.25, 1.5)

    add("Tab", 0, 2.5, 1.5)
    row = "QWERTYUIOP[]"
    sh2 = {"[": "{", "]": "}"}
    for i, c in enumerate(row):
        add(c, 1.5 + i, 2.5, label2=sh2.get(c, ""))
    add("\\", 13.5, 2.5, 1.5, label2="|")
    add("Delete", 15.25, 2.5)
    add("End", 16.25, 2.5)
    add("PgDn", 17.25, 2.5)

    add("Caps Lock", 0, 3.5, 1.75)
    sh3 = {";": ":", "'": '"'}
    for i, c in enumerate("ASDFGHJKL;'"):
        add(c, 1.75 + i, 3.5, label2=sh3.get(c, ""))
    add("Enter", 12.75, 3.5, 2.25)

    add("LShift", 0, 4.5, 2.25)
    sh4 = {",": "<", ".": ">", "/": "?"}
    for i, c in enumerate("ZXCVBNM,./"):
        add(c, 2.25 + i, 4.5, label2=sh4.get(c, ""))
    add("RShift", 12.25, 4.5, 2.75)
    add("Up", 16.25, 4.5)

    add("LCtrl", 0, 5.5, 1.25)
    add("LWin", 1.25, 5.5, 1.25)
    add("LAlt", 2.5, 5.5, 1.25)
    add("Space", 3.75, 5.5, 6.25)
    add("RAlt", 10, 5.5, 1.25)
    add("RWin", 11.25, 5.5, 1.25)
    add("Menu", 12.5, 5.5, 1.25)
    add("RCtrl", 13.75, 5.5, 1.25)
    add("Left", 15.25, 5.5)
    add("Down", 16.25, 5.5)
    add("Right", 17.25, 5.5)

    nx = 18.5
    add("Num Lock", nx, 1.5)
    add("Num /", nx + 1, 1.5)
    add("Num *", nx + 2, 1.5)
    add("Num -", nx + 3, 1.5)
    for i, d in enumerate("789"):
        add("Num " + d, nx + i, 2.5)
    add("Num +", nx + 3, 2.5, 1, 2)
    for i, d in enumerate("456"):
        add("Num " + d, nx + i, 3.5)
    for i, d in enumerate("123"):
        add("Num " + d, nx + i, 4.5)
    add("Num Enter", nx + 3, 4.5, 1, 2)
    add("Num 0", nx, 5.5, 2)
    add("Num .", nx + 2, 5.5)
    return keys


# --------------------------------------------------------------------------
# Predictive text
#
# A small word model that learns from what you type on KeyDeck:
#   uni  - how often each word was used
#   bi   - which word tends to follow a given word
#   tri  - which word tends to follow a given pair of words (your common phrases)
# A brand-new word has to be typed twice before it is learned, which keeps one-off
# typos and button-mashing out of the dictionary.
# --------------------------------------------------------------------------
SEED_WORDS = """
the be to of and a in that have i it for not on with he as you do at this but his by from
 they we say her she or an will my one all would there their what so up out if about who get
 which go me when make can like time no just him know take people into year your good some
 could them see other than then now look only come its over think also back after use two how
 our work first well way even new want because any these give day most us is was are were been
 has had did does said made went got here very where much through before right too mean old
 same tell boy follow came show small large every great still own under last never let begin
 life always those both between might next while found should home start help hand high keep
 away put need feel turn ask few part place world find thing many off again why live long little
 man cannot call really something nothing everything someone anyone yes okay ok sorry thanks
 thank please hello hi hey bye goodbye morning night evening today tomorrow tonight yesterday
 soon later already maybe probably definitely actually basically anyway however though although
 until since without within during against around another better best bad worse worst love hate
 happy sad glad funny sure true real nice cool awesome wait stop going doing being having making
 getting looking coming trying using working playing talk talking says asked told called text
 message email phone game play played player level farm crop crops collect harvest plant water grow
 money coin coins buy sell trade shop store item items quest team friend friends family mom dad
 brother sister school class teacher homework test study read write book watch movie video music
 song eat food lunch dinner breakfast drink hungry tired sleep bed late early busy free ready done
 finish finished started open close big short fast slow hard easy question answer idea problem reason
 point week month weekend minute minutes hour hours second seconds person name number things stuff
 lot lots kind sort type i'm i'll i've i'd you're you'll you've we're we'll we've they're they'll
 it's that's there's what's who's let's don't doesn't didn't can't couldn't won't wouldn't shouldn't
 isn't aren't wasn't weren't haven't hasn't hadn't

above accept account across act action activity add address adult advice afraid afternoon age ago agree
 ahead air allow almost alone along already although amazing amount animal answer appear apple area arm
 art artist ask attention aunt available avoid awake baby back background balance ball bank base basic
 beach beat beautiful became become bed bedroom begin behavior behind believe below benefit beside
 better beyond bicycle bill birthday black blue board body book borrow bottom box boy brain break bring
 build building business buy cake calculate camera camp car card care careful carry case cat catch cause
 center certain chair chance change character charge check child choice choose city claim clean clear
 client clock close clothes cloud code coffee cold college color come comfortable common company complete
 computer concern condition consider continue control conversation cook copy correct cost could count country
 couple course create creative cross crowd cry culture customer cut daily dance danger dark data date daughter
 dead deal death decide decision deep degree depend describe design desk detail develop device difference difficult
 dinner direction discover discuss disease doctor dog door download draw dream drive drop during each early earth
 east education effect effort eight either else end energy enjoy enough enter entire environment error especially
 establish even event ever every everybody everyone evidence example experience explain eye face fact fail fall family
 famous far farm father feature feel feeling few field figure fill film final finally financial finish fire first fish
 five floor fly focus follow food foot force form forward four free fresh friend front full fun future game garden gas
 general get girl give glass go goal god gold gone good government great green ground group grow guess gun guy
 habit half happen happy hard health hear heart heavy help high history hit hold hole holiday hope hospital hot hotel
 house however huge human hundred hurt idea identify image imagine important improve include increase indeed index
 individual industry information inside instead interest internet interview introduce invite involve issue item itself
 jacket job join joke journey joy judge jump just keep key kid kill kind kitchen knee know knowledge language large last
 late laugh law lead learn least leave left leg legal less lesson let letter level library lie life light likely line list
 listen little local location lock long lose loss loud low machine main major make male manage manager many map market
 matter may meal mean measure media medical meet memory mention message method middle might mile mind minute miss model
 modern moment money month mood morning mother mountain mouth move movement movie much music must name nation natural
 near necessary need neighbor never new news next nice night nine nobody noise none normal north note nothing notice
 number object obvious occur ocean offer office often okay old once one online only open opinion opportunity option order
 ordinary organization original other outside over own page pain paper parent park part party pass past path patient pattern
 pay peace people perfect perhaps period person personal phone photo physical picture piece place plan plant play player
 please point police policy poor popular position possible power practice prefer prepare present president press pretty
 prevent price primary print private problem process produce product program project promise proper protect prove provide
 public purpose push put quality question quick quickly quiet quite race raise range rate rather reach read reader ready
 real realize reason receive recent recognize record red reduce refer reflect regular relationship release remember
 remove rent repair repeat replace reply report request require research resource respect respond response rest result return
 review rich ride right rise risk road role room rule run safe safety same save say scene school science screen search season
 second section see seem sell send sense sentence separate serious serve service set seven several share she ship shirt shoe
 shoot shop short should shoulder show shut side sign simple simply since sing single sister sit site situation six size skill
 skin sleep small smart smile social society software solution someone something sometimes son song soon sound source south
 space speak special specific speed spend sport spring stand standard start state statement stay step still stock stop story
 street strong student study subject succeed success such suddenly suggest summer support sure surface system table take talk
 task taste teach teacher team technology tell ten term test than thank theory thing think third though thought thousand
 three through throw thus ticket time tiny title today together told tomorrow tone tool top topic total touch town track trade
 train training travel treat tree trial trip trouble true truth try turn twelve twenty twice two type understand unit university
 until update upon use useful user usual usually value various version video view visit voice wait walk wall want war warm
 watch water way we wear weather website wedding week weight welcome west what whatever wheel wheelchair when where whether
 which while white whole whose wide wife wild win wind window winter wish within woman wonder word work worker world worry
 worth write writer wrong yard year yellow yes yesterday yet young yourself

can't cannot won't wouldn't shouldn't couldn't isn't aren't wasn't weren't haven't hasn't hadn't doesn't don't didn't
 i've i'll i'd i'm you're you'll you've you'd we're we'll we've they'd they'll they're they'd it's that's there's what's
 who's let's here's would've could've should've would've would've would've
""".split()

# Lightweight built-in language model. Each line is a short, common sentence or phrase.
# These starter counts make context prediction useful before the user has taught it phrases.
SEED_PHRASES = """
i am happy
i am sorry
i am looking for
i need help
i need to
i want to
i would like to
i don't know
i don't think so
i can't do that
i can do it
i have a question
i have to go
i will be there
i'll be back
i'm going to
i'm trying to
i'm not sure
i think that
i think so
thank you very much
thank you for your help
how are you
how do you do
what do you mean
what do you think
what is this
what is that
where are you
where is it
when are you coming
can you help me
can you tell me
could you please
would you like to
let me know
let me see
as soon as possible
at the same time
one of the most
in order to
for example
on the other hand
because of that
I don't know
there is a way
there are many
it is important
it would be nice
that sounds good
that makes sense
have a good day
have a good night
good to know
nice to meet you
see you later
talk to you later
I'll let you know
I'm glad you
I'm going to be
I want to make
I need to get
I have been
I would have
if you want
do you want to
do you have a
are you sure
are you okay
it looks like
it seems like
this is the way
this is a good
this is not
I appreciate it
no problem at all
please let me know
thanks for your help
thanks for letting me know
what happened to
how much is
how long does
how long have
a little bit
more than that
less than that
as far as I know
I agree with you
I don't agree
I understand what you mean
I can see that
I was wondering if
the best way to
one thing at a time
make sure that
try to make it
would be able to
could be a good
it depends on
I have no idea
not sure what
the next time
in the future
right now
for a while
at least one
on my own
in front of me
out of the way
I hope you are
I hope that helps
""".lower().splitlines()

SEED_CAPS = {"i": "I", "i'm": "I'm", "i'll": "I'll", "i've": "I've", "i'd": "I'd"}

LEARN_W = 4
IDLE_RESET = 30.0   # seconds without typing before the word context is forgotten
CMD_VKS = {0xA2, 0xA3, 0xA4, 0xA5, 0x5B, 0x5C}
IGNORED_KEYS = {"LShift", "RShift", "LCtrl", "RCtrl", "LAlt", "RAlt", "LWin", "RWin",
                "Caps Lock", "Num Lock", "ScrLk", "Pause", "PrtSc", "Mute", "Vol+",
                "Vol-", "Next", "Prev", "Stop", "Play/Pause"}
BASE_CHARS = "`1234567890-=[]\\;',./"
SHIFTED_CHARS = "~!@#$%^&*()_+{}|:\"<>?"
SHIFT_OF = dict(zip(BASE_CHARS, SHIFTED_CHARS))


class Predictor:
    def __init__(self):
        self.learning = True
        self.buffer = ""        # the word being typed right now (as typed)
        self.hist = []          # previous words, lowercase; "<s>" = sentence start
        self.undo = None        # (word, hist) so Backspace after a space restores the word
        self.prev_ch = None     # the character typed just before the current one
        self.glued = False      # the current word started right after "/", "@", a digit...
        self.typo_check = lambda w: False   # set by KeyDeck: True if w looks like a typo
        self.on_word = None     # called with each finished word (read aloud)
        self._since_save = 0
        self.uni, self.bi, self.tri, self.seq, self.caps, self.pending = {}, {}, {}, {}, {}, {}
        self.load()

    # ---------- storage ----------
    def clear_data(self):
        # Give common words a useful baseline weight; frequently used words rank higher.
        n = len(SEED_WORDS)
        self.uni = {}
        for rank, w in enumerate(SEED_WORDS):
            self.uni.setdefault(w, max(2, 10 - rank * 7 // max(1, n)))
        self.bi, self.tri, self.seq, self.pending = {}, {}, {}, {}
        self.caps = dict(SEED_CAPS)
        self._add_seed_phrases()

    def _add_seed_phrases(self):
        """Load modest starter phrase counts without overpowering personal learning."""
        for line in SEED_PHRASES:
            words = [w for w in line.split() if self.norm(w) is not None]
            for w in words:
                self.uni.setdefault(w, 2)
            prev = []
            for w in words:
                if prev:
                    key = prev[-1]
                    d = self.bi.setdefault(key, {})
                    d[w] = max(d.get(w, 0), 3)
                if len(prev) >= 2:
                    key = prev[-2] + " " + prev[-1]
                    d = self.tri.setdefault(key, {})
                    d[w] = max(d.get(w, 0), 5)
                # Remember longer phrase contexts too, so repeated personal wording
                # can be predicted beyond the last two words.
                for span in range(1, min(8, len(prev)) + 1):
                    context = " ".join(prev[-span:])
                    d = self.seq.setdefault(context, {})
                    d[w] = max(d.get(w, 0), 2 + span)
                prev.append(w)

    def load(self):
        try:
            with open(PREDICT_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            self.uni = {str(k): int(v) for k, v in d["uni"].items()}
            self.bi = {str(k): {str(a): int(b) for a, b in v.items()} for k, v in d["bi"].items()}
            self.tri = {str(k): {str(a): int(b) for a, b in v.items()} for k, v in d["tri"].items()}
            self.seq = {str(k): {str(a): int(b) for a, b in v.items()}
                        for k, v in d.get("seq", {}).items()}
            self.caps = {str(k): str(v) for k, v in d.get("caps", {}).items()}
            self.pending = {str(k): int(v) for k, v in d.get("pending", {}).items()}
            if not self.uni:
                raise ValueError("empty")
            # Upgrade older predict.json files in place: add new defaults while retaining
            # the user's existing counts, learned phrases, and capitalization choices.
            n = len(SEED_WORDS)
            for rank, w in enumerate(SEED_WORDS):
                self.uni.setdefault(w, max(2, 10 - rank * 7 // max(1, n)))
            seed_bi, seed_tri, seed_seq = self.bi, self.tri, self.seq
            self.bi, self.tri, self.seq = {}, {}, {}
            self._add_seed_phrases()
            for key, values in seed_bi.items():
                target = self.bi.setdefault(key, {})
                for word, count in values.items():
                    target[word] = max(target.get(word, 0), count)
            for key, values in seed_tri.items():
                target = self.tri.setdefault(key, {})
                for word, count in values.items():
                    target[word] = max(target.get(word, 0), count)
            for key, values in seed_seq.items():
                target = self.seq.setdefault(key, {})
                for word, count in values.items():
                    target[word] = max(target.get(word, 0), count)
            self.caps = {**SEED_CAPS, **self.caps}
        except Exception:
            self.clear_data()

    def save(self):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            tmp = PREDICT_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"version": 2, "uni": self.uni, "bi": self.bi, "tri": self.tri,
                           "seq": self.seq, "caps": self.caps, "pending": self.pending}, f)
            os.replace(tmp, PREDICT_FILE)
            self._since_save = 0
        except Exception:
            pass

    def forget_all(self):
        self.clear_data()
        self.reset()
        self.save()

    def forget(self, w):
        self.uni.pop(w, None)
        self.pending.pop(w, None)
        self.caps.pop(w, None)
        # Remove the forgotten word as a prediction target, but keep other words
        # learned after the same context.
        for table in (self.bi, self.tri, self.seq):
            for context in list(table):
                table[context].pop(w, None)
                if not table[context]:
                    del table[context]
        self._since_save += 1
        self.save()

    # ---------- learning ----------
    def norm(self, raw):
        """Return the lowercase word if it is worth tracking, else None."""
        w = raw.lower().strip("'")
        if not 1 <= len(w) <= 24:
            return None
        if not all(c.isascii() and (c.isalpha() or c == "'") for c in w):
            return None
        if len(w) == 1 and w not in ("a", "i"):
            return None
        if w not in self.uni:
            if not any(c in "aeiouy" for c in w):
                return None
            if any(w[i] == w[i + 1] == w[i + 2] == w[i + 3] for i in range(len(w) - 3)):
                return None
        return w

    def learn(self, raw):
        w = self.norm(raw)
        if w is None:
            return None
        if not self.learning:
            return w
        if w in self.uni:
            self.uni[w] += LEARN_W
        elif w in self.pending:
            # A word that is one slip from a real word needs more sightings before it is
            # learned, so a typo you make a couple of times doesn't become a suggestion.
            self.pending[w] += 1
            if self.pending[w] < (4 if self.typo_check(w) else 2):
                return w
            del self.pending[w]
            self.uni[w] = LEARN_W * 2
        else:
            self.pending[w] = 1
            if len(self.pending) > 400:
                self.pending.pop(next(iter(self.pending)))
            return w
        self.note_case(w, raw)
        p1 = self.hist[-1] if self.hist else None
        if p1 and (p1 == "<s>" or p1 in self.uni):
            d = self.bi.setdefault(p1, {})
            d[w] = d.get(w, 0) + 1
            if len(self.hist) >= 2:
                p2 = self.hist[-2]
                if p2 == "<s>" or p2 in self.uni:
                    d = self.tri.setdefault(p2 + " " + p1, {})
                    d[w] = d.get(w, 0) + 1
            # Keep word-by-word continuation counts for contexts up to eight words.
            # This lets the model learn recurring sentence fragments and personal phrasing.
            for span in range(1, min(8, len(self.hist)) + 1):
                context_words = self.hist[-span:]
                if all(part == "<s>" or part in self.uni for part in context_words):
                    context = " ".join(context_words)
                    d = self.seq.setdefault(context, {})
                    d[w] = d.get(w, 0) + 1
        self._since_save += 1
        self.prune()
        if self._since_save >= 25:
            self.save()
        return w

    def note_case(self, w, raw):
        """Remember how a word is capitalised (iPhone, London) - but not just because it
        started a sentence, and only after it has been seen that way a few times."""
        votes = self.__dict__.setdefault("cap_votes", {})
        if raw == w:                         # typed in lowercase: it's an ordinary word
            votes.pop(w, None)
            if w in self.caps and w not in SEED_CAPS:
                del self.caps[w]
            return
        if any(c.isupper() for c in raw[1:]) or (
                raw[0].isupper() and self.hist and self.hist[-1] != "<s>"):
            n = votes.get(w, 0) + 1
            if n >= 3 or w in SEED_CAPS:
                self.caps[w] = raw
                votes.pop(w, None)
            else:
                votes[w] = n
                if len(votes) > 400:
                    votes.pop(next(iter(votes)))

    def clean_caps(self, common, proper):
        """Forget capitals learned for ordinary words ("Tree"), keeping real names."""
        for w in list(self.caps):
            if w in common and w not in proper and w not in SEED_CAPS:
                del self.caps[w]

    def prune(self):
        if len(self.uni) > 15000:
            keep = heapq.nlargest(12000, self.uni.items(), key=lambda kv: kv[1])
            self.uni = dict(keep)
        for table, cap in ((self.bi, 6500), (self.tri, 12000), (self.seq, 20000)):
            for key, d in list(table.items()):
                if len(d) > 40:
                    table[key] = dict(heapq.nlargest(30, d.items(), key=lambda kv: kv[1]))
            if len(table) > cap:
                ranked = sorted(table, key=lambda k: sum(table[k].values()), reverse=True)
                for key in ranked[int(cap * 0.8):]:
                    del table[key]

    # ---------- following the typing ----------
    def reset(self):
        self.buffer = ""
        self.hist = []
        self.undo = None
        self.prev_ch = None
        self.glued = False

    def _finish(self, raw):
        if self.on_word:
            self.on_word(raw)
        prev = list(self.hist)
        w = self.learn(raw)
        self.hist = (self.hist + [w])[-8:] if w else []
        return prev

    @staticmethod
    def _char(name, shift, caps):
        if name == "Space":
            return " "
        if len(name) == 1:
            if name.isalpha():
                return name.upper() if shift != caps else name.lower()
            if name in SHIFT_OF:
                return SHIFT_OF[name] if shift else name
            return None
        if name.startswith("Num ") and len(name) == 5:
            return name[4]
        return None

    def feed(self, name, shift=False, caps=False):
        """Tell the model that key `name` was just typed."""
        undo, self.undo = self.undo, None
        if name in IGNORED_KEYS:
            self.undo = undo
            return
        if name == "Backspace":
            self.prev_ch = None
            if self.buffer:
                self.buffer = self.buffer[:-1]
            elif undo:
                self.buffer, self.hist = undo[0], list(undo[1])
            else:
                self.hist = []
            return
        if name in ("Enter", "Num Enter"):
            self.prev_ch = None
            if self.buffer:
                self._finish(self.buffer)
                self.buffer = ""
            self.hist = ["<s>"]
            return
        ch = self._char(name, shift, caps)
        prev, self.prev_ch = self.prev_ch, ch
        if ch is None:                       # arrows, Tab, F-keys... cursor may have moved
            self.buffer = ""
            self.hist = []
            return
        if ch.isalpha() or (ch == "'" and self.buffer):
            if not self.buffer:
                self.glued = prev is not None and prev in AC_GLUE
            self.buffer += ch
            if len(self.buffer) > 30:
                self.reset()
            return
        if ch == "'":
            return
        if ch == " ":
            if self.buffer:
                raw, self.buffer = self.buffer, ""
                self.undo = (raw, self._finish(raw))
            return
        if ch in ",;:-":
            if self.buffer:
                raw, self.buffer = self.buffer, ""
                self._finish(raw)
            return
        if ch in ".!?":
            if self.buffer:
                raw, self.buffer = self.buffer, ""
                self._finish(raw)
            self.hist = ["<s>"]
            return
        self.buffer = ""                     # digits and other symbols
        self.hist = []

    def accept(self, text):
        """A suggestion was typed for the user (followed by a space)."""
        self.buffer = ""
        self.undo = (text, self._finish(text))

    # ---------- suggestions ----------
    def display(self, w, cap_first, all_caps):
        s = self.caps.get(w, w)
        if all_caps:
            return s.upper()
        if cap_first and s[:1].islower():
            s = s[0].upper() + s[1:]
        return s

    def suggest(self, n=3):
        """Up to n (text to show, lowercase word) pairs."""
        buf = self.buffer
        p1 = self.hist[-1] if self.hist else None
        p2 = self.hist[-2] if len(self.hist) > 1 else None
        bi = self.bi.get(p1, {}) if p1 else {}
        tri = self.tri.get(p2 + " " + p1, {}) if (p1 and p2) else {}
        seq_scores = {}
        if self.hist:
            for span in range(1, min(8, len(self.hist)) + 1):
                context = " ".join(self.hist[-span:])
                for w, count in self.seq.get(context, {}).items():
                    # Longer matching contexts are more specific; a modest weight
                    # prevents a single rare observation from dominating everything.
                    seq_scores[w] = seq_scores.get(w, 0) + count * (2 + span * 1.5)
        if buf:
            pre = buf.lower()
            # Context gently breaks ties between completions; the prefix match stays primary.
            top = heapq.nlargest(n, ((c + 5 * bi.get(w, 0) + 12 * tri.get(w, 0)
                                       + 2 * seq_scores.get(w, 0), w)
                                     for w, c in self.uni.items()
                                     if w.startswith(pre) and w != pre))
        else:
            cand = {}
            # Trigrams are strongest, bigrams next, and a small unigram fallback keeps
            # the bar useful at sentence starts and for words not yet learned in context.
            for w, c in bi.items():
                cand[w] = cand.get(w, 0) + 4 * c
            for w, c in tri.items():
                cand[w] = cand.get(w, 0) + 9 * c
            for w, score in seq_scores.items():
                cand[w] = cand.get(w, 0) + score
            for w, c in self.uni.items():
                cand[w] = cand.get(w, 0) + max(1, c // 5)
            top = heapq.nlargest(n, ((score, w) for w, score in cand.items() if w in self.uni))
        cap_first = buf[:1].isupper() if buf else bool(self.hist and self.hist[-1] == "<s>")
        all_caps = len(buf) > 1 and buf.isupper()
        return [(self.display(w, cap_first, all_caps), w) for _s, w in top]


def type_word(sender, text, caps_on=False):
    """Type letters/apostrophes through `sender`, handling Shift and Caps Lock."""
    for ch in text:
        if ch == "'":
            sender.send("'", True)
            sender.send("'", False)
            continue
        name = ch.upper()
        if name not in CATALOG or not ch.isalpha():
            continue
        tap_key(sender, name, ch.isupper() != caps_on)


# --------------------------------------------------------------------------
# Extras: macro keys, mouse keys, layer keys, dwell clicking
# --------------------------------------------------------------------------

# ---- key-name helpers shared by shortcuts and macros ----------------------
KEY_ALIASES = {
    "ctrl": "LCtrl", "control": "LCtrl", "shift": "LShift",
    "alt": "LAlt", "win": "LWin", "windows": "LWin",
    "esc": "Esc", "escape": "Esc", "spacebar": "Space",
    "return": "Enter", "del": "Delete", "ins": "Insert",
    "pageup": "PgUp", "pagedown": "PgDn", "caps": "Caps Lock",
    "bksp": "Backspace",
}


def resolve_key(part):
    """Turn a typed key name ('ctrl', 'esc', 'f5') into a CATALOG name, or None."""
    part = part.strip()
    name = KEY_ALIASES.get(part.lower(), part)
    if name in CATALOG:
        return name
    return next((n for n in CATALOG if n.lower() == name.lower()), None)


def parse_chord(raw):
    """'Ctrl+Shift+Esc' -> (['LCtrl', 'LShift', 'Esc'], None) or (None, 'error text')."""
    raw = raw.strip()
    single = resolve_key(raw) if raw else None
    if single:
        return [single], None
    parts = [p.strip() for p in raw.split("+") if p.strip()]
    if not parts:
        return None, "No key given."
    names = []
    for part in parts:
        name = resolve_key(part)
        if name is None:
            return None, "I don't recognize the key '%s'." % part
        names.append(name)
    if len(set(names)) != len(names):
        return None, "A shortcut cannot contain the same key more than once."
    vks = [CATALOG[n][0] for n in names]
    if 0x2E in vks and 0xA2 in vks and 0xA4 in vks:
        return None, ("Windows deliberately blocks software from generating Ctrl+Alt+Delete. "
                      "Choose another shortcut, such as Ctrl+Shift+Esc for Task Manager.")
    return names, None


# ---- macros ---------------------------------------------------------------
# Character -> (key name, needs Shift) for a US layout.  Anything not listed here
# (accents, symbols, emoji) is typed as Unicode text instead.
CHAR_KEYS = {}
for _c in "abcdefghijklmnopqrstuvwxyz":
    CHAR_KEYS[_c] = (_c.upper(), False)
    CHAR_KEYS[_c.upper()] = (_c.upper(), True)
for _c in BASE_CHARS:
    CHAR_KEYS[_c] = (_c, False)
    CHAR_KEYS[SHIFT_OF[_c]] = (_c, True)
CHAR_KEYS[" "] = ("Space", False)

MAX_MACRO_STEPS = 3000
_WAIT_RE = re.compile(r"wait\s+(\d+(?:\.\d+)?)\s*(ms|s)?$", re.I)
_REPEAT_RE = re.compile(r"(.+?)\s+x\s*(\d{1,2})$", re.I)

MACRO_HELP = (
    "Type the text this key should type. Put special keys inside { }:\n"
    "    {Enter}   {Tab}   {Esc}   {Ctrl+C}   {Ctrl+Shift+Esc}   {F5}\n"
    "    {Wait 500}  pauses 500 milliseconds   ({Wait 1.5s} for seconds)\n"
    "    {Tab x3}  repeats a key 3 times\n"
    "A line break presses Enter.  Use {{ and }} for literal braces."
)


def _macro_token(body, steps):
    """Parse the inside of one {...} token, appending to steps.  Returns an error or None."""
    if not body:
        return "There is an empty { } in the macro. Put a key name inside, like {Enter}."
    m = _WAIT_RE.match(body)
    if m:
        ms = float(m.group(1)) * (1000 if (m.group(2) or "ms").lower() == "s" else 1)
        if ms > 60000:
            return "A {Wait} can be at most 60 seconds."
        steps.append(("wait", int(ms)))
        return None
    count = 1
    rm = _REPEAT_RE.match(body)
    if rm:
        body, count = rm.group(1), int(rm.group(2))
        if count < 1:
            return "A repeat count must be between 1 and 99."
    names, err = parse_chord(body)
    if err:
        return err
    steps.extend([("chord", names)] * count)
    return None


def parse_macro(text):
    """Turn macro text into steps: ('type', ch) / ('chord', [names]) / ('wait', ms).

    Returns (steps, None) or (None, 'error text')."""
    steps = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "{":
            if text[i + 1:i + 2] == "{":
                steps.append(("type", "{"))
                i += 2
            else:
                j = text.find("}", i + 1)
                if j < 0:
                    return None, "A { is missing its closing }. Use {{ for a literal brace."
                err = _macro_token(text[i + 1:j].strip(), steps)
                if err:
                    return None, err
                i = j + 1
        elif ch == "}":
            if text[i + 1:i + 2] == "}":
                steps.append(("type", "}"))
                i += 2
            else:
                return None, "A stray } was found. Use }} for a literal brace."
        elif ch == "\n":
            steps.append(("chord", ["Enter"]))
            i += 1
        elif ch == "\t":
            steps.append(("chord", ["Tab"]))
            i += 1
        elif ch == "\r" or ord(ch) < 32:
            i += 1
        else:
            steps.append(("type", ch))
            i += 1
        if len(steps) > MAX_MACRO_STEPS:
            return None, "This macro is too long (limit %d steps)." % MAX_MACRO_STEPS
    return steps, None


# ---- mouse keys, layer keys, special key bookkeeping ----------------------
# name -> (kind, argument).  Clicks fire once; scroll keys stay on until toggled off.
MOUSE_KEYS = {
    "Mouse Left": ("click", "left"),
    "Mouse Right": ("click", "right"),
    "Mouse Middle": ("click", "middle"),
    "Mouse Double": ("double", "left"),
    "Scroll Up": ("scroll", 1),
    "Scroll Down": ("scroll", -1),
}
MOUSE_LABELS = {
    "Mouse Left": "Left\nclick", "Mouse Right": "Right\nclick",
    "Mouse Middle": "Middle\nclick", "Mouse Double": "Double\nclick",
    "Scroll Up": "Scroll\n▲", "Scroll Down": "Scroll\n▼",
}
LABELS.update(MOUSE_LABELS)
SPECIAL_KEYS = {"Shortcut", "Macro", "Layer", "Speak"} | set(MOUSE_KEYS)
EXTRA_CHOICES = ["Shortcut", "Macro", "Layer", "Speak"] + list(MOUSE_KEYS)
SPECIAL_FIELDS = ("shortcut", "macro", "layer", "layer_mode", "speak")
MOUSE_JITTER = 4          # pixels the pointer may wander and still count as "still"


def clear_special(k):
    """Drop the extra fields that only Shortcut / Macro / Layer keys carry."""
    for f in SPECIAL_FIELDS:
        k.pop(f, None)


def macro_label(text):
    """Default button label for a macro: the first few characters of its text."""
    first = text.strip().splitlines()[0] if text.strip() else ""
    return first[:12] if first else "Macro"


def layer_label(mode, target):
    return ("Next: " if mode == "once" else "Go: ") + (target or "Default")


# ---- dwell clicking ---------------------------------------------------------
# Hover over a key (or button, or menu item) and hold the pointer still: after the dwell
# time KeyDeck clicks for you.  A ring around the pointer fills up as the time passes.
DWELL_TIMES = (0.5, 0.8, 1.0, 1.5, 2.0, 3.0)                    # seconds
DWELL_STEADINESS = (("Normal", 6), ("Relaxed", 12), ("Shaky", 24), ("Very shaky", 40))  # pixels
RING_KEY = "#010101"                                            # transparent colour of the ring window


class DwellEngine:
    """Decides when a resting pointer should click.  Pure logic - no Tk and no Windows calls -
    so it can be tested on its own.  step() is called about 30 times a second."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.anchor = None       # where the current countdown started
        self.token = None        # what the pointer was over when it started
        self.since = 0.0
        self.cool = None         # (position, token) of the last click, until the pointer leaves
        self.fired_at = 0.0

    @staticmethod
    def _far(a, b, tol):
        return abs(a[0] - b[0]) > tol or abs(a[1] - b[1]) > tol

    def step(self, now, pos, token, dwell, tol, repeat=False):
        """Returns ("idle", 0.0), ("wait", progress 0..1) or ("click", 1.0).

        token says what is under the pointer (None = nothing clickable).  The countdown
        restarts when the token changes or the pointer drifts more than tol pixels.  After a
        click nothing more happens until the pointer leaves that spot, unless repeat is on."""
        if token is None or pos is None:
            self.reset()
            return "idle", 0.0
        if self.cool is not None:
            cpos, ctok = self.cool
            if token == ctok and not self._far(pos, cpos, tol * 2 + 6):
                if repeat and now - self.fired_at >= dwell:
                    self.fired_at = now
                    return "click", 1.0
                return "idle", 0.0                      # still resting where it just clicked
            self.cool = None                            # moved away: start fresh
        if self.anchor is None or token != self.token or self._far(pos, self.anchor, tol):
            self.anchor, self.token, self.since = pos, token, now
            return "wait", 0.0
        frac = (now - self.since) / dwell
        if frac >= 1.0:
            self.cool = (pos, token)
            self.fired_at = now
            self.anchor = None
            return "click", 1.0
        return "wait", frac


class DwellRing:
    """A small click-through ring that follows the pointer and fills as the dwell time passes."""

    def __init__(self, root, scale):
        self.root = root
        self.size = max(28, int(40 * scale))
        self.win = None
        self.canvas = None
        self.hwnd = None
        self.broken = False
        self.visible = False

    def _create(self):
        s = self.size
        win = tk.Toplevel(self.root)
        win.withdraw()
        win.overrideredirect(True)
        win.configure(bg=RING_KEY)
        win.attributes("-topmost", True)
        win.attributes("-transparentcolor", RING_KEY)
        canvas = tk.Canvas(win, width=s, height=s, bg=RING_KEY, highlightthickness=0)
        canvas.pack()
        win.update_idletasks()
        if IS_WIN:
            # Click-through and never takes focus: mouse clicks pass straight to what is below.
            hwnd = user32.GetParent(win.winfo_id()) or win.winfo_id()
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style |= WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TRANSPARENT | WS_EX_LAYERED
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            self.hwnd = hwnd
        self.win, self.canvas = win, canvas

    def show(self, x, y, frac):
        if self.broken:
            return
        try:
            if self.win is None:
                self._create()
            s, m = self.size, 4
            self.win.geometry("+%d+%d" % (x - s // 2, y - s // 2))
            c = self.canvas
            c.delete("all")
            c.create_oval(m, m, s - m, s - m, outline="#20202a", width=6)     # dark rim: shows on light keys
            c.create_oval(m, m, s - m, s - m, outline="#9aa0ad", width=3)
            if frac > 0:
                c.create_arc(m, m, s - m, s - m, start=90, extent=-360 * min(frac, 0.999),
                             style="arc", outline="#4aa3ff", width=5)
            if not self.visible:
                self.win.deiconify()
                self.visible = True
        except Exception:
            self.broken = True                          # no ring, but dwell clicking still works

    def hide(self):
        if self.visible and self.win is not None:
            try:
                self.win.withdraw()
            except Exception:
                pass
        self.visible = False


# ---- autocorrect ------------------------------------------------------------
# Fixes a misspelt word when you press Space or punctuation.  Press Backspace straight after a
# correction to put back what you typed (and KeyDeck remembers not to touch that word again).
try:
    import keydeck_words as _kw                    # the word list; autocorrect is off without it
except Exception:                                  # pragma: no cover - depends on the install
    _kw = None

AC_MODES = ("off", "gentle", "standard")
SHIFT_GAP = 0.015       # seconds: some programs (Notepad) lose a Shift that is tapped too quickly


def tap_key(sender, name, need_shift=False):
    """Press and release a key, with Shift held around it (and given a moment to register)."""
    if need_shift:
        sender.send("LShift", True)
        time.sleep(SHIFT_GAP)
    sender.send(name, True)
    sender.send(name, False)
    if need_shift:
        time.sleep(SHIFT_GAP)
        sender.send("LShift", False)


AC_IDLE = 20.0                                     # seconds: after this, the word on screen may have moved
AC_PUNCT = frozenset(".,;:!?")                     # punctuation that sticks to the word before it
AC_I_WORDS = frozenset(("i", "i'm", "i've", "i'll", "i'd"))
AC_TRIGGERS = frozenset(" .,;:!?")                 # typing one of these ends a word
AC_GLUE = frozenset("./@\\_#:0123456789")          # a word right after these (URLs, 3rd, 10am) is left alone
AC_KEYBOARD = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]

# Words people really type that are not in a dictionary but are not mistakes.
AC_EXTRA_KNOWN = frozenset("""
    lol lmao omg wtf idk imo imho tbh btw fyi thx ty np brb ok okay yeah yep nope nah hey hi
    email emails online website websites wifi login logout username usernames password passwords
    app apps youtube google gmail facebook twitter instagram tiktok reddit discord twitch steam
    iphone ipad android windows microsoft linux python github html css javascript json pdf
    gif gifs jpeg png usb hdmi pc pcs tv dvd blu ai url urls vpn gpu cpu ram ssd hdd
    ui ux api sdk exe zip config
    ya gonna gotta wanna kinda sorta dunno lemme gimme cuz tho thru
    mr mrs ms dr jr sr vs etc eg ie am pm
""".split())

# Never offered as a correction, however close: an accidental swap would be embarrassing.
AC_BLOCK = frozenset("""
    whore whores shit shits fuck fucks fucked fucker bitch bitches cunt cunts dick dicks cock cocks
    piss pissed slut sluts bastard bastards penis vagina anus rape rapes raped nazi nazis negro
    fag fags faggot retard retards porn
""".split())
# Letter pairs that sound alike, so a mix-up is a typical spelling slip rather than a mis-click.
AC_SOUNDS = frozenset(
    p for pair in ("ae", "ei", "ie", "ea", "ou", "uo", "ai", "ia", "eu", "ue", "oa", "ao",
                   "sc", "ck", "sz", "dt", "bp", "gj", "fv", "mn", "ey", "yi", "iy", "oi", "io")
    for p in (pair, pair[::-1]))

# Typed forms that are always wrong, with what was meant.  Only misspellings that are too far
# from the right word for the general rule (or too short for Gentle) to be sure about.
AC_MISSPELLINGS = {
    "teh": "the", "hte": "the", "adn": "and", "nad": "and", "taht": "that", "thta": "that",
    "wiht": "with", "waht": "what", "whta": "what", "jsut": "just", "yuo": "you", "yoru": "your",
    "yuor": "your", "ahve": "have", "hvae": "have", "haev": "have", "htis": "this", "thsi": "this",
    "tihs": "this", "tihng": "thing", "wnat": "want", "coudl": "could", "woudl": "would",
    "shoudl": "should", "shoud": "should", "shuold": "should", "thier": "their", "wich": "which",
    "whcih": "which", "whihc": "which", "becuase": "because", "becasue": "because",
    "beacuse": "because", "recieve": "receive", "recieved": "received", "reciever": "receiver",
    "beleive": "believe", "belive": "believe", "freind": "friend", "wierd": "weird",
    "definately": "definitely", "definatly": "definitely", "definitly": "definitely",
    "seperate": "separate", "seperately": "separately", "occured": "occurred",
    "occuring": "occurring", "occurence": "occurrence", "occurance": "occurrence",
    "untill": "until", "tommorow": "tomorrow", "tomorow": "tomorrow", "tommorrow": "tomorrow",
    "tomarrow": "tomorrow", "begining": "beginning", "beggining": "beginning",
    "comming": "coming", "writting": "writing", "goverment": "government",
    "enviroment": "environment", "enviornment": "environment", "probaly": "probably",
    "probablly": "probably", "proably": "probably", "alot": "a lot", "ofcourse": "of course",
    "acheive": "achieve", "acheived": "achieved", "adress": "address", "adresses": "addresses",
    "apparantly": "apparently", "arguement": "argument", "basicly": "basically",
    "basicaly": "basically", "buisness": "business", "bussiness": "business",
    "calender": "calendar", "catagory": "category", "cemetary": "cemetery",
    "collegue": "colleague", "comitted": "committed", "commitee": "committee",
    "completly": "completely", "concious": "conscious", "consistant": "consistent",
    "convienient": "convenient", "convinient": "convenient", "curiousity": "curiosity",
    "dissapoint": "disappoint", "dissapear": "disappear", "dissappear": "disappear",
    "embarass": "embarrass", "embarassed": "embarrassed", "equiptment": "equipment",
    "excercise": "exercise", "existance": "existence", "experiance": "experience",
    "familar": "familiar", "finaly": "finally", "foriegn": "foreign", "fourty": "forty",
    "futher": "further", "gaurd": "guard", "happend": "happened", "happenned": "happened",
    "harrass": "harass", "hieght": "height", "immediatly": "immediately",
    "immediatley": "immediately", "imediately": "immediately", "independant": "independent",
    "intresting": "interesting", "intrest": "interest", "knowlege": "knowledge",
    "lenght": "length", "libary": "library", "lisence": "license", "maintainance": "maintenance",
    "millenium": "millennium", "neccessary": "necessary", "necesary": "necessary",
    "neccesary": "necessary", "noticable": "noticeable", "occassion": "occasion",
    "ocassion": "occasion", "occassionally": "occasionally", "orignal": "original",
    "orignally": "originally", "peice": "piece", "posession": "possession",
    "possesion": "possession", "prefered": "preferred", "privelege": "privilege",
    "publically": "publicly", "realy": "really", "refered": "referred", "relevent": "relevant",
    "religous": "religious", "remeber": "remember", "rythm": "rhythm", "rythym": "rhythm",
    "sieze": "seize", "similiar": "similar", "simular": "similar", "sincerly": "sincerely",
    "speach": "speech", "succesful": "successful", "successfull": "successful",
    "sucessful": "successful", "suprise": "surprise", "suprised": "surprised",
    "supprise": "surprise", "tendancy": "tendency", "tounge": "tongue", "truely": "truly",
    "truley": "truly", "twelth": "twelfth", "unfortunatly": "unfortunately",
    "unfortunetly": "unfortunately", "usally": "usually", "usualy": "usually",
    "vehical": "vehicle", "visable": "visible", "wensday": "wednesday",
    "wendsday": "wednesday", "wednessday": "wednesday", "yeild": "yield", "abscence": "absence",
    "accomodate": "accommodate", "accomodation": "accommodation", "accross": "across",
    "agian": "again", "allready": "already", "anual": "annual", "anwser": "answer",
    "appearence": "appearance", "bizzare": "bizarre", "boundry": "boundary",
    "brillant": "brilliant", "cieling": "ceiling", "cheif": "chief", "develope": "develop",
    "diffrent": "different", "diffirent": "different", "discription": "description",
    "enought": "enough", "excelent": "excellent", "extreamly": "extremely",
    "febuary": "february", "fullfil": "fulfill", "greatful": "grateful",
    "gaurantee": "guarantee", "grammer": "grammar", "incredable": "incredible",
    "langauge": "language", "mantain": "maintain", "managment": "management",
    "mispell": "misspell", "mispelled": "misspelled", "naturaly": "naturally",
    "nieghbor": "neighbor", "oppurtunity": "opportunity", "oppertunity": "opportunity",
    "paralel": "parallel", "parliment": "parliament", "particulary": "particularly",
    "percieve": "perceive", "politican": "politician", "posible": "possible",
    "possable": "possible", "pronounciation": "pronunciation", "reccomend": "recommend",
    "recomend": "recommend", "resturant": "restaurant", "restaraunt": "restaurant",
    "rediculous": "ridiculous", "saftey": "safety", "scedule": "schedule",
    "schedual": "schedule", "shedule": "schedule", "sentance": "sentence",
    "somthing": "something", "strenght": "strength", "temperture": "temperature",
    "togehter": "together", "tpyo": "typo", "unecessary": "unnecessary",
    "unnecesary": "unnecessary", "useing": "using", "vaild": "valid", "villian": "villain",
    "writen": "written", "yesturday": "yesterday", "yestarday": "yesterday",
}

# Missing apostrophes (Standard only).  "cant", "wont" and friends are words too, but rarely meant.
AC_CONTRACTIONS = {
    "dont": "don't", "doesnt": "doesn't", "didnt": "didn't", "isnt": "isn't", "wasnt": "wasn't",
    "arent": "aren't", "werent": "weren't", "hasnt": "hasn't", "havent": "haven't",
    "hadnt": "hadn't", "couldnt": "couldn't", "wouldnt": "wouldn't", "shouldnt": "shouldn't",
    "cant": "can't", "wont": "won't", "youre": "you're", "theyre": "they're",
    "thats": "that's", "whats": "what's", "im": "I'm", "ive": "I've", "youve": "you've",
    "theyve": "they've", "weve": "we've", "i": "I", "i'm": "I'm", "i've": "I've", "i'll": "I'll",
    "i'd": "I'd",
}


class Autocorrect:
    """Decides whether a just-typed word should be replaced.  Pure logic (no Tk, no Windows)."""

    def __init__(self, seed_words=()):
        self.ready = False
        self.available = _kw is not None
        self.common, self.proper = set(), set()
        self.keep = set()                            # words the user told us to leave alone
        self.rank = {w: i for i, w in enumerate(seed_words)}
        offsets = (0.0, 0.25, 0.75)                  # how far each QWERTY row is shifted
        pos = {c: (r, i + offsets[r]) for r, row in enumerate(AC_KEYBOARD) for i, c in enumerate(row)}
        self._adj = {c: {d for d, (r2, x2) in pos.items()
                         if d != c and abs(r2 - r) <= 1 and abs(x2 - x) <= 1.0}
                     for c, (r, x) in pos.items()}
        self._loading = False

    # ---- loading ----
    def load_words(self):
        """Read the word list (about 30 ms).  Safe to call from a background thread."""
        if not self.available or self.ready:
            return
        try:
            self.common, self.proper = _kw.load()
            self.ready = True
        except Exception:
            self.available = False

    def load_async(self):
        if self.ready or not self.available or self._loading:
            return
        self._loading = True
        threading.Thread(target=self.load_words, daemon=True).start()

    # ---- the "leave this word alone" list ----
    def keep_path(self):
        return os.path.join(CONFIG_DIR, "autocorrect.json")

    def load_keep(self):
        try:
            with open(self.keep_path(), "r", encoding="utf-8") as f:
                self.keep = {str(w).lower() for w in json.load(f).get("keep", [])}
        except Exception:
            self.keep = set()

    def save_keep(self):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(self.keep_path(), "w", encoding="utf-8") as f:
                json.dump({"keep": sorted(self.keep)}, f)
        except Exception:
            pass

    def keep_word(self, w):
        self.keep.add(w.lower())
        self.save_keep()

    def forget_keep(self):
        self.keep.clear()
        self.save_keep()

    # ---- the decision ----
    def is_known(self, w, learned=None):
        return (w in self.common or w in self.proper or w in AC_EXTRA_KNOWN or w in self.keep
                or (learned is not None and w in learned and learned[w] > 10))

    def _bonus(self, w, learned):
        r = self.rank.get(w)
        b = 1.5 * (1 - min(r, 1500) / 1500.0) if r is not None else 0.0
        if learned:
            b += min(1.5, max(0, learned.get(w, 0) - 10) / 20.0)   # only what you taught it
        return b

    def candidates(self, w, learned=None):
        """Real words one slip away from w, best first: [(score, word), ...]."""
        adj, found = self._adj, {}
        n = len(w)

        def offer(cand, score):
            if cand in self.common and "'" not in cand and cand not in AC_BLOCK \
                    and (len(cand) > 1 or cand in ("a", "i")):
                if score > found.get(cand, 0):
                    found[cand] = score

        for i in range(n):                                       # an extra letter was typed
            doubled = (i > 0 and w[i] == w[i - 1]) or (i + 1 < n and w[i] == w[i + 1])
            offer(w[:i] + w[i + 1:], 3.0 if doubled else 2.8)
        for i in range(n - 1):                                   # two letters swapped
            if w[i] != w[i + 1]:
                offer(w[:i] + w[i + 1] + w[i] + w[i + 2:], 3.4)
        for i in range(n):                                       # a wrong letter
            for c in "abcdefghijklmnopqrstuvwxyz":
                if c != w[i]:
                    s = 2.8 if c in adj.get(w[i], ()) else (2.6 if (w[i], c) in AC_SOUNDS else 1.5)
                    offer(w[:i] + c + w[i + 1:], s - (0.5 if i == 0 else 0))
        for i in range(n + 1):                                   # a letter was left out
            for c in "abcdefghijklmnopqrstuvwxyz":
                s = 3.0
                if (i > 0 and w[i - 1] == c) or (i < n and w[i] == c):
                    s = 3.2
                offer(w[:i] + c + w[i:], s)
        scored = [(s + self._bonus(c, learned), c) for c, s in found.items()]
        scored.sort(reverse=True)
        return scored

    def correct(self, raw, mode, learned=None, sentence_start=False):
        """The replacement for the typed word `raw`, or None to leave it alone."""
        if mode not in ("gentle", "standard") or not self.ready or not raw:
            return None
        w = raw.lower()
        if len(raw) > 1 and raw.isupper():                       # NASA, OK: leave acronyms alone
            return None
        if any(c.isupper() for c in raw[1:]):                    # iPhone, McDonald
            return None
        capital = raw[0].isupper()
        if w in self.keep:
            return None
        if mode == "standard" and w in AC_CONTRACTIONS:
            fixed = AC_CONTRACTIONS[w]
            return fixed if fixed != raw else None
        if capital and not sentence_start:                       # probably a name
            return None
        if self.is_known(w, learned):
            return None
        fixed = AC_MISSPELLINGS.get(w)
        if fixed is None and len(w) >= (4 if mode == "gentle" else 3):
            cands = self.candidates(w, learned)
            if cands:
                best = cands[0][0]
                margin = best - (cands[1][0] if len(cands) > 1 else 0.0)
                if mode == "gentle":
                    ok = best >= 4.0 and margin >= 1.0
                else:
                    ok = best >= 2.5 and margin >= (0.8 if len(w) == 3 else 0.2)
                if ok:
                    fixed = cands[0][1]
        if fixed is None:
            return None
        if capital or (sentence_start and raw[0].isupper()):
            fixed = fixed[0].upper() + fixed[1:]
        return fixed

    def looks_like_typo(self, w):
        """True if w is not a word but is one slip from a real one (used so a typo you make
        twice is not learned as a new word)."""
        if not self.ready or self.is_known(w):
            return False
        return len(w) >= 3 and bool(self.candidates(w))
# ---- swipe typing -----------------------------------------------------------
# Hold the mouse button on a letter, drag across the letters of a word, let go: KeyDeck works
# out which word you traced.  (Tap = a normal key press; hold still for a moment = key repeat.)
SWIPE_HOLD_MS = 600          # holding still this long on one letter turns it into a normal press
SWIPE_REACH = 0.8            # how far (in key widths) the path may pass from a letter and still count
SWIPE_MISS = 1.35            # ...but a word may have a letter or so the path only passed this close to
SWIPE_CONTRACTIONS = (
    "don't doesn't didn't isn't wasn't aren't weren't hasn't haven't hadn't couldn't wouldn't "
    "shouldn't can't won't ain't mustn't needn't you're they're we're i'm i've i'll i'd you've "
    "they've we've you'll they'll we'll he'll she'll it'll that'll you'd he'd she'd they'd we'd "
    "that's what's there's here's who's let's he's she's it's how's where's when's why's "
    "could've would've should've might've must've o'clock y'all").split()
CSWIPE_IDLE_MS = 10000       # a click-to-swipe path that waits this long is dropped
SWIPE_POINTS = 28            # paths are compared at this many evenly spaced points


def _path_length(pts):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))


def _densify(pts, step):
    """Fill in the gaps between sparse mouse samples so a fast swipe can't skip over keys."""
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / step))
        for i in range(1, n + 1):
            t = i / n
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def _resample(pts, m):
    """m points spaced evenly along the polyline pts."""
    total = _path_length(pts)
    if total < 1e-9:
        return [pts[0]] * m
    out, seg, run = [pts[0]], 0, 0.0
    for i in range(1, m - 1):
        target = total * i / (m - 1)
        while seg < len(pts) - 2 and run + math.hypot(pts[seg + 1][0] - pts[seg][0],
                                                      pts[seg + 1][1] - pts[seg][1]) < target:
            run += math.hypot(pts[seg + 1][0] - pts[seg][0], pts[seg + 1][1] - pts[seg][1])
            seg += 1
        a, b = pts[seg], pts[seg + 1]
        d = math.hypot(b[0] - a[0], b[1] - a[1])
        t = 0.0 if d < 1e-9 else (target - run) / d
        t = max(0.0, min(1.0, t))
        out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    out.append(pts[-1])
    return out


class SwipeDecoder:
    """Turns the path of a swipe into words.  Pure logic - no Tk - so it can be tested alone.

    The idea: a word's "ideal path" joins the centres of its letters.  Words whose first and
    last letters match where the swipe began and ended, whose every letter was passed close by,
    and whose ideal path has the same shape as what you drew, are the candidates."""

    def __init__(self):
        self.by_ends = {}
        self.ready = False

    def set_words(self, words):
        idx = {}
        for w in words:
            if 2 <= len(w) <= 20 and w.isalpha() and w.isascii() and w == w.lower():
                mask = 0
                for c in w:
                    mask |= 1 << (ord(c) - 97)
                idx.setdefault((w[0], w[-1]), []).append((w, mask))
        self.by_ends = idx
        self.ready = bool(idx)

    def add_contractions(self, forms):
        """forms: lowercase words with an apostrophe, e.g. "don't".  They are traced by their letters."""
        for f in forms:
            w = f.replace("'", "")
            if 2 <= len(w) <= 20 and w.isalpha() and w.isascii():
                mask = 0
                for c in w:
                    mask |= 1 << (ord(c) - 97)
                lst = self.by_ends.setdefault((w[0], w[-1]), [])
                if (f, mask) not in lst:
                    lst.append((f, mask))
        self.ready = bool(self.by_ends)

    def decode(self, path, letters, unit, bonus=None, extra=(), limit=4):
        """path: [(x, y), ...] in pixels.  letters: {letter: (cx, cy)} in pixels.
        bonus(word) -> a number subtracted from the cost (bigger = more likely).
        Returns up to `limit` words, best first."""
        if len(path) < 2 or not letters or unit <= 0:
            return []
        pts = [(x / unit, y / unit) for x, y in path]
        dense = _densify(pts, 0.25)
        cen = {c: (x / unit, y / unit) for c, (x, y) in letters.items()}
        dmin = {c: min(math.hypot(px - cx, py - cy) for px, py in dense)
                for c, (cx, cy) in cen.items()}

        def near(pt):
            hits = [c for c, (cx, cy) in cen.items() if math.hypot(pt[0] - cx, pt[1] - cy) <= 0.9]
            return hits or [min(cen, key=lambda c: math.hypot(pt[0] - cen[c][0], pt[1] - cen[c][1]))]

        starts, ends = near(dense[0]), near(dense[-1])
        ok_mask = 0                       # letters the path passed reasonably close to
        for c, d in dmin.items():
            if d <= SWIPE_MISS and "a" <= c <= "z":
                ok_mask |= 1 << (ord(c) - 97)
        pool = {}
        for a in starts:
            for b in ends:
                for w, mask in self.by_ends.get((a, b), ()):
                    if not mask & ~ok_mask:
                        pool[w] = mask
        for w in extra:
            if len(w) >= 2 and w[0] in starts and w[-1] in ends and w.isalpha() and w.isascii():
                pool[w] = 0
        user = _resample(dense, SWIPE_POINTS)
        ulen = _path_length(dense)
        scored = []
        for w in pool:
            lw = w.replace("'", "")           # contractions are traced by their letters
            far = [dmin.get(c, 9.0) for c in set(lw) if dmin.get(c, 9.0) > SWIPE_REACH]
            if far and (max(far) > SWIPE_MISS or len(far) > 1 + len(lw) // 6):
                continue                  # the path never went near some letter of this word
            seq = []
            prev = None
            for c in lw:
                if c != prev:
                    seq.append(cen[c])
                prev = c
            if len(seq) < 2:
                continue
            ilen = _path_length(seq)
            lendiff = abs(ilen - ulen) / max(ilen, ulen, 1.0)
            if lendiff > 0.5:
                continue                  # far too long or too short to be what was drawn
            ideal = _resample(seq, SWIPE_POINTS)
            cost = sum(math.hypot(a[0] - b[0], a[1] - b[1]) for a, b in zip(user, ideal)) / SWIPE_POINTS
            cost += 0.5 * lendiff
            cost += 0.12 * len(far)
            if bonus:
                cost -= bonus(w)
            scored.append((cost, w))
        scored.sort()
        return [w for _c, w in scored[:limit]]
# ---- speak each word ------------------------------------------------------------
class Speaker:
    """Reads words aloud with Windows' built-in voice (System.Speech), through one long-lived,
    hidden PowerShell process so there is no start-up delay for each word."""
    SCRIPT = (
        "[Console]::InputEncoding=[Text.Encoding]::UTF8;"
        "Add-Type -AssemblyName System.Speech;"
        "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        "while(($l=[Console]::In.ReadLine()) -ne $null){"
        "$p=$l.Split([char]9,3);if($p.Length -lt 3){continue};"
        "try{$s.Rate=[int]$p[0];$s.Volume=[int]$p[1]}catch{};$s.SpeakAsyncCancelAll();[void]$s.SpeakAsync($p[2])}"
    )

    def __init__(self):
        self.proc = None
        self.failed = False

    def _start(self):
        if self.proc is not None and self.proc.poll() is None:
            return True
        if self.failed or not IS_WIN:
            return False
        try:
            self.proc = subprocess.Popen(
                ["powershell", "-NoProfile", "-NoLogo", "-NonInteractive", "-Command", self.SCRIPT],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=0x08000000, text=True, encoding="utf-8")   # CREATE_NO_WINDOW
            return True
        except Exception:
            self.failed = True
            return False

    def say(self, text, rate=0, volume=100):
        text = " ".join(str(text).replace("\t", " ").split())
        if not text or not self._start():
            return
        try:
            self.proc.stdin.write("%d\t%d\t%s\n" % (max(-10, min(10, int(rate))), max(0, min(100, int(volume))), text))
            self.proc.stdin.flush()
        except Exception:
            self.proc = None

    def stop(self):
        p, self.proc = self.proc, None
        if p is not None:
            try:
                p.stdin.close()
                p.terminate()
            except Exception:
                pass


SPEAK_VOLUMES = (("Quiet", 25), ("Medium", 50), ("Loud", 75), ("Full", 100))
SPEAK_RATES = (("Slow", -3), ("Normal", 0), ("Fast", 3), ("Very fast", 6))


# ---- switch scanning (row-column) ----------------------------------------------------
class ScanEngine:
    """The state machine behind row-column scanning.  Pure logic - no Tk - so it can be tested.

    rows is a list of rows, each a list of key ids.  Modes: "idle" (waiting for the first switch
    press), "rows" (highlighting one row at a time) and "keys" (highlighting one key of a row)."""

    def __init__(self, max_passes=3):
        self.rows = []
        self.mode = "idle"
        self.row = 0
        self.col = 0
        self.passes = 0
        self.max_passes = max_passes          # full loops before it pauses (0 = never pause)

    def set_rows(self, rows):
        self.rows = [list(r) for r in rows if r]
        if self.row >= len(self.rows):
            self.row, self.col = 0, 0
        elif self.col >= len(self.rows[self.row]):
            self.col = 0

    def pause(self):
        self.mode = "idle"
        self.row = self.col = self.passes = 0

    def highlight(self):
        """{key id: "row" | "key"} - what to draw highlighted right now."""
        if self.mode == "idle" or not self.rows:
            return {}
        ids = self.rows[self.row]
        if self.mode == "rows":
            return {i: "row" for i in ids}
        out = {i: "row" for i in ids}
        out[ids[self.col]] = "key"
        return out

    def tick(self):
        """The scan timer fired: move the highlight on."""
        if self.mode == "idle" or not self.rows:
            return
        if self.mode == "rows":
            self.row += 1
            if self.row >= len(self.rows):
                self.row = 0
                self.passes += 1
                if self.max_passes and self.passes >= self.max_passes:
                    self.pause()
        else:
            self.col += 1
            if self.col >= len(self.rows[self.row]):
                self.col = 0
                self.passes += 1
                if self.max_passes and self.passes >= self.max_passes:
                    self.mode, self.passes = "rows", 0      # nothing chosen: back to the rows

    def select(self):
        """The switch was pressed.  Returns ("none",), ("wake",), ("row", i) or ("press", key id)."""
        if not self.rows:
            return ("none",)
        if self.mode == "idle":
            self.mode, self.row, self.col, self.passes = "rows", 0, 0, 0
            return ("wake",)
        if self.mode == "rows":
            ids = self.rows[self.row]
            if len(ids) == 1:                               # nothing to choose between
                self.mode, self.row, self.col, self.passes = "rows", 0, 0, 0
                return ("press", ids[0])
            self.mode, self.col, self.passes = "keys", 0, 0
            return ("row", self.row)
        target = self.rows[self.row][self.col]
        self.mode, self.row, self.col, self.passes = "rows", 0, 0, 0
        return ("press", target)


# ---- pictures on keys -----------------------------------------------------------------
# A key can carry a photo or drawing.  The picture is stored inside the layout itself (as
# base64 text), so exported layouts keep their pictures.  Pillow is used when it is installed
# (any common picture type, smooth scaling); without it only PNG and GIF work.
try:
    from PIL import Image, ImageTk
    HAVE_PIL = True
except Exception:
    Image = ImageTk = None
    HAVE_PIL = False
PIC_MAX_BYTES = 400000          # biggest picture stored in a key (after shrinking)
PIC_TYPES_PIL = (("Pictures", "*.png *.gif *.jpg *.jpeg *.bmp *.webp *.tif *.tiff"), ("All files", "*.*"))
PIC_TYPES_PLAIN = (("PNG or GIF pictures", "*.png *.gif"), ("All files", "*.*"))
SPEAK_MAX = 400                 # longest phrase a Speak key can say


GIF_MAX_FRAMES = 60             # most frames kept in an animated key picture


def gif_delays(raw):
    """Frame delays (milliseconds) of a GIF, one per picture in the file; [] if it isn't a
    readable GIF.  Plain byte walking, so it works without Pillow.  A delay of 0 or 1/100 s
    is shown as 100 ms, as web browsers do."""
    try:
        if not raw.startswith((b"GIF87a", b"GIF89a")) or len(raw) < 14:
            return []
        i = 13
        if raw[10] & 0x80:
            i += 3 * (2 ** ((raw[10] & 7) + 1))
        delays, pending = [], 100
        while i < len(raw):
            b = raw[i]
            if b == 0x3B:                                   # trailer
                break
            if b == 0x21:                                   # extension
                label = raw[i + 1]
                if label == 0xF9 and raw[i + 2] >= 4:       # graphic control: delay
                    d = raw[i + 4] | (raw[i + 5] << 8)
                    pending = d * 10 if d > 1 else 100
                i += 2
                while raw[i] != 0:                          # skip sub-blocks
                    i += raw[i] + 1
                i += 1
            elif b == 0x2C:                                 # picture
                flags = raw[i + 9]
                i += 10
                if flags & 0x80:
                    i += 3 * (2 ** ((flags & 7) + 1))
                i += 1                                      # LZW minimum code size
                while raw[i] != 0:
                    i += raw[i] + 1
                i += 1
                delays.append(pending)
                pending = 100
            else:
                return []
        return delays
    except Exception:
        return []


def picture_is_animated(data):
    """True if stored picture text is a GIF with more than one frame."""
    try:
        return len(gif_delays(base64.b64decode(data))) > 1
    except Exception:
        return False


def _encode_animation(frames, delays, box):
    """Shrink every frame to fit in box x box and write one animated GIF; returns bytes."""
    small = []
    for fr in frames:
        f = fr.copy()
        f.thumbnail((box, box), Image.LANCZOS)
        small.append(f)
    out = io.BytesIO()
    small[0].save(out, "GIF", save_all=True, append_images=small[1:], duration=delays,
                  loop=0, disposal=2)
    return out.getvalue()


def prepare_picture(path):
    """Read a picture file and return (base64 text, file name) ready to store in a key.
    Animated pictures stay animated (stored as a GIF).
    Raises ValueError with a plain-language reason if it can't be used."""
    try:
        with open(path, "rb") as f:
            data = f.read(30 * 1024 * 1024 + 1)
    except OSError as ex:
        raise ValueError("Could not open the file: %s" % ex)
    if len(data) > 30 * 1024 * 1024:
        raise ValueError("That file is too big (over 30 MB).")
    name = os.path.basename(path)
    if HAVE_PIL:
        try:
            im = Image.open(io.BytesIO(data))
            count = int(getattr(im, "n_frames", 1) or 1)
            if count > 1:
                step = max(1, -(-count // GIF_MAX_FRAMES))      # keep at most 60 frames
                frames, delays, acc = [], [], 0
                for n in range(count):
                    im.seek(n)
                    acc += max(20, int(im.info.get("duration") or 100))
                    if n % step == 0:
                        frames.append(im.convert("RGBA").copy())
                        delays.append(acc)
                        acc = 0
                    elif n == count - 1 and delays:
                        delays[-1] += acc
            else:
                im.load()
                im = im.convert("RGBA")
        except Exception:
            raise ValueError("That doesn't look like a picture KeyDeck can read.")
        if count > 1 and len(frames) > 1:
            for box in (256, 160, 120, 96, 64):
                fr, dl = frames, delays
                while True:
                    try:
                        blob = _encode_animation(fr, dl, box)
                    except Exception:
                        raise ValueError("That animation couldn't be converted.")
                    if len(blob) <= PIC_MAX_BYTES or len(fr) < 6:
                        break
                    fr, dl = fr[::2], [dl[i] + (dl[i + 1] if i + 1 < len(dl) else 0)
                                       for i in range(0, len(dl), 2)]
                if len(blob) <= PIC_MAX_BYTES:
                    return base64.b64encode(blob).decode("ascii"), name
            raise ValueError("That animation is too big to store in a key. Try a shorter or "
                             "smaller one.")
        if count > 1:                                             # one real frame: a still
            im = frames[0]
        for box in (400, 256, 160, 96):
            small = im.copy()
            small.thumbnail((box, box), Image.LANCZOS)
            out = io.BytesIO()
            small.save(out, "PNG", optimize=True)
            if out.tell() <= PIC_MAX_BYTES:
                return base64.b64encode(out.getvalue()).decode("ascii"), name
        raise ValueError("That picture is too detailed to store in a key. Try a simpler one.")
    if not (data.startswith(b"\x89PNG") or data.startswith(b"GIF8")):
        raise ValueError("Only PNG and GIF pictures work here. Save the picture as a PNG first "
                         "(or install the Pillow package to use JPG and other types).")
    if len(data) > PIC_MAX_BYTES:
        raise ValueError("That picture is %d KB; the limit is %d KB. Make it smaller first "
                         "(or install the Pillow package, which shrinks pictures for you)."
                         % (len(data) // 1000, PIC_MAX_BYTES // 1000))
    return base64.b64encode(data).decode("ascii"), name


def valid_picture_data(text):
    """True if text is plausible stored picture data (used when loading layout files)."""
    if not isinstance(text, str) or not text or len(text) > PIC_MAX_BYTES * 4 // 3 + 16:
        return False
    try:
        raw = base64.b64decode(text, validate=True)
    except Exception:
        return False
    return raw.startswith(b"\x89PNG") or raw.startswith(b"GIF8")


# ---- colour themes ----------------------------------------------------------------
THEME_ROLES = ("BG", "PANEL", "KEY_COLOR", "MOD_COLOR", "KEY_EDGE", "SEL_EDGE", "PRESS_COLOR",
               "ONESHOT_COLOR", "HOLD_COLOR", "TEXT", "PRESS_FG", "ONESHOT_FG", "HOLD_FG",
               "BTN_BG", "BTN_ALT", "BTN_ACTIVE", "BTN_ALT_ACTIVE", "BTN_FG", "BTN_AFG",
               "LABEL_FG", "MUTED_FG", "MUTED_FG2", "TRAIL_COLOR", "KEY_EDGE_W", "THEME_HC",
               "SCAN_COLOR", "SCAN_FG", "SCAN_ROW", "SCAN_ROW_FG")
# Widget colours that get swapped when the theme changes while KeyDeck is running.  Within each
# group the values must differ from one another inside a theme, so the old colour identifies the role.
THEME_BG_ROLES = ("BG", "PANEL", "BTN_BG", "BTN_ALT", "BTN_ACTIVE", "BTN_ALT_ACTIVE", "HOLD_COLOR")
THEME_FG_ROLES = ("BTN_FG", "BTN_AFG", "LABEL_FG", "MUTED_FG", "MUTED_FG2")

THEMES = {
    "dark": dict(
        BG="#1b1b1f", PANEL="#24242b", KEY_COLOR="#34343c", MOD_COLOR="#2a3040", KEY_EDGE="#4a4a56",
        SEL_EDGE="#4aa3ff", PRESS_COLOR="#4a8fe8", ONESHOT_COLOR="#d9a400", HOLD_COLOR="#d9531e",
        TEXT="#f2f2f2", PRESS_FG="#ffffff", ONESHOT_FG="#1a1a1a", HOLD_FG="#ffffff",
        BTN_BG="#2b2b33", BTN_ALT="#33333d", BTN_ACTIVE="#3c3c48", BTN_ALT_ACTIVE="#44444f",
        BTN_FG="#eeeeee", BTN_AFG="#ffffff", LABEL_FG="#c8c8d0", MUTED_FG="#80808c",
        MUTED_FG2="#9a9aa6", TRAIL_COLOR="#6cc3ff", KEY_EDGE_W=1, THEME_HC=False,
        SCAN_COLOR="#ffd400", SCAN_FG="#000000", SCAN_ROW="#6b5a00", SCAN_ROW_FG="#ffffff"),
    "hc_dark": dict(
        BG="#000000", PANEL="#020202", KEY_COLOR="#000000", MOD_COLOR="#0b0b5c", KEY_EDGE="#ffffff",
        SEL_EDGE="#ffff00", PRESS_COLOR="#ffff00", ONESHOT_COLOR="#00ffff", HOLD_COLOR="#ff9900",
        TEXT="#ffffff", PRESS_FG="#000000", ONESHOT_FG="#000000", HOLD_FG="#000000",
        BTN_BG="#202020", BTN_ALT="#222222", BTN_ACTIVE="#ffff00", BTN_ALT_ACTIVE="#fffe00",
        BTN_FG="#ffff00", BTN_AFG="#000000", LABEL_FG="#ffffff", MUTED_FG="#e0e0e0",
        MUTED_FG2="#e2e2e2", TRAIL_COLOR="#ffff00", KEY_EDGE_W=3, THEME_HC=True,
        SCAN_COLOR="#ffff00", SCAN_FG="#000000", SCAN_ROW="#00ffff", SCAN_ROW_FG="#000000"),
    "hc_light": dict(
        BG="#ffffff", PANEL="#fdfdfd", KEY_COLOR="#ffffff", MOD_COLOR="#dcdcdc", KEY_EDGE="#000000",
        SEL_EDGE="#0000ff", PRESS_COLOR="#0033cc", ONESHOT_COLOR="#ffdd00", HOLD_COLOR="#cc3300",
        TEXT="#000000", PRESS_FG="#ffffff", ONESHOT_FG="#000000", HOLD_FG="#ffffff",
        BTN_BG="#e6e6e6", BTN_ALT="#e4e4e4", BTN_ACTIVE="#000000", BTN_ALT_ACTIVE="#010101",
        BTN_FG="#000000", BTN_AFG="#ffffff", LABEL_FG="#111111", MUTED_FG="#333333",
        MUTED_FG2="#353535", TRAIL_COLOR="#0033cc", KEY_EDGE_W=3, THEME_HC=True,
        SCAN_COLOR="#ff6600", SCAN_FG="#000000", SCAN_ROW="#ffc999", SCAN_ROW_FG="#000000"),
}
THEME_NAMES = (("dark", "Dark (default)"),
               ("hc_dark", "High contrast – black and yellow"),
               ("hc_light", "High contrast – white and black"))


def theme_snapshot():
    g = globals()
    return {r: g[r] for r in THEME_ROLES}


BG_OVERRIDE = ""          # a keyboard background colour chosen by the user ("" = the theme's own)


def _edge_px(raw):
    """Outline thickness stored in a key: None = the theme's default, 0 = no outline."""
    v = raw.get("edge_px")
    if v in (None, ""):
        v = raw.get("edge_w") or None        # older files: 0 meant "default"
    if v is None:
        return None
    try:
        return max(0, min(8, int(v)))
    except Exception:
        return None


def set_theme(name, bg=None):
    global BG_OVERRIDE
    if bg is not None:
        BG_OVERRIDE = bg
    globals().update(THEMES.get(name, THEMES["dark"]))
    if BG_OVERRIDE:
        globals()["BG"] = BG_OVERRIDE


set_theme("dark")


# ---- minimize to a small tab ----------------------------------------------------------
# For people who dwell-click and can't press a mouse button: the Minimize button hides the
# keyboard and leaves a small always-on-top tab at the edge of the screen.  Resting the pointer
# on the tab for a moment (a progress bar fills) brings the keyboard back -- no click needed.
MIN_POSITIONS = (("bl", "Bottom left"), ("bc", "Bottom middle"), ("br", "Bottom right"),
                 ("tl", "Top left"), ("tc", "Top middle"), ("tr", "Top right"))
MIN_OPEN_TIMES = ((0.0, "the same as the dwell time"), (0.5, "0.5 seconds"), (1.0, "1 second"),
                  (1.5, "1.5 seconds"), (2.0, "2 seconds"), (3.0, "3 seconds"))


class MinTab:
    """The little tab that stands in for the keyboard while it is minimized."""

    def __init__(self, root, scale, on_click):
        self.root = root
        self.on_click = on_click
        self.w = max(150, int(210 * scale))
        self.h = max(44, int(54 * scale))
        self.x = self.y = 0
        self.top = False
        self.win = None
        self.canvas = None
        self.visible = False
        self.broken = False

    def _create(self):
        win = tk.Toplevel(self.root)
        win.withdraw()
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=BG)
        canvas = tk.Canvas(win, width=self.w, height=self.h, bg=BG, highlightthickness=0,
                           cursor="hand2")
        canvas.pack()
        canvas.bind("<ButtonPress-1>", lambda e: self.on_click())
        win.update_idletasks()
        if IS_WIN:
            # never takes focus, so the program being typed into keeps it; no taskbar button
            hwnd = user32.GetParent(win.winfo_id()) or win.winfo_id()
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style |= WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        self.win, self.canvas = win, canvas

    def place(self, area, pos):
        """Work out where the tab goes inside area = (left, top, right, bottom)."""
        left, top, right, bottom = area
        v, h = pos[0], pos[1]
        self.top = (v == "t")
        self.y = top if self.top else bottom - self.h
        if h == "l":
            self.x = left
        elif h == "r":
            self.x = right - self.w
        else:
            self.x = left + (right - left - self.w) // 2

    def rect(self):
        return self.x, self.y, self.x + self.w, self.y + self.h

    def show(self, area, pos):
        try:
            if self.win is None:
                self._create()
            self.place(area, pos)
            self.draw(0.0)
            self.win.geometry("%dx%d+%d+%d" % (self.w, self.h, self.x, self.y))
            self.win.deiconify()
            self.win.lift()
            self.visible = True
            return True
        except Exception:
            self.broken = True
            return False

    def hide(self):
        if self.win is not None:
            try:
                self.win.withdraw()
            except Exception:
                pass
        self.visible = False

    def set_progress(self, frac):
        if self.visible and frac != getattr(self, "_shown", None):
            self.draw(frac)

    def draw(self, frac):
        self._shown = frac
        c, w, h = self.canvas, self.w, self.h
        c.delete("all")
        c.create_rectangle(2, 2, w - 2, h - 2, fill=BTN_BG, outline=SEL_EDGE, width=3)
        if frac > 0:
            bar = max(6, h // 7)
            y0 = h - 4 - bar
            c.create_rectangle(5, y0, 5 + (w - 10) * min(frac, 1.0), h - 5, fill=SEL_EDGE, outline="")
        arrow = "▼" if self.top else "▲"
        c.create_text(w // 2, int(h * 0.36), text="%s  KeyDeck" % arrow, fill=BTN_FG,
                      font=("Segoe UI", -max(12, int(h * 0.30)), "bold"))
        c.create_text(w // 2, int(h * 0.68), text="rest the pointer here to open", fill=BTN_FG,
                      font=("Segoe UI", -max(9, int(h * 0.19))))
CAPTION_IDLE = "Spoken text shows here"

# --------------------------------------------------------------------------
# Theme
# --------------------------------------------------------------------------
BG = "#1b1b1f"
PANEL = "#24242b"
KEY_COLOR = "#34343c"
MOD_COLOR = "#2a3040"
KEY_EDGE = "#4a4a56"
SEL_EDGE = "#4aa3ff"
PRESS_COLOR = "#4a8fe8"
ONESHOT_COLOR = "#d9a400"
HOLD_COLOR = "#d9531e"
TEXT = "#f2f2f2"
PAD = 10


def rounded(x1, y1, x2, y2, r):
    return [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
            x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]


def snap(v):
    return round(v * 4) / 4.0


# --------------------------------------------------------------------------
# The app
# --------------------------------------------------------------------------
class KeyDeck:
    cswipe = None            # a click-to-swipe path waiting for its last letter
    scan = None              # ScanEngine while row-column scanning is on
    scan_hl = {}             # what the scanner is highlighting right now
    scan_job = None
    scan_injecting = False   # True while the scanner presses a key for you
    speaker = None

    def __init__(self, root):
        self.root = root
        self.settings = load_settings()
        self.sender = KeySender(self.settings["scancode"])
        self.keys = []
        self.states = {}          # key id -> "mom" | "oneshot" | "hold"
        self.pressing = None
        self.repeat_job = None
        self.edit_mode = False
        self.hold_mode = False
        self.sel = None
        self.drag = None
        self.loadout_name = ""    # "" means the built-in default
        self._loading = False
        self._next_id = 1
        self.scale = max(1.0, root.winfo_fpixels("1i") / 96.0)
        self.pad = int(PAD * self.scale)
        self.settings["unit"] = max(14, min(80, int(self.settings["unit"])))
        self.unit = int(self.settings["unit"] * self.scale)
        self.pt = Predictor()
        self.pt.learning = bool(self.settings["learn"])
        self.pt_fw = None
        self.pt_last = 0.0
        self.sugg = []
        if self.settings.get("autocorrect") not in AC_MODES:
            self.settings["autocorrect"] = "off"
        self.ac = Autocorrect(SEED_WORDS)
        self.ac.load_keep()
        self.pt.typo_check = self.ac.looks_like_typo
        self.ac_pending = None       # a correction just made, waiting for its Space/punctuation
        self.ac_undo = None          # the last correction, which Backspace can take back
        self.speaker = None          # reads words aloud (Speaker), created when first needed
        self.pt.on_word = self.speak_word
        self.lone = None             # a one-letter word (a / I) just tapped; Space goes after it
        self.forced_shift = False    # Shift pressed for you (sentence capital), still held down
        self.auto_space = None       # a Space KeyDeck added after a swiped/suggested word
        self.swipe = None            # a mouse press on a letter that may turn into a swipe
        self.swipe_ctx = None        # the word just swiped, until the next key is pressed
        self.swipe_alts = []         # other words the swipe might have meant
        self.swipe_dec = SwipeDecoder()
        if self.settings["autocorrect"] != "off" or self.settings["swipe"]:
            self.ac.load_async()
        self.armed = None            # mouse key waiting for the pointer to settle
        self.macro_queue = collections.deque()
        self.macro_job = None
        self.macro_id = None
        self.macro_caps = False
        self.layer_return = None     # loadout to go back to after a one-key layer
        self.layer_pending = False
        self.dwell_engine = DwellEngine()
        self.scan_apply()
        self.ring = DwellRing(root, self.scale)
        self.last_ext_fg = 0          # last window of another program that had the focus
        self._applied_topmost = bool(self.settings["topmost"])   # what Tk was last told
        self._applied_opacity = float(self.settings["opacity"])

        set_theme(self.settings["theme"], self.settings.get("bg_color", ""))
        root.title("KeyDeck")
        root.configure(bg=BG)
        root.resizable(False, False)
        root.attributes("-topmost", bool(self.settings["topmost"]))
        try:
            root.attributes("-alpha", float(self.settings["opacity"]))
        except Exception:
            pass

        self.build_toolbar()
        self.canvas = tk.Canvas(root, bg=BG, highlightthickness=0)
        self.canvas.grid(row=2, column=0, sticky="nsew")
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<B1-Motion>", self.on_motion)
        self.canvas.bind("<ButtonPress-3>", self.on_right_press)
        self.canvas.bind("<Motion>", self.on_hover)
        self.build_suggest_bar()
        self.build_edit_panel()
        self.build_caption()
        self.apply_ui_scale()

        self.load_loadout(self.settings["loadout"])
        self._last_caps_state = self.caps_on()
        self.root.after(150, self.poll_caps_state)
        self.root.after(50, self.mouse_poll)
        self.root.after(30, self.dwell_poll)
        self.root.after(60, self.anim_tick)
        self.root.after(250, self.window_watch)
        root.update_idletasks()
        self.place_window()
        self.apply_noactivate(True)
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        atexit.register(self.emergency_release)
        atexit.register(self.pt.save)

    # ---------------- window helpers ----------------
    def apply_noactivate(self, on):
        if not IS_WIN:
            return
        self.root.update_idletasks()
        # Tk's winfo_id() is usually the client HWND.  Its parent is the
        # actual top-level window, whose extended styles control taskbar
        # behavior.
        hwnd = user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)

        # Keep KeyDeck non-activating so clicking its virtual keys does not
        # steal focus from the app receiving typed characters.  Explicitly
        # mark it as an application window, however, so Windows creates a
        # real taskbar button for the running window rather than only showing
        # the pinned shortcut (which can launch a second copy when clicked).
        style |= WS_EX_APPWINDOW
        style &= ~WS_EX_TOOLWINDOW
        if on:
            style |= WS_EX_NOACTIVATE
        else:
            style &= ~WS_EX_NOACTIVATE
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

        # Tell Windows to recalculate the non-client/taskbar representation
        # after changing extended styles.  NOACTIVATE prevents this refresh
        # from taking focus away from the user's current app.
        flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED
        user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, flags)

    def own_hwnd(self):
        if not IS_WIN:
            return 0
        return user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()

    @staticmethod
    def window_pid(hwnd):
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value

    def restore_focus(self):
        """If KeyDeck itself ended up in the foreground (after a setting change or a dialog),
        hand the focus back to the program the user was typing into."""
        if not IS_WIN or self.edit_mode or not self.last_ext_fg:
            return
        try:
            if user32.GetForegroundWindow() == self.own_hwnd():
                user32.SetForegroundWindow(self.last_ext_fg)
        except Exception:
            pass

    def window_watch(self):
        """Four times a second: remember the last other program's window, and make sure KeyDeck
        still has its 'never take focus' style (repairing it if anything dropped it)."""
        try:
            if IS_WIN:
                own = self.own_hwnd()
                fg = user32.GetForegroundWindow()
                if fg and fg != own and self.window_pid(fg) != kernel32.GetCurrentProcessId():
                    self.last_ext_fg = fg
                if not self.edit_mode:
                    if not (user32.GetWindowLongW(own, GWL_EXSTYLE) & WS_EX_NOACTIVATE):
                        self.apply_noactivate(True)
                        self.restore_focus()
        except Exception:
            pass
        finally:
            try:
                if self.root.winfo_exists():
                    self.root.after(250, self.window_watch)
            except tk.TclError:
                pass

    def place_window(self):
        r = self.root
        sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
        w, h = r.winfo_reqwidth(), r.winfo_reqheight()
        r.geometry("+%d+%d" % (max(0, (sw - w) // 2), max(0, sh - h - 90)))

    def keep_on_screen(self):
        r = self.root
        r.update_idletasks()
        sh = r.winfo_screenheight()
        bottom = r.winfo_y() + r.winfo_reqheight()
        if bottom > sh - 40:
            r.geometry("+%d+%d" % (max(0, r.winfo_x()), max(0, sh - r.winfo_reqheight() - 60)))

    # ---------------- toolbar ----------------
    def build_toolbar(self):
        tb = tk.Frame(self.root, bg=BG)
        tb.grid(row=0, column=0, sticky="ew")
        self.toolbar = tb

        def btn(text, cmd):
            b = tk.Button(tb, text=text, command=cmd, bg=BTN_BG, fg=BTN_FG,
                          activebackground=BTN_ACTIVE, activeforeground=BTN_AFG,
                          relief="flat", bd=0, padx=10, pady=4, font=("Segoe UI", 9),
                          takefocus=0)
            b.pack(side="left", padx=(6, 0), pady=6)
            return b

        def mbtn(text):
            m = tk.Menubutton(tb, text=text, bg=BTN_BG, fg=BTN_FG,
                              activebackground=BTN_ACTIVE, activeforeground=BTN_AFG,
                              relief="flat", bd=0, padx=10, pady=4, font=("Segoe UI", 9),
                              takefocus=0)
            m.pack(side="left", padx=(6, 0), pady=6)
            return m

        self.hold_btn = btn("Hold: OFF", self.toggle_hold)
        self.dwell_btn = btn("Dwell: OFF", self.toggle_dwell)
        self.update_dwell_btn()
        if not self.settings["dwell_button"]:
            self.dwell_btn.pack_forget()          # hidden by the user in Settings
        btn("Minimize", self.minimize)
        btn("Release all", self.release_all)
        self.edit_btn = btn("Edit layout", self.toggle_edit)

        lm = mbtn("Loadouts \u25BE")
        self.loadout_menu = tk.Menu(lm, tearoff=0, postcommand=self.rebuild_loadout_menu)
        lm["menu"] = self.loadout_menu
        self.v_loadout = tk.StringVar(value="")

        sm = mbtn("Settings \u25BE")
        menu = tk.Menu(sm, tearoff=0)
        sm["menu"] = menu
        self.v_unit = tk.IntVar(value=int(self.settings["unit"]))
        self.v_opacity = tk.DoubleVar(value=float(self.settings["opacity"]))
        self.v_topmost = tk.BooleanVar(value=bool(self.settings["topmost"]))
        self.v_scan = tk.BooleanVar(value=bool(self.settings["scancode"]))
        self.v_oneshot = tk.BooleanVar(value=bool(self.settings["oneshot"]))
        self.v_repeat = tk.BooleanVar(value=bool(self.settings["repeat"]))
        self.v_predict = tk.BooleanVar(value=bool(self.settings["predict"]))
        self.v_learn = tk.BooleanVar(value=bool(self.settings["learn"]))
        self.v_mdelay = tk.DoubleVar(value=float(self.settings["mouse_delay"]))
        self.v_dtime = tk.DoubleVar(value=float(self.settings["dwell_time"]))
        self.v_dtol = tk.IntVar(value=int(self.settings["dwell_tol"]))
        self.v_drepeat = tk.BooleanVar(value=bool(self.settings["dwell_repeat"]))
        self.v_dring = tk.BooleanVar(value=bool(self.settings["dwell_ring"]))
        self.v_dwellbtn = tk.BooleanVar(value=bool(self.settings["dwell_button"]))
        self.v_ac = tk.StringVar(value=self.settings["autocorrect"])
        self.v_swipe = tk.BooleanVar(value=bool(self.settings["swipe"]))
        self.v_cap = tk.BooleanVar(value=bool(self.settings["capitalize"]))
        self.v_punct = tk.BooleanVar(value=bool(self.settings["smart_punct"]))
        self.v_swipe_space = tk.BooleanVar(value=bool(self.settings["swipe_space"]))
        self.v_speak = tk.BooleanVar(value=bool(self.settings["speak"]))
        self.v_speak_rate = tk.IntVar(value=int(self.settings["speak_rate"]))
        self.v_speak_vol = tk.IntVar(value=int(self.settings["speak_volume"]))
        self.v_theme = tk.StringVar(value=self.settings["theme"])
        self.v_scan = tk.BooleanVar(value=bool(self.settings["scan"]))
        self.v_suggest_n = tk.IntVar(value=int(self.settings["suggest_count"]))
        self.v_scan_speed = tk.DoubleVar(value=float(self.settings["scan_speed"]))
        self.v_scan_first = tk.DoubleVar(value=float(self.settings["scan_first"]))
        self.v_scan_loops = tk.IntVar(value=int(self.settings["scan_loops"]))
        self.v_swipe_style = tk.StringVar(value=self.settings["swipe_style"])
        self.v_anim = tk.BooleanVar(value=bool(self.settings["animate_pictures"]))
        self.v_min_pos = tk.StringVar(value=self.settings["min_pos"])
        self.v_min_open = tk.DoubleVar(value=float(self.settings["min_open"]))
        self.v_caption = tk.BooleanVar(value=bool(self.settings["show_caption"]))
        appear_menu = tk.Menu(menu, tearoff=0)
        size_menu = tk.Menu(appear_menu, tearoff=0)
        for label, val in (("Tiny", 22), ("Very small", 26), ("Small", 30), ("Medium", 38),
                           ("Large", 46), ("Extra large", 54)):
            size_menu.add_radiobutton(label=label, variable=self.v_unit, value=val,
                                      command=self.on_setting_change)
        size_menu.add_separator()
        size_menu.add_command(label="Custom\u2026", command=self.custom_size)
        appear_menu.add_cascade(label="Key size", menu=size_menu)
        op_menu = tk.Menu(appear_menu, tearoff=0)
        for pct in (100, 90, 80, 70, 55):
            op_menu.add_radiobutton(label="%d%%" % pct, variable=self.v_opacity,
                                    value=pct / 100.0, command=self.on_setting_change)
        appear_menu.add_cascade(label="Opacity", menu=op_menu)
        appear_menu.add_separator()
        appear_menu.add_checkbutton(label="Always on top", variable=self.v_topmost,
                                    command=self.on_setting_change)
        appear_menu.add_separator()
        theme_menu = tk.Menu(appear_menu, tearoff=0)
        for value, label in THEME_NAMES:
            theme_menu.add_radiobutton(label=label, variable=self.v_theme, value=value,
                                       command=self.on_setting_change)
        appear_menu.add_cascade(label="Colour theme", menu=theme_menu)
        appear_menu.add_command(label="Background color\u2026", command=self.pick_bg)
        appear_menu.add_command(label="Reset background color",
                                command=lambda: self.apply_bg(""))
        appear_menu.add_checkbutton(label="Play animated pictures on keys", variable=self.v_anim,
                                    command=self.on_setting_change)
        menu.add_cascade(label="Appearance", menu=appear_menu)
        min_menu = tk.Menu(menu, tearoff=0)
        min_menu.add_command(label="The Minimize button hides the keyboard and leaves a small tab.",
                             state="disabled")
        min_menu.add_command(label="Rest the pointer on the tab to open it again (a click works too).",
                             state="disabled")
        min_menu.add_separator()
        for value, label in MIN_POSITIONS:
            min_menu.add_radiobutton(label="Tab position: " + label, variable=self.v_min_pos,
                                     value=value, command=self.on_setting_change)
        min_menu.add_separator()
        for value, label in MIN_OPEN_TIMES:
            min_menu.add_radiobutton(label="Opens after resting: " + label,
                                     variable=self.v_min_open, value=value,
                                     command=self.on_setting_change)
        menu.add_cascade(label="Minimize tab", menu=min_menu)

        typing_menu = tk.Menu(menu, tearoff=0)
        typing_menu.add_checkbutton(label="Send hardware scan codes (best for games)",
                                    variable=self.v_scan, command=self.on_setting_change)
        typing_menu.add_checkbutton(label="Modifiers release after the next key",
                                    variable=self.v_oneshot, command=self.on_setting_change)
        typing_menu.add_checkbutton(label="Auto-repeat when a key is pressed and held",
                                    variable=self.v_repeat, command=self.on_setting_change)
        menu.add_cascade(label="Typing", menu=typing_menu)

        predict_menu = tk.Menu(menu, tearoff=0)
        predict_menu.add_checkbutton(label="Predictive text bar", variable=self.v_predict,
                                     command=self.on_setting_change)
        predict_menu.add_checkbutton(label="Learn words and phrases as I type",
                                     variable=self.v_learn, command=self.on_setting_change)
        count_menu = tk.Menu(predict_menu, tearoff=0)
        for n in range(1, 9):
            count_menu.add_radiobutton(label="%d word%s" % (n, "" if n == 1 else "s"),
                                       variable=self.v_suggest_n, value=n,
                                       command=self.on_setting_change)
        predict_menu.add_cascade(label="Number of suggestions", menu=count_menu)
        predict_menu.add_separator()
        predict_menu.add_command(label="Forget everything it learned\u2026", command=self.forget_all)
        menu.add_cascade(label="Predictive text", menu=predict_menu)

        cap_menu = tk.Menu(menu, tearoff=0)
        cap_menu.add_checkbutton(label="Capitalize the first word of a sentence, and the word I",
                                 variable=self.v_cap, command=self.on_setting_change)
        cap_menu.add_checkbutton(label="Keep punctuation next to the word before it",
                                 variable=self.v_punct, command=self.on_setting_change)
        menu.add_cascade(label="Capitals and punctuation", menu=cap_menu)

        ac_menu = tk.Menu(menu, tearoff=0)
        for value, label in (("off", "Off"),
                             ("gentle", "Gentle – only fix obvious typos"),
                             ("standard", "Standard – also add apostrophes (dont → don't)")):
            ac_menu.add_radiobutton(label=label, variable=self.v_ac, value=value,
                                    command=self.on_setting_change)
        ac_menu.add_separator()
        ac_menu.add_command(label="Right-click Backspace right after a correction to undo it",
                            state="disabled")
        ac_menu.add_command(label="Forget the words I told it to leave alone…",
                            command=self.forget_ac_keep)
        menu.add_cascade(label="Autocorrect", menu=ac_menu)

        speak_menu = tk.Menu(menu, tearoff=0)
        speak_menu.add_checkbutton(label="Read each word aloud when I finish it",
                                   variable=self.v_speak, command=self.on_setting_change)
        speak_menu.add_checkbutton(label="Show spoken text in a caption bar (words and Speak keys)",
                                   variable=self.v_caption, command=self.on_setting_change)
        speak_menu.add_separator()
        for label, value in SPEAK_RATES:
            speak_menu.add_radiobutton(label="Speed: " + label, variable=self.v_speak_rate,
                                       value=value, command=self.on_setting_change)
        speak_menu.add_separator()
        for label, value in SPEAK_VOLUMES:
            speak_menu.add_radiobutton(label="Volume: " + label, variable=self.v_speak_vol,
                                       value=value, command=self.on_setting_change)
        speak_menu.add_separator()
        speak_menu.add_command(label="Uses the Windows voice. Words are spoken in password boxes too.",
                               state="disabled")
        menu.add_cascade(label="Speak words", menu=speak_menu)

        scan_menu = tk.Menu(menu, tearoff=0)
        scan_menu.add_checkbutton(label="Row-column scanning (for a single switch)",
                                  variable=self.v_scan, command=self.on_setting_change)
        scan_menu.add_command(label="Your switch = a left click on the keys. Click once to start,",
                              state="disabled")
        scan_menu.add_command(label="again on the row you want, again on the key. Right-click pauses.",
                              state="disabled")
        scan_menu.add_separator()
        speed_menu = tk.Menu(scan_menu, tearoff=0)
        for v in (0.4, 0.6, 0.8, 1.0, 1.5, 2.0, 3.0):
            speed_menu.add_radiobutton(label="%.1f seconds" % v, variable=self.v_scan_speed,
                                       value=v, command=self.on_setting_change)
        scan_menu.add_cascade(label="Scan speed (time on each row / key)", menu=speed_menu)
        first_menu = tk.Menu(scan_menu, tearoff=0)
        for v in (0.0, 0.5, 1.0, 1.5):
            first_menu.add_radiobutton(label="None" if v == 0 else "%.1f seconds more" % v,
                                       variable=self.v_scan_first, value=v,
                                       command=self.on_setting_change)
        scan_menu.add_cascade(label="Extra time on the first row / key", menu=first_menu)
        loops_menu = tk.Menu(scan_menu, tearoff=0)
        for v, label in ((1, "1 pass"), (2, "2 passes"), (3, "3 passes"), (5, "5 passes"),
                         (0, "Never pause")):
            loops_menu.add_radiobutton(label=label, variable=self.v_scan_loops, value=v,
                                       command=self.on_setting_change)
        scan_menu.add_cascade(label="Pause after this many passes with no choice", menu=loops_menu)
        menu.add_cascade(label="Switch scanning", menu=scan_menu)

        swipe_menu = tk.Menu(menu, tearoff=0)
        swipe_menu.add_checkbutton(label="Swipe typing", variable=self.v_swipe,
                                   command=self.on_setting_change)
        swipe_menu.add_checkbutton(label="Add a space after each swiped word",
                                   variable=self.v_swipe_space, command=self.on_setting_change)
        swipe_menu.add_separator()
        for value, label in (("drag", "Hold the button and drag over the letters"),
                             ("click", "Click the first letter, glide over the rest, click the last"),
                             ("both", "Either way (a plain click then starts a click-to-swipe path)")):
            swipe_menu.add_radiobutton(label=label, variable=self.v_swipe_style, value=value,
                                       command=self.on_setting_change)
        swipe_menu.add_separator()
        swipe_menu.add_command(label="Hold the mouse button on a letter, drag over the letters",
                               state="disabled")
        swipe_menu.add_command(label="of a word, then let go. With Predictive text on, other likely words appear above.",
                               state="disabled")
        menu.add_cascade(label="Swipe typing", menu=swipe_menu)

        mouse_menu = tk.Menu(menu, tearoff=0)
        md_menu = tk.Menu(mouse_menu, tearoff=0)
        for secs in (0.4, 0.7, 1.0, 1.5):
            md_menu.add_radiobutton(label="%.1f seconds" % secs, variable=self.v_mdelay,
                                    value=secs, command=self.on_setting_change)
        mouse_menu.add_cascade(label="Click delay (hold still before clicking)", menu=md_menu)
        menu.add_cascade(label="Mouse keys", menu=mouse_menu)

        dwell_menu = tk.Menu(menu, tearoff=0)
        dt_menu = tk.Menu(dwell_menu, tearoff=0)
        for secs in DWELL_TIMES:
            dt_menu.add_radiobutton(label="%.1f seconds" % secs, variable=self.v_dtime,
                                    value=secs, command=self.on_setting_change)
        dwell_menu.add_cascade(label="Dwell time", menu=dt_menu)
        ds_menu = tk.Menu(dwell_menu, tearoff=0)
        for name, px in DWELL_STEADINESS:
            ds_menu.add_radiobutton(label="%s (%d px)" % (name, px), variable=self.v_dtol,
                                    value=px, command=self.on_setting_change)
        dwell_menu.add_cascade(label="Steadiness (shaky pointer)", menu=ds_menu)
        dwell_menu.add_separator()
        dwell_menu.add_checkbutton(label="Keep clicking while the pointer rests (repeat)",
                                   variable=self.v_drepeat, command=self.on_setting_change)
        dwell_menu.add_checkbutton(label="Show the countdown ring", variable=self.v_dring,
                                   command=self.on_setting_change)
        dwell_menu.add_checkbutton(label="Show the Dwell button on the toolbar",
                                   variable=self.v_dwellbtn, command=self.on_dwell_btn_change)
        menu.add_cascade(label="Dwell clicking", menu=dwell_menu)

        self.menus = [self.loadout_menu, menu, appear_menu, size_menu, op_menu, typing_menu,
                      predict_menu, cap_menu, ac_menu, swipe_menu, mouse_menu, md_menu, dwell_menu, dt_menu,
                      ds_menu]
        self.hint = tk.Label(tb, text="Right-click a key to hold it", bg=BG, fg=MUTED_FG,
                             font=("Segoe UI", 9))
        self.update_hint()

    def update_hint(self):
        # The hint makes the toolbar wider; drop it at small sizes so the window can shrink.
        if int(self.settings["unit"]) < 34:
            self.hint.pack_forget()
        else:
            self.hint.pack(side="right", padx=max(4, round(self.unit * 0.26)))

    def apply_ui_scale(self):
        """Size every button, menu and bar to match the key size (self.unit)."""
        u = self.unit
        f = max(8, int(u * 0.32))            # text size in pixels (Medium = 12px, as before)
        big = max(9, int(u * 0.40))          # suggestion bar text
        px, py = max(3, round(u * 0.26)), max(1, round(u * 0.105))
        gap = max(2, round(u * 0.16))
        half = max(2, gap // 2)
        font = ("Segoe UI", -f)
        self.cap_size()

        for w in self.toolbar.winfo_children():
            cls = w.winfo_class()
            if cls in ("Button", "Menubutton"):
                w.config(font=font, padx=px, pady=py)
                if w.winfo_manager():                  # leave a hidden button hidden
                    w.pack_configure(padx=(gap, 0), pady=gap)
            elif cls == "Label":
                w.config(font=font)
        for m in self.menus:
            try:
                m.config(font=font)
            except tk.TclError:
                pass

        for i, b in enumerate(self.sbtns):
            b.config(font=("Segoe UI", -big), pady=max(2, round(u * 0.13)))
            b.pack_configure(padx=(gap if i == 0 else half, half), pady=(0, gap))
        self.sreset.config(font=("Segoe UI", -big), padx=max(4, round(u * 0.21)),
                           pady=max(2, round(u * 0.13)))
        self.sreset.pack_configure(padx=(half, gap), pady=(0, gap))

        for fr in self.panel.winfo_children():
            for w in fr.winfo_children():
                cls = w.winfo_class()
                if cls == "Button":
                    w.config(font=font, padx=max(4, round(u * 0.24)),
                             pady=max(1, round(u * 0.08)))
                elif cls in ("Label", "Entry", "Spinbox"):
                    w.config(font=font)
        try:
            ttk.Style().configure("TCombobox", font=font)
            self.root.option_add("*TCombobox*Listbox.font", font)
        except Exception:
            pass

    def custom_size(self):
        val = simpledialog.askinteger(
            "Key size", "Key size in pixels (14 to 80). Medium is 38, Tiny is 22:",
            initialvalue=int(self.v_unit.get()), minvalue=14, maxvalue=80, parent=self.root)
        if val:
            self.v_unit.set(val)
            self.on_setting_change()

    def on_setting_change(self):
        s = self.settings
        s["unit"] = max(14, min(80, int(self.v_unit.get())))
        self.update_hint()
        s["opacity"] = float(self.v_opacity.get())
        s["topmost"] = bool(self.v_topmost.get())
        s["scancode"] = bool(self.v_scan.get())
        s["oneshot"] = bool(self.v_oneshot.get())
        s["repeat"] = bool(self.v_repeat.get())
        s["predict"] = bool(self.v_predict.get())
        s["learn"] = bool(self.v_learn.get())
        s["autocorrect"] = self.v_ac.get() if self.v_ac.get() in AC_MODES else "off"
        if s["autocorrect"] != "off":
            self.ac_enable()
        else:
            self.ac_pending = self.ac_undo = None
        s["capitalize"] = bool(self.v_cap.get())
        s["smart_punct"] = bool(self.v_punct.get())
        s["swipe"] = bool(self.v_swipe.get())
        s["swipe_space"] = bool(self.v_swipe_space.get())
        want_anim = bool(self.v_anim.get())
        if want_anim != bool(s.get("animate_pictures", True)):
            s["animate_pictures"] = want_anim
            self.redraw()
        want_cap = bool(self.v_caption.get())
        if want_cap != bool(s.get("show_caption", True)):
            s["show_caption"] = want_cap
            self.apply_caption_setting()
        mp = self.v_min_pos.get()
        s["min_pos"] = mp if mp in dict(MIN_POSITIONS) else "bc"
        s["min_open"] = max(0.0, float(self.v_min_open.get()))
        th = self.v_theme.get()
        if th in THEMES and th != s["theme"]:
            old = theme_snapshot()
            set_theme(th)
            s["theme"] = th
            self.recolor_ui(old)
        want = max(1, min(8, int(self.v_suggest_n.get())))
        if want != int(s["suggest_count"]):
            self.set_suggest_count(want)
        s["scan"] = bool(self.v_scan.get())
        s["scan_speed"] = float(self.v_scan_speed.get())
        s["scan_first"] = float(self.v_scan_first.get())
        s["scan_loops"] = int(self.v_scan_loops.get())
        self.scan_apply()
        style = self.v_swipe_style.get()
        s["swipe_style"] = style if style in ("drag", "click", "both") else "drag"
        self.cswipe_cancel()
        s["speak"] = bool(self.v_speak.get())
        s["speak_rate"] = int(self.v_speak_rate.get())
        s["speak_volume"] = int(self.v_speak_vol.get())
        if not s["speak"] and self.speaker is not None:
            self.speaker.stop()
        if s["swipe"]:
            self.ac.load_async()
        else:
            self.swipe_cancel()
        s["mouse_delay"] = float(self.v_mdelay.get())
        s["dwell_time"] = float(self.v_dtime.get())
        s["dwell_tol"] = int(self.v_dtol.get())
        s["dwell_repeat"] = bool(self.v_drepeat.get())
        s["dwell_ring"] = bool(self.v_dring.get())
        self.pt.learning = s["learn"]
        if not s["predict"]:
            self.pt.reset()
        self.refresh_bar()
        self.sender.scancode_mode = s["scancode"]
        # Setting -topmost or -alpha makes Tk rewrite the window's extended style, which
        # silently drops WS_EX_NOACTIVATE.  After that every click on a key activates KeyDeck
        # itself, so nothing is typed anywhere.  So: only touch them when they really changed,
        # and put the style back straight afterwards.
        touched = False
        if s["topmost"] != self._applied_topmost:
            self.root.attributes("-topmost", s["topmost"])
            self._applied_topmost = s["topmost"]
            touched = True
        if s["opacity"] != self._applied_opacity:
            try:
                self.root.attributes("-alpha", s["opacity"])
            except Exception:
                pass
            self._applied_opacity = s["opacity"]
            touched = True
        if touched:
            self.apply_noactivate(not self.edit_mode)
        new_unit = int(s["unit"] * self.scale)
        if new_unit != self.unit:
            self.unit = new_unit
            self.apply_ui_scale()
            self.redraw()
            self.keep_on_screen()
        save_settings(s)
        self.restore_focus()

    # ---------------- edit panel ----------------
    def build_edit_panel(self):
        p = tk.Frame(self.root, bg=PANEL)
        p.grid(row=3, column=0, sticky="ew")
        p.grid_remove()
        self.panel = p
        self.v_key = tk.StringVar()
        self.v_label = tk.StringVar()
        self.v_label2 = tk.StringVar()
        self.v_w = tk.StringVar()
        self.v_h = tk.StringVar()

        def lbl(parent, text):
            tk.Label(parent, text=text, bg=PANEL, fg=LABEL_FG,
                     font=("Segoe UI", 9)).pack(side="left", padx=(8, 2))

        def pbtn(parent, text, cmd):
            b = tk.Button(parent, text=text, command=cmd, bg=BTN_ALT, fg=BTN_FG,
                          activebackground=BTN_ALT_ACTIVE, activeforeground=BTN_AFG,
                          relief="flat", bd=0, padx=9, pady=3, font=("Segoe UI", 9))
            b.pack(side="left", padx=(6, 0))
            return b

        r1 = tk.Frame(p, bg=PANEL)
        r1.pack(fill="x", padx=4, pady=(8, 3))
        lbl(r1, "Sends")
        cb = ttk.Combobox(r1, textvariable=self.v_key, values=list(CATALOG) + EXTRA_CHOICES,
                          width=12, state="readonly")
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", self.on_key_choice)
        lbl(r1, "Label")
        tk.Entry(r1, textvariable=self.v_label, width=10).pack(side="left")
        lbl(r1, "Shift label")
        tk.Entry(r1, textvariable=self.v_label2, width=6).pack(side="left")
        lbl(r1, "Width")
        sw = tk.Spinbox(r1, from_=0.25, to=20, increment=0.25, textvariable=self.v_w,
                        width=5, command=self.on_dim_edit)
        sw.pack(side="left")
        sw.bind("<Return>", lambda e: self.on_dim_edit())
        sw.bind("<FocusOut>", lambda e: self.on_dim_edit())
        lbl(r1, "Height")
        sh = tk.Spinbox(r1, from_=0.25, to=20, increment=0.25, textvariable=self.v_h,
                        width=5, command=self.on_dim_edit)
        sh.pack(side="left")
        sh.bind("<Return>", lambda e: self.on_dim_edit())
        sh.bind("<FocusOut>", lambda e: self.on_dim_edit())
        self.v_label.trace_add("write", self.on_label_edit)
        self.v_label2.trace_add("write", self.on_label_edit)

        r2 = tk.Frame(p, bg=PANEL)
        r2.pack(fill="x", padx=4, pady=(3, 3))
        pbtn(r2, "+ Add key", self.add_key)
        pbtn(r2, "Key color\u2026", lambda: self.pick_color("color"))
        pbtn(r2, "Text color\u2026", lambda: self.pick_color("fg"))
        pbtn(r2, "Outline color\u2026", lambda: self.pick_color("edge"))
        pbtn(r2, "Outline thickness\u2026", self.pick_edge_width)
        pbtn(r2, "Reset colors", self.reset_colors)
        pbtn(r2, "Program shortcut\u2026", self.configure_shortcut)
        pbtn(r2, "Program macro\u2026", self.configure_macro)
        pbtn(r2, "Layer key\u2026", self.configure_layer)
        tk.Label(r2, text="Drag keys to move \u2022 drag a corner to resize", bg=PANEL,
                 fg=MUTED_FG, font=("Segoe UI", 9)).pack(side="right", padx=8)

        r2b = tk.Frame(p, bg=PANEL)
        r2b.pack(fill="x", padx=4, pady=(0, 3))
        pbtn(r2b, "Picture\u2026", self.pick_picture)
        pbtn(r2b, "Remove picture", self.remove_picture)
        pbtn(r2b, "Program speech\u2026", self.configure_speak)
        tk.Label(r2b, text="A key can show a picture and say a phrase out loud", bg=PANEL,
                 fg=MUTED_FG, font=("Segoe UI", 9)).pack(side="right", padx=8)

        r3 = tk.Frame(p, bg=PANEL)
        r3.pack(fill="x", padx=4, pady=(0, 8))
        pbtn(r3, "Duplicate", self.duplicate_key)
        pbtn(r3, "Delete", self.delete_key)
        pbtn(r3, "Clear all", self.clear_all_keys)
        pbtn(r3, "Save loadout", self.save_loadout)
        pbtn(r3, "Save as\u2026", self.save_loadout_as)
        tk.Label(r3, text="Mouse click and scroll keys are in the Sends list", bg=PANEL,
                 fg=MUTED_FG, font=("Segoe UI", 9)).pack(side="right", padx=8)

    def load_props(self):
        self._loading = True
        k = self.sel
        if k:
            self.v_key.set(k["key"])
            self.v_label.set(k["label"])
            self.v_label2.set(k["label2"])
            self.v_w.set(("%g" % k["w"]))
            self.v_h.set(("%g" % k["h"]))
        else:
            for v in (self.v_key, self.v_label, self.v_label2, self.v_w, self.v_h):
                v.set("")
        self._loading = False

    def on_label_edit(self, *_):
        if self._loading or not self.sel:
            return
        self.sel["label"] = self.v_label.get()
        self.sel["label2"] = self.v_label2.get()
        self.refresh_key(self.sel)

    def on_key_choice(self, _e=None):
        k = self.sel
        if not k:
            return
        old, new = k["key"], self.v_key.get()
        if new in ("Shortcut", "Macro", "Layer", "Speak"):
            {"Shortcut": self.configure_shortcut, "Macro": self.configure_macro,
             "Layer": self.configure_layer, "Speak": self.configure_speak}[new]()
            self.load_props()                 # re-sync the box if the dialog was cancelled
            return
        if new not in CATALOG and new not in MOUSE_KEYS:
            return
        auto = {"", LABELS.get(old)}          # labels that were never typed by the user
        if old == "Macro":
            auto.add(macro_label(k.get("macro", "")))
        elif old == "Layer":
            auto.add(layer_label(k.get("layer_mode", "go"), k.get("layer", "")))
        elif old == "Speak":
            auto.add(macro_label(k.get("speak", "")))
        if k["label"] in auto:
            k["label"] = LABELS[new]
            k["label2"] = ""
        k["key"] = new
        clear_special(k)
        self.load_props()
        self.refresh_key(k)

    def on_dim_edit(self):
        k = self.sel
        if self._loading or not k:
            return
        try:
            w = max(0.25, min(20.0, snap(float(self.v_w.get()))))
            h = max(0.25, min(20.0, snap(float(self.v_h.get()))))
        except ValueError:
            self.load_props()
            return
        k["w"], k["h"] = w, h
        self.load_props()
        self.refresh_key(k)
        self.fit_canvas()

    def pick_color(self, field):
        k = self.sel
        if not k:
            return
        initial = k.get(field) or {"color": KEY_COLOR, "fg": TEXT, "edge": KEY_EDGE}[field]
        res = colorchooser.askcolor(color=initial, parent=self.root,
                                    title={"color": "Key color", "fg": "Text color",
                                           "edge": "Outline color"}[field])
        if res and res[1]:
            k[field] = res[1]
            self.refresh_key(k)

    def reset_colors(self):
        if self.sel:
            self.sel["color"] = ""
            self.sel["fg"] = ""
            self.sel["edge"] = ""
            self.sel["edge_px"] = None
            self.refresh_key(self.sel)

    def new_id(self):
        i = self._next_id
        self._next_id += 1
        return i

    def add_key(self):
        bottom = max((k["y"] + k["h"] for k in self.keys), default=0)
        k = new_key_dict("A", 0, bottom + 0.5)
        k["id"] = self.new_id()
        self.keys.append(k)
        self.sel = k
        self.load_props()
        self.redraw()

    def duplicate_key(self):
        if not self.sel:
            return
        k = dict(self.sel)
        k["id"] = self.new_id()
        k["x"] = self.sel["x"] + 0.5
        k["y"] = self.sel["y"] + 0.5
        self.keys.append(k)
        self.sel = k
        self.load_props()
        self.redraw()

    def configure_shortcut(self):
        """Turn the selected button into a key that sends a modifier shortcut."""
        k = self.sel
        if not k:
            messagebox.showinfo("KeyDeck", "Select a key in Edit layout first.", parent=self.root)
            return
        current = k.get("shortcut", "Ctrl+Shift+Esc") if k.get("key") == "Shortcut" else "Ctrl+Shift+Esc"
        raw = simpledialog.askstring(
            "Program shortcut",
            "Enter a shortcut using + between keys, e.g. Ctrl+Shift+Esc or Alt+F4.\n"
            "Supported names include Ctrl, Shift, Alt, Win, letters, numbers, F1–F24, and other keyboard keys.\n"
            "Note: Windows blocks software-generated Ctrl+Alt+Delete.",
            initialvalue=current, parent=self.root)
        if raw is None:
            return
        parsed, error = self.parse_shortcut(raw)
        if error:
            messagebox.showwarning("KeyDeck", error, parent=self.root)
            return
        clear_special(k)
        k["key"] = "Shortcut"
        k["shortcut"] = parsed
        k["label"] = raw.strip()
        k["label2"] = ""
        self.load_props()
        self.refresh_key(k)
        self.fit_canvas()

    def parse_shortcut(self, raw):
        parts = [part.strip() for part in raw.split("+") if part.strip()]
        if len(parts) < 2:
            return None, "Enter at least two keys separated by +, such as Ctrl+Shift+Esc."
        return parse_chord(raw)

    def clear_all_keys(self):
        if not messagebox.askyesno("Clear keyboard", "Remove every key from this layout?\nYou can add keys again or save it as a blank loadout.", parent=self.root):
            return
        self.release_all(redraw=False)
        self.keys = []
        self.sel = None
        self.load_props()
        self.redraw()

    def create_blank_layout(self):
        self.release_all(redraw=False)
        self.keys = []
        self.sel = None
        self.drag = None
        self.loadout_name = ""
        self.v_loadout.set("")
        self.load_props()
        self.redraw()
        self.keep_on_screen()

    def delete_key(self):
        if not self.sel:
            return
        self.keys = [k for k in self.keys if k is not self.sel]
        self.sel = None
        self.load_props()
        self.redraw()

    # ---------------- loadouts ----------------
    def rebuild_loadout_menu(self):
        m = self.loadout_menu
        m.delete(0, "end")
        self.v_loadout.set(self.loadout_name)
        m.add_radiobutton(label="Default (built-in)", variable=self.v_loadout, value="",
                          command=lambda: self.load_loadout(""))
        saved = list_loadouts()
        if saved:
            m.add_separator()
        for name in saved:
            m.add_radiobutton(label=name, variable=self.v_loadout, value=name,
                              command=lambda n=name: self.load_loadout(n))
        m.add_separator()
        m.add_command(label="Blank layout (edit from scratch)", command=self.create_blank_layout)
        m.add_command(label="Save", command=self.save_loadout)
        m.add_command(label="Save as\u2026", command=self.save_loadout_as)
        m.add_command(label="Delete current loadout", command=self.delete_loadout)
        m.add_command(label="Reset to default layout", command=lambda: self.load_loadout(""))
        m.add_separator()
        m.add_command(label="Export this layout\u2026", command=self.export_layout)
        m.add_command(label="Export all layouts\u2026", command=self.export_all_layouts)
        m.add_command(label="Import layouts\u2026", command=self.import_layouts)
        if IS_WIN:
            m.add_separator()
            m.add_command(label="Open loadouts folder", command=self.open_folder)

    def open_folder(self):
        os.makedirs(LOADOUT_DIR, exist_ok=True)
        try:
            os.startfile(LOADOUT_DIR)
        except Exception:
            pass

    def load_loadout(self, name, persist=True):
        """persist=False is a temporary switch (one-key layers): it isn't remembered for
        next launch and it leaves a running macro / armed mouse key alone."""
        self.release_all(redraw=False, keep_actions=not persist)
        if persist:
            self.layer_return = None
            self.layer_pending = False
        keys = None
        if name:
            try:
                with open(os.path.join(LOADOUT_DIR, name + ".json"), "r", encoding="utf-8") as f:
                    data = json.load(f)
                keys = self.keys_from_data(data)
            except Exception:
                keys = None
                name = ""
        if keys is None:
            keys = default_layout()
            name = ""
        self._next_id = 1
        for k in keys:
            k["id"] = self.new_id()
        self.keys = keys
        self.loadout_name = name
        self.sel = None
        self.states.clear()
        self.macro_id = None                  # key ids were reassigned; drop stale highlights
        if self.armed:
            self.armed["id"] = None
        if persist:
            self.settings["loadout"] = name
            save_settings(self.settings)
        self.load_props()
        self.redraw()
        self.keep_on_screen()

    def write_loadout(self, name):
        os.makedirs(LOADOUT_DIR, exist_ok=True)
        data = {"version": 1, "keys": [{kk: vv for kk, vv in k.items() if kk != "id"}
                                       for k in self.keys]}
        with open(os.path.join(LOADOUT_DIR, name + ".json"), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        self.loadout_name = name
        self.settings["loadout"] = name
        save_settings(self.settings)

    def save_loadout(self):
        if not self.loadout_name:
            return self.save_loadout_as()
        try:
            self.write_loadout(self.loadout_name)
        except Exception as e:
            messagebox.showerror("KeyDeck", "Could not save: %s" % e, parent=self.root)

    def save_loadout_as(self):
        raw = simpledialog.askstring("Save loadout", "Loadout name:", parent=self.root)
        if raw is None:
            return
        name = safe_name(raw)
        if not name:
            messagebox.showwarning("KeyDeck", "Please enter a name.", parent=self.root)
            return
        if name in list_loadouts() and name != self.loadout_name:
            if not messagebox.askyesno("KeyDeck", "Replace the existing loadout '%s'?" % name,
                                       parent=self.root):
                return
        try:
            self.write_loadout(name)
        except Exception as e:
            messagebox.showerror("KeyDeck", "Could not save: %s" % e, parent=self.root)

    def delete_loadout(self):
        if not self.loadout_name:
            messagebox.showinfo("KeyDeck", "The built-in default can't be deleted.",
                                parent=self.root)
            return
        if messagebox.askyesno("KeyDeck", "Delete loadout '%s'?" % self.loadout_name,
                               parent=self.root):
            try:
                os.remove(os.path.join(LOADOUT_DIR, self.loadout_name + ".json"))
            except Exception:
                pass
            self.load_loadout("")

    # ---------------- drawing ----------------
    def rect(self, k):
        u, p = self.unit, self.pad
        return (p + k["x"] * u, p + k["y"] * u,
                p + (k["x"] + k["w"]) * u, p + (k["y"] + k["h"]) * u)

    def key_at(self, x, y):
        for k in reversed(self.keys):
            x1, y1, x2, y2 = self.rect(k)
            if x1 <= x < x2 and y1 <= y < y2:
                return k
        return None

    def is_mod(self, k):
        return k.get("key") in CATALOG and CATALOG[k["key"]][0] in MOD_VKS

    def shift_active(self):
        for k in self.keys:
            if k.get("key") in CATALOG and self.states.get(k["id"]) in ("oneshot", "hold") and CATALOG[k["key"]][0] in SHIFT_VKS:
                return True
        return False

    def colors_for(self, k):
        base = k.get("color") or (MOD_COLOR if self.is_mod(k) else KEY_COLOR)
        fg = k.get("fg") or TEXT
        if self.edit_mode:
            return base, fg
        if self.armed and self.armed["id"] == k["id"]:
            if self.armed["kind"] == "scroll":
                return HOLD_COLOR, HOLD_FG
            return ONESHOT_COLOR, ONESHOT_FG
        h = self.scan_hl.get(k["id"])
        if h == "key":
            return SCAN_COLOR, SCAN_FG
        if h == "row":
            return SCAN_ROW, SCAN_ROW_FG
        if self.macro_id is not None and self.macro_id == k["id"]:
            return PRESS_COLOR, PRESS_FG
        if self.swipe and k["id"] in self.swipe["touched"]:
            return PRESS_COLOR, PRESS_FG
        if self.cswipe and k["id"] in self.cswipe["touched"]:
            return PRESS_COLOR, PRESS_FG
        st = self.states.get(k["id"])
        if k.get("key") == "Caps Lock" and self.caps_on():
            return ONESHOT_COLOR, ONESHOT_FG
        if st == "mom":
            return PRESS_COLOR, PRESS_FG
        if st == "oneshot":
            return ONESHOT_COLOR, ONESHOT_FG
        if st == "hold":
            return HOLD_COLOR, HOLD_FG
        return base, fg

    def label_for(self, k):
        if k.get("label2") and self.shift_active():
            return k["label2"]
        return k["label"]

    def fit_text(self, k, text):
        """Pick a pixel font size so the label fits inside the key; clip it if it can't."""
        u = self.unit
        avail = max(6, k["w"] * u - max(6, u * 0.2))
        lines = text.split("\n")
        n = max(1, max(len(s) for s in lines))
        px = max(6, min(int(u * 0.38), int(k["h"] * u * 0.6), int(avail / (0.62 * n))))
        maxc = max(1, int(avail / (0.62 * px)))
        if n > maxc:
            text = "\n".join(s[:maxc] for s in lines)
        return ("Segoe UI", -px, "bold"), text

    def draw_key(self, k):
        c = self.canvas
        tag = "key%d" % k["id"]
        self.anim_items().pop(k["id"], None)
        x1, y1, x2, y2 = self.rect(k)
        g = 2
        fill, fg = self.colors_for(k)
        selected = self.edit_mode and self.sel is k
        r = max(4, int(self.unit * 0.12))
        c.create_polygon(rounded(x1 + g, y1 + g, x2 - g, y2 - g, r), smooth=True,
                         fill=fill, outline=(SEL_EDGE if selected else "" if k.get("edge_px") == 0
                                  else (k.get("edge") or KEY_EDGE)),
                         width=(max(3, k.get("edge_px") or 0) if selected else
                                k["edge_px"] if k.get("edge_px") is not None
                                else max(KEY_EDGE_W, 2 if k.get("edge") else 1)), tags=(tag,))
        text = self.label_for(k)
        img = None
        cap_h = 0
        if k.get("image_data"):
            bw, bh = (x2 - x1) - 2 * g - 8, (y2 - y1) - 2 * g - 8
            cap_h = max(14, int(bh * 0.28)) if text else 0
            img = self.key_image(k, bw, bh - cap_h)
            movie = (self.key_frames(k, bw, bh - cap_h)
                     if img and self.settings.get("animate_pictures", True) else None)
            if img:
                item = c.create_image((x1 + x2) / 2, y1 + g + 4 + (bh - cap_h) / 2,
                                      image=movie[0][0] if movie else img, tags=(tag,))
                if movie:
                    self.anim_items()[k["id"]] = {
                        "item": item, "frames": movie[0], "delays": movie[1], "i": 0,
                        "due": time.monotonic() + movie[1][0] / 1000.0}
        if text and img:
            px = max(8, min(int(cap_h * 0.7), int(self.unit * 0.38)))
            avail = max(6, (x2 - x1) - 2 * g - 8)
            line = " ".join(text.split())
            line = line[:max(1, int(avail / (0.6 * px)))]
            c.create_text((x1 + x2) / 2, y2 - g - 4 - cap_h / 2, text=line, fill=fg,
                          font=("Segoe UI", -px, "bold"), tags=(tag,))
        elif text:
            font, text = self.fit_text(k, text)
            c.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=text, fill=fg,
                          font=font, justify="center", tags=(tag,))
        if selected:
            c.create_rectangle(x2 - g - 9, y2 - g - 9, x2 - g - 1, y2 - g - 1,
                               fill=SEL_EDGE, outline="", tags=(tag,))

    def refresh_key(self, k):
        self.canvas.delete("key%d" % k["id"])
        self.draw_key(k)

    def redraw(self):
        self.canvas.delete("all")
        self.anim_items().clear()
        for k in self.keys:
            self.draw_key(k)
        self.fit_canvas()

    def fit_canvas(self):
        u = self.unit
        mx = max((k["x"] + k["w"] for k in self.keys), default=10)
        my = max((k["y"] + k["h"] for k in self.keys), default=4)
        extra = 2 if self.edit_mode else 0
        w = int(self.pad * 2 + (mx + extra) * u)
        h = int(self.pad * 2 + (my + extra) * u)
        w = max(w, int(300 * self.scale))
        self.canvas.config(width=w, height=h)

    # ---------------- typing ----------------
    def press_key(self, k):
        name = k.get("key")
        if name == "Shortcut":
            self.send_shortcut(k.get("shortcut", []))
        elif name in CATALOG:
            self.sender.send(name, True)

    def release_key(self, k):
        if k.get("key") in CATALOG:
            self.sender.send(k["key"], False)

    def send_shortcut(self, names):
        """Tap a chord in modifier-first order, then release in reverse order."""
        if not names:
            return
        mods = [n for n in names if CATALOG[n][0] in MOD_VKS]
        regular = [n for n in names if n not in mods]
        # Press modifiers first; tap each non-modifier while they are held.
        pressed = []
        try:
            for name in mods:
                self.sender.send(name, True)
                pressed.append(name)
            for name in regular:
                self.sender.send(name, True)
                self.sender.send(name, False)
        finally:
            for name in reversed(pressed):
                self.sender.send(name, False)

    def set_state(self, k, st):
        was_shift = self.shift_active()
        if st is None:
            self.states.pop(k["id"], None)
        else:
            self.states[k["id"]] = st
        if self.is_mod(k) and CATALOG[k["key"]][0] in SHIFT_VKS and was_shift != self.shift_active():
            self.redraw()
        else:
            self.refresh_key(k)

    def key_by_id(self, kid):
        for k in self.keys:
            if k["id"] == kid:
                return k
        return None

    def release_latched(self, k):
        self.release_key(k)
        self.set_state(k, None)

    def release_oneshots(self):
        for kid, st in list(self.states.items()):
            if st == "oneshot":
                k = self.key_by_id(kid)
                if k:
                    self.release_latched(k)

    def release_all(self, redraw=True, keep_actions=False):
        self.cancel_repeat()
        self.end_forced_shift()
        if not keep_actions:
            self.cancel_macro(redraw=False)
            self.disarm_mouse(redraw=False)
        for kid in list(self.states):
            k = self.key_by_id(kid)
            if k:
                self.release_key(k)
        self.states.clear()
        self.pressing = None
        if redraw:
            self.redraw()

    def emergency_release(self):
        try:
            for kid in list(self.states):
                k = self.key_by_id(kid)
                if k:
                    self.release_key(k)
        except Exception:
            pass

    def toggle_hold(self):
        self.hold_mode = not self.hold_mode
        self.hold_btn.config(text="Hold: ON" if self.hold_mode else "Hold: OFF",
                             bg=HOLD_COLOR if self.hold_mode else BTN_BG)

    def cancel_repeat(self):
        if self.repeat_job:
            self.root.after_cancel(self.repeat_job)
            self.repeat_job = None

    def repeat_tick(self, k):
        if self.pressing is k and self.states.get(k["id"]) == "mom":
            self.press_key(k)
            self.predict_key(k)
            self.repeat_job = self.root.after(35, lambda: self.repeat_tick(k))

    # ---------------- mouse: typing mode ----------------
    def on_press(self, e):
        if self.edit_mode:
            return self.edit_press(e)
        if self.scan_on() and not self.scan_injecting:
            return self.scan_switch()        # scanning: any click on the keys is the switch
        k = self.key_at(e.x, e.y)
        if not k:
            return
        name = k.get("key")
        if self.layer_return is not None and not self.is_mod(k):
            self.layer_pending = True        # this press ends a one-key layer when it is released
        if name in MOUSE_KEYS:
            return self.toggle_mouse_arm(k)
        if name == "Speak":
            return self.trigger_speak(k)
        if name == "Macro":
            return self.trigger_macro(k)
        if name == "Layer":
            return self.trigger_layer(k)
        if self.cswipe is not None and self.cswipe_click(e, k):
            return                           # this click was the end of a click-to-swipe path
        st = self.states.get(k["id"])
        if st in ("hold", "oneshot"):
            self.release_latched(k)
            return
        if self.hold_mode and name in CATALOG:
            self.press_key(k)
            self.set_state(k, "hold")
        elif self.is_mod(k):
            self.press_key(k)
            self.set_state(k, "oneshot" if self.settings["oneshot"] else "hold")
        elif self.swipe_ok(k):
            self.swipe_begin(e, k)           # tap, hold or swipe: decided as the mouse moves
        elif self.click_ok(k):
            self.cswipe_begin(k, e)          # click-to-swipe: this click starts a path
        else:
            forced = self.press_with_pre(k)  # fix the word just typed, tidy spacing, capitalise
            self.pressing = k
            self.set_state(k, "mom")
            self.predict_key(k, forced)
            if self.settings["repeat"] and name in CATALOG:     # shortcut keys fire only once
                self.cancel_repeat()
                self.repeat_job = self.root.after(450, lambda: self.repeat_tick(k))

    def on_release(self, e):
        if self.edit_mode:
            return self.edit_release(e)
        if self.scan_on() and not self.scan_injecting:
            return
        if self.swipe is not None:
            self.swipe_end(e)
        k = self.pressing
        if k is not None:
            self.cancel_repeat()
            self.pressing = None
            if self.states.get(k["id"]) == "mom":
                self.release_key(k)
                self.set_state(k, None)
                self.release_oneshots()
        self.end_forced_shift()
        self.finish_lone()
        if self.layer_return is not None and self.layer_pending:
            base, self.layer_return, self.layer_pending = self.layer_return, None, False
            self.load_loadout(base, persist=False)

    def on_right_press(self, e):
        if self.edit_mode:
            return
        if self.scan_on():
            self.scan_pause()                # right-click pauses the scanner
            return
        k = self.key_at(e.x, e.y)
        if self.cswipe is not None:
            self.cswipe_cancel()             # right-click cancels a click-to-swipe path
            return
        if k and k.get("key") == "Backspace" and self.swipe_ctx and self.swipe_delete():
            self.update_suggestions()
            return                           # right-click Backspace wipes the word just swiped
        if k and k.get("key") == "Backspace" and self.ac_undo and self.ac_revert():
            self.update_suggestions()
            return                           # right-click Backspace undoes an autocorrection
        if not k or k.get("key") not in CATALOG:
            return                           # macro, mouse, layer and shortcut keys can't be held
        if self.states.get(k["id"]) in ("hold", "oneshot"):
            self.release_latched(k)
        elif self.states.get(k["id"]) is None:
            self.press_key(k)
            self.set_state(k, "hold")

    # ---------------- mouse: edit mode ----------------
    def on_hover(self, e):
        if self.scan_on():
            return
        if self.cswipe is not None:
            self.cswipe_move(e)
            return
        if not self.edit_mode:
            return
        near = self.near_handle(e.x, e.y)
        self.canvas.config(cursor="size_nw_se" if near else "")

    def near_handle(self, x, y):
        k = self.sel
        if not (self.edit_mode and k):
            return False
        _x1, _y1, x2, y2 = self.rect(k)
        return abs(x - (x2 - 5)) <= 10 and abs(y - (y2 - 5)) <= 10

    def edit_press(self, e):
        if self.near_handle(e.x, e.y):
            self.drag = ("resize",)
            return
        k = self.key_at(e.x, e.y)
        if k:
            self.keys.remove(k)
            self.keys.append(k)
            x1, y1, _x2, _y2 = self.rect(k)
            self.sel = k
            self.drag = ("move", e.x - x1, e.y - y1)
        else:
            self.sel = None
            self.drag = None
        self.load_props()
        self.redraw()

    def on_motion(self, e):
        if self.swipe is not None and self.swipe_move(e):
            return
        if not self.edit_mode or not self.drag or not self.sel:
            return
        k = self.sel
        u, p = self.unit, self.pad
        if self.drag[0] == "move":
            nx = max(0.0, snap((e.x - self.drag[1] - p) / u))
            ny = max(0.0, snap((e.y - self.drag[2] - p) / u))
            if nx != k["x"] or ny != k["y"]:
                self.canvas.move("key%d" % k["id"], (nx - k["x"]) * u, (ny - k["y"]) * u)
                k["x"], k["y"] = nx, ny
        else:
            nw = max(0.25, snap((e.x - p) / u - k["x"]))
            nh = max(0.25, snap((e.y - p) / u - k["y"]))
            if nw != k["w"] or nh != k["h"]:
                k["w"], k["h"] = nw, nh
                self.refresh_key(k)

    def edit_release(self, e):
        if self.drag:
            self.drag = None
            self.load_props()
            self.fit_canvas()

    def toggle_edit(self):
        self.release_all(redraw=False)
        self.layer_return = None
        self.layer_pending = False
        self.edit_mode = not self.edit_mode
        self.sel = None
        self.drag = None
        self.load_props()
        self.edit_btn.config(text="Done editing" if self.edit_mode else "Edit layout",
                             bg="#2f6fb5" if self.edit_mode else BTN_BG)
        if self.edit_mode:
            self.panel.grid()
            self.apply_noactivate(False)   # text boxes need keyboard focus
        else:
            self.panel.grid_remove()
            self.apply_noactivate(True)
            self.canvas.config(cursor="")
        self.pt.reset()
        self.refresh_bar()
        self.redraw()
        self.keep_on_screen()

    # ---------------- predictive text ----------------
    def build_suggest_bar(self):
        bar = tk.Frame(self.root, bg=BG)
        bar.grid(row=1, column=0, sticky="ew")
        self.sbar = bar
        self.sbtns = []
        self.make_suggest_buttons()
        if not self.settings["predict"]:
            bar.grid_remove()

    def make_suggest_buttons(self):
        """(Re)build the word buttons: as many as the 'number of suggestions' setting says."""
        for w in self.sbar.winfo_children():
            w.destroy()
        self.sbtns = []
        n = max(1, min(8, int(self.settings["suggest_count"])))
        for i in range(n):
            b = tk.Button(self.sbar, text="", width=max(5, 36 // n), bg=BTN_BG, fg=BTN_FG,
                          activebackground=BTN_ACTIVE, activeforeground=BTN_AFG,
                          relief="flat", bd=0, pady=5, font=("Segoe UI", 11), takefocus=0,
                          command=lambda i=i: self.accept_suggestion(i))
            b.pack(side="left", fill="x", expand=True, padx=(6 if i == 0 else 3, 3),
                   pady=(0, 6))
            b.bind("<ButtonPress-3>", lambda e, i=i: self.forget_suggestion(i))
            self.sbtns.append(b)
        r = tk.Button(self.sbar, text="\u21ba", command=self.reset_prediction, bg=BTN_BG,
                      fg=MUTED_FG2, activebackground=BTN_ACTIVE, activeforeground=BTN_AFG,
                      relief="flat", bd=0, padx=8, pady=5, font=("Segoe UI", 11),
                      takefocus=0)
        r.pack(side="left", padx=(3, 6), pady=(0, 6))
        self.sreset = r

    def set_suggest_count(self, n):
        """The user chose a different number of suggestions."""
        self.settings["suggest_count"] = max(1, min(8, int(n)))
        self.scan_hl = {}
        self.make_suggest_buttons()
        self.apply_ui_scale()
        self.update_suggestions()
        self.keep_on_screen()

    def refresh_bar(self):
        if self.settings["predict"] and not self.edit_mode:
            self.sbar.grid()
        else:
            self.sbar.grid_remove()
        self.update_suggestions()
        self.keep_on_screen()

    def reset_prediction(self):
        self.pt.reset()
        self.update_suggestions()

    def forget_all(self):
        if messagebox.askyesno("KeyDeck", "Forget all the words and phrases KeyDeck has "
                               "learned from you?", parent=self.root):
            self.pt.forget_all()
            self.update_suggestions()

    def fg_window(self):
        return user32.GetForegroundWindow() if IS_WIN else 0

    def caps_on(self):
        return bool(user32.GetKeyState(0x14) & 1) if IS_WIN else False

    def poll_caps_state(self):
        """Keep Caps Lock visibly lit even when toggled outside KeyDeck."""
        try:
            current = self.caps_on()
            if current != self._last_caps_state:
                self._last_caps_state = current
                for k in self.keys:
                    if k.get("key") == "Caps Lock":
                        self.refresh_key(k)
        finally:
            if self.root.winfo_exists():
                self.root.after(150, self.poll_caps_state)

    def game_like(self):
        """Held-down letter keys mean a game, not typing: don't track those."""
        if self.hold_mode:
            return True
        for kid, st in self.states.items():
            if st == "hold":
                k = self.key_by_id(kid)
                if k and not self.is_mod(k):
                    return True
        return False

    def cmd_mod_active(self):
        for kid, st in self.states.items():
            if st in ("oneshot", "hold"):
                k = self.key_by_id(kid)
                if k and k.get("key") in CATALOG and CATALOG[k["key"]][0] in CMD_VKS:
                    return True
        return False

    def predict_key(self, k, forced=False):
        pending, self.ac_pending = self.ac_pending, None
        if self.swipe_ctx:
            self.swipe_commit()
        if self.ac.ready and not getattr(self, "caps_clean", False):
            self.caps_clean = True
            self.pt.clean_caps(self.ac.common, self.ac.proper)
        if k.get("key") not in CATALOG:
            return                           # shortcut / macro / mouse / layer keys type no word
        mode = self.settings["autocorrect"]
        if self.edit_mode or not (self.settings["predict"] or mode != "off"
                                  or self.settings["capitalize"] or self.settings["swipe"]):
            self.ac_undo = None
            return
        now = time.monotonic()
        fw = self.fg_window()
        if fw != self.pt_fw or now - self.pt_last > IDLE_RESET:
            self.pt.reset()          # switched windows or paused: cursor may have moved
            self.ac_undo = None
        self.pt_fw, self.pt_last = fw, now
        if self.game_like() or self.cmd_mod_active():
            self.pt.reset()
            self.ac_undo = None
        else:
            self.ac_undo = None
            self.pt.feed(k["key"], self.shift_active() or forced, self.caps_on())
            if pending:
                self.ac_undo = pending       # Backspace next will undo this correction
        self.update_suggestions()

    def update_suggestions(self):
        items = []
        if self.swipe_ctx and self.swipe_alts:
            items = list(self.swipe_alts)     # other words the swipe might have meant
        elif self.settings["predict"] and not self.edit_mode and not self.game_like():
            items = self.pt.suggest(int(self.settings["suggest_count"]))
        self.sugg = items
        for i, b in enumerate(self.sbtns):
            b.config(text=items[i][0] if i < len(items) else "")

    def tap(self, name):
        self.sender.send(name, True)
        self.sender.send(name, False)

    def accept_suggestion(self, i):
        if i >= len(self.sugg):
            return
        if self.swipe_ctx:
            if self.swipe_alts:
                return self.swipe_replace(i)
            self.swipe_commit()
        text = self.sugg[i][0]
        if not text:
            return
        capitalize = self.shift_active() and not self.pt.buffer
        for kid, st in list(self.states.items()):       # injected letters must not be shifted
            k = self.key_by_id(kid)
            if k and k.get("key") in CATALOG and st in ("oneshot", "hold") and CATALOG[k["key"]][0] in SHIFT_VKS:
                self.release_latched(k)
        if capitalize:
            text = text[0].upper() + text[1:]
        if not self.pt.buffer and self.settings["smart_punct"] and self.pt.prev_ch in AC_PUNCT:
            self.tap("Space")                # "cool!" + a suggestion: keep the words apart
        for _ in range(len(self.pt.buffer)):
            self.tap("Backspace")
        type_word(self.sender, text, self.caps_on())
        self.tap("Space")
        self.note_auto_space()
        self.pt_last = time.monotonic()
        self.pt.accept(text)
        self.update_suggestions()

    def forget_suggestion(self, i):
        if i < len(self.sugg):
            self.pt.forget(self.sugg[i][1])
            self.update_suggestions()

    # ---------------- macros ----------------
    def trigger_macro(self, k):
        steps, error = parse_macro(k.get("macro", ""))
        if error or not steps:
            return
        if self.macro_queue or self.macro_job:
            self.cancel_macro()              # pressing a macro key again stops the running one
            return
        self.release_oneshots()              # a lit Shift/Ctrl would garble the typed text
        self.macro_queue = collections.deque(steps)
        self.macro_id = k["id"]
        self.macro_caps = self.caps_on()
        self.refresh_key(k)
        self.macro_tick()

    def macro_tick(self):
        """Run a few steps, then hand control back to Tk so the window stays responsive."""
        self.macro_job = None
        try:
            done = 0
            while self.macro_queue and done < 4:
                step = self.macro_queue.popleft()
                if step[0] == "wait":
                    self.macro_job = self.root.after(step[1], self.macro_tick)
                    return
                if step[0] == "chord":
                    self.send_shortcut(step[1])
                else:
                    self.type_char(step[1])
                done += 1
            if self.macro_queue:
                self.macro_job = self.root.after(4, self.macro_tick)
            else:
                self.finish_macro()
        except Exception:
            self.cancel_macro()

    def type_char(self, ch):
        spec = CHAR_KEYS.get(ch)
        if spec is None:
            self.sender.unicode_char(ch)
            return
        name, shifted = spec
        need_shift = shifted
        if len(name) == 1 and name.isalpha():
            need_shift = shifted != self.macro_caps       # Caps Lock flips letters only
        tap_key(self.sender, name, need_shift)

    def finish_macro(self):
        self.cancel_macro()
        self.pt.reset()                      # the cursor context changed under the predictor
        self.update_suggestions()

    def cancel_macro(self, redraw=True):
        if self.macro_job:
            try:
                self.root.after_cancel(self.macro_job)
            except Exception:
                pass
            self.macro_job = None
        self.macro_queue.clear()
        kid, self.macro_id = self.macro_id, None
        if redraw and kid is not None:
            k = self.key_by_id(kid)
            if k:
                self.refresh_key(k)

    def configure_macro(self):
        """Turn the selected button into a key that types text / runs a key sequence."""
        k = self.sel
        if not k:
            messagebox.showinfo("KeyDeck", "Select a key in Edit layout first.", parent=self.root)
            return
        was_macro = k.get("key") == "Macro"
        current = k.get("macro", "") if was_macro else ""
        dlg = tk.Toplevel(self.root)
        dlg.title("Program macro")
        dlg.configure(bg=PANEL)
        dlg.transient(self.root)
        tk.Label(dlg, text=MACRO_HELP, justify="left", bg=PANEL, fg=LABEL_FG,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=12, pady=(12, 6))
        txt = tk.Text(dlg, width=58, height=7, wrap="word", font=("Consolas", 10))
        txt.pack(padx=12)
        txt.insert("1.0", current)
        msg = tk.Label(dlg, text="", bg=PANEL, fg="#ff8c8c", justify="left", wraplength=480,
                       font=("Segoe UI", 9))
        msg.pack(anchor="w", padx=12, pady=(6, 0))
        row = tk.Frame(dlg, bg=PANEL)
        row.pack(fill="x", padx=12, pady=10)

        def ok():
            raw = txt.get("1.0", "end-1c")
            steps, error = parse_macro(raw)
            if error:
                msg.config(text=error)
                return
            if not steps:
                msg.config(text="The macro is empty.")
                return
            if not was_macro or k.get("label", "") in ("", "Macro", macro_label(current)):
                k["label"] = macro_label(raw)         # keep a label the user typed themselves
            clear_special(k)
            k["key"] = "Macro"
            k["macro"] = raw
            k["label2"] = ""
            dlg.destroy()
            self.load_props()
            self.refresh_key(k)
            self.fit_canvas()

        for text, cmd in (("OK", ok), ("Cancel", dlg.destroy)):
            tk.Button(row, text=text, command=cmd, bg=BTN_ALT, fg=BTN_FG,
                      activebackground=BTN_ALT_ACTIVE, activeforeground=BTN_AFG, relief="flat",
                      bd=0, padx=14, pady=4, font=("Segoe UI", 9)).pack(side="right", padx=(6, 0))
        txt.focus_set()
        dlg.grab_set()
        self.root.wait_window(dlg)

    # ---------------- mouse keys ----------------
    def cursor_pos(self):
        if not IS_WIN:
            return None
        pt = wintypes.POINT()
        if not user32.GetCursorPos(ctypes.byref(pt)):
            return None
        return pt.x, pt.y

    def window_rect(self):
        """Screen rectangle of the whole KeyDeck window, title bar included."""
        r = self.root
        if IS_WIN:
            hwnd = user32.GetParent(r.winfo_id()) or r.winfo_id()
            rc = wintypes.RECT()
            if user32.GetWindowRect(hwnd, ctypes.byref(rc)):
                return rc.left, rc.top, rc.right, rc.bottom
        x, y = r.winfo_rootx(), r.winfo_rooty()
        return x - 8, y - 40, x + r.winfo_width() + 8, y + r.winfo_height() + 8

    def over_window(self, pos):
        x1, y1, x2, y2 = self.window_rect()
        return x1 <= pos[0] < x2 and y1 <= pos[1] < y2

    def title_text(self):
        if self.armed:
            return "KeyDeck — hold the pointer still on the target"
        return "KeyDeck"

    def flash_title(self, text, ms=5000):
        self.root.title(text)
        self.root.after(ms, lambda: self.root.title(self.title_text()))

    def toggle_mouse_arm(self, k):
        if self.armed and self.armed["id"] == k["id"]:
            self.disarm_mouse()                       # pressed again: cancel
            return
        self.disarm_mouse()
        kind, arg = MOUSE_KEYS[k["key"]]
        self.armed = {"id": k["id"], "kind": kind, "arg": arg, "anchor": None,
                      "since": time.monotonic(), "last": 0.0}
        self.root.title(self.title_text())
        self.refresh_key(k)

    def disarm_mouse(self, redraw=True):
        a, self.armed = self.armed, None
        if a:
            self.root.title(self.title_text())
            if redraw:
                k = self.key_by_id(a["id"])
                if k:
                    self.refresh_key(k)

    def mouse_poll(self):
        try:
            if self.armed and not self.edit_mode:
                self.mouse_step(time.monotonic())
        except Exception:
            pass
        finally:
            try:
                if self.root.winfo_exists():
                    self.root.after(50, self.mouse_poll)
            except tk.TclError:
                pass

    def mouse_step(self, now):
        """Fire the armed mouse action once the pointer rests outside KeyDeck."""
        a = self.armed
        pos = self.cursor_pos()
        if pos is None:
            return
        if self.over_window(pos):
            a["anchor"] = None                        # still on KeyDeck: keep waiting
            return
        anchor = a["anchor"]
        if (anchor is None or abs(pos[0] - anchor[0]) > MOUSE_JITTER
                or abs(pos[1] - anchor[1]) > MOUSE_JITTER):
            a["anchor"], a["since"] = pos, now        # pointer moved: restart the countdown
            return
        rest = now - a["since"]
        delay = float(self.settings.get("mouse_delay", 0.7))
        if a["kind"] == "scroll":
            if rest >= min(delay, 0.4) and now - a["last"] >= 0.09:
                a["last"] = now
                self.sender.mouse_wheel(a["arg"])
            return
        if rest >= delay:
            kind, arg = a["kind"], a["arg"]
            self.disarm_mouse()
            self.sender.mouse_click(arg, double=(kind == "double"))

    # ---------------- layer keys ----------------
    def configure_layer(self):
        """Turn the selected button into a key that switches to another loadout."""
        k = self.sel
        if not k:
            messagebox.showinfo("KeyDeck", "Select a key in Edit layout first.", parent=self.root)
            return
        was_layer = k.get("key") == "Layer"
        choices = ["Default (built-in)"] + list_loadouts()
        cur = k.get("layer", "") if was_layer else ""
        v_target = tk.StringVar(value=cur if cur in choices else choices[0])
        v_mode = tk.StringVar(value=k.get("layer_mode", "go") if was_layer else "go")
        dlg = tk.Toplevel(self.root)
        dlg.title("Layer key")
        dlg.configure(bg=PANEL)
        dlg.transient(self.root)
        lab = dict(bg=PANEL, fg=LABEL_FG, font=("Segoe UI", 9))
        tk.Label(dlg, text="Switch to this loadout:", **lab).pack(anchor="w", padx=12, pady=(12, 2))
        ttk.Combobox(dlg, textvariable=v_target, values=choices, state="readonly",
                     width=32).pack(anchor="w", padx=12)
        for text, val in (("Stay on that loadout (put a Layer key on it to come back)", "go"),
                          ("Use it for the next key press only, then return", "once")):
            tk.Radiobutton(dlg, text=text, variable=v_mode, value=val, bg=PANEL, fg=BTN_FG,
                           selectcolor=BTN_ALT, activebackground=PANEL,
                           activeforeground=BTN_AFG, font=("Segoe UI", 9),
                           anchor="w").pack(anchor="w", padx=12, pady=(6, 0))
        row = tk.Frame(dlg, bg=PANEL)
        row.pack(fill="x", padx=12, pady=12)

        def ok():
            target = v_target.get()
            target = "" if target == choices[0] else target
            mode = v_mode.get()
            old_auto = layer_label(k.get("layer_mode", "go"), k.get("layer", ""))
            if not was_layer or k.get("label") in ("", old_auto):
                k["label"] = layer_label(mode, target)
            clear_special(k)
            k["key"] = "Layer"
            k["layer"] = target
            k["layer_mode"] = mode
            k["label2"] = ""
            dlg.destroy()
            self.load_props()
            self.refresh_key(k)
            self.fit_canvas()

        for text, cmd in (("OK", ok), ("Cancel", dlg.destroy)):
            tk.Button(row, text=text, command=cmd, bg=BTN_ALT, fg=BTN_FG,
                      activebackground=BTN_ALT_ACTIVE, activeforeground=BTN_AFG, relief="flat",
                      bd=0, padx=14, pady=4, font=("Segoe UI", 9)).pack(side="right", padx=(6, 0))
        dlg.grab_set()
        self.root.wait_window(dlg)

    def trigger_layer(self, k):
        target = k.get("layer", "")
        if target and target not in list_loadouts():
            return                                    # loadout was deleted or renamed
        self.layer_pending = False
        if k.get("layer_mode") == "once":
            if self.layer_return is None:
                self.layer_return = self.loadout_name
            self.load_loadout(target, persist=False)
        else:
            self.load_loadout(target)                 # clears any pending return

    # ---------------- dwell clicking ----------------
    def update_dwell_btn(self):
        on = bool(self.settings["dwell"])
        self.dwell_btn.config(text="Dwell: ON" if on else "Dwell: OFF",
                              bg="#2f8f5b" if on else BTN_BG)

    def toggle_dwell(self):
        self.settings["dwell"] = not self.settings["dwell"]
        self.dwell_engine.reset()
        self.ring.hide()
        self.update_dwell_btn()
        save_settings(self.settings)

    def on_dwell_btn_change(self):
        show = bool(self.v_dwellbtn.get())
        self.settings["dwell_button"] = show
        if show:
            self.dwell_btn.pack(side="left", after=self.hold_btn)
            self.apply_ui_scale()                 # gives it the same spacing as its neighbours
        else:
            self.dwell_btn.pack_forget()
            if self.settings["dwell"]:            # nothing could switch it off now, so do it here
                self.settings["dwell"] = False
                self.dwell_engine.reset()
                self.ring.hide()
                self.update_dwell_btn()
        save_settings(self.settings)
        self.keep_on_screen()

    @staticmethod
    def widget_rect(w):
        x, y = w.winfo_rootx(), w.winfo_rooty()
        return x, y, x + w.winfo_width(), y + w.winfo_height()

    def client_rect(self):
        """The usable area of the window (no title bar or border, so dwell can't hit close)."""
        return self.widget_rect(self.root)

    @staticmethod
    def rect_has(rect, pos):
        return rect[0] <= pos[0] < rect[2] and rect[1] <= pos[1] < rect[3]

    def over_own_popup(self, pos):
        """Handle of one of our own drop-down menus under pos, else None."""
        if not IS_WIN:
            return None
        hwnd = user32.WindowFromPoint(wintypes.POINT(pos[0], pos[1]))
        if not hwnd or hwnd == self.ring.hwnd:
            return None
        top = user32.GetAncestor(hwnd, 2)                 # GA_ROOT
        if not top or top == self.ring.hwnd:
            return None
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(top, ctypes.byref(pid))
        if pid.value != kernel32.GetCurrentProcessId():
            return None                                   # another program's window or menu
        buf = ctypes.create_unicode_buffer(32)
        user32.GetClassNameW(top, buf, 32)
        return top if buf.value == "#32768" else None     # "#32768" is the Windows menu class

    def dwell_token(self, pos, active):
        """What the pointer is over, as a hashable token, or None where dwell must not click.

        The Dwell button always works (so dwell can be switched back on); everything else
        only while dwell is on.  Never the title bar, window borders or empty background."""
        hold = self.__dict__.get("dwell_hold")
        if hold:                                  # just reopened from the tab: wait for the pointer to move off
            reach = 3 * max(2, int(float(self.settings["dwell_tol"]) * self.scale))
            if abs(pos[0] - hold[0]) <= reach and abs(pos[1] - hold[1]) <= reach:
                return None
            self.dwell_hold = None
        if self.settings["dwell_button"] and self.rect_has(self.widget_rect(self.dwell_btn), pos):
            return ("dwell-button",)
        if not active:
            return None
        if self.rect_has(self.client_rect(), pos):
            cx1, cy1, cx2, cy2 = self.widget_rect(self.canvas)
            if cx1 <= pos[0] < cx2 and cy1 <= pos[1] < cy2:
                if self.edit_mode:
                    return None                           # dragging keys needs a real mouse
                k = self.key_at(pos[0] - cx1, pos[1] - cy1)
                return ("key", k["id"]) if k else None
            w = self.root.winfo_containing(pos[0], pos[1])
            if w is None or w is self.root:
                return None
            return ("widget", str(w))
        popup = self.over_own_popup(pos)
        return ("popup", popup) if popup else None

    def dwell_poll(self):
        try:
            self.dwell_step(time.monotonic())
        except Exception:
            self.ring.hide()
        finally:
            try:
                if self.root.winfo_exists():
                    self.root.after(30, self.dwell_poll)
            except tk.TclError:
                pass

    def dwell_step(self, now):
        if self.is_minimized():
            self.min_step(now)                    # only the tab matters while minimized
            return
        pos = self.cursor_pos()
        token = self.dwell_token(pos, bool(self.settings["dwell"])) if pos is not None else None
        tol = max(2, int(float(self.settings["dwell_tol"]) * self.scale))
        dwell = max(0.2, float(self.settings["dwell_time"]))
        state, frac = self.dwell_engine.step(now, pos, token, dwell, tol,
                                             bool(self.settings["dwell_repeat"]))
        if state == "click":
            self.ring.hide()
            self.sender.mouse_click("left")               # a real click, wherever the pointer is
        elif state == "wait" and self.settings["dwell_ring"] and frac * dwell >= 0.25:
            self.ring.show(pos[0], pos[1], frac)          # ring appears after a short moment
        else:
            self.ring.hide()

    # ---------------- autocorrect ----------------
    def ac_enable(self):
        """Called when autocorrect is switched on: load the word list, or say why we can't."""
        if not self.ac.available:
            messagebox.showinfo("KeyDeck", "Autocorrect needs the word list file, "
                                "keydeck_words.py, in the same folder as KeyDeck.\n\n"
                                "It wasn't found, so autocorrect stays off.", parent=self.root)
            self.settings["autocorrect"] = "off"
            self.v_ac.set("off")
            return
        self.ac.load_async()

    def forget_ac_keep(self):
        if messagebox.askyesno("KeyDeck", "Autocorrect will start fixing the words you told it "
                               "to leave alone (by pressing Backspace after a correction).\n\n"
                               "Forget them all?", parent=self.root):
            self.ac.forget_keep()

    def shifts_lifted(self, fn):
        """Run fn() with any latched Shift key released, so injected letters aren't capitalized
        (and put the Shift back afterwards, so a latched Shift still applies to the real key)."""
        held = []
        for kid, st in list(self.states.items()):
            k = self.key_by_id(kid)
            if (k and st in ("oneshot", "hold") and k.get("key") in CATALOG
                    and CATALOG[k["key"]][0] in SHIFT_VKS):
                held.append(k["key"])
        for name in held:
            self.sender.send(name, False)
        try:
            fn()
        finally:
            for name in held:
                self.sender.send(name, True)

    def type_text(self, text):
        caps = self.caps_on()
        for ch in text:
            if ch == " ":
                self.tap("Space")
            else:
                type_word(self.sender, ch, caps)

    def sentence_start(self, after_space=False):
        """True when the next letter typed begins a sentence: after . ! ? and a space, or after
        Enter.  (Not straight after a full stop, so web addresses and "e.g." are left alone.)"""
        pt = self.pt
        return bool(self.settings["capitalize"] and not pt.buffer and pt.hist
                    and pt.hist[-1] == "<s>" and (after_space or pt.prev_ch in (None, " ")))

    def punct_fix(self, k):
        """A word was just added for you (swipe / suggestion) along with a Space.  If the next
        key is punctuation, take that Space back so the punctuation sticks to the word."""
        a, self.auto_space = self.auto_space, None
        if not a or self.edit_mode:
            return
        if time.monotonic() - a["t"] > AC_IDLE or self.fg_window() != a["fw"]:
            return
        name = k.get("key")
        if name not in CATALOG:
            return
        self.auto_space = a
        lone_hit = a.get("lone") and self.lone_undo(name)
        self.auto_space = None
        if lone_hit or not self.settings["smart_punct"]:
            return
        ch = Predictor._char(name, self.shift_active(), self.caps_on())
        if ch is not None and ch in AC_PUNCT:
            self.shifts_lifted(lambda: self.tap("Backspace"))

    def finish_lone(self):
        """Swipe typing is on and a one-letter word (a / I) was just tapped: add its Space."""
        lone, self.lone = getattr(self, "lone", None), None
        if not lone:
            return
        self.shifts_lifted(lambda: self.tap("Space"))
        self.pt.feed("Space", False, False)
        self.note_auto_space()
        self.auto_space["lone"] = lone

    def lone_undo(self, name):
        """The key after a lone 'a'/'I' + Space is a letter: it was the start of a longer word
        (at, it, in...), so take the Space back (and the capital, for 'i')."""
        a = self.auto_space
        lone = a.get("lone") if a else None
        if not lone or not (len(name) == 1 and name.isalnum()):
            return False
        def run():
            self.tap("Backspace")
            if lone["cap"] and lone["ch"] == "i":
                self.tap("Backspace")
                type_word(self.sender, "i", False)
        self.shifts_lifted(run)
        if self.pt.hist and self.pt.hist[-1] == lone["ch"]:
            self.pt.hist.pop()
        self.pt.buffer = lone["ch"]
        self.pt.prev_ch = lone["ch"]
        return True

    def note_auto_space(self):
        self.auto_space = {"fw": self.fg_window(), "t": time.monotonic()}
        self.pt.prev_ch = " "

    def press_with_pre(self, k):
        """Everything that happens just before a normal key goes out: fix the word just typed,
        tidy a Space before punctuation, capitalise a sentence's first letter.  Then press it.
        Returns True if the letter was sent capitalised for you."""
        self.punct_fix(k)
        self.ac_before(k)
        n = k.get("key")
        force = bool(self.settings["capitalize"] and n in CATALOG and len(n) == 1 and n.isalpha()
                     and not self.edit_mode and not self.hold_mode and not self.shift_active()
                     and not self.caps_on() and self.sentence_start()
                     and not self.game_like() and not self.cmd_mod_active())
        lone = bool(self.settings["swipe"] and self.settings["swipe_space"] and n in ("A", "I")
                    and not self.edit_mode and not self.hold_mode and not self.shift_active()
                    and not self.caps_on() and not self.game_like() and not self.cmd_mod_active()
                    and not self.pt.buffer and self.pt.prev_ch == " ")
        cap_i = bool(lone and n == "I" and (self.settings["capitalize"] or self.settings["autocorrect"] != "off"))
        self.lone = {"ch": n.lower(), "cap": force or cap_i} if lone else None
        force = force or cap_i
        if force:
            self.sender.send("LShift", True)
            time.sleep(SHIFT_GAP)
            self.forced_shift = True         # let go of Shift only after the key is released
        self.press_key(k)
        return force

    def end_forced_shift(self):
        if getattr(self, "forced_shift", False):
            self.forced_shift = False
            time.sleep(SHIFT_GAP)
            self.sender.send("LShift", False)

    def ac_before(self, k):
        """Called just before a key is sent.  If it ends a word (Space or punctuation) and the
        word looks misspelt, replace the word first; the key then goes out as normal."""
        mode = self.settings["autocorrect"]
        if self.edit_mode or self.hold_mode:
            return
        name = k.get("key")
        if name not in CATALOG:
            return
        ch = Predictor._char(name, self.shift_active(), self.caps_on())
        if ch is None or ch not in AC_TRIGGERS:
            return
        pt = self.pt
        raw = pt.buffer
        if not raw or pt.glued:
            return
        if self.fg_window() != self.pt_fw or time.monotonic() - self.pt_last > AC_IDLE:
            return                                   # not sure the cursor is still after the word
        if self.game_like() or self.cmd_mod_active():
            return
        fixed = None
        if self.settings["capitalize"] and raw[0] == "i" and raw.lower() in AC_I_WORDS:
            fixed = "I" + raw[1:]                    # "i", "i'm", "i've"... always get a capital I
        elif mode != "off" and self.ac.ready:
            sentence_start = not pt.hist or pt.hist[-1] == "<s>"
            fixed = self.ac.correct(raw, mode, pt.uni, sentence_start)
        if not fixed or fixed == raw:
            return

        def replace():
            for _ in range(len(raw)):
                self.tap("Backspace")
            self.type_text(fixed)

        self.shifts_lifted(replace)
        pt.buffer = fixed.split(" ")[-1]             # so the predictor learns the right word
        self.ac_pending = {"orig": raw, "fixed": fixed, "term": ch, "t": time.monotonic()}

    def ac_revert(self):
        """Right-click on Backspace right after a correction: put back exactly what was typed
        (and the Space or punctuation after it), and remember not to touch that word again.
        True if it did."""
        u, self.ac_undo = self.ac_undo, None
        if not u or time.monotonic() - u["t"] > AC_IDLE:
            return False

        def restore():
            for _ in range(len(u["fixed"]) + 1):         # the fixed word and the key after it
                self.tap("Backspace")
            self.type_text(u["orig"])
            self.macro_caps = self.caps_on()
            self.type_char(u["term"])

        self.shifts_lifted(restore)
        self.ac.keep_word(u["orig"])
        self.pt.reset()
        return True

    # ---------------- swipe typing ----------------
    def letter_centres(self):
        out = {}
        for k in self.keys:
            n = k.get("key")
            if n in CATALOG and len(n) == 1 and n.isalpha():
                x1, y1, x2, y2 = self.rect(k)
                out[n.lower()] = ((x1 + x2) / 2, (y1 + y2) / 2)
        return out

    def swipe_ok(self, k):
        n = k.get("key")
        return bool(self.settings["swipe"] and not self.edit_mode and not self.hold_mode
                    and self.settings.get("swipe_style", "drag") in ("drag", "both")
                    and n in CATALOG and len(n) == 1 and n.isalpha())

    def click_ok(self, k):
        n = k.get("key")
        return bool(self.settings["swipe"] and not self.edit_mode and not self.hold_mode
                    and self.settings.get("swipe_style", "drag") in ("click", "both")
                    and n in CATALOG and len(n) == 1 and n.isalpha())

    def tap_letter(self, k):
        """Type a letter as an ordinary key press."""
        forced = self.press_with_pre(k)
        self.predict_key(k, forced)
        self.release_key(k)
        self.end_forced_shift()
        self.finish_lone()
        self.release_oneshots()

    # ---- click-to-swipe: click the first letter, glide over the rest, click the last ----
    def cswipe_begin(self, k, e):
        self.cswipe_cancel()
        self.cswipe = {"start": k, "path": [(e.x, e.y)], "touched": [k["id"]], "line": None,
                       "job": self.root.after(CSWIPE_IDLE_MS, self.cswipe_cancel)}
        self.refresh_key(k)

    def cswipe_cancel(self):
        s, self.cswipe = self.cswipe, None
        if s:
            if s["job"]:
                try:
                    self.root.after_cancel(s["job"])
                except Exception:
                    pass
            self.canvas.delete("swipe")
            for kid in s["touched"]:
                k = self.key_by_id(kid)
                if k:
                    self.refresh_key(k)

    def cswipe_move(self, e):
        """The pointer moved (no button down) while a click-to-swipe path is waiting."""
        s = self.cswipe
        if not s or (e.x, e.y) == s["path"][-1]:
            return
        s["path"].append((e.x, e.y))
        if s["job"]:
            try:
                self.root.after_cancel(s["job"])
            except Exception:
                pass
        s["job"] = self.root.after(CSWIPE_IDLE_MS, self.cswipe_cancel)
        k = self.key_at(e.x, e.y)
        if k is not None and k["id"] not in s["touched"]:
            s["touched"].append(k["id"])
            self.refresh_key(k)
        flat = [v for p in s["path"][-300:] for v in p]
        if s["line"] is None:
            s["line"] = self.canvas.create_line(*flat, fill=TRAIL_COLOR, width=max(3, self.unit // 8),
                                                capstyle="round", joinstyle="round",
                                                smooth=True, tags=("swipe",))
        else:
            self.canvas.coords(s["line"], *flat)
        self.canvas.tag_raise("swipe")

    def cswipe_click(self, e, k):
        """A click while a path is waiting.  True if the click was used up (it ended the path)."""
        s = self.cswipe
        n = k.get("key")
        if n in CATALOG and len(n) == 1 and n.isalpha() and not self.hold_mode:
            s["path"].append((e.x, e.y))
            if k["id"] != s["start"]["id"] or len(s["touched"]) > 1:
                path = s["path"]
                self.cswipe_cancel()
                self.swipe_finish(path)      # the clicked letter is where the word ends
                return True
            self.cswipe_cancel()             # same letter again, nothing crossed: just that letter
            self.tap_letter(s["start"])
            return True
        self.cswipe_cancel()                 # Space, Backspace...: the first letter was a lone letter
        self.tap_letter(s["start"])
        return False

    def swipe_begin(self, e, k):
        """The mouse went down on a letter: wait and see whether this is a tap, a hold, or a swipe."""
        self.swipe = {"start": k, "path": [(e.x, e.y)], "active": False, "touched": [k["id"]],
                      "line": None, "job": self.root.after(SWIPE_HOLD_MS, self.swipe_hold)}
        self.refresh_key(k)

    def swipe_cancel(self):
        s, self.swipe = self.swipe, None
        if s:
            if s["job"]:
                try:
                    self.root.after_cancel(s["job"])
                except Exception:
                    pass
            self.canvas.delete("swipe")
            for kid in s["touched"]:
                k = self.key_by_id(kid)
                if k:
                    self.refresh_key(k)

    def swipe_hold(self):
        """Held still on one letter: it's an ordinary key press (and can auto-repeat)."""
        s = self.swipe
        if not s or s["active"]:
            return
        s["job"] = None
        k = s["start"]
        self.swipe_cancel()
        forced = self.press_with_pre(k)
        self.pressing = k
        self.set_state(k, "mom")
        self.predict_key(k, forced)
        if self.settings["repeat"]:
            self.cancel_repeat()
            self.repeat_job = self.root.after(150, lambda: self.repeat_tick(k))

    def swipe_move(self, e):
        """Mouse moved with the button down.  True if a swipe gesture is in progress."""
        s = self.swipe
        if not s:
            return False
        if (e.x, e.y) == s["path"][-1]:
            return True
        s["path"].append((e.x, e.y))
        k = self.key_at(e.x, e.y)
        if not s["active"]:
            if k is not None and k["id"] == s["start"]["id"]:
                return True                  # still on the first letter: could yet be a tap
            s["active"] = True               # left the first letter: this is a swipe
            if s["job"]:
                self.root.after_cancel(s["job"])
                s["job"] = None
        if k is not None and k["id"] not in s["touched"]:
            s["touched"].append(k["id"])
            self.refresh_key(k)
        flat = [v for p in s["path"][-300:] for v in p]
        if s["line"] is None:
            s["line"] = self.canvas.create_line(*flat, fill=TRAIL_COLOR, width=max(3, self.unit // 8),
                                                capstyle="round", joinstyle="round",
                                                smooth=True, tags=("swipe",))
        else:
            self.canvas.coords(s["line"], *flat)
        self.canvas.tag_raise("swipe")
        return True

    def swipe_end(self, e):
        """Mouse button released."""
        s = self.swipe
        if not s:
            return
        if s["job"]:
            try:
                self.root.after_cancel(s["job"])
            except Exception:
                pass
            s["job"] = None
        if s["active"] and (e.x, e.y) != s["path"][-1]:
            s["path"].append((e.x, e.y))
        self.swipe_cancel()                  # removes the trail and un-highlights the keys
        if not s["active"]:
            k = s["start"]
            if self.settings.get("swipe_style") == "both":
                self.cswipe_begin(k, e)      # a click: the start of a click-to-swipe path
                return
            self.tap_letter(k)               # a plain tap: type the letter now
            return
        self.swipe_finish(s["path"])

    def swipe_bonus(self, w):
        """How much a word is favoured over an equally good path match."""
        if "'" in w:
            # "dont" traced = don't, unless the letters are also a real word (its, were, well...)
            return 0.0 if (w.replace("'", "") in self.ac.common or w.replace("'", "") in self.ac.rank) else 0.30
        r = self.ac.rank.get(w)
        b = 0.30 * (1 - min(r, 1500) / 1500.0) if r is not None else -0.12
        n = self.pt.uni.get(w, 0)
        if n > 10:
            b += min(0.3, (n - 10) / 60.0)
        return b

    def swipe_display(self, w, capital):
        if "'" in w:
            s = w
            if s.startswith("i'"):
                s = "I" + s[1:]
            elif capital:
                s = s[0].upper() + s[1:]
            return s
        return self.pt.display(w, capital, False)

    def swipe_words(self, path):
        letters = self.letter_centres()
        if not self.swipe_dec.ready:
            pool = set(self.ac.common) if self.ac.ready else set()
            pool.update(self.ac.rank)
            self.swipe_dec.set_words(pool or {w for w in self.pt.uni if w.isalpha()})
            self.swipe_dec.add_contractions(SWIPE_CONTRACTIONS)
        extra = [w for w in self.pt.uni if w.isalpha() and w.isascii()]
        return self.swipe_dec.decode(path, letters, self.unit, self.swipe_bonus, extra,
                                    limit=max(4, int(self.settings.get("suggest_count", 3)) + 1))

    def swipe_finish(self, path):
        if self.cmd_mod_active() or self.game_like():
            return
        words = self.swipe_words(path)
        if not words:
            return
        self.swipe_commit()
        if self.pt.buffer:                   # a half-typed word: end it first
            self.tap("Space")
            self.pt.feed("Space", False, False)
        gap = bool(self.settings["smart_punct"] and self.pt.prev_ch in AC_PUNCT)
        capital = self.shift_active() or self.sentence_start(after_space=gap)
        for kid, st in list(self.states.items()):      # injected letters must not be shifted
            k = self.key_by_id(kid)
            if k and k.get("key") in CATALOG and st in ("oneshot", "hold") \
                    and CATALOG[k["key"]][0] in SHIFT_VKS:
                self.release_latched(k)
        text = self.swipe_display(words[0], capital)
        self.speak_word(text)
        space = bool(self.settings["swipe_space"])
        if gap:
            self.tap("Space")                # "cool!" + swipe: keep the words apart
        type_word(self.sender, text, self.caps_on())
        if space:
            self.tap("Space")
            self.note_auto_space()
        self.release_oneshots()
        self.pt_fw, self.pt_last = self.fg_window(), time.monotonic()
        if space:
            self.swipe_ctx = {"typed": text, "space": True}
            # other words the swipe might have meant, offered in the suggestion bar (only when the
            # user has predictive text switched on: with it off the bar must stay hidden)
            self.swipe_alts = ([(self.swipe_display(a, capital), a) for a in
                                words[1:1 + int(self.settings.get("suggest_count", 3))]]
                               if self.settings.get("predict") else [])
        else:
            self.pt.buffer = text
            self.swipe_alts = []
        self.refresh_bar()

    def swipe_commit(self):
        """The swiped word is accepted (another key was pressed): let the predictor learn it."""
        c, self.swipe_ctx = self.swipe_ctx, None
        had_alts, self.swipe_alts = bool(self.swipe_alts), []
        if not c:
            return
        self.speak_mute = True               # it was already read out when it was swiped
        try:
            prev = self.pt._finish(c["typed"])
        finally:
            self.speak_mute = False
        self.pt.undo = (c["typed"], prev)    # Backspace on the space brings the word back
        if had_alts and not self.settings["predict"]:
            self.refresh_bar()

    def swipe_delete(self):
        """Right-click Backspace right after a swipe: wipe the whole swiped word (and its space)."""
        c, self.swipe_ctx = self.swipe_ctx, None
        self.swipe_alts = []
        if not c:
            return False
        n = len(c["typed"]) + (1 if c["space"] else 0)

        def run():
            for _ in range(n):
                self.tap("Backspace")

        self.shifts_lifted(run)
        self.auto_space = None
        self.pt.buffer = ""
        self.pt.undo = None
        return True

    def swipe_replace(self, i):
        """One of the alternative words was clicked: swap it in for the swiped word."""
        c = self.swipe_ctx
        alt = self.sugg[i][0]

        def run():
            for _ in range(len(c["typed"]) + (1 if c["space"] else 0)):
                self.tap("Backspace")
            self.type_text(alt + (" " if c["space"] else ""))

        self.shifts_lifted(run)
        if c["space"]:
            self.note_auto_space()
        c["typed"] = alt
        self.speak_word(alt)
        self.swipe_commit()
        self.pt_last = time.monotonic()
        self.update_suggestions()

    # ---------------- speak each word ----------------
    def speak_word(self, text):
        """Called when a word is finished (typed, swiped or picked from the bar)."""
        if not self.settings.get("speak") or self.edit_mode or getattr(self, "speak_mute", False):
            return
        w = "".join(c for c in str(text) if c.isalpha() or c == "'")
        if not w.strip("'"):
            return
        if getattr(self, "speaker", None) is None:
            self.speaker = Speaker()
        self.speaker.say(w, self.settings.get("speak_rate", 0), self.settings.get("speak_volume", 100))
        self.show_caption(w)

    # ---------------- switch scanning ----------------
    def scan_on(self):
        return self.scan is not None and bool(self.settings.get("scan"))

    def scan_apply(self):
        """Create / update / remove the scanner to match the settings."""
        s = self.settings
        if s.get("scan") and self.scan is None:
            self.scan = ScanEngine()
        elif not s.get("scan") and self.scan is not None:
            self.scan_stop()
        if self.scan is not None:
            self.scan.max_passes = int(s.get("scan_loops", 3))
        hint = getattr(self, "hint", None)
        if hint is not None:
            try:
                hint.config(text="Scanning: click anywhere on the keys to start and to choose"
                            if self.scan_on() else "Right-click a key to hold it")
            except Exception:
                pass

    def scan_stop(self):
        if self.scan_job is not None:
            try:
                self.root.after_cancel(self.scan_job)
            except Exception:
                pass
            self.scan_job = None
        old, self.scan_hl = self.scan_hl, {}
        self.scan = None
        self.scan_show(old)

    def scan_rows(self):
        keys = sorted(self.keys, key=lambda k: (k["y"], k["x"]))
        rows, cur, top = [], [], None
        for k in keys:
            if top is None or k["y"] - top > 0.6:
                if cur:
                    rows.append(cur)
                cur, top = [], k["y"]
            cur.append(k)
        if cur:
            rows.append(cur)
        out = [[k["id"] for k in sorted(r, key=lambda k: k["x"])] for r in rows]
        if (self.settings["predict"] or self.swipe_alts) and not self.edit_mode:
            bar = ["s%d" % i for i in range(len(self.sbtns)) if i < len(self.sugg) and self.sugg[i][0]]
            if bar:
                out.append(bar)
        return out

    def scan_show(self, old):
        for kid in set(old) | set(self.scan_hl):
            kind = self.scan_hl.get(kid)
            if isinstance(kid, str):
                try:
                    b = self.sbtns[int(kid[1:])]
                    if kind == "key":
                        b.config(bg=SCAN_COLOR, fg=SCAN_FG)
                    elif kind == "row":
                        b.config(bg=SCAN_ROW, fg=SCAN_ROW_FG)
                    else:
                        b.config(bg=BTN_BG, fg=BTN_FG)
                except Exception:
                    pass
            else:
                k = self.key_by_id(kid)
                if k:
                    self.refresh_key(k)

    def scan_schedule(self, fresh=False):
        if self.scan_job is not None:
            try:
                self.root.after_cancel(self.scan_job)
            except Exception:
                pass
            self.scan_job = None
        if self.scan is None or self.scan.mode == "idle":
            return
        extra = float(self.settings.get("scan_first", 0.5)) if fresh else 0.0
        delay = int((float(self.settings.get("scan_speed", 1.0)) + extra) * 1000)
        self.scan_job = self.root.after(delay, self.scan_tick)

    def scan_tick(self):
        self.scan_job = None
        if not self.scan_on() or self.edit_mode:
            return
        self.scan.set_rows(self.scan_rows())
        old = self.scan_hl
        self.scan.tick()
        self.scan_hl = self.scan.highlight()
        self.scan_show(old)
        self.scan_schedule()

    def scan_switch(self):
        """The switch (a click on the keys) was pressed."""
        if not self.scan_on() or self.edit_mode:
            return
        self.scan.set_rows(self.scan_rows())
        old = self.scan_hl
        action = self.scan.select()
        self.scan_hl = self.scan.highlight()
        if action[0] == "press":
            self.scan_press(action[1])
        self.scan_show(old)
        self.scan_schedule(fresh=True)

    def scan_pause(self):
        """Right-click: stop highlighting until the next switch press."""
        if not self.scan_on():
            return
        old = self.scan_hl
        self.scan.pause()
        self.scan_hl = {}
        self.scan_show(old)
        self.scan_schedule()

    def scan_press(self, target):
        """Press the chosen key exactly as a click on it would."""
        if isinstance(target, str):
            self.accept_suggestion(int(target[1:]))
            return
        k = self.key_by_id(target)
        if not k:
            return
        x1, y1, x2, y2 = self.rect(k)
        e = types.SimpleNamespace(x=(x1 + x2) / 2, y=(y1 + y2) / 2)
        self.scan_injecting = True
        try:
            self.on_press(e)
            self.on_release(e)
        finally:
            self.scan_injecting = False

    # ---------------- pictures on keys ----------------
    def key_image(self, k, bw, bh):
        """A Tk image of the key's picture that fits inside bw x bh pixels, or None."""
        data = k.get("image_data")
        if not data or bw < 6 or bh < 6:
            return None
        cache = self.__dict__.setdefault("img_cache", {})
        ck = (hash(data), int(bw), int(bh))
        img = cache.get(ck)
        if img is None:
            try:
                if HAVE_PIL:
                    im = Image.open(io.BytesIO(base64.b64decode(data))).convert("RGBA")
                    f = min(bw / im.width, bh / im.height)
                    size = (max(1, int(im.width * f)), max(1, int(im.height * f)))
                    img = ImageTk.PhotoImage(im.resize(size, Image.LANCZOS))
                else:
                    img = tk.PhotoImage(data=data)
                    f = min(bw / img.width(), bh / img.height())
                    if f < 1:
                        n = int(math.ceil(1 / f))
                        img = img.subsample(n, n)
                    elif f >= 2:
                        img = img.zoom(int(f), int(f))
            except Exception:
                img = False
            if len(cache) > 300:
                cache.clear()
            cache[ck] = img
        return img or None

    def anim_items(self):
        return self.__dict__.setdefault("anim_state", {})

    def key_frames(self, k, bw, bh):
        """For an animated picture: ([Tk images that fit bw x bh], [delay in ms per image]);
        None if the key's picture is not animated or can't be read."""
        data = k.get("image_data")
        if not data or bw < 6 or bh < 6 or not picture_is_animated(data):
            return None
        cache = self.__dict__.setdefault("frame_cache", {})
        ck = (hash(data), int(bw), int(bh))
        if ck in cache:
            return cache[ck] or None
        result = None
        try:
            raw = base64.b64decode(data)
            delays = gif_delays(raw)[:GIF_MAX_FRAMES * 2]
            frames = []
            if HAVE_PIL:
                im = Image.open(io.BytesIO(raw))
                for n in range(len(delays)):
                    im.seek(n)
                    fr = im.convert("RGBA")
                    f = min(bw / fr.width, bh / fr.height)
                    size = (max(1, int(fr.width * f)), max(1, int(fr.height * f)))
                    frames.append(ImageTk.PhotoImage(fr.resize(size, Image.LANCZOS)))
            else:
                for n in range(len(delays)):
                    img = tk.PhotoImage(data=data, format="gif -index %d" % n)
                    f = min(bw / img.width(), bh / img.height())
                    if f < 1:
                        s = int(math.ceil(1 / f))
                        img = img.subsample(s, s)
                    elif f >= 2:
                        img = img.zoom(int(f), int(f))
                    frames.append(img)
            if len(frames) > 1:
                result = (frames, [max(20, d) for d in delays[:len(frames)]])
        except Exception:
            result = None
        if len(cache) > 40:
            cache.clear()
        cache[ck] = result
        return result

    def anim_tick(self):
        """About 25 times a second: move every animated key picture on to its next frame."""
        try:
            anim = self.anim_items()
            if anim and self.settings.get("animate_pictures", True) and not self.is_minimized():
                now = time.monotonic()
                for a in list(anim.values()):
                    if now >= a["due"]:
                        a["i"] = (a["i"] + 1) % len(a["frames"])
                        self.canvas.itemconfig(a["item"], image=a["frames"][a["i"]])
                        a["due"] = max(now, a["due"]) + a["delays"][a["i"]] / 1000.0
        except Exception:
            pass
        finally:
            try:
                if self.root.winfo_exists():
                    self.root.after(40, self.anim_tick)
            except Exception:
                pass

    def pick_picture(self):
        k = self.sel
        if not k:
            messagebox.showinfo("KeyDeck", "Select a key in Edit layout first.", parent=self.root)
            return
        path = filedialog.askopenfilename(
            parent=self.root, title="Choose a picture for this key",
            filetypes=PIC_TYPES_PIL if HAVE_PIL else PIC_TYPES_PLAIN)
        if not path:
            return
        try:
            data, name = prepare_picture(path)
        except ValueError as ex:
            messagebox.showerror("Picture", str(ex), parent=self.root)
            return
        k["image_data"], k["image_name"] = data, name
        self.refresh_key(k)

    def remove_picture(self):
        k = self.sel
        if k and k.get("image_data"):
            k.pop("image_data", None)
            k.pop("image_name", None)
            self.refresh_key(k)

    # ---------------- speech keys ----------------
    def configure_speak(self):
        """Turn the selected button into a key that says a phrase out loud."""
        k = self.sel
        if not k:
            messagebox.showinfo("KeyDeck", "Select a key in Edit layout first.", parent=self.root)
            return
        was = k.get("key") == "Speak"
        current = k.get("speak", "") if was else ""
        raw = simpledialog.askstring(
            "Program speech",
            "What should this key say out loud when it is pressed?\n"
            "(It uses the Windows voice, speed and volume from Settings → Speak words.)",
            initialvalue=current, parent=self.root)
        if raw is None:
            return
        raw = " ".join(raw.split())[:SPEAK_MAX]
        if not raw:
            messagebox.showinfo("Program speech", "The phrase was empty, so nothing changed.",
                                parent=self.root)
            return
        if not was or k.get("label", "") in ("", "Speak", macro_label(current)):
            k["label"] = macro_label(raw)
        clear_special(k)
        k["key"] = "Speak"
        k["speak"] = raw
        k["label2"] = ""
        self.load_props()
        self.refresh_key(k)
        self.fit_canvas()

    def trigger_speak(self, k):
        phrase = k.get("speak", "")
        if phrase:
            if getattr(self, "speaker", None) is None:
                self.speaker = Speaker()
            self.speaker.say(phrase, self.settings.get("speak_rate", 0),
                             self.settings.get("speak_volume", 100))
            self.show_caption(phrase)
        self.set_state(k, "mom")
        self.root.after(450, lambda: (self.states.get(k["id"]) == "mom" and
                                      (self.set_state(k, None) or True)))

    # ---------------- minimize to a tab ----------------
    def is_minimized(self):
        return bool(self.__dict__.get("minimized", False))

    def work_area(self):
        """The screen area not covered by the taskbar: (left, top, right, bottom)."""
        if IS_WIN:
            try:
                r = wintypes.RECT()
                if user32.SystemParametersInfoW(0x30, 0, ctypes.byref(r), 0):   # SPI_GETWORKAREA
                    return r.left, r.top, r.right, r.bottom
            except Exception:
                pass
        return 0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight()

    def min_need(self):
        """How long (seconds) the pointer must rest on the tab to open the keyboard."""
        try:
            own = float(self.settings.get("min_open", 0))
        except Exception:
            own = 0.0
        if own > 0:
            return own
        return max(0.5, float(self.settings.get("dwell_time", 1.0)))

    def minimize(self):
        """Hide the keyboard and leave a small tab that opens it again by resting on it."""
        if self.is_minimized():
            return
        tab = self.__dict__.get("mintab")
        if tab is None:
            tab = self.mintab = MinTab(self.root, self.scale, self.restore_window)
        if not tab.show(self.work_area(), self.settings.get("min_pos", "bc")):
            return                                   # no tab, so keep the keyboard visible
        self.cswipe_cancel()
        self.swipe_cancel()
        self.minimized = True
        self.min_since = self.min_last_in = None
        self.ring.hide()
        self.root.withdraw()

    def restore_window(self, pos=None):
        """Bring the keyboard back (called by the tab, by resting on it or by clicking it)."""
        if not self.is_minimized():
            return
        self.minimized = False
        try:
            self.mintab.hide()
        except Exception:
            pass
        self.root.deiconify()
        self.apply_noactivate(not self.edit_mode)
        self.dwell_engine.reset()
        # The pointer is still where the tab was, now probably over a key.  Dwell clicking must
        # not press it: wait until the pointer has moved away.
        self.dwell_hold = pos or self.cursor_pos()
        self.root.after(30, self.restore_focus)
        self.root.after(250, self.restore_focus)

    def min_step(self, now):
        """While minimized (called 30 times a second): time how long the pointer rests on the tab."""
        pos = self.cursor_pos()
        tab = self.mintab
        inside = pos is not None and self.rect_has(tab.rect(), pos)
        if inside:
            self.min_last_in = now
            if self.min_since is None:
                self.min_since = now
        elif self.min_since is not None and now - (self.min_last_in or now) > 0.3:
            self.min_since = None                    # a brief wobble off the edge is forgiven
        if self.min_since is None:
            tab.set_progress(0.0)
            return
        frac = (now - self.min_since) / self.min_need()
        if frac >= 1.0:
            self.restore_window(pos)
        else:
            tab.set_progress(frac)

    # ---------------- caption bar for spoken text ----------------
    def build_caption(self):
        """A strip under the keys that shows what was just spoken (it can be switched off)."""
        fr = tk.Frame(self.root, bg=PANEL)
        fr.grid(row=4, column=0, sticky="ew")
        self.cap_frame = fr
        self.cap_job = None
        self.cap_label = tk.Label(fr, text=CAPTION_IDLE, bg=PANEL, fg=MUTED_FG, anchor="center",
                                  height=1)
        self.cap_label.pack(fill="x", padx=8, pady=4)
        self.cap_size()
        if not self.settings.get("show_caption", True):
            fr.grid_remove()

    def cap_px(self):
        return max(14, int(self.unit * 0.55))

    def cap_size(self):
        if getattr(self, "cap_label", None) is None:
            return
        self.cap_label.config(font=("Segoe UI", -self.cap_px(), "bold"))
        self.cap_label.pack_configure(pady=max(3, int(self.unit * 0.12)))

    def show_caption(self, text):
        """Show a phrase in the caption bar for a few seconds (longer phrases stay longer)."""
        if not self.settings.get("show_caption", True) or getattr(self, "cap_label", None) is None:
            return
        text = " ".join(str(text).split())
        if not text:
            return
        try:
            width = int(self.canvas.winfo_width())
        except Exception:
            width = 0
        width = width if width > 100 else 600
        limit = max(8, int(width / (0.52 * self.cap_px())) - 2)      # one line: never resizes the window
        shown = text if len(text) <= limit else text[:limit - 1].rstrip() + "…"
        self.cap_label.config(text=shown, fg=BTN_FG)
        if self.cap_job is not None:
            try:
                self.root.after_cancel(self.cap_job)
            except Exception:
                pass
        self.cap_job = self.root.after(max(2500, min(12000, 1500 + 90 * len(text))), self.clear_caption)

    def clear_caption(self):
        self.cap_job = None
        if getattr(self, "cap_label", None) is not None:
            self.cap_label.config(text=CAPTION_IDLE, fg=MUTED_FG)

    def apply_caption_setting(self):
        """Show or hide the caption bar to match the setting."""
        if getattr(self, "cap_frame", None) is None:
            return
        if self.settings.get("show_caption", True):
            self.cap_frame.grid()
        else:
            if self.cap_job is not None:
                try:
                    self.root.after_cancel(self.cap_job)
                except Exception:
                    pass
                self.cap_job = None
            self.clear_caption()
            self.cap_frame.grid_remove()
        self.root.update_idletasks()
        self.keep_on_screen()

    # ---------------- themes ----------------
    def recolor_ui(self, old):
        """The theme changed while running: swap the colours of every widget and redraw the keys."""
        new = theme_snapshot()
        bgmap = {old[r].lower(): new[r] for r in THEME_BG_ROLES}
        fgmap = {old[r].lower(): new[r] for r in THEME_FG_ROLES}
        opts = (("bg", bgmap), ("activebackground", bgmap), ("selectcolor", bgmap),
                ("highlightbackground", bgmap), ("fg", fgmap), ("activeforeground", fgmap))

        def walk(w):
            for opt, m in opts:
                try:
                    cur = str(w.cget(opt)).lower()
                except Exception:
                    continue
                if cur in m:
                    try:
                        w.configure(**{opt: m[cur]})
                    except Exception:
                        pass
            for c in w.winfo_children():
                walk(c)

        walk(self.root)
        self.root.configure(bg=BG)
        self.canvas.configure(bg=BG)
        self.redraw()

    def apply_bg(self, color):
        """Set (or, with "", clear) the colour behind the keys, toolbar and suggestion bar."""
        old = theme_snapshot()
        self.settings["bg_color"] = color
        set_theme(self.settings["theme"], color)
        self.recolor_ui(old)

    def pick_bg(self):
        res = colorchooser.askcolor(color=BG, parent=self.root, title="Keyboard background color")
        if res and res[1]:
            self.apply_bg(res[1])

    def pick_edge_width(self):
        k = self.sel
        if not k:
            return
        cur = k.get("edge_px")
        v = simpledialog.askinteger(
            "Outline thickness",
            "Outline thickness in pixels (1 to 8).\nEnter 0 for no outline.\n"
            "(Reset colors puts it back to the theme's default.)",
            initialvalue=KEY_EDGE_W if cur is None else int(cur), minvalue=0, maxvalue=8,
            parent=self.root)
        if v is not None:
            k["edge_px"] = int(v)
            self.refresh_key(k)

    # ---------------- sharing layouts: export / import ----------------
    def keys_from_data(self, data):
        """Turn the contents of a layout file into key dicts, skipping anything invalid."""
        keys = []
        for raw in data.get("keys", []):
            if not isinstance(raw, dict):
                continue
            kn = raw.get("key")
            if kn not in CATALOG and kn not in SPECIAL_KEYS:
                continue
            k = new_key_dict(kn, float(raw.get("x", 0)), float(raw.get("y", 0)),
                             max(0.25, float(raw.get("w", 1))),
                             max(0.25, float(raw.get("h", 1))),
                             str(raw.get("label", LABELS.get(kn, kn))),
                             str(raw.get("label2", "")), str(raw.get("color", "")),
                             str(raw.get("fg", "")), str(raw.get("edge", "")), _edge_px(raw))
            if kn == "Shortcut":
                if not isinstance(raw.get("shortcut"), list):
                    continue
                parsed, error = self.parse_shortcut("+".join(str(x) for x in raw["shortcut"]))
                if error:
                    continue
                k["shortcut"] = parsed
            elif kn == "Macro":
                text = raw.get("macro")
                if not isinstance(text, str):
                    continue
                steps, error = parse_macro(text)
                if error or not steps:
                    continue
                k["macro"] = text
            elif kn == "Layer":
                k["layer"] = str(raw.get("layer", ""))
                k["layer_mode"] = "once" if raw.get("layer_mode") == "once" else "go"
            elif kn == "Speak":
                phrase = raw.get("speak")
                if not isinstance(phrase, str) or not phrase.strip():
                    continue
                k["speak"] = " ".join(phrase.split())[:SPEAK_MAX]
            if valid_picture_data(raw.get("image_data")):
                k["image_data"] = raw["image_data"]
                k["image_name"] = str(raw.get("image_name", ""))[:80]
            keys.append(k)
        return keys

    def layout_data(self, keys):
        return {"version": 1, "keys": [{kk: vv for kk, vv in k.items() if kk != "id"} for k in keys]}

    def export_layout(self):
        """Save the layout on screen as one file that can be sent to someone else."""
        name = self.loadout_name or "My layout"
        path = filedialog.asksaveasfilename(
            parent=self.root, title="Export this layout", defaultextension=".json",
            initialfile=safe_name(name) + ".json", filetypes=[("KeyDeck layout", "*.json")])
        if not path:
            return
        try:
            data = self.layout_data(self.keys)
            data.update({"keydeck": "layout", "name": name})
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as ex:
            messagebox.showerror("Export layout", "Could not save the file:\n%s" % ex)
            return
        messagebox.showinfo("Export layout", "Saved. Send that file to anyone: they can load it with "
                            "Loadouts → Import layouts.")

    def export_all_layouts(self):
        """Every saved loadout in a single file (layer keys keep working for the receiver)."""
        names = list_loadouts()
        if not names:
            messagebox.showinfo("Export all layouts", "You have no saved loadouts yet. "
                                "Use Save as… first, or export the layout on screen.")
            return
        path = filedialog.asksaveasfilename(
            parent=self.root, title="Export all layouts", defaultextension=".json",
            initialfile="KeyDeck layouts.json", filetypes=[("KeyDeck layouts", "*.json")])
        if not path:
            return
        bundle = {}
        for n in names:
            try:
                with open(os.path.join(LOADOUT_DIR, n + ".json"), "r", encoding="utf-8") as f:
                    bundle[n] = self.layout_data(self.keys_from_data(json.load(f)))
            except Exception:
                continue
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"keydeck": "bundle", "layouts": bundle}, f, indent=2)
        except Exception as ex:
            messagebox.showerror("Export all layouts", "Could not save the file:\n%s" % ex)
            return
        messagebox.showinfo("Export all layouts", "Saved %d layouts." % len(bundle))

    def read_layouts_file(self, path):
        """[(name, keys)] from a layout or bundle file.  Raises ValueError if it isn't one."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            raise ValueError("it isn't a KeyDeck layout file")
        if not isinstance(data, dict):
            raise ValueError("it isn't a KeyDeck layout file")
        stem = os.path.splitext(os.path.basename(path))[0]
        out = []
        if isinstance(data.get("layouts"), dict):
            for n, d in data["layouts"].items():
                if isinstance(d, dict):
                    out.append((str(n), self.keys_from_data(d)))
        elif isinstance(data.get("keys"), list):
            out.append((str(data.get("name") or stem), self.keys_from_data(data)))
        out = [(n, ks) for n, ks in out if ks]
        if not out:
            raise ValueError("it has no usable keys in it")
        return out

    @staticmethod
    def risky_keys(keys):
        """Short descriptions of keys that press other keys for you (macros, shortcuts)."""
        out = []
        for k in keys:
            if k.get("key") == "Macro":
                out.append("macro “%s”: %s" % (k.get("label", ""), k.get("macro", "")[:60]))
            elif k.get("key") == "Shortcut":
                out.append("shortcut “%s”: %s" % (k.get("label", ""), "+".join(k.get("shortcut", []))))
        return out

    def import_layouts(self):
        paths = filedialog.askopenfilenames(
            parent=self.root, title="Import layouts",
            filetypes=[("KeyDeck layouts", "*.json"), ("All files", "*.*")])
        if not paths:
            return
        added, problems = [], []
        for path in paths:
            try:
                found = self.read_layouts_file(path)
            except ValueError as ex:
                problems.append("%s: %s" % (os.path.basename(path), ex))
                continue
            risky = [r for _n, ks in found for r in self.risky_keys(ks)]
            if risky:
                shown = "\n".join(risky[:8]) + ("\n…and %d more" % (len(risky) - 8) if len(risky) > 8 else "")
                if not messagebox.askyesno(
                        "Import layouts",
                        "%s has keys that press other keys for you:\n\n%s\n\nOnly import layouts "
                        "from people you trust. Import it?" % (os.path.basename(path), shown),
                        parent=self.root):
                    continue
            for name, keys in found:
                name = safe_name(name) or "Imported layout"
                final = name
                if final in list_loadouts():
                    answer = messagebox.askyesnocancel(
                        "Import layouts",
                        "You already have a layout called “%s”.\n\nYes = replace it\n"
                        "No = keep both (the new one is renamed)\nCancel = skip it" % name,
                        parent=self.root)
                    if answer is None:
                        continue
                    if not answer:
                        n = 2
                        while "%s (%d)" % (name, n) in list_loadouts():
                            n += 1
                        final = "%s (%d)" % (name, n)
                try:
                    os.makedirs(LOADOUT_DIR, exist_ok=True)
                    with open(os.path.join(LOADOUT_DIR, final + ".json"), "w", encoding="utf-8") as f:
                        json.dump(self.layout_data(keys), f, indent=2)
                    added.append(final)
                except Exception as ex:
                    problems.append("%s: %s" % (final, ex))
        msg = []
        if added:
            msg.append("Imported: " + ", ".join(added) + ".\nFind them in the Loadouts menu.")
        if problems:
            msg.append("Couldn't import:\n" + "\n".join(problems))
        if msg:
            (messagebox.showinfo if added and not problems else messagebox.showwarning)(
                "Import layouts", "\n\n".join(msg), parent=self.root)
        if len(added) == 1 and messagebox.askyesno("Import layouts", "Switch to it now?", parent=self.root):
            self.load_loadout(added[0])

    # ---------------- shutdown ----------------
    def on_close(self):
        if self.speaker is not None:
            self.speaker.stop()
        self.release_all(redraw=False)
        save_settings(self.settings)
        self.pt.save()
        self.root.destroy()


def main():
    if IS_WIN:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
        
        # Give Windows a stable app ID so the taskbar button groups properly.
        try:
            myappid = "com.keydeck.plus.v1"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

    root = tk.Tk()
    KeyDeck(root)
    root.mainloop()


if __name__ == "__main__":
    main()
