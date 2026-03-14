"""
app.py — TypewriterApp: the top-level coordinator.

Owns all subsystems and runs the pygame event loop.  Acts as the glue
between:
  InputHandler  (what the user pressed)
  Carriage      (where we are on the page)
  Page          (the canvas being written onto)
  SoundManager  (audio feedback)
  Renderer      (drawing everything to the screen)
  Document      (save / restore in .typewriter format)
  Exporter      (PNG / PDF output)

Multi-page model
----------------
The document is a list of Page objects with a parallel list of saved
carriage states.  self._page and self._carriage always reflect the active
sheet.  Switching sheets commits the live carriage state to the list, swaps
self._page, and restores the target sheet's carriage state.

  self._pages        : list[Page]   — all sheets in order
  self._page_states  : list[dict]   — saved carriage state for each sheet
                                       (current sheet's state is live in
                                        self._carriage; synced on switch/save)
  self._page_idx     : int          — index of the active sheet
"""

from __future__ import annotations

import sys
import time
import os
import pygame

from config import (
    WINDOW_TITLE, TARGET_FPS,
    FONT_NAMES_PRIORITY, FONT_SIZE,
    AUTO_SAVE_SECONDS, SCROLL_STEP,
    OVERLAY_FONT_SIZE, BACKGROUND_COLOR,
)
from page          import Page
from carriage      import Carriage
from sound_manager import SoundManager
from input_handler import InputHandler, InputAction
from renderer      import Renderer
from document      import Document
from modal         import TextInputModal, DocumentBrowserModal, ConfirmModal
from exporter      import Exporter


