"""Small JSON-backed item store for notes and reminders.

Items live next to settings.json in %APPDATA%\\CrownNotch.
"""

from __future__ import annotations

import json
import os
import uuid

from config import APP_DIR


def _path(name: str) -> str:
    return os.path.join(APP_DIR, f"{name}.json")


def uid() -> str:
    return uuid.uuid4().hex[:8]


def load_items(name: str) -> list:
    try:
        with open(_path(name), "r", encoding="utf-8") as fh:
            items = json.load(fh)
        return items if isinstance(items, list) else []
    except Exception:
        return []


def save_items(name: str, items: list) -> None:
    try:
        os.makedirs(APP_DIR, exist_ok=True)
        with open(_path(name), "w", encoding="utf-8") as fh:
            json.dump(items, fh, indent=2, ensure_ascii=False)
    except Exception:
        pass
