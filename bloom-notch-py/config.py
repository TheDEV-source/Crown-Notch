"""Persistent settings for Crown Notch.

Stored as JSON in %APPDATA%\\CrownNotch\\settings.json; first-run detection is
simply ``onboarded: false`` in the loaded config.
"""

from __future__ import annotations

import json
import os
import sys

APP_DIR = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")), "CrownNotch"
)
CONFIG_PATH = os.path.join(APP_DIR, "settings.json")
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "CrownNotch"

DEFAULTS: dict = {
    "onboarded": False,       # first-run onboarding shown yet?
    "start_with_windows": False,
    "hover_peek": True,       # hover expands to the compact peek
    "fullscreen_hide": True,  # tuck away during fullscreen apps
    "clock_24h": False,       # idle pill clock format (flyout style: 09:38 a.m.)
    "compact": True,          # smaller notch sizes (default)
    "liquid_glass": True,     # Windows 11 acrylic backdrop (DWM)
}


def load() -> dict:
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            stored = json.load(fh)
        if isinstance(stored, dict):
            cfg.update({k: v for k, v in stored.items() if k in DEFAULTS})
    except Exception:
        pass
    return cfg


def save(cfg: dict) -> None:
    try:
        os.makedirs(APP_DIR, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump({k: cfg.get(k, DEFAULTS[k]) for k in DEFAULTS}, fh, indent=2)
    except Exception:
        pass


def set_start_with_windows(enabled: bool) -> str | None:
    """Add/remove the HKCU Run entry. Returns an error string on failure."""
    try:
        import winreg

        exe = sys.executable
        if exe.lower().endswith("python.exe"):
            pythonw = os.path.join(os.path.dirname(exe), "pythonw.exe")
            if os.path.exists(pythonw):
                exe = pythonw
        main_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
        target = f'"{exe}" "{main_py}"'
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            if enabled:
                winreg.SetValueEx(key, RUN_NAME, 0, winreg.REG_SZ, target)
            else:
                try:
                    winreg.DeleteValue(key, RUN_NAME)
                except FileNotFoundError:
                    pass
        return None
    except Exception as exc:
        return str(exc)
