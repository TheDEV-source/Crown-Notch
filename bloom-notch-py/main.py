import faulthandler
import os
import sys
import traceback
from datetime import datetime

from PySide6.QtCore import qInstallMessageHandler, QTimer
from PySide6.QtWidgets import QApplication

import config
from media import MediaWorker
from notch_window import NotchWindow
from system_audio import SystemAudioWorker

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notch.log")
FATAL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notch-fatal.log")

# Dump the native stack on hard crashes (access violations etc.)
try:
    fatal_fh = open(FATAL_PATH, "w", encoding="utf-8", buffering=1)
    faulthandler.enable(fatal_fh)
except Exception:
    pass


def _append(text: str) -> None:
    try:
        with open(LOG_PATH, "a", encoding="utf-8", errors="replace") as fh:
            fh.write(text + "\n")
    except Exception:
        pass


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _qt_message_handler(mode, context, message) -> None:
    _append(f"{_stamp()}  [qt] {message}")


def _excepthook(tp, val, tb) -> None:
    _append(
        f"{_stamp()}  [crash] unhandled exception:\n"
        + "".join(traceback.format_exception(tp, val, tb))
    )
    traceback.print_exception(tp, val, tb)


def _thread_excepthook(args) -> None:
    name = args.thread.name if args.thread is not None else "?"
    _append(
        f"{_stamp()}  [crash] thread {name!r}:\n"
        + "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
    )


def main() -> None:
    sys.excepthook = _excepthook
    if hasattr(sys, "threading_excepthook"):
        sys.threading_excepthook = _thread_excepthook
    qInstallMessageHandler(_qt_message_handler)

    _append(f"{_stamp()}  [app] starting (Python {sys.version.split()[0]})")

    app = QApplication(sys.argv)
    app.setApplicationName("Crown Notch")
    app.setApplicationVersion("0.3.0b1")
    app.setQuitOnLastWindowClosed(True)
    app.aboutToQuit.connect(lambda: _append(f"{_stamp()}  [app] quitting"))

    cfg = config.load()

    media_worker = MediaWorker()
    media_worker.start()

    audio_worker = SystemAudioWorker()
    audio_worker.start()

    window = NotchWindow(media_worker, audio_worker, cfg)
    window.show()

    if not cfg.get("onboarded"):
        QTimer.singleShot(700, window.show_onboarding)

    exit_code = app.exec()
    _append(f"{_stamp()}  [app] exec() returned with code {exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
