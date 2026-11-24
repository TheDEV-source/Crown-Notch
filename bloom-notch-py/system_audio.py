"""Microphone-in-use and audio-device monitoring via Core Audio.

- Mic in use: polls the peak meter (``IAudioMeterInformation``) of the default
  capture device — a non-zero peak means something is recording.
- Device monitoring: tracks the set of active render endpoints and the default
  render endpoint; a change means headphones / speakers were plugged,
  switched or removed.

Runs on its own thread and reports through a Qt signal. If pycaw cannot be
initialized the worker exits and the indicators simply stay off.
"""

from __future__ import annotations

from ctypes import POINTER, cast

import comtypes
from audio import com_apartment
from pycaw.constants import DEVICE_STATE, EDataFlow, ERole
from PySide6.QtCore import QThread, Signal

MIC_ON_THRESHOLD = 0.02    # peak level that counts as "microphone in use"
MIC_OFF_THRESHOLD = 0.005  # hysteresis to avoid flicker around the threshold
POLL_MS = 700


def _create_enumerator():
    """Caller must have called comtypes.CoInitialize() on this thread."""
    from pycaw.pycaw import AudioUtilities, IMMDeviceEnumerator

    try:
        return AudioUtilities.GetDeviceEnumerator()
    except Exception:
        # fall back to a direct CoCreateInstance of MMDeviceEnumerator
        return comtypes.CoCreateInstance(
            "{BCDE0395-E52F-467C-8E3D-C4579291692E}",
            interface=IMMDeviceEnumerator,
        )


def _meter_peak(enumerator) -> float | None:
    """Peak level 0..1 of the default microphone, or None if unavailable."""
    try:
        from pycaw.pycaw import IAudioMeterInformation

        device = enumerator.GetDefaultAudioEndpoint(
            EDataFlow.eCapture, ERole.eConsole
        )
        obj = device.Activate(IAudioMeterInformation._iid_, comtypes.CLSCTX_ALL, None)
        return cast(obj, POINTER(IAudioMeterInformation)).GetPeakValue()
    except Exception:
        return None


def _render_ids(enumerator) -> list:
    try:
        collection = enumerator.EnumAudioEndpoints(
            EDataFlow.eRender, DEVICE_STATE.ACTIVE
        )
        count = collection.GetCount()
        return [collection.Item(i).GetId() for i in range(count)]
    except Exception:
        return []


def _default_render_id(enumerator):
    try:
        return enumerator.GetDefaultAudioEndpoint(
            EDataFlow.eRender, ERole.eConsole
        ).GetId()
    except Exception:
        return None


class SystemAudioWorker(QThread):
    status = Signal(dict)

    def __init__(self) -> None:
        super().__init__()
        self._mic_on = False

    def run(self) -> None:
        try:
            with com_apartment():
                _create_enumerator()  # fail fast if pycaw is unusable
        except Exception as exc:
            print(f"[notch] audio device monitoring unavailable: {exc}")
            return

        while not self.isInterruptionRequested():
            snapshot = {"mic": self._mic_on, "devices": [], "default_id": None}
            try:
                with com_apartment():
                    enum = _create_enumerator()
                    peak = _meter_peak(enum)
                    snapshot["devices"] = _render_ids(enum)
                    snapshot["default_id"] = _default_render_id(enum)
                if peak is not None:
                    if self._mic_on:
                        self._mic_on = peak > MIC_OFF_THRESHOLD
                    else:
                        self._mic_on = peak > MIC_ON_THRESHOLD
                snapshot["mic"] = self._mic_on
            except Exception:
                pass
            self.status.emit(snapshot)
            self.msleep(POLL_MS)
