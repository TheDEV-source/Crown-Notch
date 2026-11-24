"""Settings dialog for Crown Notch. Edits a config dict in place; the caller
persists and applies it on accept."""

from __future__ import annotations

import config
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

DIALOG_CSS = """
QDialog { background: #17171b; }
QLabel { color: #e6e6ea; }
QLabel#title { font-size: 14px; font-weight: 600; }
QCheckBox { color: #cfcfd6; font-size: 12px; spacing: 9px; }
QCheckBox::indicator {
    width: 15px; height: 15px; border-radius: 3px;
    border: 1px solid rgba(255,255,255,0.25); background: rgba(255,255,255,0.05);
}
QCheckBox::indicator:checked {
    background: rgba(224,178,115,0.85); border-color: rgba(224,178,115,0.85);
}
QCheckBox:disabled { color: #6a6a74; }
QPushButton {
    background: rgba(255,255,255,0.07); border: none; border-radius: 6px;
    color: #d6d6dc; font-size: 12px; padding: 6px 16px;
}
QPushButton:hover { background: rgba(255,255,255,0.12); }
QPushButton#primary { background: rgba(224,178,115,0.85); color: #1a1408; font-weight: 600; }
QPushButton#primary:hover { background: rgba(224,178,115,0.95); }
QLabel#hint { color: #6a6a74; font-size: 10px; }
"""

CHECK_ITEMS = [
    ("compact", "Compact notch size"),
    ("hover_peek", "Hover expands to the compact peek"),
    ("fullscreen_hide", "Tuck away during fullscreen apps"),
    ("liquid_glass", "Liquid glass backdrop (Windows 11 acrylic)"),
    ("clock_24h", "24-hour clock"),
    ("start_with_windows", "Start Crown Notch when Windows starts"),
]


class SettingsDialog(QDialog):
    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.values = dict(cfg)
        self.setWindowTitle("Crown Notch — Settings")
        self.setStyleSheet(DIALOG_CSS)
        self.setFixedSize(330, 300)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.MSWindowsFixedSizeDialogHint
        )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 14)
        lay.setSpacing(10)

        title = QLabel("Settings")
        title.setObjectName("title")
        lay.addWidget(title)

        self._boxes: dict[str, QCheckBox] = {}
        for key, label in CHECK_ITEMS:
            box = QCheckBox(label)
            box.setChecked(bool(self.values.get(key)))
            box.toggled.connect(lambda on, k=key: self._toggled(k, on))
            self._boxes[key] = box
            lay.addWidget(box)

        lay.addStretch(1)
        self.hint = QLabel("")
        self.hint.setObjectName("hint")
        self.hint.setWordWrap(True)
        lay.addWidget(self.hint)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        save.setObjectName("primary")
        save.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        lay.addLayout(buttons)

    def _toggled(self, key: str, on: bool) -> None:
        self.values[key] = on
        if key == "start_with_windows":
            error = config.set_start_with_windows(on)
            if error:
                self.hint.setText(f"Could not update startup entry: {error}")

    def accept(self) -> None:  # noqa: D102
        super().accept()
