"""System telemetry: CPU %, RAM %, battery %.

Polled only while the notch is peeking/expanded (2 s throttle) by the window,
so an idle notch costs nothing.
"""

from __future__ import annotations

import psutil


def snapshot() -> dict:
    try:
        cpu = psutil.cpu_percent(interval=None)
    except Exception:
        cpu = 0.0
    try:
        ram = psutil.virtual_memory().percent
    except Exception:
        ram = 0.0
    battery = None
    plugged = None
    try:
        bat = psutil.sensors_battery()
        if bat is not None:
            battery = bat.percent
            plugged = bool(bat.power_plugged)
    except Exception:
        battery = None
    return {"cpu": cpu, "ram": ram, "battery": battery, "plugged": plugged}
