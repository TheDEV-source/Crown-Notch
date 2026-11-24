"""Crown Notch — Python/PySide6 edition.

A Windows 11 dynamic notch: Bloom-style spring morphs, a paged command
center (media / controls / utility) with slide transitions, SMTC media
controls with best-effort seek, master volume/mute, brightness, keep-awake,
a 25:00 focus timer, live telemetry, a drag-and-drop file shelf, and live
microphone / audio-device indicators.

Native behavior: frameless, transparent, always-on-top at top-center of the
primary display; clicks pass through everywhere except the notch pill; the
notch tucks off-screen during fullscreen apps. Tray icon, settings and
first-run onboarding included.
"""

from __future__ import annotations

import ctypes
import os
import re
import threading
from ctypes import wintypes
from datetime import datetime, timedelta

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRect,
    QTimer,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QIcon,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPixmap,
    QPen,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSlider,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

import brightness
import config
import data
import sysinfo
from popups import NoteEditor
from widgets import (
    BatteryBar,
    ElidedLabel,
    Equalizer,
    Glyph,
    PageDots,
    SlideStack,
    icon_family,
    icon_font,
)

WIN_H = 220  # reference height for the fullscreen tuck
SIZES_SETS = {
    "compact": {"idle": (152, 26), "peek": (224, 36), "expanded": (376, 158)},
    "comfort": {"idle": (176, 30), "peek": (252, 42), "expanded": (412, 186)},
}

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x20
GWL_STYLE = -16
WS_MAXIMIZE = 0x01000000
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002
QUNS_FULLSCREEN = {3, 4}  # RUNNING_DIRECT3D_FULL_SCREEN, PRESENTATION_MODE

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notch.log")

# --------------------------------------------------------------------------
# design tokens — native-feeling: one muted accent, hairline borders,
# monochrome status, no emoji, Segoe Fluent Icons glyphs.
# --------------------------------------------------------------------------
GLASS = "rgba(16, 16, 20, 0.90)"
HAIRLINE = "rgba(255, 255, 255, 0.09)"
SURFACE = "rgba(255, 255, 255, 0.055)"
SURFACE_HOVER = "rgba(255, 255, 255, 0.11)"
TEXT = "#e6e6ea"
DIM = "#9b9ba4"
FAINT = "#63636d"
ACCENT = "#e0b273"          # crown gold
ACCENT_SOFT = "rgba(224, 178, 115, 0.16)"
ACCENT_BORDER = "rgba(224, 178, 115, 0.38)"

EMPTY_MEDIA = {
    "available": False,
    "title": "",
    "artist": "",
    "album": "",
    "is_playing": False,
    "position_ms": 0,
    "duration_ms": 0,
    "art": None,
}

FRAME_CSS_TEMPLATE = """
#notchFrame {{
    background: rgba(16, 16, 20, {alpha});
    border: 1px solid {HAIRLINE};
    border-top: none;
    border-top-left-radius: 0px;
    border-top-right-radius: 0px;
    border-bottom-left-radius: 13px;
    border-bottom-right-radius: 13px;
}}
QLabel {{ color: {TEXT}; }}
"""


def _frame_css(alpha: float) -> str:
    return FRAME_CSS_TEMPLATE.format(alpha=alpha, HAIRLINE=HAIRLINE, TEXT=TEXT)

ICON_BTN_CSS = f"""
QPushButton {{ background: transparent; border: none; border-radius: 5px;
               color: #d6d6dc; }}
QPushButton:hover {{ background: {SURFACE_HOVER}; }}
"""

TEXT_BTN_CSS = f"""
QPushButton {{ background: {SURFACE}; border: none; border-radius: 5px;
               color: #cfcfd6; font-size: 9.5px; padding: 3px 9px; }}
QPushButton:hover {{ background: {SURFACE_HOVER}; }}
"""

TOGGLE_ON_CSS = f"""
QPushButton {{ background: {ACCENT_SOFT}; border: 1px solid {ACCENT_BORDER};
               border-radius: 5px; color: {ACCENT}; font-size: 9.5px;
               font-weight: 600; padding: 2px 8px; }}
"""

CHIP_CSS = f"""
QPushButton {{ background: {SURFACE}; border: none; border-radius: 5px;
               color: #c8c8cf; font-size: 9px; padding: 2px 8px; }}
QPushButton:hover {{ background: {SURFACE_HOVER}; }}
"""

INPUT_CSS = f"""
QLineEdit {{ background: {SURFACE}; border: 1px solid {HAIRLINE};
             border-radius: 5px; color: {TEXT}; font-size: 9.5px;
             padding: 3px 8px;
             selection-background-color: rgba(224,178,115,0.40); }}
"""

LIST_CSS = f"""
QListWidget {{ background: transparent; border: none; color: #cfcfd6;
               font-size: 9.5px; outline: none; }}
QListWidget::item {{ padding: 3px 6px; border-radius: 4px; }}
QListWidget::item:hover {{ background: rgba(255,255,255,0.07); }}
QListWidget::item:selected {{ background: rgba(224,178,115,0.16);
                              color: #ead9b8; }}
"""

SLIDER_CSS = f"""
QSlider {{ background: transparent; }}
QSlider::groove:horizontal {{ height: 3px; background: rgba(255,255,255,0.13);
                              border-radius: 1px; }}
QSlider::sub-page:horizontal {{ background: rgba(224,178,115,0.70);
                                border-radius: 1px; }}
QSlider::handle:horizontal {{ width: 9px; height: 9px; margin: -3px 0;
                              border-radius: 4px; background: #e8dcc4; }}
QSlider:disabled::sub-page:horizontal {{ background: rgba(255,255,255,0.15); }}
"""

TOAST_CSS = f"""
#toast {{
    background: {GLASS};
    border: 1px solid {HAIRLINE};
    border-radius: 8px;
}}
#toast QLabel {{ color: {TEXT}; font-size: 9.5px; }}
"""


def _log(msg: str) -> None:
    try:
        with open(LOG_PATH, "a", encoding="utf-8", errors="replace") as fh:
            fh.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {msg}\n")
    except Exception:
        pass


# --------------------------------------------------------------------------
# native window helpers
# --------------------------------------------------------------------------
def parse_when(raw: str) -> datetime | None:
    """Parse a reminder time: '18:30' (today/tomorrow), '9:00pm', '25m',
    '2h', '3d', or '2026-01-05 09:00'. Returns None when unparseable."""
    s = (raw or "").strip().lower()
    if not s:
        return None
    now = datetime.now()
    m = re.fullmatch(
        r"(\d+)\s*(s|sec|secs|seconds?|m|min|mins|minutes?|h|hr|hrs|hours?|d|days?)",
        s,
    )
    if m:
        amount = int(m.group(1))
        unit = m.group(2)[0]
        seconds = {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
        return now + timedelta(seconds=amount * seconds)
    m = re.fullmatch(r"(\d{1,2})[:.](\d{2})\s*(am|pm)?", s)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2))
        ampm = m.group(3)
        if ampm == "pm" and hour < 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        try:
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        except ValueError:
            return None
        if target <= now:
            target += timedelta(days=1)  # tomorrow
        return target
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M")
    except ValueError:
        return None


class _MonitorInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


class _DwmMargins(ctypes.Structure):
    _fields_ = [
        ("cxLeftWidth", ctypes.c_int),
        ("cxRightWidth", ctypes.c_int),
        ("cyTopHeight", ctypes.c_int),
        ("cyBottomHeight", ctypes.c_int),
    ]


