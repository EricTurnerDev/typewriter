"""
keybindings.py — Load and resolve configurable key bindings.

Default bindings are read from keybindings.toml (next to this file).
A user config at ~/.config/typewriter/keybindings.toml is merged on top:
any action listed there replaces the default for that action only.

Key spec format
---------------
  [modifier+[modifier+]]key_name

  Modifiers (combinable with +):  ctrl  shift  alt
  Key names: a-z, 0-9, f1-f12, enter, tab, backspace, space, escape,
             up, down, left, right, home, end, pageup, pagedown,
             plus (=), minus (-), equals, kp_plus, kp_minus, kp_enter

  Examples:  "ctrl+r"   "ctrl+shift+-"   "shift+tab"   "f1"
"""

from __future__ import annotations

import os
import sys

import pygame


# ---------------------------------------------------------------------------
# Key name → pygame constant
# ---------------------------------------------------------------------------

def _build_key_map() -> dict[str, int]:
    m: dict[str, int] = {
        "escape":    pygame.K_ESCAPE,
        "enter":     pygame.K_RETURN,
        "tab":       pygame.K_TAB,
        "backspace": pygame.K_BACKSPACE,
        "space":     pygame.K_SPACE,
        "up":        pygame.K_UP,
        "down":      pygame.K_DOWN,
        "left":      pygame.K_LEFT,
        "right":     pygame.K_RIGHT,
        "home":      pygame.K_HOME,
        "end":       pygame.K_END,
        "pageup":    pygame.K_PAGEUP,
        "pagedown":  pygame.K_PAGEDOWN,
        "plus":      pygame.K_PLUS,
        "+":         pygame.K_PLUS,
        "minus":     pygame.K_MINUS,
        "-":         pygame.K_MINUS,
        "equals":    pygame.K_EQUALS,
        "=":         pygame.K_EQUALS,
        "kp_plus":   pygame.K_KP_PLUS,
        "kp_minus":  pygame.K_KP_MINUS,
        "kp_enter":  pygame.K_KP_ENTER,
    }
    for c in "abcdefghijklmnopqrstuvwxyz":
        m[c] = getattr(pygame, f"K_{c}")
    for n in range(10):
        m[str(n)] = getattr(pygame, f"K_{n}")
    for n in range(1, 13):
        m[f"f{n}"] = getattr(pygame, f"K_F{n}")
    return m


# Built once after pygame is imported (constants are available without init()).
_KEY_MAP: dict[str, int] = _build_key_map()

# Reverse map: pygame constant → canonical name (first match wins).
_KEY_NAME_PRETTY: dict[int, str] = {
    pygame.K_ESCAPE:    "Esc",
    pygame.K_RETURN:    "Enter",
    pygame.K_TAB:       "Tab",
    pygame.K_BACKSPACE: "Backspace",
    pygame.K_SPACE:     "Space",
    pygame.K_UP:        "↑",
    pygame.K_DOWN:      "↓",
    pygame.K_LEFT:      "←",
    pygame.K_RIGHT:     "→",
    pygame.K_HOME:      "Home",
    pygame.K_END:       "End",
    pygame.K_PAGEUP:    "PgUp",
    pygame.K_PAGEDOWN:  "PgDn",
    pygame.K_PLUS:      "+",
    pygame.K_MINUS:     "-",
    pygame.K_EQUALS:    "=",
    pygame.K_KP_PLUS:   "Num+",
    pygame.K_KP_MINUS:  "Num-",
    pygame.K_KP_ENTER:  "Num Enter",
}
for _c in "abcdefghijklmnopqrstuvwxyz":
    _KEY_NAME_PRETTY.setdefault(getattr(pygame, f"K_{_c}"), _c.upper())
for _n in range(10):
    _KEY_NAME_PRETTY.setdefault(getattr(pygame, f"K_{_n}"), str(_n))
for _n in range(1, 13):
    _KEY_NAME_PRETTY.setdefault(getattr(pygame, f"K_F{_n}"), f"F{_n}")


