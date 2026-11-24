"""Frameless popup for editing a note (same dark-card language as onboarding)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from widgets import Glyph, icon_font

CARD_CSS = """
#noteCard {
    background: rgba(22, 22, 27, 0.97);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 12px;
}
QLabel { color: #e6e6ea; }
QPlainTextEdit {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 6px;
    color: #e6e6ea;
    font-size: 10.5px;
    padding: 6px;
    selection-background-color: rgba(224, 178, 115, 0.40);
}
QPushButton {
    background: rgba(255, 255, 255, 0.06);
    border: none; border-radius: 6px; color: #d6d6dc;
    font-size: 11px; padding: 5px 14px;
}
QPushButton:hover { background: rgba(255, 255, 255, 0.12); }
QPushButton#danger:hover { color: #f87171; }
QPushButton#save { background: rgba(224, 178, 115, 0.16); color: #e6c793; font-weight: 600; }
QPushButton#save:hover { background: rgba(224, 178, 115, 0.24); }
"""

CLOSE_BTN_CSS = """
QPushButton { background: transparent; border: none; border-radius: 5px;
              color: #9b9ba4; }
QPushButton:hover { background: rgba(255, 255, 255, 0.10); color: #e6e6ea; }
"""


class NoteEditor(QFrame):
    def __init__(self, note: dict, on_save, on_delete) -> None:
        super().__init__(None)
        self._id = note.get("id")
        self._on_save = on_save
        self._on_delete = on_delete
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(320, 216)

        card = QFrame(self)
        card.setObjectName("noteCard")
        card.setStyleSheet(CARD_CSS)
        card.setGeometry(self.rect())

        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("Edit note")
        title.setStyleSheet("font-size: 11px; font-weight: 600;")
        header.addWidget(title)
        header.addStretch(1)
        close_btn = QPushButton(Glyph.CLOSE)
        close_btn.setFont(icon_font(10))
        close_btn.setFixedSize(24, 22)
        close_btn.setStyleSheet(CLOSE_BTN_CSS)
        close_btn.setToolTip("Close without saving")
        close_btn.clicked.connect(self.close)
        header.addWidget(close_btn)
        lay.addLayout(header)

        self.text_edit = QPlainTextEdit(note.get("text", ""))
        self.text_edit.setPlaceholderText("Write something…")
        lay.addWidget(self.text_edit, 1)

        buttons = QHBoxLayout()
        delete_btn = QPushButton("Delete")
        delete_btn.setObjectName("danger")
        delete_btn.clicked.connect(self._delete)
        save_btn = QPushButton("Save")
        save_btn.setObjectName("save")
        save_btn.clicked.connect(self._save)
        buttons.addWidget(delete_btn)
        buttons.addStretch(1)
        buttons.addWidget(save_btn)
        lay.addLayout(buttons)

    def open_top_center(self) -> None:
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.x() + (screen.width() - self.width()) // 2, screen.y() + 44)
        self.show()
        self.raise_()
        self.text_edit.setFocus()

    def _save(self) -> None:
        if callable(self._on_save):
            self._on_save(self._id, self.text_edit.toPlainText())
        self.close()

    def _delete(self) -> None:
        if callable(self._on_delete):
            self._on_delete(self._id)
        self.close()
