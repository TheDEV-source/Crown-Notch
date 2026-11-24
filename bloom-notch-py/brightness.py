"""Screen brightness via the standard WMI brightness classes.

Works for internal laptop panels; external monitors use DDC/CI instead.
Out-of-process PowerShell call; CREATE_NO_WINDOW keeps it invisible.
"""

from __future__ import annotations

import subprocess

_CREATE_NO_WINDOW = 0x08000000


def _powershell(script: str) -> str | None:
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=_CREATE_NO_WINDOW,
        )
    except Exception:
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip()


def get() -> float | None:
    """Current brightness 0..=100, or None when unsupported."""
    value = _powershell(
        "(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness)"
        ".CurrentBrightness"
    )
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def set(v: float) -> None:
    v = max(0.0, min(100.0, v))
    _powershell(
        "(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods)"
        f".WmiSetBrightness(1, {v})"
    )
