"""Windows master volume + mute via pycaw (Core Audio IAudioEndpointVolume).

Also hosts the ``com_apartment`` helper: a per-thread COM apartment that is
initialized once and kept alive for the thread's lifetime (comtypes 1.5+
removed the old context-manager ``CoInitialize`` idiom).
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from ctypes import POINTER, cast

import comtypes
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

_local = threading.local()


@contextmanager
def com_apartment():
    """Initialize COM on the calling thread once; keep it alive afterwards.

    CoInitialize is per-thread: worker threads and the GUI thread each get
    their own apartment. We never CoUninitialize — long-lived threads keep
    the apartment until process exit.
    """
    if not getattr(_local, "inited", False):
        try:
            comtypes.CoInitialize()
            _local.inited = True
        except Exception:
            pass  # already initialized (S_FALSE still counts as usable)
    yield


def _endpoint():
    """IAudioEndpointVolume of the default render device.

    Newer pycaw wraps devices in AudioDevice with a ready EndpointVolume;
    older versions return the raw IMMDevice."""
    device = AudioUtilities.GetSpeakers()
    endpoint = getattr(device, "EndpointVolume", None)
    if endpoint is not None:
        return endpoint
    raw = getattr(device, "_dev", device)
    interface = raw.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))


def get_volume() -> float:
    """Master volume as 0.0..=1.0"""
    with com_apartment():
        return _endpoint().GetMasterVolumeLevelScalar()


def set_volume(v: float) -> None:
    with com_apartment():
        _endpoint().SetMasterVolumeLevelScalar(min(1.0, max(0.0, v)), None)


def get_mute() -> bool:
    with com_apartment():
        return bool(_endpoint().GetMute())


def set_mute(muted: bool) -> None:
    with com_apartment():
        _endpoint().SetMute(1 if muted else 0, None)