class TypewriterApp:
    """
    Initialises pygame and all subsystems, then runs the event loop.

    Parameters (from argparse namespace)
    -------------------------------------
    windowed      : bool — run in a resizable window instead of full-screen
    no_sound      : bool — disable all audio
    document_path : str | None — path to a .typewriter file to open at start
    """

    def __init__(self, args):
        self._args         = args
        self._running      = False
        self._show_overlay = False
        self._last_autosave = 0.0
        self._status_message: str | None = None
        self._status_until:   float       = 0.0
        self._document: Document          = Document()
        self._modal                       = None
        self._modal_purpose: str | None   = None
        self._pending_path: str | None    = None   # path queued for open after confirm
        self._pending_carriage_view: tuple | None = None  # deferred cursor advance

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def initialize(self):
        pygame.init()

        # ── Screen ────────────────────────────────────────────────────
        if getattr(self._args, "windowed", False):
            flags = pygame.RESIZABLE
            size  = (1280, 820)
        else:
            flags = pygame.FULLSCREEN | pygame.HWSURFACE | pygame.DOUBLEBUF
            size  = (0, 0)

        self._screen = pygame.display.set_mode(size, flags)
        pygame.display.set_caption(WINDOW_TITLE)
        pygame.mouse.set_visible(False)

        # Fill both buffers with the background colour immediately so there is
        # no black or garbage frame visible while the rest of initialisation
        # (font loading, sound init, etc.) runs.
        for _ in range(2):
            self._screen.fill(BACKGROUND_COLOR)
            pygame.display.flip()

        # ── Font ──────────────────────────────────────────────────────
        self._font = self._load_font()
        char_w, char_h = self._font.size("M")

        # ── Subsystems ────────────────────────────────────────────────
        self._sound    = SoundManager(enabled=not getattr(self._args, "no_sound", False))
        self._carriage = Carriage(char_w, char_h)
        self._renderer = Renderer(self._screen)
        self._input    = InputHandler()
        self._exporter = Exporter()
        self._clock    = pygame.time.Clock()

        # ── Overlay font (lazy-initialised) ───────────────────────────
        self._overlay_font: pygame.font.Font | None = None

        # ── Page list (single blank sheet to start) ───────────────────
        self._page        = Page(self._font)
        self._pages       = [self._page]
        self._page_states = [{}]          # current sheet's state is live
        self._page_idx    = 0

        # ── Load document if specified on the command line ────────────
        load_path = getattr(self._args, "document_path", None)
        if load_path:
            self._load_from_path(load_path)

        self._renderer.update_carriage_view(self._carriage.x, self._carriage.y, self._page_idx)
        self._last_autosave = time.monotonic()
        self._running = True

        # Prime both display buffers with a fully-drawn frame so neither
        # buffer is ever shown blank or stale after the first flip.
        self._render()
        self._render()

    # ------------------------------------------------------------------
    # Font loading
    # ------------------------------------------------------------------

    def _load_font(self) -> pygame.font.Font:
        for name in FONT_NAMES_PRIORITY:
            try:
                f  = pygame.font.SysFont(name, FONT_SIZE)
                wi = f.size("i")[0]
                wm = f.size("M")[0]
                if wi == wm and wi > 0:
                    print(f"[font] Using '{name}' at {FONT_SIZE}pt  (char cell {wi}×{f.get_height()})")
                    return f
            except Exception:
                continue
        print("[font] Warning: no monospace font found, using pygame default")
        return pygame.font.Font(pygame.font.get_default_font(), FONT_SIZE)

    # ------------------------------------------------------------------
    # Document loading helpers
    # ------------------------------------------------------------------

    def _load_from_path(self, path: str) -> None:
        """
        Attempt to load a document from *path*.

        Tries the new .typewriter ZIP format first, then the legacy directory
        format.  On failure, prints a warning and leaves the blank document
        in place.
        """
        result = Document.load(path)
        if result is None:
            # Try legacy directory format (path might be a directory)
            result = Document.load_legacy(path)
        if result:
            self._document, pages_data, idx = result
            self._apply_pages_data(pages_data, idx)
        else:
            print(f"[app] Warning: could not load '{path}' — starting blank")

    def _apply_pages_data(self, pages_data: list[dict], current_idx: int) -> None:
        """Reconstruct self._pages / self._page_states from loaded page data."""
        self._pages       = []
        self._page_states = []
        for pd in pages_data:
            p = Page(self._font)
            p.restore_from_strikes(pd.get("strikes", []))
            self._pages.append(p)
            self._page_states.append(pd.get("carriage", {}))

        if not self._pages:
            # Safety net: always have at least one page
            self._pages       = [Page(self._font)]
            self._page_states = [{}]
            current_idx       = 0

        self._page_idx = max(0, min(current_idx, len(self._pages) - 1))
        self._page     = self._pages[self._page_idx]
        if self._page_states[self._page_idx]:
            self._carriage.set_state(self._page_states[self._page_idx])
        else:
            self._carriage.reset()

    # ------------------------------------------------------------------
    # Overlay font (lazy)
    # ------------------------------------------------------------------

    def _get_overlay_font(self) -> pygame.font.Font:
        if self._overlay_font is None:
            self._overlay_font = pygame.font.SysFont("monospace", OVERLAY_FONT_SIZE)
        return self._overlay_font

    # ------------------------------------------------------------------
    # Window title
    # ------------------------------------------------------------------

    def _update_title(self) -> None:
        dirty_marker = "*" if self._document.dirty else ""
        pygame.display.set_caption(
            f"{WINDOW_TITLE} — {self._document.display_name}{dirty_marker}"
        )

    # ------------------------------------------------------------------
    # Modal helpers
    # ------------------------------------------------------------------

    def _show_confirm(self, message: str, purpose: str) -> None:
        self._modal         = ConfirmModal(message)
        self._modal_purpose = purpose
        self._show_overlay  = False

    def _show_text_input(
        self, prompt: str, purpose: str, initial: str = ""
    ) -> None:
        self._modal         = TextInputModal(prompt, initial)
        self._modal_purpose = purpose
        self._show_overlay  = False

    def _show_document_browser(self) -> None:
        search_dirs: list[str] = [os.getcwd()]
        if self._document.path:
            doc_dir = os.path.dirname(os.path.abspath(self._document.path))
            if doc_dir not in search_dirs:
                search_dirs.append(doc_dir)
        home_share = os.path.expanduser("~/.local/share/typewriter")
        if home_share not in search_dirs:
            search_dirs.append(home_share)
        self._modal         = DocumentBrowserModal(search_dirs, self._document.path)
        self._modal_purpose = "open"
        self._show_overlay  = False

    def _finish_modal(self) -> None:
        modal   = self._modal
        purpose = self._modal_purpose   # noqa: F841 — may be used later
        self._modal         = None
        self._modal_purpose = None

        if isinstance(modal, TextInputModal):
            if not modal.confirmed or not modal.text.strip():
                return
            name = modal.text.strip()
            # Resolve to an absolute path
            if os.sep in name or name.startswith("~"):
                path = os.path.expanduser(name)
            else:
                path = os.path.join(os.getcwd(), name)
            if not path.endswith(".typewriter"):
                path += ".typewriter"
            self._commit_current_page_state()
            try:
                self._document.save(
                    self._pages, self._page_states, self._page_idx, path=path
                )
                self._update_title()
                self._set_status(f"Saved → {self._document.display_name}")
            except Exception as exc:
                self._set_status(f"Save failed: {exc}")

        elif isinstance(modal, DocumentBrowserModal):
            if modal.create_new:
                self._start_new_document()
            elif modal.selected_path:
                self._open_document_file(modal.selected_path)

        elif isinstance(modal, ConfirmModal):
            if not modal.confirmed:
                self._pending_path = None
                return
            if purpose == "quit":
                self._running = False
            elif purpose == "new_document":
                self._do_start_new_document()
            elif purpose == "open_document" and self._pending_path:
                path = self._pending_path
                self._pending_path = None
                self._do_open_document_file(path)

    def _start_new_document(self) -> None:
        """Reset to a single blank untitled page, prompting if there are unsaved changes."""
        if self._document.dirty:
            self._show_confirm(
                f'"{self._document.display_name}" has unsaved changes. Discard and start new?',
                purpose="new_document",
            )
            return
        self._do_start_new_document()

    def _do_start_new_document(self) -> None:
        self._document    = Document()
        self._page        = Page(self._font)
        self._pages       = [self._page]
        self._page_states = [{}]
        self._page_idx    = 0
        self._carriage.reset()

        self._renderer.update_carriage_view(self._carriage.x, self._carriage.y, self._page_idx)
        self._update_title()
        self._set_status("New document")

    def _open_document_file(self, path: str) -> None:
        """Load the document at *path*, prompting first if there are unsaved changes."""
        if self._document.dirty:
            self._pending_path = path
            name = os.path.splitext(os.path.basename(path))[0]
            self._show_confirm(
                f'"{self._document.display_name}" has unsaved changes. Discard and open "{name}"?',
                purpose="open_document",
            )
            return
        self._do_open_document_file(path)

    def _do_open_document_file(self, path: str) -> None:
        """Load the document at *path*, replacing the current document."""
        # Reset to blank in case load fails
        self._document    = Document()
        self._page        = Page(self._font)
        self._pages       = [self._page]
        self._page_states = [{}]
        self._page_idx    = 0
        self._carriage.reset()

        self._load_from_path(path)

        self._renderer.update_carriage_view(self._carriage.x, self._carriage.y, self._page_idx)
        self._update_title()
        self._set_status(f"Opened → {self._document.display_name}")

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self):
        while self._running:
            self._handle_events()
            self._tick_autosave()
            self._render()
            self._clock.tick(TARGET_FPS)

        pygame.quit()

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def _handle_events(self):
        if self._pending_carriage_view is not None:
            self._renderer.update_carriage_view(*self._pending_carriage_view)
            self._pending_carriage_view = None

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._running = False
                return
            if event.type == pygame.MOUSEWHEEL:
                # y > 0 = wheel up = scroll to earlier lines
                self._renderer.scroll_by(-event.y * SCROLL_STEP)
            if event.type == pygame.KEYDOWN:
                if self._modal is not None:
                    self._modal.handle_event(event)
                    if self._modal.done:
                        self._finish_modal()
                else:
                    result = self._input.process(event)
                    if result:
                        action, char = result
                        self._dispatch(action, char)

    def _dispatch(self, action: str, char: str | None):
        # Any key dismisses the overlay (except the toggle itself)
        if self._show_overlay and action != InputAction.TOGGLE_HELP:
            self._show_overlay = False
            return  # consume the key to avoid accidental typing

        if action == InputAction.QUIT:
            if self._document.dirty:
                self._show_confirm(
                    f'"{self._document.display_name}" has unsaved changes. Quit anyway?',
                    purpose="quit",
                )
            else:
                self._running = False

        elif action == InputAction.TOGGLE_HELP:
            self._show_overlay = not self._show_overlay

        elif action == InputAction.PRINT_CHAR:
            self._type_char(char)

        elif action == InputAction.FORWARD_CHAR:
            self._type_space()

        elif action == InputAction.CARRIAGE_RETURN:
            self._do_carriage_return()

        elif action == InputAction.LINE_FEED:
            self._do_line_feed()

        elif action == InputAction.RETURN_AND_LINE_FEED:
            self._do_return_and_line_feed()

        elif action == InputAction.BACK_CHAR:
            self._do_backspace()

        elif action == InputAction.FORWARD_TAB:
            self._do_tab()

        elif action == InputAction.BACK_TAB:
            self._do_back_tab()

        elif action == InputAction.SAVE:
            if self._document.path is None:
                self._show_text_input("Save as:", "save", "")
            else:
                self._commit_current_page_state()
                try:
                    self._document.save(self._pages, self._page_states, self._page_idx)
                    self._update_title()
                    self._set_status(f"Saved → {self._document.display_name}")
                except Exception as exc:
                    self._set_status(f"Save failed: {exc}")

        elif action == InputAction.SAVE_AS:
            self._show_text_input(
                "Save as:",
                "save_as",
                self._document.display_name if self._document.path else "",
            )

        elif action == InputAction.OPEN_DOCUMENT:
            self._show_document_browser()

        elif action == InputAction.NEW_DOCUMENT:
            self._start_new_document()

        elif action == InputAction.EXPORT_PDF:
            path = self._exporter.export_pdf(self._pages)
            if path:
                self._set_status(f"Exported → {os.path.basename(path)}")
            else:
                self._set_status("PDF export requires: pip install reportlab")

        elif action == InputAction.INSERT_PAGE:
            self._insert_page()

        elif action == InputAction.DELETE_PAGE:
            self._delete_page()

        elif action == InputAction.PREV_PAGE:
            self._go_to_page(self._page_idx - 1)

        elif action == InputAction.NEXT_PAGE:
            self._go_to_page(self._page_idx + 1)

        elif action == InputAction.LINE_UP:
            if not self._carriage.line_up():
                if self._page_idx > 0:
                    self._switch_page(self._page_idx - 1, last_line=True)
            self._renderer.update_carriage_view(self._carriage.x, self._carriage.y, self._page_idx)

        elif action == InputAction.LINE_DOWN:
            if not self._carriage.line_down():
                if self._page_idx < len(self._pages) - 1:
                    self._switch_page(self._page_idx + 1, last_line=False)
            self._renderer.update_carriage_view(self._carriage.x, self._carriage.y, self._page_idx)

        elif action == InputAction.HALF_LINE_UP:
            self._carriage.half_line_up()
            self._renderer.update_carriage_view(self._carriage.x, self._carriage.y, self._page_idx)

        elif action == InputAction.HALF_LINE_DOWN:
            self._carriage.half_line_down()
            self._renderer.update_carriage_view(self._carriage.x, self._carriage.y, self._page_idx)

        elif action == InputAction.SCROLL_TOP:
            self._go_to_page(0)
            self._carriage.y   = self._carriage.top_margin
            self._carriage.row = 0
            self._renderer.update_carriage_view(self._carriage.x, self._carriage.y, self._page_idx)

        elif action == InputAction.VOLUME_UP:
            vol = min(1.0, self._sound.volume + 0.1)
            self._sound.set_volume(vol)
            self._set_status(f"Volume: {int(vol * 100)}%")

        elif action == InputAction.VOLUME_DOWN:
            vol = max(0.0, self._sound.volume - 0.1)
            self._sound.set_volume(vol)
            self._set_status(f"Volume: {int(vol * 100)}%")

        elif action == InputAction.STRIKETHROUGH:
            self._type_strikethrough()

    # ------------------------------------------------------------------
    # Typewriter mechanics
    # ------------------------------------------------------------------

    def _type_char(self, char: str):
        """Stamp a visible character and advance the carriage."""
        if self._carriage.is_at_right_margin():
            return

        self._page.stamp(char, self._carriage.x, self._carriage.y)
        self._sound.play_key_strike()

        # Show the cursor at the stamped position for this frame, then defer
        # the visual advance to the next frame so the character appears under
        # the cursor before it moves.
        self._renderer.update_carriage_view(self._carriage.x, self._carriage.y, self._page_idx)
        self._carriage.advance()
        self._document.mark_dirty()

        if self._carriage.should_ring_bell():
            self._sound.play_bell()

        self._pending_carriage_view = (self._carriage.x, self._carriage.y, self._page_idx)

    def _type_strikethrough(self):
        """Stamp a centred dash for overstrike and advance."""
        if self._carriage.is_at_right_margin():
            return
        self._page.stamp("-", self._carriage.x, self._carriage.y, jitter=False)
        self._sound.play_key_strike()
        self._renderer.update_carriage_view(self._carriage.x, self._carriage.y, self._page_idx)
        self._carriage.advance()
        self._document.mark_dirty()
        self._pending_carriage_view = (self._carriage.x, self._carriage.y, self._page_idx)

    def _type_space(self):
        """Advance carriage one position without stamping a glyph."""
        if self._carriage.is_at_right_margin():
            return
        self._sound.play_space()
        self._carriage.advance()
        self._document.mark_dirty()

        if self._carriage.should_ring_bell():
            self._sound.play_bell()

        self._renderer.update_carriage_view(self._carriage.x, self._carriage.y, self._page_idx)

    def _do_carriage_return(self):
        """Snap carriage to the left margin (no line feed)."""
        if self._carriage.col > 0:
            self._renderer.start_carriage_return(self._sound.carriage_return_duration())
            self._sound.play_carriage_return()
        self._carriage.carriage_return()
        self._document.mark_dirty()
        self._renderer.update_carriage_view(self._carriage.x, self._carriage.y, self._page_idx)

    def _do_line_feed(self):
        """Advance the platen one line (no carriage return)."""
        self._sound.play_line_feed()
        page_full = self._carriage.line_feed()
        self._document.mark_dirty()
        self._renderer.update_carriage_view(self._carriage.x, self._carriage.y, self._page_idx)
        if page_full:
            self._set_status("Page full — Ctrl+N for a new page  |  PgDn to go forward")

    def _do_return_and_line_feed(self):
        """Carriage return followed by line feed."""
        if self._carriage.col > 0:
            self._renderer.start_carriage_return(self._sound.carriage_return_duration())
            self._sound.play_carriage_return()
        self._carriage.carriage_return()
        self._sound.play_line_feed()
        page_full = self._carriage.line_feed()
        self._document.mark_dirty()
        self._renderer.update_carriage_view(self._carriage.x, self._carriage.y, self._page_idx)
        if page_full:
            self._set_status("Page full — Ctrl+N for a new page  |  PgDn to go forward")

    def _do_backspace(self):
        """Move the carriage back one position.  No erasure."""
        if self._carriage.backspace():
            self._sound.play_backspace()
            self._document.mark_dirty()
            self._renderer.update_carriage_view(self._carriage.x, self._carriage.y, self._page_idx)

    def _do_tab(self):
        """Advance to the next tab stop."""
        if self._carriage.tab() > 0:
            self._sound.play_space()
            self._document.mark_dirty()
            self._renderer.update_carriage_view(self._carriage.x, self._carriage.y, self._page_idx)

    def _do_back_tab(self):
        """Retreat to the previous tab stop."""
        if self._carriage.back_tab() > 0:
            self._sound.play_backspace()
            self._document.mark_dirty()
            self._renderer.update_carriage_view(self._carriage.x, self._carriage.y, self._page_idx)

    # ------------------------------------------------------------------
    # Page / sheet navigation
    # ------------------------------------------------------------------

    def _commit_current_page_state(self):
        """Flush the live carriage state into the page_states list."""
        self._page_states[self._page_idx] = self._carriage.get_state()

    def _switch_page(self, idx: int, last_line: bool):
        """
        Switch to page idx, preserving horizontal position.
        If last_line is True, land on the last line; otherwise land on the first.
        Used by line-up/down navigation to cross page boundaries silently.
        """
        saved_x   = self._carriage.x
        saved_col = self._carriage.col

        self._commit_current_page_state()
        self._page_idx = idx
        self._page     = self._pages[idx]

        state = self._page_states[idx]
        if state:
            self._carriage.set_state(state)
        else:
            self._carriage.reset()

        self._carriage.x   = saved_x
        self._carriage.col = saved_col

        if last_line:
            c = self._carriage
            lines = (c.bottom_margin - c.top_margin) // c.line_height
            c.row = max(0, lines - 1)
            c.y   = c.top_margin + c.row * c.line_height

    def _insert_page(self):
        """Insert a fresh sheet after the current one and switch to it."""
        self._commit_current_page_state()

        new_page  = Page(self._font)
        insert_at = self._page_idx + 1

        self._pages.insert(insert_at, new_page)
        self._page_states.insert(insert_at, {})

        self._page_idx = insert_at
        self._page     = self._pages[self._page_idx]
        self._carriage.reset()
        self._document.mark_dirty()
        self._renderer.update_carriage_view(self._carriage.x, self._carriage.y, self._page_idx)

        total = len(self._pages)
        self._set_status(f"New sheet — page {self._page_idx + 1} of {total}")

    def _delete_page(self):
        """Delete the current sheet; refuse if it is the only one."""
        if len(self._pages) == 1:
            self._set_status("Can't delete the only page")
            return

        del self._pages[self._page_idx]
        del self._page_states[self._page_idx]

        new_idx        = min(self._page_idx, len(self._pages) - 1)
        self._page_idx = new_idx
        self._page     = self._pages[new_idx]

        state = self._page_states[new_idx]
        if state:
            self._carriage.set_state(state)
        else:
            self._carriage.reset()

        self._document.mark_dirty()
        self._renderer.update_carriage_view(self._carriage.x, self._carriage.y, self._page_idx)
        total = len(self._pages)
        self._set_status(f"Page deleted — now on page {self._page_idx + 1} of {total}")

    def _go_to_page(self, idx: int):
        """Navigate to sheet idx, clamped to valid range."""
        if idx < 0 or idx >= len(self._pages):
            if idx < 0:
                self._set_status("Already on the first sheet")
            else:
                self._set_status("Already on the last sheet — Ctrl+N to insert one")
            return

        saved_x   = self._carriage.x
        saved_col = self._carriage.col

        self._commit_current_page_state()

        self._page_idx = idx
        self._page     = self._pages[self._page_idx]

        state = self._page_states[self._page_idx]
        if state:
            self._carriage.set_state(state)
        else:
            self._carriage.reset()

        # Preserve horizontal position across page switches
        self._carriage.x   = saved_x
        self._carriage.col = saved_col

        self._renderer.update_carriage_view(self._carriage.x, self._carriage.y, self._page_idx)

        total = len(self._pages)
        self._set_status(f"Page {self._page_idx + 1} of {total}")

    # ------------------------------------------------------------------
    # Periodic save
    # ------------------------------------------------------------------

    def _tick_autosave(self):
        """Periodically save to the current file if the document has been named."""
        now = time.monotonic()
        if now - self._last_autosave >= AUTO_SAVE_SECONDS:
            self._last_autosave = now
            if self._document.path is not None and self._document.dirty:
                self._commit_current_page_state()
                try:
                    self._document.save(self._pages, self._page_states, self._page_idx)
                    self._update_title()
                except Exception:
                    pass  # silent — user will see dirty marker remain

    # ------------------------------------------------------------------
    # Status message
    # ------------------------------------------------------------------

    def _set_status(self, message: str, duration: float = 2.5):
        self._status_message = message
        self._status_until   = time.monotonic() + duration

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def _render(self):
        self._update_title()

        if self._status_message and time.monotonic() > self._status_until:
            self._status_message = None

        overlay_lines = None
        if self._show_overlay:
            overlay_lines = self._input.overlay_lines()
        elif self._status_message:
            overlay_lines = [self._status_message]

        self._renderer.draw(
            self._pages,
            self._page_idx,
            self._carriage,
            show_overlay=bool(overlay_lines),
            overlay_lines=overlay_lines,
        )

        if self._modal is not None:
            self._modal.render(self._screen, self._get_overlay_font())

        pygame.display.flip()
