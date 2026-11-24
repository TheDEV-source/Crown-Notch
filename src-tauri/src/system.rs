//! Native cursor hit-testing + fullscreen auto-hide for the notch window.

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;
use tauri::{AppHandle, Emitter, Manager};
use windows::Win32::Foundation::{POINT, RECT};
use windows::Win32::Graphics::Gdi::{
    GetMonitorInfoW, MonitorFromWindow, MONITORINFO, MONITOR_DEFAULTTOPRIMARY,
};
use windows::Win32::UI::Shell::{
    SHQueryUserNotificationState, QUNS_PRESENTATION_MODE, QUNS_RUNNING_DIRECT3D_FULL_SCREEN,
};
use windows::Win32::UI::WindowsAndMessaging::{
    GetCursorPos, GetForegroundWindow, GetWindowRect,
};

/// The interactive rect of the notch, in window-local logical coordinates.
/// Reported by the frontend whenever the notch morphs; everything outside it
/// passes mouse events through to whatever is underneath.
#[derive(Debug, Clone, Copy, PartialEq, Default)]
pub struct ActiveRect {
    pub x: f64,
    pub y: f64,
    pub width: f64,
    pub height: f64,
}

pub struct NotchRect(pub Arc<Mutex<ActiveRect>>);
pub struct HiddenFlag(pub Arc<AtomicBool>);

/// Position the notch window flush at top-center of its monitor.
pub fn position_centered_top(win: &tauri::WebviewWindow) {
    use tauri::PhysicalPosition;
    const LOGICAL_WIDTH: f64 = 460.0; // must match tauri.conf.json width
    if let Ok(Some(monitor)) = win.current_monitor() {
        let scale = monitor.scale_factor();
        let x = (monitor.size().width as f64 - LOGICAL_WIDTH * scale) / 2.0;
        let _ = win.set_position(PhysicalPosition::new(x.round() as i32, 0));
    }
}

/// Loop (~40Hz) toggling WS_EX_TRANSPARENT-equivalent click-through based on
/// whether the cursor is inside the active notch rect. This is what keeps the
/// transparent bounding box from ever blocking browser tabs / title bars.
pub fn spawn_hit_test(app: AppHandle) {
    std::thread::spawn(move || {
        let mut ignoring = true;
        loop {
            std::thread::sleep(Duration::from_millis(25));
            let Some(win) = app.get_webview_window("notch") else {
                continue;
            };
            let rect = *app.state::<NotchRect>().0.lock().unwrap();
            let hidden = app.state::<HiddenFlag>().0.load(Ordering::Relaxed);

            let want_ignore = if hidden || rect.width <= 0.0 {
                true
            } else {
                let mut pt = POINT::default();
                if unsafe { GetCursorPos(&mut pt) }.is_err() {
                    continue;
                }
                let Ok(origin) = win.outer_position() else {
                    continue;
                };
                let Ok(scale) = win.scale_factor() else {
                    continue;
                };
                // cursor position in window-local logical coordinates
                let lx = (pt.x - origin.x) as f64 / scale;
                let ly = (pt.y - origin.y) as f64 / scale;
                // small margin so edge pixels remain hoverable
                lx >= rect.x - 2.0
                    && lx <= rect.x + rect.width + 2.0
                    && ly >= rect.y - 4.0
                    && ly <= rect.y + rect.height + 4.0
            };

            if want_ignore != ignoring {
                if win.set_ignore_cursor_events(want_ignore).is_ok() {
                    ignoring = want_ignore;
                }
            }
        }
    });
}

/// Loop (~2Hz) detecting exclusive or borderless fullscreen on the primary
/// monitor and telling the notch to tuck itself off-screen.
pub fn spawn_fullscreen_watcher(app: AppHandle) {
    std::thread::spawn(move || {
        let mut last = false;
        loop {
            std::thread::sleep(Duration::from_millis(500));
            let fs = is_fullscreen();
            if fs != last {
                last = fs;
                app.state::<HiddenFlag>().0.store(fs, Ordering::Relaxed);
                let _ = app.emit("notch://fullscreen", fs);
            }
        }
    });
}

fn is_fullscreen() -> bool {
    unsafe {
        let hwnd = GetForegroundWindow();
        if hwnd.is_invalid() {
            return false;
        }

        // Borderless fullscreen: foreground window rect == primary monitor rect.
        let monitor = MonitorFromWindow(hwnd, MONITOR_DEFAULTTOPRIMARY);
        let mut mi = MONITORINFO {
            cbSize: std::mem::size_of::<MONITORINFO>() as u32,
            ..Default::default()
        };
        if GetMonitorInfoW(monitor, &mut mi).as_bool() {
            let mut wr = RECT::default();
            let _ = GetWindowRect(hwnd, &mut wr);
            if wr == mi.rcMonitor {
                return true;
            }
        }

        // Exclusive fullscreen / presentation mode via the shell API.
        matches!(
            SHQueryUserNotificationState(),
            Ok(s) if s == QUNS_RUNNING_DIRECT3D_FULL_SCREEN || s == QUNS_PRESENTATION_MODE
        )
    }
}
