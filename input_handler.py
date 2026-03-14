"""
input_handler.py — Keyboard event → typewriter action translation.

Responsibilities:
  - Translate raw pygame KEYDOWN events into semantic InputAction values.
  - Delegate all key-binding decisions to the Keybindings config object.
  - Generate the in-app help overlay text from the live bindings.
  - Never touch game state — only interpret and return.
"""

from __future__ import annotations

import pygame

from keybindings import Keybindings


class InputAction:
    """Enumeration of possible typewriter actions."""
    # Typing
    PRINT_CHAR           = "print_char"           # stamp a visible character
    FORWARD_CHAR         = "forward_char"          # advance without stamping (space)
    BACK_CHAR            = "back_char"             # move carriage back (no erase)
    CARRIAGE_RETURN      = "carriage_return"       # snap to left margin
    LINE_FEED            = "line_feed"             # advance one line
    RETURN_AND_LINE_FEED = "return_and_line_feed"  # carriage return + line feed
    FORWARD_TAB          = "forward_tab"           # advance to next tab stop
    BACK_TAB             = "back_tab"              # retreat to previous tab stop
    STRIKETHROUGH        = "strikethrough"         # overstrike dash at midline

    # Navigation
    LINE_UP              = "line_up"
    LINE_DOWN            = "line_down"
    HALF_LINE_UP         = "half_line_up"
    HALF_LINE_DOWN       = "half_line_down"
    PREV_PAGE            = "prev_page"
    NEXT_PAGE            = "next_page"
    SCROLL_TOP           = "scroll_top"

    # Document
    INSERT_PAGE          = "insert_page"
    DELETE_PAGE          = "delete_page"

    # Application
    VOLUME_UP            = "volume_up"
    VOLUME_DOWN          = "volume_down"
    SAVE                 = "save"
    SAVE_AS              = "save_as"
    OPEN_DOCUMENT        = "open_document"
    NEW_DOCUMENT         = "new_document"
    EXPORT_PDF           = "export_pdf"
    TOGGLE_HELP          = "toggle_help"
    QUIT                 = "quit"


# Human-readable description for each action (used in the help overlay).
_ACTION_DESCRIPTIONS: list[tuple[str, str] | None] = [
    (InputAction.LINE_FEED,            "line feed"),
    (InputAction.CARRIAGE_RETURN,      "carriage return"),
    (InputAction.RETURN_AND_LINE_FEED, "carriage return + line feed"),
    (InputAction.BACK_CHAR,            "back one character  (no erasure)"),
    (InputAction.FORWARD_CHAR,         "forward one character"),
    (InputAction.FORWARD_TAB,          "forward to next tab stop"),
    (InputAction.BACK_TAB,             "back to previous tab stop"),
    (InputAction.STRIKETHROUGH,        "strikethrough dash  (overstrike at midline)"),
    None,
    (InputAction.LINE_UP,              "up one line"),
    (InputAction.LINE_DOWN,            "down one line"),
    (InputAction.HALF_LINE_UP,         "up half a line"),
    (InputAction.HALF_LINE_DOWN,       "down half a line"),
    (InputAction.PREV_PAGE,            "previous sheet"),
    (InputAction.NEXT_PAGE,            "next sheet"),
    (InputAction.SCROLL_TOP,           "go to start of first sheet"),
    None,
    (InputAction.INSERT_PAGE,          "insert page after current"),
    (InputAction.DELETE_PAGE,          "delete current page"),
    (InputAction.SAVE,                 "save session"),
    (InputAction.EXPORT_PDF,           "export as PDF"),
    (InputAction.VOLUME_UP,            "volume up"),
    (InputAction.VOLUME_DOWN,          "volume down"),
    (InputAction.SAVE_AS,              "save as new document"),
    (InputAction.OPEN_DOCUMENT,        "open document"),
    (InputAction.NEW_DOCUMENT,         "new document"),
    None,
    (InputAction.TOGGLE_HELP,          "toggle this help"),
    (InputAction.QUIT,                 "quit"),
]


class InputHandler:
    """
    Translates a pygame.KEYDOWN event into an (InputAction, char | None) pair.

    Returns None for events that have no typewriter meaning (bare modifier
    keys, unrecognised Ctrl combos, etc.).
    """

    def __init__(self, keybindings: Keybindings | None = None):
        self._kb = keybindings or Keybindings.load()

    def process(
        self, event: pygame.event.Event
    ) -> tuple[str, str | None] | None:
        """
        Process one pygame KEYDOWN event.

        Returns (action, char) where char is the unicode character for
        PRINT_CHAR and FORWARD_CHAR, or None for all other actions.
        Returns None if the event has no typewriter meaning.
        """
        if event.type != pygame.KEYDOWN:
            return None

        key  = event.key
        mods = event.mod
        ctrl  = bool(mods & pygame.KMOD_CTRL)
        shift = bool(mods & pygame.KMOD_SHIFT)
        alt   = bool(mods & pygame.KMOD_ALT)

        # ── Bound actions ──────────────────────────────────────────────
        action = self._kb.action_for(key, ctrl, shift, alt)
        if action is not None:
            char = event.unicode if action == InputAction.FORWARD_CHAR else None
            return (action, char)

        # ── Swallow unrecognised Ctrl / Alt combos ─────────────────────
        # Prevents accidental characters from modifier+key combos.
        if ctrl or alt:
            return None

        # ── Printable characters (catch-all) ───────────────────────────
        char = event.unicode
        if char and char.isprintable() and char != " ":
            return (InputAction.PRINT_CHAR, char)

        return None

    def overlay_lines(self) -> list[str]:
        """Generate the help overlay text from the current bindings."""
        col_width = 36   # description column width (padded to align shortcuts)
        lines = ["─── TYPEWRITER  KEY  REFERENCE ───", ""]

        for entry in _ACTION_DESCRIPTIONS:
            if entry is None:
                lines.append("")
                continue
            action, description = entry
            labels = self._kb.labels_for(action)
            if not labels:
                label_str = "(unbound)"
            else:
                label_str = "  /  ".join(labels)
            lines.append(f"  {description.capitalize():<{col_width}}{label_str}")

        lines += ["", "  ─── press any key to dismiss ───"]
        return lines
