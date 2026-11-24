# Crown Notch — Windows 11 Dynamic Notch

A lightweight, native-feeling Dynamic Island / notch companion for Windows 11,
inspired by [Bloom](https://github.com/david-shortman/bloom). The notch sits
flush at the top-center of the primary monitor, morphs with spring physics, and
expands into a live command center.

**Two editions:**

- [`bloom-notch-py/`](bloom-notch-py/README.md) — **Python / PySide6 edition
  (recommended first, beta `0.3.0b1`)**. Crown-style spring animations,
  Vayli-style *paged* command center (media / controls / utility / notes /
  reminders), mic-in-use and audio-device indicators, tray icon, live
  settings with start-with-Windows, notes + reminders, and first-run
  onboarding. No toolchain downloads needed beyond
  `pip install -r requirements.txt`.
- Root of this repo — **Tauri v2 edition** (Rust + WinRT/COM, React 18 +
  Framer Motion). Same feature set; requires the Rust/Node toolchain to build.

---

## States

| State | Size | Trigger | Content |
|---|---|---|---|
| **Idle pill** | 180 × 32 | default | `HH:MM` clock · live audio equalizer while media plays, else battery/status dot |
| **Compact peek** | 260 × 44 | 150 ms hover debounce | track title + album art thumb + equalizer, or CPU/RAM telemetry |
| **Command center** | 420 × 190 | click (collapses 600 ms after cursor leaves) | SMTC media controller w/ seek bar & glow art · volume + brightness sliders · Keep Awake toggle · CPU/RAM pill · 1-click Pomodoro (25:00) · drag-&-drop file shelf |

## Windows-11-specific behavior (implemented in Rust)

- **Click-through hit-testing** (`src-tauri/src/system.rs`): a ~40 Hz loop reads
  `GetCursorPos` and toggles Tauri's `set_ignore_cursor_events` (i.e.
  `WS_EX_TRANSPARENT`) whenever the cursor is outside the notch's *active*
  rect — which the frontend reports on every morph (`set_active_rect`). The
  transparent bounding box therefore never blocks browser tabs or title bars.
- **Fullscreen auto-hide** (`system.rs::is_fullscreen`): detects borderless
  fullscreen (foreground window rect == monitor rect) and exclusive/presentation
  modes (`SHQueryUserNotificationState`) every 500 ms and emits
  `notch://fullscreen`; the notch slides up off-screen and becomes inert.
- **Tool window**: `skipTaskbar: true` + `focusable: false` (no Alt-Tab entry,
  no taskbar button, never steals focus from the app you're working in).
- **SMTC media** (`media.rs`): `GlobalSystemMediaTransportControlsSessionManager`
  listener (`CurrentSessionChanged` + `AnyMediaPropertyChanged`) → title,
  artist, album art (streamed → base64), playback status, timeline position.
  Play/pause/skip via `TryPlayAsync` / `TryPauseAsync` / `TrySkipNext/PreviousAsync`.
- **Telemetry** (`telemetry.rs`): `sysinfo` CPU/RAM + WinRT `Battery.Aggregate`.
  Polled **only** while expanded (2 s throttle), idle cost is zero.
- **Master volume** (`volume.rs`): Core Audio `IAudioEndpointVolume` COM.
- **Brightness** (`brightness.rs`): WMI `WmiMonitorBrightness(Methods)`.
- **Keep Awake** (`power.rs`): `SetThreadExecutionState(ES_CONTINUOUS |
  ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)` from a dedicated keeper thread.

## Project layout

```
src/                     React frontend
  App.tsx                state machine (idle/peek/expanded/hidden), timers, event wiring
  components/NotchShell.tsx   morphing container (Framer Motion spring)
  components/IdlePeek.tsx     idle pill + peek content, equalizer, status dot
  components/Panels.tsx       media controller, system sliders, utility bar
  lib/motion.ts          shared spring config + state sizes
src-tauri/
  src/lib.rs             Tauri setup + all IPC commands
  src/system.rs          hit-testing, fullscreen detection, window placement
  src/media.rs           SMTC listener + playback controls
  src/telemetry.rs       CPU/RAM/battery
  src/volume.rs          master volume (COM)
  src/brightness.rs      WMI brightness
  src/power.rs           keep-awake
  tauri.conf.json        frameless, transparent, always-on-top, y=0, 460×220 host window
```

## Running it

> This workspace had no Rust/Node toolchains installed and outbound network
> access blocked, so the code was **not compiled or executed here**. Build it
> on your machine with:

**Prerequisites**

1. [Rust](https://rustup.rs) with the MSVC toolchain + **Visual Studio Build
   Tools** ("Desktop development with C++" workload)
2. [Node.js](https://nodejs.org) ≥ 18
3. WebView2 — already built into Windows 11

```powershell
npm install
npm run tauri dev     # run with live reload
npm run tauri build   # production bundle (msi + nsis)
```

Before `tauri build`, generate the app icon once (any square PNG ≥ 1024px):

```powershell
npm run tauri icon path\to\icon.png
```

## Known limitations

- **Seek bar is display-only.** The public SMTC API exposes the timeline but
  does not let third-party apps *set* playback position (only the media app
  itself can). Play/pause/skip work; the progress bar follows the system media
  clock.
- **Brightness** only applies to internal panels that expose WMI brightness
  (typical for laptops; external monitors use DDC/CI, not implemented).
- The Python edition already ships real DWM acrylic "liquid glass" behind the
  panel; the Tauri edition uses near-opaque obsidian glass
  (`rgba(15,15,18,0.88)`) from the spec — a `window-vibrancy` plugin could
  add DWM acrylic there later if desired.
