"""
carriage.py — Typewriter carriage and platen state.

The Carriage tracks:
  - the current pixel position on the page (x = horizontal, y = top of line)
  - the logical column index (for tab stops and bell-zone detection)
  - the line index (for page-full detection)

All movement methods mirror real typewriter mechanics:
  advance()          — move one character-width to the right
  backspace()        — move one character-width to the left (no erasure)
  carriage_return()  — snap x back to the left margin
  line_feed()        — advance y by one line height (platen rotation)
  tab()              — advance to the next tab stop
"""

from config import (
    PAPER_WIDTH, PAPER_HEIGHT,
    MARGIN_LEFT, MARGIN_RIGHT, MARGIN_TOP, MARGIN_BOTTOM,
    LINE_HEIGHT_MULTIPLIER, TAB_STOP_WIDTH,
    BELL_CHARS_FROM_RIGHT,
)


class Carriage:
    """
    Tracks carriage (horizontal) and platen (vertical) position.

    Positions are always in page-pixel coordinates so the renderer can
    draw the carriage indicator without any coordinate conversion.
    """

    def __init__(self, char_width: int, char_height: int):
        self.char_width  = char_width
        self.char_height = char_height
        self.line_height = max(1, int(char_height * LINE_HEIGHT_MULTIPLIER))

        # Typing-area boundaries in page pixels
        self.left_margin   = MARGIN_LEFT
        self.right_margin  = PAPER_WIDTH - MARGIN_RIGHT
        self.top_margin    = MARGIN_TOP
        self.bottom_margin = PAPER_HEIGHT - MARGIN_BOTTOM

        # How many character cells fit across the typing area
        self.cols_per_line = max(
            1,
            (self.right_margin - self.left_margin) // self.char_width,
        )

        # Current position
        self.x   = self.left_margin   # pixel x of left edge of next glyph
        self.y   = self.top_margin    # pixel y of top edge of current line
        self.col = 0                  # logical column index
        self.row = 0                  # logical line index

        self._bell_rung_this_line = False

    # ------------------------------------------------------------------
    # Movement
    # ------------------------------------------------------------------

    def advance(self) -> bool:
        """
        Move one character to the right.

        Returns True if the carriage has reached or passed the right margin
        (so the caller can decide whether to block further input or wrap).
        """
        self.x   += self.char_width
        self.col += 1
        return self.x >= self.right_margin

    def backspace(self) -> bool:
        """
        Move one character to the left without erasing anything.

        Returns True if movement was possible (i.e. not already at left margin).
        """
        if self.x > self.left_margin:
            self.x   -= self.char_width
            self.col  = max(0, self.col - 1)
            # Crossing back into the non-bell zone resets the bell flag
            if self.col < self.cols_per_line - BELL_CHARS_FROM_RIGHT:
                self._bell_rung_this_line = False
            return True
        return False

    def carriage_return(self):
        """Snap carriage to the left margin."""
        self.x   = self.left_margin
        self.col = 0
        self._bell_rung_this_line = False

    def line_up(self) -> bool:
        """
        Move the carriage up one line (reverse platen roll).
        Returns True if movement was possible (not already at top margin).
        """
        if self.y - self.line_height < self.top_margin:
            return False
        self.y   -= self.line_height
        self.row  = max(0, self.row - 1)
        self._bell_rung_this_line = False
        return True

    def line_down(self) -> bool:
        """
        Move the carriage down one line (forward platen roll).
        Returns True if movement was possible (not already past bottom margin).
        """
        if self.y + self.line_height > self.bottom_margin:
            return False
        self.y   += self.line_height
        self.row += 1
        self._bell_rung_this_line = False
        return True

    def half_line_up(self) -> bool:
        """
        Move the carriage up half a line.
        Returns True if movement was possible (not already at top margin).
        """
        step = self.line_height // 2
        if self.y - step < self.top_margin:
            return False
        self.y -= step
        self._bell_rung_this_line = False
        return True

    def half_line_down(self) -> bool:
        """
        Move the carriage down half a line.
        Returns True if movement was possible (not already past bottom margin).
        """
        step = self.line_height // 2
        if self.y + step > self.bottom_margin:
            return False
        self.y += step
        self._bell_rung_this_line = False
        return True

    def line_feed(self) -> bool:
        """
        Advance the platen by one line.

        Returns True if the page is now full (current line top is below
        the bottom margin), so the caller can warn the user.
        """
        self.y   += self.line_height
        self.row += 1
        return self.y + self.line_height > self.bottom_margin

    def tab(self) -> int:
        """
        Advance to the next tab stop.

        Returns the number of character-widths advanced (0 if already at
        or past the right margin).
        """
        if self.x >= self.right_margin:
            return 0
        next_col = ((self.col // TAB_STOP_WIDTH) + 1) * TAB_STOP_WIDTH
        steps = 0
        while self.col < next_col:
            at_margin = self.advance()
            steps += 1
            if at_margin:
                break
        return steps

    def back_tab(self) -> int:
        """
        Retreat to the previous tab stop.

        Returns the number of character-widths moved back (0 if already at
        the left margin).
        """
        if self.x <= self.left_margin:
            return 0
        prev_col = ((self.col - 1) // TAB_STOP_WIDTH) * TAB_STOP_WIDTH
        steps = 0
        while self.col > prev_col and self.x > self.left_margin:
            self.x   -= self.char_width
            self.col  = max(0, self.col - 1)
            steps    += 1
        if self.col < self.cols_per_line - BELL_CHARS_FROM_RIGHT:
            self._bell_rung_this_line = False
        return steps

    # ------------------------------------------------------------------
    # Full-page / bell queries
    # ------------------------------------------------------------------

    def is_at_right_margin(self) -> bool:
        return self.x >= self.right_margin

    def is_page_full(self) -> bool:
        return self.y + self.line_height > self.bottom_margin

    def should_ring_bell(self) -> bool:
        """
        Return True (once per line) when the carriage enters the bell zone.

        The bell zone begins BELL_CHARS_FROM_RIGHT columns before the right
        margin, matching the behaviour of a real typewriter.
        """
        cols_remaining = self.cols_per_line - self.col
        in_zone = cols_remaining <= BELL_CHARS_FROM_RIGHT and cols_remaining >= 0
        if in_zone and not self._bell_rung_this_line:
            self._bell_rung_this_line = True
            return True
        return False

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(self):
        """Return to the home position (top-left of typing area)."""
        self.x   = self.left_margin
        self.y   = self.top_margin
        self.col = 0
        self.row = 0
        self._bell_rung_this_line = False

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def get_state(self) -> dict:
        return {
            "x":   self.x,
            "y":   self.y,
            "col": self.col,
            "row": self.row,
        }

    def set_state(self, state: dict):
        self.x   = state["x"]
        self.y   = state["y"]
        self.col = state["col"]
        self.row = state.get("row", 0)
        self._bell_rung_this_line = False
