"""
config.py — All tunable constants for the typewriter application.

Centralising settings here keeps the other modules free of magic numbers
and makes visual/behavioural tuning easy without touching logic code.
"""

import os

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
SOUNDS_DIR = os.path.join(ASSETS_DIR, "sounds")
FONTS_DIR  = os.path.join(ASSETS_DIR, "fonts")
EXPORTS_DIR  = os.path.join(BASE_DIR, "exports")

# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

WINDOW_TITLE = "Typewriter"
TARGET_FPS   = 60

# Desk / background colour  (dark warm wood tone)
BACKGROUND_COLOR = (28, 25, 22)

# ---------------------------------------------------------------------------
# Paper
# ---------------------------------------------------------------------------

# Physical page dimensions in pixels (approx 8.5" × 11" at ~96 px/in)
PAPER_WIDTH  = 850
PAPER_HEIGHT = 1100

# Paper fill colour — warm off-white
PAPER_COLOR        = (247, 243, 232)
PAPER_SHADOW_COLOR = (10, 8, 6)
PAPER_SHADOW_OFFSET = (5, 7)     # (x, y) offset of the drop shadow

# How much paper texture noise to add at startup (0 = none)
PAPER_TEXTURE_NOISE = 5

# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------

# Ordered list of monospace fonts to try at startup
FONT_NAMES_PRIORITY = [
    "courier new",
    "courier",
    "liberation mono",
    "dejavu sans mono",
    "freemono",
    "monospace",
]

FONT_SIZE = 17          # Points — adjust for your display density

# ---------------------------------------------------------------------------
# Ink
# ---------------------------------------------------------------------------

# Base ink colour: near-black with a warm brown cast (like a worn ribbon)
INK_COLOR_BASE = (22, 18, 14)

# Ink opacity range; each keystroke picks a random value in this range
INK_ALPHA_MIN = 175
INK_ALPHA_MAX = 248

# Max random pixel jitter applied to each stamp (simulates loose type bars)
INK_JITTER_X = 0.9   # horizontal pixels
INK_JITTER_Y = 0.0  # vertical pixels

# ---------------------------------------------------------------------------
# Margins  (pixels from paper edge)
# ---------------------------------------------------------------------------

MARGIN_LEFT   = 40
MARGIN_RIGHT  = 40
MARGIN_TOP    = 45
MARGIN_BOTTOM = 45

# ---------------------------------------------------------------------------
# Line spacing & tabs
# ---------------------------------------------------------------------------

LINE_HEIGHT_MULTIPLIER = 1.55   # Relative to font cap-height
TAB_STOP_WIDTH = 4              # Characters per tab stop

# ---------------------------------------------------------------------------
# Bell zone
# ---------------------------------------------------------------------------

# Ring the bell this many character-widths before the right margin
BELL_CHARS_FROM_RIGHT = 8

# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------

SOUND_ENABLED_DEFAULT = True
SOUND_VOLUME          = 0.72
SOUND_FREQUENCY       = 44100
SOUND_BUFFER          = 256     # Samples — lower = less latency (~6 ms)
SOUND_CHANNELS        = 8

# Mixer channel assignments (keeps concurrent sounds from cutting each other)
CH_KEY      = 0    # Key strike / space / backspace
CH_CARRIAGE = 1    # Carriage return sweep
CH_LINEFEED = 2    # Platen ratchet
CH_BELL     = 3    # Bell ding

# ---------------------------------------------------------------------------
# Carriage indicator
# ---------------------------------------------------------------------------

# Thin vertical highlight drawn at the current carriage position
CARRIAGE_INDICATOR_COLOR = (50, 50, 50, 70)   # RGBA
CARRIAGE_INDICATOR_WIDTH = 2

# ---------------------------------------------------------------------------
# Scroll / viewport
# ---------------------------------------------------------------------------

# Zoom multiplier applied on top of fit-to-height.
# 1.0 = whole page fits on screen (no forced overflow).
PAPER_ZOOM = 1.0

# Where on screen the carriage cursor is anchored (fractions of screen size).
# The page pans around this fixed point as you type, just like a real typewriter.
CURSOR_TARGET_X_FRAC = 0.50   # horizontal centre
CURSOR_TARGET_Y_FRAC = 0.95   # 95 % down — 5 % above the bottom

# Gap between pages in the document view (page-pixel units, scales with paper)
PAGE_GAP = 40

# Pixels scrolled per arrow-key press or mouse-wheel notch.
SCROLL_STEP = 60

# ---------------------------------------------------------------------------
# Session / persistence
# ---------------------------------------------------------------------------

SESSION_FORMAT_VERSION = 1
AUTO_SAVE_SECONDS      = 45     # How often to write an auto-save

# ---------------------------------------------------------------------------
# Overlay / HUD
# ---------------------------------------------------------------------------

OVERLAY_FONT_SIZE  = 14
OVERLAY_LINE_H     = 22
OVERLAY_PADDING    = 22
OVERLAY_BG_ALPHA   = 195
OVERLAY_TEXT_COLOR = (225, 220, 205)