class _AccentPolicy(ctypes.Structure):
    _fields_ = [
        ("AccentState", ctypes.c_int),
        ("AccentFlags", ctypes.c_int),
        ("GradientColor", ctypes.c_uint),
        ("AnimationId", ctypes.c_int),
    ]


class _WindowCompositionAttribData(ctypes.Structure):
    _fields_ = [
        ("Attribute", ctypes.c_int),
        ("Data", ctypes.c_void_p),
        ("SizeOfData", ctypes.c_size_t),
    ]


_ACCENT_DISABLED = 0
_ACCENT_ENABLE_ACRYLICBLURBEHIND = 4
_WCA_ACCENT_POLICY = 0x13


def _get_window_long(hwnd: int, index: int) -> int:
    user32 = ctypes.windll.user32
    if hasattr(user32, "GetWindowLongPtrW"):
        return user32.GetWindowLongPtrW(hwnd, index)
    return user32.GetWindowLongW(hwnd, index)


def _set_window_long(hwnd: int, index: int, value: int) -> None:
    user32 = ctypes.windll.user32
    fn = getattr(user32, "SetWindowLongPtrW", None)
    if fn:
        fn(hwnd, index, value)
    else:
        user32.SetWindowLongW(hwnd, index, value)


def _window_title(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    try:
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, 256)
    except Exception:
        return ""
    return buf.value


def _is_foreground_fullscreen(own_hwnd: int = 0) -> tuple[bool, str]:
    """Borderless fullscreen (window rect == monitor rect, no WS_MAXIMIZE)
    or exclusive/presentation mode via SHQueryUserNotificationState.
    Maximized windows are excluded — with an auto-hidden/replaced taskbar a
    maximized window's rect equals the monitor rect without being fullscreen.
    Returns (is_fullscreen, fg_title)."""
    try:
        user32 = ctypes.windll.user32
        fg = user32.GetForegroundWindow()
        if not fg or fg == own_hwnd:
            return False, ""
        title = _window_title(fg)
        if _get_window_long(fg, GWL_STYLE) & WS_MAXIMIZE:
            return False, title
        mon = user32.MonitorFromWindow(fg, 1)  # MONITOR_DEFAULTTOPRIMARY
        mi = _MonitorInfo()
        mi.cbSize = ctypes.sizeof(_MonitorInfo)
        if not user32.GetMonitorInfoW(mon, ctypes.byref(mi)):
            return False, title
        rect = wintypes.RECT()
        if not user32.GetWindowRect(fg, ctypes.byref(rect)):
            return False, title
        if (
            rect.left,
            rect.top,
            rect.right,
            rect.bottom,
        ) == (
            mi.rcMonitor.left,
            mi.rcMonitor.top,
            mi.rcMonitor.right,
            mi.rcMonitor.bottom,
        ):
            return True, title
        state = ctypes.c_int(0)
        if ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(state)) == 0:
            if state.value in QUNS_FULLSCREEN:
                return True, title
    except Exception:
        pass
    return False, ""


class NotchFrame(QFrame):
    """The morphing pill; forwards pointer events to the owning window."""

    def __init__(self, win: "NotchWindow") -> None:
        super().__init__(win)
        self.win = win
        self.setObjectName("notchFrame")
        self.setStyleSheet(_frame_css(0.90))
        self.setAcceptDrops(True)

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        # crown hairline: a gold gradient line fused to the top screen bezel
        p = QPainter(self)
        w = self.width()
        gradient = QLinearGradient(0, 0, w, 0)
        gradient.setColorAt(0.0, QColor(224, 178, 115, 0))
        gradient.setColorAt(0.25, QColor(224, 178, 115, 110))
        gradient.setColorAt(0.75, QColor(224, 178, 115, 110))
        gradient.setColorAt(1.0, QColor(224, 178, 115, 0))
        p.fillRect(0, 0, w, 1, gradient)

    def enterEvent(self, event) -> None:  # noqa: N802
        self.win.on_enter()

    def leaveEvent(self, event) -> None:  # noqa: N802
        self.win.on_leave()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.win.on_click()
        event.accept()

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        self.win.on_drag_enter(event)

    def dropEvent(self, event) -> None:  # noqa: N802
        self.win.on_drop(event)


