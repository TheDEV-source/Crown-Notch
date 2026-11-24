#[cfg(windows)]
mod brightness;
#[cfg(windows)]
mod media;
#[cfg(windows)]
mod power;
#[cfg(windows)]
mod system;
#[cfg(windows)]
mod telemetry;
#[cfg(windows)]
mod volume;

use std::sync::{Arc, Mutex};
use tauri::Manager;

/// Temporarily shelved files (drag & drop), owned by the backend so the
/// list survives webview reloads.
pub struct Shelf(pub Arc<Mutex<Vec<String>>>);

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(Shelf(Arc::new(Mutex::new(Vec::new()))))
        .setup(|app| {
            #[cfg(windows)]
            {
                let handle = app.handle().clone();
                let win = handle
                    .get_webview_window("notch")
                    .expect("notch window missing from tauri.conf.json");

                // Horizontally centered on the primary display, fused to y = 0.
                system::position_centered_top(&win);

                handle.manage(system::HiddenFlag(Arc::new(
                    std::sync::atomic::AtomicBool::new(false),
                )));
                handle.manage(system::NotchRect(Arc::new(Mutex::new(
                    system::ActiveRect::default(),
                ))));

                // Cursor hit-testing: pass clicks through outside the notch pill.
                system::spawn_hit_test(handle.clone());
                // Fullscreen auto-hide watcher.
                system::spawn_fullscreen_watcher(handle.clone());
                // Windows SMTC media listener.
                media::start(handle.clone());

                let _ = win.show();
            }
            Ok(())
        })
        .invoke_handler({
            #[cfg(windows)]
            let handler = tauri::generate_handler![
                set_active_rect,
                get_telemetry,
                get_media_snapshot,
                media_play_pause,
                media_next,
                media_prev,
                get_volume,
                set_volume,
                get_brightness,
                set_brightness,
                set_awake,
                get_shelf,
                add_shelf_files,
                remove_shelf_file,
                clear_shelf,
            ];
            #[cfg(not(windows))]
            let handler = tauri::generate_handler![];
            handler
        })
        .run(tauri::generate_context!())
        .expect("error while running bloom notch");
}

/* ------------------------------- commands ------------------------------- */

#[cfg(windows)]
#[tauri::command(rename_all = "snake_case")]
fn set_active_rect(
    state: tauri::State<system::NotchRect>,
    x: f64,
    y: f64,
    width: f64,
    height: f64,
) {
    *state.0.lock().unwrap() = system::ActiveRect { x, y, width, height };
}

#[cfg(windows)]
#[tauri::command(rename_all = "snake_case")]
fn get_telemetry() -> telemetry::Telemetry {
    telemetry::snapshot()
}

#[cfg(windows)]
#[tauri::command(rename_all = "snake_case")]
fn get_media_snapshot() -> media::MediaPayload {
    media::current_payload()
}

#[cfg(windows)]
#[tauri::command(rename_all = "snake_case")]
fn media_play_pause() {
    media::toggle_play();
}

#[cfg(windows)]
#[tauri::command(rename_all = "snake_case")]
fn media_next() {
    media::next();
}

#[cfg(windows)]
#[tauri::command(rename_all = "snake_case")]
fn media_prev() {
    media::prev();
}

#[cfg(windows)]
#[tauri::command(rename_all = "snake_case")]
fn get_volume() -> f32 {
    volume::get().unwrap_or(0.5)
}

#[cfg(windows)]
#[tauri::command(rename_all = "snake_case")]
fn set_volume(v: f32) {
    volume::set(v);
}

#[cfg(windows)]
#[tauri::command(rename_all = "snake_case")]
fn get_brightness() -> Option<f64> {
    brightness::get()
}

#[cfg(windows)]
#[tauri::command(rename_all = "snake_case")]
fn set_brightness(v: f64) {
    brightness::set(v);
}

#[cfg(windows)]
#[tauri::command(rename_all = "snake_case")]
fn set_awake(on: bool) {
    power::set_awake(on);
}

#[tauri::command(rename_all = "snake_case")]
fn get_shelf(shelf: tauri::State<Shelf>) -> Vec<String> {
    shelf.0.lock().unwrap().clone()
}

#[tauri::command(rename_all = "snake_case")]
fn add_shelf_files(shelf: tauri::State<Shelf>, paths: Vec<String>) -> Vec<String> {
    let mut list = shelf.0.lock().unwrap();
    for p in paths {
        if !list.contains(&p) {
            list.push(p);
        }
    }
    list.clone()
}

#[tauri::command(rename_all = "snake_case")]
fn remove_shelf_file(shelf: tauri::State<Shelf>, path: String) -> Vec<String> {
    let mut list = shelf.0.lock().unwrap();
    list.retain(|p| p != &path);
    list.clone()
}

#[tauri::command(rename_all = "snake_case")]
fn clear_shelf(shelf: tauri::State<Shelf>) -> Vec<String> {
    shelf.0.lock().unwrap().clear();
    Vec::new()
}
