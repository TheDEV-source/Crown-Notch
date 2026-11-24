"""First-run onboarding: a small card under the notch walking through the
basics in four steps. Restartable from the tray menu."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from widgets import icon_font

STEPS = [
    (
        "Meet your notch",
        "Crown Notch sits at the top-center of your screen. It is small on "
        "purpose: hover it for a quick peek at what is playing and how your "
        "system is doing.",
    ),
    (
        "Open it",
        "Click the notch to open the command center. Scroll the mouse wheel "
        "or tap the dots below the panel to move between pages. Move the "
        "cursor away and it closes by itself.",
    ),
    (
        "Capture things",
        "Drag files onto the notch to shelve them while you work, and use "
        "the notes and reminders pages to keep quick thoughts and timers "
        "without opening another app.",
    ),
    (
        "Make it yours",
        "The notch shows when your microphone is in use and when your audio "
        "output changes. The tray icon in the bottom-right corner has "
        "settings, onboarding and quit.",
    ),
]

CARD_CSS = """
#OnboardingCard {
    background: rgba(22, 22, 27, 0.96);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 12px;
}
QLabel { color: #e6e6ea; }
QPushButton {
    background: rgba(255, 255, 255, 0.06);
    border: none; border-radius: 6px; color: #d6d6dc;
    font-size: 11px; padding: 4px 12px;
}
QPushButton:hover { background: rgba(255, 255, 255, 0.12); }
QPushButton:disabled { color: #55555e; }
QPushButton#primary {
    background: rgba(224, 178, 115, 0.16);
    color: #e6c793; font-weight: 600;
}
QPushButton#primary:hover { background: rgba(224, 178, 115, 0.24); }
"""


class OnboardingCard(QWidget):
    finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._step = 0
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(360, 168)

        card = QFrame(self)
        card.setObjectName("OnboardingCard")
        card.setStyleSheet(CARD_CSS)
        card.setGeometry(self.rect())

        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 14, 18, 12)
        lay.setSpacing(6)

        self.stack = QStackedWidget(card)
        for title, body in STEPS:
            page = QWidget()
            pl = QVBoxLayout(page)
            pl.setContentsMargins(0, 0, 0, 0)
            pl.setSpacing(6)
            t = QLabel(title)
            f = QFont("Segoe UI")
            f.setPixelSize(13)
            f.setBold(True)
            t.setFont(f)
            b = QLabel(body)
            b.setWordWrap(True)
            bf = QFont("Segoe UI")
            bf.setPixelSize(10)
            b.setFont(bf)
            b.setStyleSheet("color: #b9b9c2; line-height: 1.45;")
            pl.addWidget(t)
            pl.addWidget(b, 1)
            self.stack.addWidget(page)
        lay.addWidget(self.stack, 1)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        self.dots = QLabel("")
        self.dots.setStyleSheet("color: #6a6a74; font-size: 9px;")
        footer.addWidget(self.dots)
        footer.addStretch(1)
        self.back_btn = QPushButton("Back")
        self.back_btn.clicked.connect(self._back)
        self.skip_btn = QPushButton("Skip")
        self.skip_btn.clicked.connect(self._finish)
        self.next_btn = QPushButton("Next")
        self.next_btn.setObjectName("primary")
        self.next_btn.clicked.connect(self._next)
        footer.addWidget(self.back_btn)
        footer.addWidget(self.skip_btn)
        footer.addWidget(self.next_btn)
        lay.addLayout(footer)

        self._apply()

    # ---- positioning ----
    def show_at_top_center(self) -> None:
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.x() + (screen.width() - self.width()) // 2, screen.y() + 44)
        self.show()
        self.raise_()

    # ---- navigation ----
    def _apply(self) -> None:
        self.stack.setCurrentIndex(self._step)
        self.dots.setText("  ".join("\u25cf" if i == self._step else "\u25cb" for i in range(len(STEPS))))
        self.back_btn.setEnabled(self._step > 0)
        self.next_btn.setText("Done" if self._step == len(STEPS) - 1 else "Next")
        self.skip_btn.setText("Skip" if self._step < len(STEPS) - 1 else "Close")

    def _next(self) -> None:
        if self._step >= len(STEPS) - 1:
            self._finish()
            return
        self._step += 1
        self._apply()

    def _back(self) -> None:
        self._step = max(0, self._step - 1)
        self._apply()

    def _finish(self) -> None:
        self.hide()
        self.finished.emit()