class NotchWindow(QWidget):
    brightness_ready = Signal(object)  # float | None (from a worker thread)

    def __init__(self, media_worker, audio_worker, cfg: dict) -> None:
        super().__init__()
        self.media = media_worker
        self.audio_worker = audio_worker
        self.cfg = cfg
        self._sizes = SIZES_SETS["compact" if cfg.get("compact") else "comfort"]

        self.state = "idle"
        self.fullscreen_hidden = False
        self._transparent = False
        self._fs_strikes = 0
        self._glass = False
        self.awake = False
        self.pomodoro = {"remaining": 25 * 60, "running": False}
        self.shelf: list[str] = []
        self.media_payload = dict(EMPTY_MEDIA)
        self.telemetry = {"cpu": 0.0, "ram": 0.0, "battery": None}
        self.volume = 0.5
        self.muted = False
        self.brightness: float | None = None
        self._syncing_volume = False
        self._seeking = False
        self._base_pos = QPoint(0, 0)
        self.mic_active = False
        self._initial_default_id: str | None = None
        self._on_external_device = False
        self._device_toasted: set[str] = set()
        self.notes = data.load_items("notes")
        self.reminders = data.load_items("reminders")
        self._note_editor = None
        self._reminder_timer = QTimer(self)
        self._reminder_timer.timeout.connect(self._check_reminders)
        self._reminder_timer.start(15000)

        # ---- native window setup ----
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAcceptDrops(True)
        self.setWindowTitle("Crown Notch")

        # The window IS the notch: it resizes/moves with every morph so the
        # DWM acrylic backdrop never draws a bigger rectangle than the pill.
        self._screen_geo = QApplication.primaryScreen().geometry()
        w0, h0 = self._sizes["idle"]
        self._base_pos = QPoint(
            self._screen_geo.x() + (self._screen_geo.width() - w0) // 2,
            self._screen_geo.y(),
        )
        self.setGeometry(QRect(self._base_pos.x(), self._base_pos.y(), w0, h0))

        # ---- morphing frame (fills the window) ----
        self.frame = NotchFrame(self)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.frame)

        self.opacity = QGraphicsOpacityEffect(self.frame)
        self.opacity.setOpacity(1.0)
        self.frame.setGraphicsEffect(self.opacity)

        self.stack = QStackedWidget(self.frame)
        frame_lay = QVBoxLayout(self.frame)
        frame_lay.setContentsMargins(0, 0, 0, 0)
        frame_lay.addWidget(self.stack)
        self._build_idle_page()
        self._build_peek_page()
        self._build_expanded_page()

        self.brightness_ready.connect(self._on_brightness_ready)
        if self.media is not None:
            self.media.media_changed.connect(self.on_media)
        if self.audio_worker is not None:
            self.audio_worker.status.connect(self.on_audio_status)

        self._build_tray()
        self._toast = None
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self._hide_toast)

        # ---- timers ----
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.timeout.connect(self._hover_expand)
        self._grace_timer = QTimer(self)
        self._grace_timer.setSingleShot(True)
        self._grace_timer.timeout.connect(self._grace_collapse)

        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._update_clock()

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(2000)
        self._poll_timer.timeout.connect(self._poll_expanded)

        self._pomodoro_timer = QTimer(self)
        self._pomodoro_timer.timeout.connect(self._tick_pomodoro)
        self._pomodoro_timer.start(1000)

        self._awake_timer = QTimer(self)
        self._awake_timer.timeout.connect(self._keep_awake_refresh)

        self._brightness_debounce = QTimer(self)
        self._brightness_debounce.setSingleShot(True)
        self._brightness_debounce.setInterval(300)
        self._brightness_debounce.timeout.connect(self._apply_brightness)

        self._geom_anim: QPropertyAnimation | None = None
        self._fade_anim: QPropertyAnimation | None = None
        self._tuck_anim: QPropertyAnimation | None = None

        # heartbeat into notch.log so we can pinpoint when the process dies
        self._beat_timer = QTimer(self)
        self._beat_timer.timeout.connect(lambda: _log("alive"))
        self._beat_timer.start(5000)

    # ------------------------------------------------------------------
    # pages
    # ------------------------------------------------------------------
    def _build_idle_page(self) -> None:
        """Flyout-style idle pill: page dots · clock · status icon."""
        page = QWidget()
        lay = QHBoxLayout(page)
        lay.setContentsMargins(10, 0, 10, 0)
        lay.setSpacing(6)
        self.idle_dots = PageDots(5, mini=True)
        self.idle_dots.changed.connect(self._idle_dot_jump)
        self.idle_dots.setToolTip("Click to jump to a page")
        self.clock_label = QLabel("09:38 a.m.")
        self.clock_label.setStyleSheet(
            f"font-size: 10px; font-weight: 600; color: {TEXT};"
        )
        self.idle_dev = QLabel(Glyph.DEVICES)
        self.idle_dev.setFont(icon_font(9))
        self.idle_dev.setStyleSheet(f"color: {ACCENT};")
        self.idle_dev.hide()
        self.idle_mic = QLabel(Glyph.MIC)
        self.idle_mic.setFont(icon_font(9))
        self.idle_mic.setStyleSheet("color: #f87171;")
        self.idle_mic.hide()
        self.idle_stack = QStackedWidget()
        self.eq_idle = Equalizer()
        self.idle_battery = QLabel("")
        self.idle_battery.setStyleSheet(f"font-size: 8.5px; color: {DIM};")
        self.idle_stack.addWidget(self.eq_idle)
        self.idle_stack.addWidget(self.idle_battery)
        self.idle_stack.setCurrentIndex(1)
        lay.addWidget(self.idle_dots, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addStretch(1)
        lay.addWidget(self.clock_label)
        lay.addStretch(1)
        lay.addWidget(self.idle_dev)
        lay.addWidget(self.idle_mic)
        lay.addWidget(self.idle_stack, 0, Qt.AlignmentFlag.AlignVCenter)
        self.stack.addWidget(page)

    def _idle_dot_jump(self, index: int) -> None:
        self.set_state("expanded")
        self.pages.setCurrentIndex(index)

    def _build_peek_page(self) -> None:
        page = QWidget()
        outer = QHBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        self.peek_stack = QStackedWidget(page)
        outer.addWidget(self.peek_stack)

        media_page = QWidget()
        lay = QHBoxLayout(media_page)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(7)
        self.peek_art = QLabel()
        self.peek_art.setFixedSize(22, 22)
        self.peek_title = ElidedLabel("Nothing playing", TEXT, 9, bold=True)
        self.peek_artist = ElidedLabel("", DIM, 8)
        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        col.addWidget(self.peek_title)
        col.addWidget(self.peek_artist)
        self.eq_peek = Equalizer()
        self.peek_dev = QLabel(Glyph.DEVICES)
        self.peek_dev.setFont(icon_font(9))
        self.peek_dev.setStyleSheet(f"color: {ACCENT};")
        self.peek_dev.hide()
        self.peek_mic = QLabel(Glyph.MIC)
        self.peek_mic.setFont(icon_font(9))
        self.peek_mic.setStyleSheet("color: #f87171;")
        self.peek_mic.hide()
        lay.addWidget(self.peek_art)
        lay.addLayout(col, 1)
        lay.addWidget(self.eq_peek, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self.peek_dev)
        lay.addWidget(self.peek_mic)
        self.peek_stack.addWidget(media_page)

        telemetry_page = QWidget()
        tlay = QHBoxLayout(telemetry_page)
        tlay.setContentsMargins(12, 0, 12, 0)
        self.peek_telemetry = QLabel("")
        self.peek_telemetry.setStyleSheet(f"font-size: 9px; color: {DIM};")
        tlay.addWidget(self.peek_telemetry)
        self.peek_stack.addWidget(telemetry_page)
        self.peek_stack.setCurrentIndex(1)
        self.stack.addWidget(page)

    def _build_expanded_page(self) -> None:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(10, 8, 10, 6)
        lay.setSpacing(4)

        self.pages = SlideStack(page)
        self.pages.currentChanged.connect(self._on_page_changed)
        self.pages.addPage(self._build_media_page())
        self.pages.addPage(self._build_controls_page())
        self.pages.addPage(self._build_utility_page())
        self.pages.addPage(self._build_notes_page())
        self.pages.addPage(self._build_reminders_page())
        lay.addWidget(self.pages, 1)

        dots_row = QHBoxLayout()
        dots_row.setSpacing(10)
        dots_row.addStretch(1)
        self.page_label = QLabel("")
        self.page_label.setStyleSheet(
            f"font-size: 9px; color: {FAINT}; letter-spacing: 3px;"
        )
        dots_row.addWidget(self.page_label)
        self.dots = PageDots(self.pages.count())
        self.dots.changed.connect(self.pages.setCurrentIndex)
        dots_row.addWidget(self.dots)
        dots_row.addStretch(1)
        lay.addLayout(dots_row)
        self._on_page_changed(0)
        self.stack.addWidget(page)

    def _build_media_page(self) -> QWidget:
        """Windows 11 media-flyout layout: big art, title/artist, centered
        transport, full-width seek, ··· button for the other pages."""
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(12, 10, 12, 9)
        lay.setSpacing(7)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.x_art = QLabel()
        self.x_art.setFixedSize(78, 78)
        self.x_art.setStyleSheet(
            "border: 1px solid rgba(255,255,255,0.09); border-radius: 7px;"
        )
        mid = QVBoxLayout()
        mid.setSpacing(3)
        head = QHBoxLayout()
        self.x_title = ElidedLabel("Nothing playing", TEXT, 12, bold=True)
        self.more_btn = self._glyph_button(
            Glyph.MORE, "Controls, notes & reminders", self._more_jump, 10
        )
        self.more_btn.setFixedSize(22, 20)
        head.addWidget(self.x_title, 1)
        head.addWidget(self.more_btn)
        self.x_artist = ElidedLabel("Open a media app to control it here", DIM, 10)
        mid.addLayout(head)
        mid.addWidget(self.x_artist)
        mid.addStretch(1)
        transport = QHBoxLayout()
        transport.setSpacing(8)
        transport.addStretch(1)
        self.btn_prev = self._glyph_button(Glyph.PREV_TRACK, "Previous", self._cmd_prev, 12)
        self.btn_prev.setFixedSize(30, 26)
        self.btn_play = self._glyph_button(Glyph.PLAY, "Play / Pause", self._cmd_play, 14)
        self.btn_play.setFixedSize(38, 28)
        self.btn_next = self._glyph_button(Glyph.NEXT_TRACK, "Next", self._cmd_next, 12)
        self.btn_next.setFixedSize(30, 26)
        transport.addWidget(self.btn_prev)
        transport.addWidget(self.btn_play)
        transport.addWidget(self.btn_next)
        transport.addStretch(1)
        mid.addLayout(transport)
        row.addWidget(self.x_art, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addLayout(mid, 1)
        lay.addLayout(row, 1)

        self.seek = QSlider(Qt.Orientation.Horizontal)
        self.seek.setStyleSheet(SLIDER_CSS)
        self.seek.setRange(0, 1)
        self.seek.setFixedHeight(14)
        self.seek.setToolTip("Seek (best-effort via system rewind / fast-forward)")
        self.seek.sliderPressed.connect(lambda: setattr(self, "_seeking", True))
        self.seek.sliderReleased.connect(self._on_seek_released)
        lay.addWidget(self.seek)
        return page

    def _more_jump(self) -> None:
        self.pages.setCurrentIndex(1)

    def _build_controls_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(4, 3, 4, 2)
        lay.setSpacing(7)

        vol_row = QHBoxLayout()
        vol_row.setSpacing(7)
        self.mute_btn = self._glyph_button(Glyph.VOLUME, "Mute / Unmute", self._toggle_mute, 10)
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setStyleSheet(SLIDER_CSS)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setToolTip("Master volume")
        self.vol_slider.valueChanged.connect(self._on_volume_changed)
        vol_row.addWidget(self.mute_btn)
        vol_row.addWidget(self.vol_slider, 1)
        lay.addLayout(vol_row)

        bri_row = QHBoxLayout()
        bri_row.setSpacing(7)
        sun = QLabel(Glyph.BRIGHTNESS)
        sun.setFont(icon_font(10))
        sun.setStyleSheet(f"color: {DIM};")
        self.bri_slider = QSlider(Qt.Orientation.Horizontal)
        self.bri_slider.setStyleSheet(SLIDER_CSS)
        self.bri_slider.setRange(1, 100)
        self.bri_slider.setEnabled(False)
        self.bri_slider.setToolTip("Screen brightness (internal display)")
        self.bri_slider.valueChanged.connect(self._on_brightness_moved)
        self.awake_btn = QPushButton("Awake")
        self.awake_btn.setStyleSheet(TEXT_BTN_CSS)
        self.awake_btn.setToolTip("Keep the display and system awake")
        self.awake_btn.clicked.connect(self.toggle_awake)
        bri_row.addWidget(sun)
        bri_row.addWidget(self.bri_slider, 1)
        bri_row.addWidget(self.awake_btn)
        lay.addLayout(bri_row)
        return page

    def _build_utility_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(4, 3, 4, 2)
        lay.setSpacing(6)

        # "This PC" device row (Windows-flyout style)
        pc_row = QHBoxLayout()
        pc_row.setSpacing(8)
        pc_col = QVBoxLayout()
        pc_col.setContentsMargins(0, 0, 0, 0)
        pc_col.setSpacing(1)
        self.pc_title = QLabel("This PC")
        self.pc_title.setStyleSheet(
            f"font-size: 10px; font-weight: 600; color: {TEXT};"
        )
        self.pc_state = QLabel("")
        self.pc_state.setStyleSheet(f"font-size: 8.5px; color: {DIM};")
        pc_col.addWidget(self.pc_title)
        pc_col.addWidget(self.pc_state)
        self.pc_battery = BatteryBar()
        self.pc_pct = QLabel("")
        self.pc_pct.setStyleSheet(f"font-size: 10px; color: {TEXT};")
        self.pc_row_widget = QWidget()
        pc_row.addLayout(pc_col, 1)
        pc_row.addWidget(self.pc_pct, 0, Qt.AlignmentFlag.AlignVCenter)
        pc_row.addWidget(self.pc_battery, 0, Qt.AlignmentFlag.AlignVCenter)
        self.pc_row_widget.setLayout(pc_row)
        self.pc_row_widget.setStyleSheet(
            f"background: {SURFACE}; border-radius: 6px; padding: 4px 8px;"
        )
        self.pc_row_widget.hide()
        lay.addWidget(self.pc_row_widget)

        t_row = QHBoxLayout()
        t_row.setSpacing(7)
        self.mic_pill = QLabel(Glyph.MIC)
        self.mic_pill.setFont(icon_font(9))
        self.mic_pill.setStyleSheet("color: #f87171;")
        self.mic_pill.hide()
        self.x_telemetry = QLabel("")
        self.x_telemetry.setStyleSheet(f"font-size: 9px; color: {DIM};")
        t_row.addWidget(self.mic_pill)
        t_row.addWidget(self.x_telemetry)
        t_row.addStretch(1)
        lay.addLayout(t_row)

        u_row = QHBoxLayout()
        u_row.setSpacing(6)
        timer_icon = QLabel(Glyph.CLOCK)
        timer_icon.setFont(icon_font(9))
        timer_icon.setStyleSheet(f"color: {DIM};")
        self.pomodoro_btn = QPushButton("25:00")
        self.pomodoro_btn.setStyleSheet(TEXT_BTN_CSS)
        self.pomodoro_btn.setToolTip("1-click focus timer — click to start / pause")
        self.pomodoro_btn.clicked.connect(self.toggle_pomodoro)
        self.shelf_row = QHBoxLayout()
        self.shelf_row.setSpacing(4)
        self.clear_btn = self._glyph_button(Glyph.CLOSE, "Clear file shelf", self._clear_shelf, 8)
        self.clear_btn.hide()
        u_row.addWidget(timer_icon)
        u_row.addWidget(self.pomodoro_btn)
        u_row.addLayout(self.shelf_row, 1)
        u_row.addWidget(self.clear_btn)
        lay.addLayout(u_row)

        b_row = QHBoxLayout()
        self.shelf_hint = QLabel("Drop files onto the notch to shelve them.")
        self.shelf_hint.setStyleSheet(f"font-size: 8.5px; color: {FAINT};")
        self.quit_btn = self._glyph_button(Glyph.POWER, "Quit Crown Notch", self._quit, 10)
        b_row.addWidget(self.shelf_hint)
        b_row.addStretch(1)
        b_row.addWidget(self.quit_btn)
        lay.addLayout(b_row)
        return page

    # ------------------------------------------------------------------
    # notes
    # ------------------------------------------------------------------
    def _build_notes_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(4, 3, 4, 2)
        lay.setSpacing(5)
        self.note_input = QLineEdit()
        self.note_input.setPlaceholderText("Type a note and press Enter")
        self.note_input.setStyleSheet(INPUT_CSS)
        self.note_input.setFixedHeight(22)
        self.note_input.returnPressed.connect(self._add_note)
        lay.addWidget(self.note_input)
        self.notes_list = QListWidget()
        self.notes_list.setStyleSheet(LIST_CSS)
        self.notes_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.notes_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.notes_list.itemClicked.connect(self._on_note_clicked)
        self.notes_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.notes_list.customContextMenuRequested.connect(self._notes_menu)
        self.notes_list.setToolTip("Click to edit — right-click to delete")
        lay.addWidget(self.notes_list, 1)
        self._refresh_notes()
        return page

    def _refresh_notes(self) -> None:
        self.notes_list.clear()
        for note in self.notes:
            text = (note.get("text") or "").strip().replace("\n", " ")
            item = QListWidgetItem(text[:48] or "(empty)")
            item.setData(Qt.ItemDataRole.UserRole, note.get("id"))
            item.setToolTip(text)
            self.notes_list.addItem(item)

    def _add_note(self) -> None:
        text = self.note_input.text().strip()
        if not text:
            return
        self.notes.insert(0, {
            "id": data.uid(),
            "text": text,
            "updated": datetime.now().isoformat(timespec="seconds"),
        })
        self.note_input.clear()
        data.save_items("notes", self.notes)
        self._refresh_notes()

    def _on_note_clicked(self, item) -> None:
        note_id = item.data(Qt.ItemDataRole.UserRole)
        note = next((n for n in self.notes if n.get("id") == note_id), None)
        if note:
            self._open_note_editor(note)

    def _open_note_editor(self, note: dict) -> None:
        if self._note_editor is not None:
            self._note_editor.hide()
            self._note_editor.deleteLater()
        self._note_editor = NoteEditor(note, self._save_note, self._delete_note)
        self._note_editor.open_top_center()

    def _save_note(self, note_id: str, text: str) -> None:
        for note in self.notes:
            if note.get("id") == note_id:
                note["text"] = text
                note["updated"] = datetime.now().isoformat(timespec="seconds")
        data.save_items("notes", self.notes)
        self._refresh_notes()

    def _delete_note(self, note_id: str) -> None:
        self.notes = [n for n in self.notes if n.get("id") != note_id]
        data.save_items("notes", self.notes)
        self._refresh_notes()

    def _notes_menu(self, pos) -> None:
        item = self.notes_list.itemAt(pos)
        if item is None:
            return
        note_id = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        menu.addAction("Edit", lambda: self._on_note_clicked(item))
        menu.addAction("Delete", lambda: self._delete_note(note_id))
        menu.exec(self.notes_list.mapToGlobal(pos))

    # ------------------------------------------------------------------
    # reminders
    # ------------------------------------------------------------------
    def _build_reminders_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(4, 3, 4, 2)
        lay.setSpacing(5)
        row = QHBoxLayout()
        row.setSpacing(5)
        self.reminder_input = QLineEdit()
        self.reminder_input.setPlaceholderText("Reminder — e.g. Call mom")
        self.reminder_input.setStyleSheet(INPUT_CSS)
        self.reminder_input.setFixedHeight(22)
        self.reminder_input.returnPressed.connect(self._add_reminder)
        self.reminder_when = QLineEdit()
        self.reminder_when.setPlaceholderText("18:30")
        self.reminder_when.setStyleSheet(INPUT_CSS)
        self.reminder_when.setFixedSize(72, 22)
        self.reminder_when.setToolTip("When: 18:30 (today/tomorrow) or 25m / 2h from now")
        self.reminder_when.returnPressed.connect(self._add_reminder)
        row.addWidget(self.reminder_input, 1)
        row.addWidget(self.reminder_when)
        lay.addLayout(row)
        self.reminders_list = QListWidget()
        self.reminders_list.setStyleSheet(LIST_CSS)
        self.reminders_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.reminders_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.reminders_list.itemClicked.connect(self._on_reminder_clicked)
        self.reminders_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.reminders_list.customContextMenuRequested.connect(self._reminders_menu)
        self.reminders_list.setToolTip("Click to acknowledge — right-click for more")
        lay.addWidget(self.reminders_list, 1)
        self._refresh_reminders()
        return page

    def _refresh_reminders(self) -> None:
        self.reminders_list.clear()
        today = datetime.now().date()
        for r in sorted(self.reminders, key=lambda r: r.get("at", "")):
            try:
                at = datetime.fromisoformat(r["at"])
                when = at.strftime("%H:%M") if at.date() == today else at.strftime("%a %H:%M")
            except Exception:
                when = "?"
            text = (r.get("text") or "").replace("\n", " ")
            label = f"{when}   {text[:40]}"
            if r.get("done"):
                label = "✓ " + label
            item = QListWidgetItem(label)
            if r.get("done"):
                item.setForeground(QColor("#5a5a64"))
            item.setData(Qt.ItemDataRole.UserRole, r.get("id"))
            item.setToolTip(text)
            self.reminders_list.addItem(item)

    def _add_reminder(self) -> None:
        text = self.reminder_input.text().strip()
        if not text:
            return
        when = parse_when(self.reminder_when.text())
        if when is None:
            self._show_toast("Use a time like 18:30 or 25m")
            return
        self.reminders.append({
            "id": data.uid(),
            "text": text,
            "at": when.isoformat(timespec="seconds"),
            "done": False,
        })
        self.reminder_input.clear()
        data.save_items("reminders", self.reminders)
        self._refresh_reminders()

    def _on_reminder_clicked(self, item) -> None:
        reminder_id = item.data(Qt.ItemDataRole.UserRole)
        for r in self.reminders:
            if r.get("id") == reminder_id and not r.get("done"):
                r["done"] = True
                data.save_items("reminders", self.reminders)
                self._refresh_reminders()
                return

    def _reminders_menu(self, pos) -> None:
        item = self.reminders_list.itemAt(pos)
        if item is None:
            return
        reminder_id = item.data(Qt.ItemDataRole.UserRole)
        target = next((r for r in self.reminders if r.get("id") == reminder_id), None)
        menu = QMenu(self)
        if target is not None and not target.get("done"):
            menu.addAction("Mark as done", lambda: self._on_reminder_clicked(item))
        menu.addAction("Delete", lambda: self._delete_reminder(reminder_id))
        menu.exec(self.reminders_list.mapToGlobal(pos))

    def _delete_reminder(self, reminder_id: str) -> None:
        self.reminders = [r for r in self.reminders if r.get("id") != reminder_id]
        data.save_items("reminders", self.reminders)
        self._refresh_reminders()

    def _check_reminders(self) -> None:
        now = datetime.now()
        fired = False
        for r in self.reminders:
            if r.get("done"):
                continue
            try:
                at = datetime.fromisoformat(r["at"])
            except Exception:
                continue
            if at <= now:
                r["done"] = True
                fired = True
                text = r.get("text", "")
                self._show_toast(f"Reminder — {text[:60]}")
                QApplication.beep()
                if self.tray.isVisible():
                    self.tray.showMessage(
                        "Crown Notch — Reminder", text,
                        QSystemTrayIcon.MessageIcon.Information, 8000,
                    )
        if fired:
            data.save_items("reminders", self.reminders)
            self._refresh_reminders()

    def _glyph_button(self, glyph: str, tooltip: str, cb, px: int) -> QPushButton:
        btn = QPushButton(glyph)
        btn.setFont(icon_font(px))
        btn.setStyleSheet(ICON_BTN_CSS)
        btn.setFixedSize(24, 20)
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(cb)
        return btn

    def _on_page_changed(self, index: int) -> None:
        self.dots.set_current(index)
        names = ("Media", "Controls", "Utility", "Notes", "Reminders")
        self.page_label.setText(
            names[index].upper() if index < len(names) else ""
        )

    # ------------------------------------------------------------------
    # tray
    # ------------------------------------------------------------------
    def _tray_pixmap(self) -> QPixmap:
        pm = QPixmap(64, 64)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(16, 16, 20, 240))
        p.setPen(QPen(QColor(255, 255, 255, 45), 2))
        p.drawRoundedRect(10, 24, 44, 20, 9, 9)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(224, 178, 115))
        p.drawEllipse(40, 31, 6, 6)
        p.end()
        return pm

    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(QIcon(self._tray_pixmap()), self)
        self.tray.setToolTip("Crown Notch")
        menu = QMenu()
        self._tray_toggle_act = menu.addAction("Hide notch", self.toggle_visible)
        menu.addAction("Settings\u2026", self.open_settings)
        menu.addAction("Replay onboarding", self.show_onboarding)
        menu.addSeparator()
        menu.addAction("Quit", self._quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_visible()

    def toggle_visible(self) -> None:
        if self.isVisible():
            self.hide()
            self._tray_toggle_act.setText("Show notch")
        else:
            self.show()
            self._tray_toggle_act.setText("Hide notch")

    def open_settings(self) -> None:
        from settings_dialog import SettingsDialog

        dlg = SettingsDialog(self.cfg, self)
        dlg.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        if dlg.exec():
            self.apply_settings(dlg.values)

    def show_onboarding(self) -> None:
        from onboarding import OnboardingCard

        self._onboarding = OnboardingCard(self)
        self._onboarding.finished.connect(self._onboarding_done)
        self._onboarding.show_at_top_center()

    def _onboarding_done(self) -> None:
        self.cfg["onboarded"] = True
        config.save(self.cfg)

    def apply_settings(self, values: dict) -> None:
        self.cfg.update({k: values.get(k) for k in config.DEFAULTS})
        config.save(self.cfg)
        self._sizes = SIZES_SETS["compact" if self.cfg.get("compact") else "comfort"]
        self.set_state(self.state, force=True)  # re-morph to the new size
        self._update_clock()
        self._set_liquid_glass(bool(self.cfg.get("liquid_glass", True)))
        _log(f"settings applied: {self.cfg}")

    # ------------------------------------------------------------------
    # toast
    # ------------------------------------------------------------------
    def _show_toast(self, text: str, glyph: str | None = None) -> None:
        if self.fullscreen_hidden or not self.isVisible():
            return
        if self._toast is None:
            self._toast = QFrame(self)
            self._toast.setObjectName("toast")
            self._toast.setStyleSheet(TOAST_CSS)
            lay = QHBoxLayout(self._toast)
            lay.setContentsMargins(9, 0, 11, 0)
            lay.setSpacing(8)
            bar = QFrame(self._toast)
            bar.setFixedSize(2, 14)
            bar.setStyleSheet(f"background: {ACCENT}; border-radius: 1px;")
            lay.addWidget(bar)
            self._toast_label = QLabel("")
            self._toast_label.setTextFormat(Qt.TextFormat.RichText)
            lay.addWidget(self._toast_label, 1, Qt.AlignmentFlag.AlignVCenter)
            self._toast.setFixedSize(206, 26)
        if glyph:
            self._toast_label.setText(
                f"<span style=\"font-family:'{icon_family()}'"
                f"; color:{ACCENT};\">{glyph}</span>&nbsp;&nbsp;{text}"
            )
        else:
            self._toast_label.setText(text)
        y = self._sizes["idle"][1] + 10
        self._toast.move((self.width() - self._toast.width()) // 2, y)
        self._toast.show()
        self._toast.raise_()
        self._toast_timer.start(3000)

    def _hide_toast(self) -> None:
        if self._toast is not None:
            self._toast.hide()

    # ------------------------------------------------------------------
    # state machine + morphs
    # ------------------------------------------------------------------
    def on_enter(self) -> None:
        self._grace_timer.stop()
        if self.state == "idle" and self.cfg.get("hover_peek", True):
            self._hover_timer.start(150)

    def on_leave(self) -> None:
        self._hover_timer.stop()
        if self.state == "peek":
            self.set_state("idle")
        elif self.state == "expanded":
            self._grace_timer.start(600)

    def on_click(self) -> None:
        self._hover_timer.stop()
        if self.state != "expanded":
            self.set_state("expanded")

    def _hover_expand(self) -> None:
        if self.state == "idle":
            self.set_state("peek")

    def _grace_collapse(self) -> None:
        if self.state == "expanded":
            self.set_state("idle")

    def set_state(self, state: str, force: bool = False) -> None:
        if state == self.state and not force:
            return
        _log(f"state {self.state} -> {state}")
        self.state = state
        self.stack.setCurrentIndex(
            {"idle": 0, "peek": 1, "expanded": 2}[state]
        )
        self._fade_in()
        w, h = self._sizes[state]
        screen = self._screen_geo
        anim = QPropertyAnimation(self, b"geometry")
        anim.setDuration(430)
        anim.setEasingCurve(_spring_curve())
        anim.setStartValue(self.geometry())
        anim.setEndValue(
            QRect(screen.x() + (screen.width() - w) // 2, screen.y(), w, h)
        )
        anim.start()
        self._geom_anim = anim
        if state in ("peek", "expanded"):
            if state == "expanded":
                self._refresh_expanded()
            self._poll_timer.start()
        else:
            self._poll_timer.stop()

    def _fade_in(self) -> None:
        self.opacity.setOpacity(0.25)
        anim = QPropertyAnimation(self.opacity, b"opacity")
        anim.setDuration(280)
        anim.setStartValue(0.25)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._fade_anim = anim

    # ------------------------------------------------------------------
    # media
    # ------------------------------------------------------------------
    def on_media(self, payload: dict) -> None:
        self.media_payload = payload
        playing = payload["available"] and payload["is_playing"]
        self.eq_idle.set_playing(playing)
        self.eq_peek.set_playing(playing)
        self.idle_stack.setCurrentIndex(0 if playing else 1)

        art_small = self._art_pixmap(payload["art"], 22, 5)
        if art_small is not None:
            self.peek_art.setPixmap(art_small)
        else:
            self.peek_art.clear()
        art_big = self._art_pixmap(payload["art"], 78, 7)
        if art_big is not None:
            self.x_art.setPixmap(art_big)
        else:
            self.x_art.clear()

        self.peek_title.setText(payload["title"] or "Nothing playing")
        self.peek_artist.setText(payload["artist"] or "")
        self.x_title.setText(payload["title"] or "Nothing playing")
        self.x_artist.setText(payload["artist"] or "Open a media app to control it here")
        self.btn_play.setText(Glyph.PAUSE if playing else Glyph.PLAY)
        self.peek_stack.setCurrentIndex(0 if payload["available"] else 1)

        if not self.seek.isSliderDown():
            duration = max(1, payload["duration_ms"])
            self.seek.setRange(0, duration)
            self.seek.setValue(min(payload["position_ms"], duration))

        self._update_battery_labels()

    def _on_seek_released(self) -> None:
        self._seeking = False
        target = self.seek.value()
        current = int(self.media_payload["position_ms"])
        if not self.media_payload["available"] or abs(target - current) < 4000:
            return
        if target < current:
            self.media.rewind()
        else:
            self.media.fast_forward()

    def _cmd_play(self) -> None:
        playing = self.media_payload["is_playing"]
        self.btn_play.setText(Glyph.PLAY if playing else Glyph.PAUSE)
        self.media.play_pause()

    def _cmd_next(self) -> None:
        self.media.next()

    def _cmd_prev(self) -> None:
        self.media.prev()

    # ------------------------------------------------------------------
    # mic / device indicators
    # ------------------------------------------------------------------
    def on_audio_status(self, s: dict) -> None:
        mic = bool(s.get("mic"))
        if mic and not self.mic_active:
            self._show_toast("Microphone in use", Glyph.MIC)
        self.mic_active = mic

        did = s.get("default_id")
        if did:
            if self._initial_default_id is None:
                self._initial_default_id = did
            elif did != self._initial_default_id and did not in self._device_toasted:
                self._show_toast("Audio output changed", Glyph.DEVICES)
                self._device_toasted.add(did)
            self._on_external_device = did != self._initial_default_id

        self._update_indicators()

    def _update_indicators(self) -> None:
        for label in (self.idle_dev, self.peek_dev):
            label.setVisible(self._on_external_device)
        for label in (self.idle_mic, self.peek_mic, self.mic_pill):
            label.setVisible(self.mic_active)
        self._render_telemetry()

    # ------------------------------------------------------------------
    # telemetry / volume / brightness / awake
    # ------------------------------------------------------------------
    def _refresh_expanded(self) -> None:
        self._apply_telemetry(sysinfo.snapshot())
        self._sync_volume()
        self._apply_brightness_if_needed()

    def _apply_brightness_if_needed(self) -> None:
        """Fetch current brightness once per expand (in a thread — WMI is slow)."""
        if self.brightness is None:
            threading.Thread(
                target=lambda: self.brightness_ready.emit(brightness.get()), daemon=True
            ).start()

    def _poll_expanded(self) -> None:
        self._apply_telemetry(sysinfo.snapshot())
        if not self.vol_slider.isSliderDown():
            self._sync_volume()

    def _render_telemetry(self) -> None:
        t = self.telemetry
        parts = [f"CPU {t['cpu']:.0f}%", f"RAM {t['ram']:.0f}%"]
        if t["battery"] is not None:
            parts.append(f"{t['battery']:.0f}%")
        self.x_telemetry.setText("   ".join(parts))
        self.peek_telemetry.setText("   ".join(parts))
        # "This PC" flyout-style device row
        if t["battery"] is not None:
            self.pc_row_widget.show()
            self.pc_battery.set_value(t["battery"])
            self.pc_pct.setText(f"{t['battery']:.0f}%")
            self.pc_state.setText("Charging" if t.get("plugged") else "On battery")
        else:
            self.pc_row_widget.hide()

    def _apply_telemetry(self, t: dict) -> None:
        self.telemetry = t
        self._render_telemetry()
        self._update_battery_labels()

    def _update_battery_labels(self) -> None:
        battery = self.telemetry.get("battery")
        if battery is None:
            self.idle_battery.setText("")
        elif battery <= 10:
            self.idle_battery.setText(f"{battery:.0f}%")
            self.idle_battery.setStyleSheet("font-size: 8.5px; color: #f87171;")
        elif battery <= 20:
            self.idle_battery.setText(f"{battery:.0f}%")
            self.idle_battery.setStyleSheet("font-size: 8.5px; color: #fbbf24;")
        else:
            self.idle_battery.setText(f"{battery:.0f}%")
            self.idle_battery.setStyleSheet(f"font-size: 8.5px; color: {DIM};")
        if not (self.media_payload["available"] and self.media_payload["is_playing"]):
            self.idle_stack.setCurrentIndex(1)

    def _sync_volume(self) -> None:
        try:
            import audio

            self.volume = audio.get_volume()
        except Exception as exc:
            _log(f"get_volume failed: {exc}")
            return
        try:
            import audio

            self.muted = audio.get_mute()
        except Exception:
            pass
        self._syncing_volume = True
        self.vol_slider.setValue(int(self.volume * 100))
        self._syncing_volume = False
        self.mute_btn.setText(Glyph.MUTE if self.muted else Glyph.VOLUME)
        self._apply_brightness_if_needed()

    def _on_volume_changed(self, value: int) -> None:
        if self._syncing_volume:
            return
        try:
            import audio

            audio.set_volume(value / 100.0)
        except Exception as exc:
            _log(f"set_volume({value}) failed: {exc}")

    def _toggle_mute(self) -> None:
        try:
            import audio

            self.muted = not audio.get_mute()
            audio.set_mute(self.muted)
        except Exception as exc:
            _log(f"set_mute failed: {exc}")
            self.muted = not self.muted
        self.mute_btn.setText(Glyph.MUTE if self.muted else Glyph.VOLUME)

    def _on_brightness_ready(self, value: object) -> None:
        if value is None:
            self.bri_slider.setEnabled(False)
            self.bri_slider.setToolTip("No internal display brightness sensor found")
            return
        self.brightness = float(value)
        self.bri_slider.blockSignals(True)
        self.bri_slider.setValue(int(self.brightness))
        self.bri_slider.blockSignals(False)
        self.bri_slider.setEnabled(True)

    def _on_brightness_moved(self, value: int) -> None:
        self.brightness = float(value)
        self._brightness_debounce.start()

    def _apply_brightness(self) -> None:
        if self.brightness is not None:
            try:
                brightness.set(self.brightness)
            except Exception as exc:
                _log(f"set_brightness({self.brightness}) failed: {exc}")

    def toggle_awake(self) -> None:
        self.awake = not self.awake
        self.awake_btn.setStyleSheet(TOGGLE_ON_CSS if self.awake else TEXT_BTN_CSS)
        if self.awake:
            self._keep_awake_refresh()
            self._awake_timer.start(2000)
        else:
            self._awake_timer.stop()
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)

    def _keep_awake_refresh(self) -> None:
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
        )

    # ------------------------------------------------------------------
    # pomodoro
    # ------------------------------------------------------------------
    def toggle_pomodoro(self) -> None:
        self.pomodoro["running"] = not self.pomodoro["running"]
        self._update_pomodoro()

    def _tick_pomodoro(self) -> None:
        if not self.pomodoro["running"]:
            return
        self.pomodoro["remaining"] -= 1
        if self.pomodoro["remaining"] <= 0:
            self.pomodoro = {"remaining": 25 * 60, "running": False}
            QApplication.beep()
        self._update_pomodoro()

    def _update_pomodoro(self) -> None:
        remaining = self.pomodoro["remaining"]
        fresh = remaining == 25 * 60 and not self.pomodoro["running"]
        self.pomodoro_btn.setText("25:00" if fresh else f"{remaining // 60:02d}:{remaining % 60:02d}")

    # ------------------------------------------------------------------
    # file shelf
    # ------------------------------------------------------------------
    def on_drag_enter(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def on_drop(self, event) -> None:
        added = False
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path and path not in self.shelf:
                self.shelf.append(path)
                added = True
        event.acceptProposedAction()
        if added:
            self._refresh_shelf()
            self.set_state("expanded")

    def _refresh_shelf(self) -> None:
        while self.shelf_row.count():
            item = self.shelf_row.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        for path in self.shelf[:6]:
            name = os.path.basename(path.rstrip("/\\")) or path
            chip = QPushButton(name[:18])
            chip.setStyleSheet(CHIP_CSS)
            chip.setToolTip(path)
            chip.clicked.connect(lambda _=False, p=path: self._open_shelf_file(p))
            chip.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            chip.customContextMenuRequested.connect(
                lambda _p, b=chip, pth=path: self._chip_menu(b, pth)
            )
            self.shelf_row.addWidget(chip)
        self.shelf_hint.setVisible(not self.shelf)
        self.clear_btn.setVisible(bool(self.shelf))

    def _chip_menu(self, chip: QWidget, path: str) -> None:
        menu = QMenu(self)
        menu.addAction("Remove from shelf", lambda: self._remove_shelf_file(path))
        menu.exec(chip.mapToGlobal(QPoint(0, chip.height())))

    def _open_shelf_file(self, path: str) -> None:
        try:
            os.startfile(path)  # noqa: S606 (intentional shell open)
        except Exception:
            pass

    def _remove_shelf_file(self, path: str) -> None:
        if path in self.shelf:
            self.shelf.remove(path)
            self._refresh_shelf()

    def _clear_shelf(self) -> None:
        self.shelf.clear()
        self._refresh_shelf()

    def _quit(self) -> None:
        if self.media is not None:
            self.media.requestInterruption()
        if self.audio_worker is not None:
            self.audio_worker.requestInterruption()
        if self.tray.isVisible():
            self.tray.hide()
        QApplication.instance().quit()

    # ------------------------------------------------------------------
    # native: click-through hit-testing + fullscreen tuck
    # ------------------------------------------------------------------
    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._set_transparent(True)
        if not hasattr(self, "_native_timers_started"):
            self._native_timers_started = True
            _log("notch window shown")
            self._hit_timer = QTimer(self)
            self._hit_timer.timeout.connect(self._update_click_through)
            self._hit_timer.start(25)
            self._fs_timer = QTimer(self)
            self._fs_timer.timeout.connect(self.check_fullscreen)
            self._fs_timer.start(500)
            self._set_liquid_glass(bool(self.cfg.get("liquid_glass", True)))

    def _set_accent(self, hwnd: int, policy: "_AccentPolicy") -> bool:
        data = _WindowCompositionAttribData(
            _WCA_ACCENT_POLICY,
            ctypes.cast(ctypes.byref(policy), ctypes.c_void_p),
            ctypes.sizeof(policy),
        )
        return bool(
            ctypes.windll.user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data))
        )

    def _set_liquid_glass(self, on: bool) -> None:
        """Windows 11 acrylic backdrop behind the notch glass.

        Chain: official DWM backdrop (DWMWA_SYSTEMBACKDROP_TYPE = acrylic)
        first; if the window doesn't support it (E_HANDLE on layered
        windows), fall back to SetWindowCompositionAttribute acrylic blur.
        The window is exactly pill-sized, so the blur never draws outside
        the notch. Falls back to plain obsidian glass when neither works."""
        try:
            hwnd = int(self.winId())
            dwm = ctypes.windll.dwmapi
            # reset both mechanisms first
            dwm_none = ctypes.c_int(1)  # DWMSBT_NONE
            dwm.DwmSetWindowAttribute(
                hwnd, 38, ctypes.byref(dwm_none), ctypes.sizeof(dwm_none)
            )
            self._set_accent(hwnd, _AccentPolicy(_ACCENT_DISABLED, 0, 0, 0))

            glass = False
            method = ""
            if on:
                dark = ctypes.c_int(1)  # immersive dark mode
                dwm.DwmSetWindowAttribute(
                    hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark)
                )
                acrylic = ctypes.c_int(3)  # DWMSBT_TRANSIENTWINDOW
                hr = dwm.DwmSetWindowAttribute(
                    hwnd, 38, ctypes.byref(acrylic), ctypes.sizeof(acrylic)
                )
                if hr == 0:
                    dwm.DwmExtendFrameIntoClientArea(
                        hwnd, ctypes.byref(_DwmMargins(-1, -1, -1, -1))
                    )
                    glass, method = True, "dwm acrylic"
                else:
                    # tinted dark acrylic via composition attribute
                    policy = _AccentPolicy(
                        _ACCENT_ENABLE_ACRYLICBLURBEHIND, 2, 0xA6120F0F, 0
                    )
                    if self._set_accent(hwnd, policy):
                        glass, method = True, "composition acrylic"
            self._glass = glass
            self.frame.setStyleSheet(_frame_css(0.55 if glass else 0.90))
            _log(
                f"liquid glass {'on via ' + method if glass else 'off'}"
            )
        except Exception as exc:
            _log(f"liquid glass error: {exc}")

    def _set_transparent(self, on: bool) -> None:
        if on == self._transparent:
            return
        try:
            hwnd = int(self.winId())
            style = _get_window_long(hwnd, GWL_EXSTYLE)
            style = (style | WS_EX_TRANSPARENT) if on else (style & ~WS_EX_TRANSPARENT)
            _set_window_long(hwnd, GWL_EXSTYLE, style)
            self._transparent = on
        except Exception:
            pass

    def _update_click_through(self) -> None:
        if self.fullscreen_hidden:
            self._set_transparent(True)
            return
        try:
            pt = wintypes.POINT()
            if not ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
                return
            hwnd = int(self.winId())
            rect = wintypes.RECT()
            if not ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                return
            scale = self.devicePixelRatioF() or 1.0
            local = QPoint(
                int((pt.x - rect.left) / scale),
                int((pt.y - rect.top) / scale),
            )
            g = self.frame.geometry().adjusted(-2, -3, 2, 3)
            self._set_transparent(not g.contains(local))
        except Exception:
            pass

    def check_fullscreen(self) -> None:
        if not self.cfg.get("fullscreen_hide", True):
            if self.fullscreen_hidden:
                self.fullscreen_hidden = False
                self._animate_tuck(False)
            return
        try:
            fs, title = _is_foreground_fullscreen(int(self.winId()))
        except Exception:
            fs, title = False, ""
        if fs != self.fullscreen_hidden:
            self._fs_strikes += 1
            if self._fs_strikes >= 2:  # hold ~1s before tucking
                self._fs_strikes = 0
                _log(f"fullscreen hide={fs} foreground={title!r}")
                self.fullscreen_hidden = fs
                self._animate_tuck(fs)
        else:
            self._fs_strikes = 0

    def _animate_tuck(self, hide: bool) -> None:
        anim = QPropertyAnimation(self, b"pos")
        anim.setDuration(450)
        anim.setEasingCurve(_spring_curve())
        anim.setStartValue(self.pos())
        anim.setEndValue(
            QPoint(self.x(), -(self.height() + 8) if hide else 0)
        )
        anim.start()
        self._tuck_anim = anim
        if hide:
            self._set_transparent(True)

    # ------------------------------------------------------------------
    def _update_clock(self) -> None:
        now = datetime.now()
        if self.cfg.get("clock_24h", False):
            self.clock_label.setText(now.strftime("%H:%M"))
        else:
            ampm = "a.m." if now.hour < 12 else "p.m."
            self.clock_label.setText(f"{now:%I:%M} {ampm}")

    def _art_pixmap(self, art: bytes | None, size: int, radius: int) -> QPixmap | None:
        if not art:
            return None
        try:
            img = QImage.fromData(art)
            if img.isNull():
                return None
            src = QPixmap.fromImage(img).scaled(
                size,
                size,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            out = QPixmap(size, size)
            out.fill(Qt.GlobalColor.transparent)
            p = QPainter(out)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            path = QPainterPath()
            path.addRoundedRect(0.0, 0.0, float(size), float(size), radius, radius)
            p.setClipPath(path)
            p.drawPixmap((size - src.width()) // 2, (size - src.height()) // 2, src)
            p.end()
            return out
        except Exception:
            return None


def _spring_curve() -> QEasingCurve:
    """Spring-like settle with a slight overshoot.

    Deliberately avoids QEasingCurve.setCustomType with a Python callable:
    when the curve is copied into a QPropertyAnimation, the copy's
    custom-function pointer can dangle and hard-crash the process on the
    first animation tick (reproduced as a bare segfault with no traceback).
    """
    curve = QEasingCurve()
    curve.setType(QEasingCurve.Type.OutBack)
    try:
        curve.setOvershoot(0.4)
    except Exception:
        pass
    return curve
