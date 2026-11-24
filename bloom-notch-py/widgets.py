"""Custom widgets: Segoe Fluent Icons glyphs, sliding page stack,
page indicator, battery bar, equalizer, eliding labels. Styled to match
the native Windows 11 flyout surfaces."""

from __future__ import annotations

import math

from PySide6.QtCore import (
    QParallelAnimationGroup,
    QPointF,
    QPoint,
    QPropertyAnimation,
    QRect,
    QRectF,
    QEasingCurve,
    QTimer,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QWidget


# --------------------------------------------------------------------------
# Segoe Fluent Icons glyphs (Segoe MDL2 Assets fallback on older systems)
# --------------------------------------------------------------------------
class Glyph:
    PLAY = "\uE768"
    PAUSE = "\uE769"
    PREV_TRACK = "\uE892"
    NEXT_TRACK = "\uE893"
    VOLUME = "\uE767"
    MUTE = "\uE74F"
    BRIGHTNESS = "\uE706"
    POWER = "\uE7E8"
    MIC = "\uE720"
    DEVICES = "\uE772"
    CLOCK = "\uE823"
    FOLDER = "\uE8B7"
    CLOSE = "\uE711"
    MORE = "\uE712"


_ICON_FAMILY: str | None = None


def icon_family() -> str:
    global _ICON_FAMILY
    if _ICON_FAMILY is None:
        for fam in ("Segoe Fluent Icons", "Segoe MDL2 Assets"):
            if QFontMetrics(QFont(fam)).inFontUcs4(0xE768):
                _ICON_FAMILY = fam
                break
        else:
            _ICON_FAMILY = "Segoe MDL2 Assets"
    return _ICON_FAMILY


def icon_font(px: int) -> QFont:
    font = QFont(icon_family())
    font.setPixelSize(px)
    return font


class SlideStack(QWidget):
    """Stacked pages with smooth horizontal slide transitions.

    Flip with ``setCurrentIndex`` (animated), the mouse wheel, or the page
    indicator. Children are clipped to the container, so overshoot easing
    is safe.
    """

    currentChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pages: list[QWidget] = []
        self._current = 0
        self._anim: QParallelAnimationGroup | None = None
        self._animating = False

    def count(self) -> int:
        return len(self._pages)

    def currentIndex(self) -> int:
        return self._current

    def page(self, index: int) -> QWidget:
        return self._pages[index]

    def addPage(self, page: QWidget) -> int:
        page.setParent(self)
        page.hide()
        self._pages.append(page)
        if len(self._pages) == 1:
            page.setGeometry(self.rect())
            page.show()
        return len(self._pages) - 1

    def setCurrentIndex(self, index: int, animate: bool = True) -> None:
        if index < 0 or index >= len(self._pages):
            return
        if index == self._current or self._animating:
            return

        src = self._pages[self._current]
        dst = self._pages[index]
        src_idx = self._pages.index(src)
        direction = 1 if index > src_idx else -1
        self._current = index
        self.currentChanged.emit(index)

        if not animate:
            src.hide()
            dst.setGeometry(self.rect())
            dst.show()
            return

        w = max(1, self.width())
        h = max(1, self.height())

        self._animating = True
        src.setGeometry(QRect(0, 0, w, h))
        dst.setGeometry(QRect(direction * w, 0, w, h))
        src.show()
        dst.show()
        dst.raise_()

        slide = QEasingCurve()
        slide.setType(QEasingCurve.Type.OutBack)
        try:
            slide.setOvershoot(0.25)
        except Exception:
            pass

        group = QParallelAnimationGroup(self)
        a_src = QPropertyAnimation(src, b"pos")
        a_src.setDuration(320)
        a_src.setEasingCurve(slide)
        a_src.setEndValue(QPoint(-direction * w, 0))
        a_dst = QPropertyAnimation(dst, b"pos")
        a_dst.setDuration(320)
        a_dst.setEasingCurve(slide)
        a_dst.setEndValue(QPoint(0, 0))
        group.addAnimation(a_src)
        group.addAnimation(a_dst)

        def _finished() -> None:
            src.hide()
            src.move(0, 0)
            dst.setGeometry(self.rect())
            self._animating = False

        group.finished.connect(_finished)
        group.start()
        self._anim = group  # keep referenced

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._animating:
            return
        for i, page in enumerate(self._pages):
            if i == self._current:
                page.setGeometry(self.rect())
            else:
                page.setGeometry(QRect(self.width(), 0, self.width(), self.height()))

    def wheelEvent(self, event) -> None:  # noqa: N802
        delta = event.angleDelta().y()
        if delta == 0:
            return
        if delta < 0:
            self.setCurrentIndex(min(self._current + 1, len(self._pages) - 1))
        else:
            self.setCurrentIndex(max(self._current - 1, 0))
        event.accept()


class PageDots(QWidget):
    """Windows-11-style page indicator: a bar for the active page, quiet
    dots for the rest; click to switch. ``mini`` variant for the idle pill."""

    changed = Signal(int)

    def __init__(
        self,
        count: int = 0,
        active_color: QColor | None = None,
        mini: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._active = active_color or QColor(224, 178, 115)
        self._count = count
        self._current = 0
        self._mini = mini
        self._update_size()

    def set_count(self, count: int) -> None:
        self._count = count
        self._update_size()
        self.update()

    def set_current(self, index: int) -> None:
        self._current = index
        self.update()

    def _update_size(self) -> None:
        cell, height = (8, 10) if self._mini else (16, 12)
        self.setFixedSize(max(self._count, 1) * cell, height)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        cell = 8 if self._mini else 16
        for i in range(self._count):
            cx = i * cell + cell / 2
            if i == self._current:
                p.setBrush(self._active)
                if self._mini:
                    p.drawRoundedRect(QRectF(cx - 4, 4, 8, 2), 1, 1)
                else:
                    p.drawRoundedRect(QRectF(cx - 6, 4.5, 12, 3), 1.5, 1.5)
            else:
                r = 1.1 if self._mini else 1.5
                p.setBrush(QColor(255, 255, 255, 60))
                p.drawEllipse(QPointF(cx, 6), r, r)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        cell = 8 if self._mini else 16
        index = int(event.position().x() // cell)
        if 0 <= index < self._count:
            self.changed.emit(index)


class BatteryBar(QWidget):
    """Windows-flyout-style battery level bar (green/amber/red)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pct = 0.0
        self.setFixedSize(46, 5)

    def set_value(self, pct: float) -> None:
        self._pct = max(0.0, min(100.0, pct))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 30))
        p.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 2.5, 2.5)
        if self._pct > 0:
            color = (
                QColor(62, 207, 110)
                if self._pct > 20
                else QColor(240, 180, 41)
                if self._pct > 10
                else QColor(248, 113, 113)
            )
            p.setBrush(color)
            p.drawRoundedRect(
                QRectF(0, 0, self.width() * self._pct / 100.0, self.height()), 2.5, 2.5
            )


class Equalizer(QWidget):
    """Live audio equalizer bars; settles low when paused."""

    def __init__(self, color=QColor(255, 255, 255, 105), parent=None):
        super().__init__(parent)
        self._color = color
        self._playing = True
        self._t = 0.0
        self.setFixedSize(20, 11)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(90)

    def set_playing(self, playing: bool) -> None:
        self._playing = playing

    def _tick(self) -> None:
        if self._playing:
            self._t += 0.35
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h, n = self.width(), self.height(), 5
        gap = 2.0
        bw = (w - gap * (n - 1)) / n
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._color)
        for i in range(n):
            if self._playing:
                k = 0.25 + 0.75 * abs(math.sin(self._t * 1.35 + i * 0.9))
            else:
                k = 0.22
            bh = max(1.5, h * k)
            p.drawRoundedRect(QRectF(i * (bw + gap), h - bh, bw, bh), 1.0, 1.0)


class ElidedLabel(QWidget):
    """Paints text truncated with an ellipsis, never wrapping or overflowing."""

    def __init__(self, text="", color="#e6e6ea", px=10, bold=False, parent=None):
        super().__init__(parent)
        self._text = text
        self._color = color
        font = QFont("Segoe UI")
        font.setPixelSize(px)
        font.setBold(bold)
        self.setFont(font)
        self.setMinimumHeight(px + 4)

    def setText(self, text: str) -> None:
        self._text = text
        self.update()

    def text(self) -> str:
        return self._text

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        fm = QFontMetrics(self.font())
        elided = fm.elidedText(
            self._text, Qt.TextElideMode.ElideRight, self.width()
        )
        p.setPen(QColor(self._color))
        p.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            elided,
        )
