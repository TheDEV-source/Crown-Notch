# Crown Notch (Python edition) — beta

A lightweight **Windows 11 dynamic notch** desktop companion: **spring-settle
morphs** with a **paged command-center**, styled to feel native — Segoe
Fluent Icons glyphs, a crown-gold accent, hairline borders, a real acrylic
**liquid glass** backdrop, no emoji, no glow.

The notch sits flush at the top-center of the primary display, passes mouse
clicks through everywhere except the pill itself, morphs between states with
a spring-settle curve, and tucks off-screen whenever a fullscreen app takes
over.

> **Status: beta (`0.3.0b1`)** — expected rough edges are documented under
> [Limitations](#limitations--known-issues).

---

## Features

### The notch (three states, native styling)

| State | Size | Trigger | Content |
|---|---|---|---|
| **Idle pill** | 152 × 26 | default | page dots · clock (flyout style `09:38 a.m.`, 24 h optional) · live equalizer while media plays · battery % (turns amber/red when low) · audio-device and mic glyphs |
| **Compact peek** | 224 × 36 | 150 ms hover debounce | track + album art + equalizer, or CPU/RAM telemetry |
| **Command center** | 376 × 158 | click | **five paged panels** — move with the mouse wheel or the page indicator; collapses 600 ms after the cursor leaves |

> The top-level window is exactly pill-sized and moves/resizes with every
> morph, so the liquid-glass blur never paints outside the notch.

### Paged command center (Vayli-style, one topic per page)

- **Page 1 — Media**: Windows 11 media-flyout layout: large album art,
  track/artist, centered transport controls, full-width seek bar and a
  `···` button to the other pages. Works for *any* app (Spotify, browsers,
  players); seek is best-effort (drag → system rewind/fast-forward).
- **Page 2 — Controls**: master volume slider + mute, screen brightness
  (WMI, internal display), and the **Keep Awake** toggle.
- **Page 3 — Utility**: Windows-flyout **"This PC" device row** (battery
  bar, On battery/Charging), live CPU/RAM/battery telemetry (polled only
  while open), 1-click **Pomodoro 25:00** with a chime, the **drag-&-drop
  file shelf** (click a chip to open, right-click to remove), and quit.
- **Page 4 — Notes**: quick single-line capture with a popup multi-line
  editor; persisted and searchable-by-eye.
- **Page 5 — Reminders**: natural time parsing (`18:30`, `9:00pm`, `25m`,
  `2h`, `3d`); fires with a notch toast, a chime and a native Windows
  notification; overdue reminders fire on startup.

Slides between pages use an overshoot-settle curve, clipped to the panel.

### System awareness

- **Liquid glass**: real Windows 11 acrylic backdrop via DWM
  (`DWMWA_SYSTEMBACKDROP_TYPE`, with a `SetWindowCompositionAttribute`
  fallback); toggleable in Settings.

- **Microphone in use**: Core Audio peak-metering of the default capture
  device; the pill shows a red mic glyph and a toast fires when recording
  starts.
- **Audio device changes**: when the default output changes (headphones
  plugged, output switched), a device glyph appears and a toast announces it.
- **Fullscreen auto-hide**: borderless + exclusive fullscreen detection
  (maximized windows are explicitly excluded, so an auto-hidden taskbar
  can't fool it), with ~1 s hysteresis.
- **Click-through**: a ~40 Hz cursor hit-test toggles `WS_EX_TRANSPARENT` —
  browser tabs and title bars are never blocked.
- **Unobtrusive**: tool window — no taskbar button, no Alt-Tab entry, never
  steals focus.

### Tray, settings, onboarding

- **Tray icon** (bottom-right): click to hide/show the notch; menu with
  Settings, Replay onboarding, and Quit.
- **Settings**: compact size, hover peek, fullscreen hiding, liquid glass,
  24 h clock, and **Start with Windows** (HKCU Run entry). Persisted in
  `%APPDATA%\CrownNotch\settings.json`, applied live.
- **First-run onboarding**: a four-step card under the notch; replayable
  from the tray.

### Crown-style animations

- Spring-settle morphs (subtle overshoot) between all states.
- Cross-fading content while the container morphs; text elides cleanly.
- Live audio equalizer bars (freeze when paused).
- Smooth spring tuck off-screen for fullscreen apps.

## Requirements

- **Windows 10/11** (built for Windows 11)
- **Python 3.10 or 3.11** — 3.12+ works but loses media controls (see below)

## Install & run

```powershell
py install 3.11        # if you use the new Python install manager
py -0p                 # verify a 3.11 runtime exists
cd bloom-notch-py
py -3.11 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python main.py     # or double-click run.bat
```

Enable **Start with Windows** in Settings (tray icon → Settings) instead of
making your own startup shortcut.

### Optional: single-file exe

```powershell
pip install pyinstaller
pyinstaller --noconsole --onefile --name CrownNotch main.py
```

### Or install it like a real app (recommended)

The GitHub **Releases** page has **`CrownNotch-Setup.exe`** — download it,
double-click, and Crown Notch installs to `%LOCALAPPDATA%\CrownNotch` with a
Start Menu shortcut and an uninstaller in *Settings → Apps* (per-user, no
admin needed), then launches right away. A portable single-file
`CrownNotch.exe` is also attached for USB-stick use. Every version tag
(`v*`) triggers an automated build of both, so the newest release always has
fresh binaries.

To build the installer locally:

```powershell
pyinstaller --noconsole --onefile --name CrownNotch main.py
& "C:\Program Files (x86)\NSIS\makensis.exe" installer.nsi   # needs NSIS
```

## Usage

| Action | Result |
|---|---|
| Hover the notch | compact peek after 150 ms |
| Click the notch | command center (paged) |
| Mouse wheel / dots | flip pages |
| Move away | peek collapses; expanded collapses after 600 ms |
| Drop files on the notch | shelved; click to open, right-click to remove |
| Tray icon | hide/show, settings, onboarding, quit |

## Troubleshooting

- **No media info / controls** — `winsdk` wheels only ship for Python
  3.10/3.11. Check `pip show winsdk`. Everything else works without it.
- **Brightness slider disabled** — your display doesn't expose WMI
  brightness (desktop + external monitor). DDC/CI is on the roadmap.
- **Notch hidden** — a genuinely fullscreen app was detected; it returns
  automatically. If it hides wrongly, send us `notch.log` (it records the
  foreground window that triggered the tuck).
- **Mic glyph never appears** — some headsets mute the meter below our
  threshold; the indicator is level-based (peak metering), not API-based.

## Limitations / known issues

- **Seek is best-effort**: the public SMTC API cannot set playback position;
  dragging the bar nudges playback via rewind/fast-forward. Exact scrubbing
  depends on the media app.
- Brightness applies to internal panels only (WMI).
- The device indicator tracks the *default* output device — a plugged-in
  device that isn't made default won't show a toast.
- The first CPU reading is 0% (psutil warm-up); it corrects on the next poll.

## Roadmap (post-beta)

- Swipe/drag gestures between pages; page reorder
- Notification mirroring
- Per-page settings (hide Pomodoro, hide shelf…)
- DDC/CI brightness for external monitors
- Tauri/Rust edition (see `../src-tauri`) with the same feature set

## License

[MIT](../LICENSE)
