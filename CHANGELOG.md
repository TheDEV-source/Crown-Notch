# Changelog

## Unreleased (working toward 0.3.0b2)

### Planned
- CI: also smoke-test Python 3.12 to prove the no-winsdk graceful
  degradation path stays working.
- Fixes and polish from beta-1 feedback (fill in as reports come in).

## 0.3.0b1 — 2026-11-23

**Rename:** the app is now **Crown Notch** (previously Bloom Notch). Settings
moved to `%APPDATA%\CrownNotch`; first-run onboarding replays once.

### Added
- **Notes page**: single-line capture, popup multi-line editor, JSON-persisted.
- **Reminders page**: natural time parsing (`18:30`, `9:00pm`, `25m`, `2h`,
  `3d`); fires with toast + chime + native Windows notification; overdue
  reminders fire on startup; click to acknowledge, right-click to delete.
- **Liquid glass**: Windows 11 acrylic backdrop behind the notch via DWM
  (`DWMWA_SYSTEMBACKDROP_TYPE`) with a `SetWindowCompositionAttribute`
  fallback; toggle in Settings. The top-level window is now exactly
  pill-sized and moves/resizes with each morph.
- Tray toggle, Settings, and onboarding reflect the new pages.

### Changed
- **Design**: Windows 11 media-flyout look — near-black glass, flyout-style
  idle pill (page dots · `09:38 a.m.` clock · device/equalizer icon, dots
  click-jump to a page), media page with large album art + centered transport
  + full-width seek + `···` button, "This PC" device row (battery bar,
  On battery/Charging) on the utility page. 12-hour clock is now the default
  (24 h still available in Settings).
- Crown-style: crown-gold accent, gold hairline fused to the top bezel,
  painted page indicator (bar for active page) with uppercase page label,
  accent bar in toasts, consistent tokens across all surfaces.
- `windows-sizes`: idle 152×26, peek 224×36, expanded 376×158 (Comfort set
  available in Settings).

### Fixed
- **Media**: winsdk 1.0.0b10 dialect — `get_sessions`, `get_playback_info`
  and `get_timeline_properties` are synchronous and media properties live at
  `try_get_media_properties_async`; every snapshot previously threw and was
  swallowed, so metadata/controls appeared dead.
- **Volume**: pycaw 2026 API (`AudioDevice.EndpointVolume` with raw-device
  fallback) and comtypes 1.5 (per-thread `CoInitialize` helper replacing the
  removed context-manager idiom).
- **Brightness** errors now surface in `notch.log` instead of being silent.
- **Onboarding card** background actually paints (object-name stylesheet
  selector).
- Hard-crash vector: `QEasingCurve.setCustomType` with a Python callable
  dangles after the curve is copied into an animation — replaced with tuned
  `OutBack` overshoot (documented in code).

## 0.2.0b1 — 2026-11-23

- Paged command center with slide transitions (media / controls / utility),
  mouse-wheel + dots navigation.
- Tray icon (hide/show, settings, onboarding, quit), live Settings with
  `%APPDATA%` persistence and start-with-windows (HKCU Run).
- First-run onboarding card (4 steps, replayable from tray).
- Mic-in-use indicator (Core Audio peak metering) and audio-device change
  toasts.
- Compact size set by default; fullscreen detector excludes maximized
  windows (auto-hidden/replaced taskbar false positives) with 1 s
  hysteresis; decisions logged to `notch.log`.
- Crash instrumentation: `notch.log` heartbeat, unhandled-exception hooks,
  Qt message handler, faulthandler native dumps.

## 0.1.0b1 — 2026-11-23

- Initial Python/PySide6 edition: morphing notch (idle / peek / expanded),
  click-through hit-testing, fullscreen auto-hide, SMTC media worker,
  telemetry, master volume, WMI brightness, keep-awake, Pomodoro, file
  shelf, Bloom-style equalizer.