# ---------------------------------------------------------------------------
# Binding tuple type
# ---------------------------------------------------------------------------

# (pygame_key_constant, ctrl, shift, alt)
BindingKey = tuple[int, bool, bool, bool]


def parse_spec(spec: str) -> BindingKey:
    """Parse a key-spec string such as 'ctrl+shift+-' into a BindingKey."""
    parts = [p.strip().lower() for p in spec.split("+")]
    ctrl = shift = alt = False
    key_name: str | None = None

    for part in parts:
        if part == "ctrl":
            ctrl = True
        elif part == "shift":
            shift = True
        elif part == "alt":
            alt = True
        elif part:
            key_name = part

    if key_name is None:
        raise ValueError(f"Key spec has no key name: {spec!r}")
    if key_name not in _KEY_MAP:
        raise ValueError(f"Unknown key name {key_name!r} in spec {spec!r}")

    return (_KEY_MAP[key_name], ctrl, shift, alt)


def binding_key_to_str(bk: BindingKey) -> str:
    """Convert a BindingKey back to a human-readable label like 'Ctrl+Shift+-'."""
    key_const, ctrl, shift, alt = bk
    name = _KEY_NAME_PRETTY.get(key_const, f"key({key_const})")
    parts: list[str] = []
    if ctrl:  parts.append("Ctrl")
    if shift: parts.append("Shift")
    if alt:   parts.append("Alt")
    parts.append(name)
    return "+".join(parts)


# ---------------------------------------------------------------------------
# TOML loader
# ---------------------------------------------------------------------------

_DEFAULT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keybindings.toml")
_USER_PATH    = os.path.expanduser("~/.config/typewriter/keybindings.toml")


def _load_toml(path: str) -> dict:
    """Load a TOML file; returns {} if missing or unreadable."""
    if not os.path.isfile(path):
        return {}
    try:
        if sys.version_info >= (3, 11):
            import tomllib
            with open(path, "rb") as f:
                return tomllib.load(f)
        else:
            import tomli  # type: ignore[import]
            with open(path, "rb") as f:
                return tomli.load(f)
    except Exception as exc:
        print(f"[keybindings] Could not load {path}: {exc}")
        return {}


# ---------------------------------------------------------------------------
# Keybindings class
# ---------------------------------------------------------------------------

class Keybindings:
    """
    Resolved keybinding table.

    Maps BindingKey → action name and action name → list[BindingKey].
    Multiple specs can map to the same action; an action can have zero specs.
    """

    def __init__(self):
        self._by_action: dict[str, list[BindingKey]] = {}
        self._lookup:    dict[BindingKey, str]        = {}

    @classmethod
    def load(cls) -> "Keybindings":
        """Load defaults then user overrides; return a ready Keybindings instance."""
        defaults  = _load_toml(_DEFAULT_PATH).get("bindings", {})
        overrides = _load_toml(_USER_PATH).get("bindings", {})
        merged    = {**defaults, **overrides}

        kb = cls()
        for action, specs in merged.items():
            if not isinstance(specs, list):
                specs = [specs]
            keys: list[BindingKey] = []
            for spec in specs:
                try:
                    bk = parse_spec(spec)
                except ValueError as exc:
                    print(f"[keybindings] {exc} — skipped")
                    continue
                if bk in kb._lookup:
                    existing = kb._lookup[bk]
                    print(
                        f"[keybindings] Conflict: {spec!r} is already bound to "
                        f"{existing!r}; overriding with {action!r}"
                    )
                kb._lookup[bk] = action
                keys.append(bk)
            kb._by_action[action] = keys

        return kb

    def action_for(self, key: int, ctrl: bool, shift: bool, alt: bool = False) -> str | None:
        """Return the action name for a key event, or None if unbound."""
        return self._lookup.get((key, ctrl, shift, alt))

    def labels_for(self, action: str) -> list[str]:
        """Return human-readable labels for all bindings of an action."""
        return [binding_key_to_str(bk) for bk in self._by_action.get(action, [])]
