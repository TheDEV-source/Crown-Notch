"""Windows SMTC media worker.

Polls ``GlobalSystemMediaTransportControlsSessionManager`` for live metadata
(title / artist / album / album-art bytes / position / duration) from any
system media session (Spotify, browsers, players) and executes playback
commands: play/pause, next/previous, and best-effort seek via rewind /
fast-forward (the public SMTC API does not allow third-party apps to set
playback position directly).

Runs on its own thread with an asyncio loop; snapshots are delivered to the
UI thread through a Qt signal. If ``winsdk`` is not installed the worker
exits quietly and the UI falls back to telemetry-only mode.
"""

from __future__ import annotations

import asyncio
import queue

from PySide6.QtCore import QThread, Signal

EMPTY = {
    "available": False,
    "title": "",
    "artist": "",
    "album": "",
    "is_playing": False,
    "position_ms": 0,
    "duration_ms": 0,
    "art": None,
}

POLL_INTERVAL = 0.4  # seconds


class MediaWorker(QThread):
    media_changed = Signal(dict)

    def __init__(self) -> None:
        super().__init__()
        self._commands: "queue.Queue[str]" = queue.Queue()
        self.available = False

    # ---- public API (thread-safe, consumed by the worker loop) ----
    def play_pause(self) -> None:
        self._commands.put("toggle")

    def next(self) -> None:
        self._commands.put("next")

    def prev(self) -> None:
        self._commands.put("prev")

    def rewind(self) -> None:
        self._commands.put("rewind")

    def fast_forward(self) -> None:
        self._commands.put("ffwd")

    # ---- worker ----
    def run(self) -> None:
        try:
            from winsdk.windows.media.control import (
                GlobalSystemMediaTransportControlsSessionManager as SM,
            )
            from winsdk.windows.media.control import (
                GlobalSystemMediaTransportControlsSessionPlaybackStatus as PS,
            )
        except Exception as exc:  # winsdk missing / unsupported Python
            print(f"[notch] winsdk unavailable — media controls disabled: {exc}")
            return
        try:
            asyncio.run(self._main(SM, PS))
        except Exception as exc:
            print(f"[notch] media worker stopped: {exc}")

    async def _main(self, SM, PS) -> None:
        playing_val = _playing_value(PS)
        mgr = await SM.request_async()
        self.available = True
        cache_key = None
        art_cache = None

        while not self.isInterruptionRequested():
            await self._drain_commands(mgr, playing_val)
            try:
                payload, cache_key, art_cache = await self._snapshot(
                    mgr, playing_val, cache_key, art_cache
                )
                self.media_changed.emit(payload)
            except Exception:
                self.media_changed.emit(dict(EMPTY))
            await asyncio.sleep(POLL_INTERVAL)

    async def _drain_commands(self, mgr, playing_val) -> None:
        while True:
            try:
                cmd = self._commands.get_nowait()
            except queue.Empty:
                return
            try:
                session = await self._pick_session(mgr, playing_val)
                if session is None:
                    continue
                if cmd == "toggle":
                    info = session.get_playback_info()
                    if info.playback_status == playing_val:
                        await session.try_pause_async()
                    else:
                        await session.try_play_async()
                elif cmd == "next":
                    await session.try_skip_next_async()
                elif cmd == "prev":
                    await session.try_skip_previous_async()
                elif cmd == "rewind":
                    await session.try_rewind_async()
                elif cmd == "ffwd":
                    await session.try_fast_forward_async()
            except Exception:
                pass  # best effort; the app the controls belong to may refuse

    async def _pick_session(self, mgr, playing_val):
        """Prefer the playing session; fall back to the first available."""
        sessions = mgr.get_sessions()  # sync in winsdk 1.0.0b10
        first = None
        for session in sessions:
            if first is None:
                first = session
            try:
                info = session.get_playback_info()  # sync in winsdk 1.0.0b10
                if info.playback_status == playing_val:
                    return session
            except Exception:
                continue
        return first

    async def _snapshot(self, mgr, playing_val, cache_key, art_cache):
        session = await self._pick_session(mgr, playing_val)
        if session is None:
            return dict(EMPTY), cache_key, art_cache

        props = await session.try_get_media_properties_async()
        timeline = session.get_timeline_properties()  # sync in winsdk 1.0.0b10
        info = session.get_playback_info()

        title = props.title or ""
        artist = props.artist or ""
        album = props.album_title or ""
        playing = info.playback_status == playing_val
        position_ms = max(0, int(timeline.position.total_seconds() * 1000))
        duration_ms = max(0, int(timeline.end_time.total_seconds() * 1000))

        key = (title, artist, album)
        art = art_cache
        if key != cache_key:
            art = await self._read_art(props)
            cache_key = key

        payload = {
            "available": True,
            "title": title,
            "artist": artist,
            "album": album,
            "is_playing": playing,
            "position_ms": position_ms,
            "duration_ms": duration_ms,
            "art": art,
        }
        return payload, cache_key, art

    async def _read_art(self, props):
        """Album art as raw image bytes (PNG/JPEG), or None."""
        try:
            from winsdk.windows.storage.streams import Buffer, InputStreamOptions

            thumb = props.thumbnail
            if thumb is None:
                return None
            stream = await thumb.open_read_async()
            size = int(min(stream.size, 4_000_000))
            if size == 0:
                return None
            try:
                buffer = Buffer.create(size)
            except Exception:
                buffer = Buffer(size)
            result = await stream.read_async(buffer, size, InputStreamOptions.NONE)
            raw = None
            for attr in ("content", "data", "value"):
                obj = getattr(result, attr, None)
                if obj is not None:
                    raw = bytes(obj)
                    break
            if raw is None:
                raw = bytes(result)
            return raw or None
        except Exception:
            return None


def _playing_value(PS):
    """winsdk/pywinrt enum member name differs across versions."""
    return getattr(PS, "PLAYING", getattr(PS, "Playing", None))
