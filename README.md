# Typewriter

A distraction-free mechanical typewriter simulator for Linux. There is no editing, no cursor keys for repositioning text, no undo. You type. The ink goes on the page. Just like the real thing.

![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![Pygame](https://img.shields.io/badge/pygame-2.1%2B-green) ![Platform](https://img.shields.io/badge/platform-Linux-lightgrey)

---

## What it is

Typewriter renders a sheet of paper on a dark desk. Every keystroke stamps a glyph directly onto that paper canvas — with randomised ink opacity and sub-pixel jitter to simulate a worn ribbon and loose type bars. The carriage tracks position, rings a bell near the right margin, and scrolls the page so the typing point stays near the bottom of the screen.

It is not a text editor. There is no text model, no line wrapping, no selection. Backspace moves the carriage left without erasing. Overtyping is how you strike through a word. What you see on screen is exactly what you get in the export.

---

## Features

- **Canvas-based rendering** — glyphs are stamped permanently onto a `pygame.Surface`; no text model
- **Authentic ink simulation** — random opacity (175–248) and ±0.9 px horizontal jitter per keystroke
- **Full typewriter mechanics** — carriage return, line feed, tab stops, bell zone, right-margin cutoff
- **Multi-page documents** — insert and delete sheets; navigate with Page Up/Down or arrow keys across page boundaries
- **Synthesised sound effects** — key strikes, space bar, backspace, carriage return sweep, platen ratchet, bell; no bundled audio assets required
- **Portable document format** — `.typewriter` files are ZIP archives containing a strike log and page snapshots; documents can be moved freely between machines
- **Lossless session replay** — jitter values are saved per-keystroke, so pages render identically after reload
- **PDF and PNG export** — PNG always works; PDF requires `reportlab`
- **Configurable key bindings** — TOML file; any action can have multiple bindings or none
- **Auto-save** — writes to the open file every 45 seconds if there are unsaved changes
- **Dirty-document protection** — confirms before closing or switching away from unsaved work
- **Full-screen and windowed** — command-line flags control the display mode

---

## Requirements

- Python 3.10 or later
- pygame >= 2.1.0
- numpy >= 1.21.0 (for paper texture; gracefully skipped if absent)
- reportlab >= 3.6.0 (optional; enables PDF export)

On Debian/Ubuntu you also need the SDL2 system libraries:

```
sudo apt install libsdl2-dev libsdl2-mixer-dev libsdl2-image-dev libsdl2-ttf-dev
```

---

## Installation

```bash
git clone <repo-url>
cd typewriter
bash setup.sh      # creates venv, installs deps, synthesises sound files
```

`setup.sh` installs the SDL2 system libraries, creates a Python virtual environment, installs Python dependencies, and generates all WAV files from scratch using pure-Python synthesis — no bundled audio assets needed.

---

## Running

```bash
bash run.sh                        # full-screen, blank document
bash run.sh novel.typewriter       # open an existing document
python main.py --windowed          # resizable window (useful for testing)
python main.py --no-sound          # disable all audio
python main.py FILE.typewriter     # open a specific document
```

---

## Key bindings

| Action | Default |
|---|---|
| Type character | Any printable key |
| Carriage return | Ctrl+R |
| Line feed | Enter / Numpad Enter |
| Return + line feed | Ctrl+Enter |
| Back one character | Backspace / ← |
| Forward one character | Space / → |
| Tab forward | Tab |
| Tab backward | Shift+Tab |
| Strikethrough | Ctrl+- |
| Line up / down | ↑ / ↓ |
| Previous / next page | Page Up / Page Down |
| Go to top | Home |
| Insert page after current | Ctrl+N |
| Delete current page | Ctrl+D |
| Save | Ctrl+S |
| Save as | Ctrl+Shift+S |
| Open document | Ctrl+O |
| New document | Ctrl+Shift+N |
| Export (PDF/PNG) | Ctrl+E |
| Volume up / down | Ctrl++ / Ctrl+Shift+- |
| Show key reference | F1 |
| Quit | Esc / Ctrl+Q |

Press **F1** at any time to see the full key reference with your current bindings.

### Customising bindings

Copy `keybindings.toml` to `~/.config/typewriter/keybindings.toml` and edit it. Your file is merged over the defaults — you only need to include the actions you want to change. Each action takes a list of key specs; use an empty list to disable an action entirely.

```toml
[bindings]
line_feed = ["enter", "kp_enter", "ctrl+j"]   # add Ctrl+J as an extra binding
toggle_help = []                                # disable F1
```

Key specs follow the pattern `[ctrl+][shift+][alt+]keyname`. Key names match pygame constants in lowercase: `return`, `backspace`, `f1`, `pageup`, `kp_enter`, `minus`, `plus`, etc.

---

## Document format

Documents are saved as `.typewriter` files — standard ZIP archives you can inspect with any ZIP tool:

```
document.typewriter
├── meta.json          version, timestamp, page count, current page index
├── strikes_000.json   complete keystroke log for page 1
├── strikes_001.json   complete keystroke log for page 2
├── page_000.png       rendered snapshot of page 1
├── page_001.png       rendered snapshot of page 2
└── ...
```

Each entry in a strike log records the character, position, ink alpha, and jitter offsets. When a document is loaded the pages are reconstructed by replaying the strike log — the snapshots are there for external tools and quick preview only.

Documents are written atomically (to a `.tmp` file, then renamed) so a crash during save cannot corrupt an existing file.

---

## Customising sounds

Each sound event maps to a WAV file in `assets/sounds/`. To use your own sounds, copy `sounds.toml` to `~/.config/typewriter/sounds.toml` and edit it. Only include the events you want to change; everything else falls back to the built-in defaults.

```toml
[sounds]
bell            = "/home/alice/samples/ding.wav"   # absolute path
key_strike      = "my_key.wav"                     # bare filename → assets/sounds/
carriage_return = "../sounds/cr.wav"               # relative to the config file
space           = ""                               # empty string = silence
```

The seven configurable events are: `key_strike`, `space`, `backspace`, `carriage_return`, `line_feed`, `bell`, `carriage_move`.

---

## Exporting

**Ctrl+E** exports the current document. If `reportlab` is installed a PDF is written to the `exports/` folder; otherwise a PNG composite of all pages is written instead.

PDF pages are letter-sized (8.5 × 11 inches). PNG output stacks all pages vertically with a small gap between them.

---

## Configuration

All visual and behavioural constants live in `config.py`. The most useful ones to adjust:

| Constant | Default | Effect |
|---|---|---|
| `FONT_SIZE` | 17 | Type size in points |
| `FONT_NAMES_PRIORITY` | Courier New, … | Ordered list of fonts to try |
| `LINE_HEIGHT_MULTIPLIER` | 1.55 | Line spacing relative to cap-height |
| `MARGIN_LEFT / RIGHT` | 80 px | Left and right margins |
| `MARGIN_TOP / BOTTOM` | 90 px | Top and bottom margins |
| `PAPER_ZOOM` | 1.0 | Scale factor (1.0 = full page fits on screen) |
| `BELL_CHARS_FROM_RIGHT` | 8 | How many characters before the bell rings |
| `INK_ALPHA_MIN / MAX` | 175 / 248 | Ink opacity variation range |
| `INK_JITTER_X` | 0.9 px | Horizontal type-bar wobble |
| `SOUND_VOLUME` | 0.72 | Default volume (0.0–1.0) |
| `AUTO_SAVE_SECONDS` | 45 | Auto-save interval |
| `TARGET_FPS` | 60 | Render frame rate |

---

## How it works

**Input** — `InputHandler` translates `pygame.KEYDOWN` events into typed `InputAction` values using the loaded key binding table. Printable characters that don't match any binding become `PRINT_CHAR` actions. Unrecognised Ctrl and Alt combinations are swallowed to prevent accidental key events.

**Page** — `Page` owns a `pygame.Surface` that acts as the permanent paper canvas. `stamp()` renders a glyph with the current ink alpha and jitter, records the call in the strike log, and returns. Nothing is ever erased.

**Carriage** — `Carriage` tracks the current position in pixel space alongside logical column and row numbers. It enforces the right margin, advances tab stops, and signals when the bell zone is entered (once per line).

**Renderer** — `Renderer` scales the paper surface to fit the screen and pans it so the carriage is always anchored at a fixed screen position (horizontal centre, 5 % above the bottom). Horizontal panning animates smoothly; the page snaps vertically on line feed.

**Sound** — `SoundManager` assigns each sound type a dedicated mixer channel so simultaneous sounds (e.g. bell overlapping a key strike) don't cut each other off. All WAV files are synthesised at startup by `generate_sounds.py` using basic waveform math — there are no bundled audio assets.

**Document** — `Document` wraps a path and a dirty flag. `save()` writes an atomic ZIP archive; `load()` reads one back and returns the raw data for `App` to reconstruct the page objects. A legacy directory format (earlier development) can still be loaded.

---

## Project layout

```
typewriter/
├── main.py              Entry point, argument parsing
├── app.py               Top-level coordinator, event loop
├── config.py            All tunable constants
├── page.py              Paper canvas (pygame.Surface + strike log)
├── carriage.py          Carriage position and mechanics
├── renderer.py          Scale, pan, and draw every frame
├── input_handler.py     KEYDOWN → InputAction dispatch
├── keybindings.py       TOML key-spec parser and binding resolver
├── keybindings.toml     Default key bindings
├── sound_manager.py     Audio playback with channel assignment
├── document.py          .typewriter ZIP format, save/load
├── modal.py             Text input, document browser, confirm dialogs
├── exporter.py          PNG and PDF export
├── generate_sounds.py   Synthesise WAV assets from scratch
├── setup.sh             One-shot install script
├── run.sh               Launch wrapper
├── requirements.txt     Python dependencies
└── assets/
    ├── sounds/          Generated WAV files (created by setup.sh)
    └── fonts/           Optional bundled fonts
```

---

## Licence

MIT
