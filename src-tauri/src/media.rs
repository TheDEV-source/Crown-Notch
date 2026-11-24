//! Windows System Media Transport Controls (SMTC) listener.
//!
//! Streams real-time track metadata (title / artist / album art as base64)
//! from any media session on the system (Spotify, browsers, YouTube in Edge,
//! etc.) and drives play / pause / skip through the same channel.

use std::sync::OnceLock;
use base64::Engine;
use serde::Serialize;
use tauri::{AppHandle, Emitter};
use windows::core::TypedEventHandler;
use windows::Media::Control::{
    GlobalSystemMediaTransportControlsSession as Session,
    GlobalSystemMediaTransportControlsSessionManager as SessionManager,
    GlobalSystemMediaTransportControlsSessionMediaProperties as SessionMediaProperties,
    GlobalSystemMediaTransportControlsSessionPlaybackStatus,
};
use windows::Storage::Streams::{Buffer, InputStreamOptions};
use windows::Win32::System::Com::{CoInitializeEx, COINIT_MULTITHREADED};

#[derive(Debug, Clone, Serialize, Default)]
pub struct MediaPayload {
    pub available: bool,
    pub title: String,
    pub artist: String,
    pub album: String,
    #[serde(rename = "artBase64")]
    pub art_base64: Option<String>,
    #[serde(rename = "isPlaying")]
    pub is_playing: bool,
    #[serde(rename = "positionMs")]
    pub position_ms: u64,
    #[serde(rename = "durationMs")]
    pub duration_ms: u64,
}

static MANAGER: OnceLock<SessionManager> = OnceLock::new();

/// Initialize the manager and subscribe to session + media-property changes.
pub fn start(app: AppHandle) {
    std::thread::spawn(move || {
        unsafe {
            // WinRT needs an initialized apartment on this thread.
            let _ = CoInitializeEx(None, COINIT_MULTITHREADED);
        }
        let Ok(op) = SessionManager::RequestAsync() else {
            eprintln!("[notch] SMTC unavailable on this system");
            return;
        };
        let Ok(manager) = op.get() else {
            eprintln!("[notch] SMTC RequestAsync failed");
            return;
        };
        let _ = MANAGER.set(manager.clone());

        // Both events re-emit a full snapshot; cheap and always consistent.
        // Each event needs its own handler (different args types).
        let app_for_current = app.clone();
        let current_changed = TypedEventHandler::new(move |_, _| {
            emit_snapshot(&app_for_current);
            Ok(())
        });
        let app_for_media = app.clone();
        let media_changed = TypedEventHandler::new(move |_, _| {
            emit_snapshot(&app_for_media);
            Ok(())
        });
        let _ = manager.CurrentSessionChanged(&current_changed);
        let _ = manager.AnyMediaPropertyChanged(&media_changed);

        emit_snapshot(&app);
    });
}

fn emit_snapshot(app: &AppHandle) {
    let _ = app.emit("notch://media", current_payload());
}

/// Pick the session to surface: the playing one, else the first available.
fn pick_session(manager: &SessionManager) -> Option<Session> {
    let sessions = manager.GetSessions().ok()?;
    let count = sessions.Size().ok()? as u32;
    let mut first: Option<Session> = None;
    for i in 0..count {
        let Ok(s) = sessions.GetAt(i) else { continue };
        if first.is_none() {
            first = Some(s.clone());
        }
        if let Ok(info) = s.GetPlaybackInfo() {
            if let Ok(status) = info.PlaybackStatus() {
                if status == GlobalSystemMediaTransportControlsSessionPlaybackStatus::Playing {
                    return Some(s);
                }
            }
        }
    }
    first
}

fn is_playing(session: &Session) -> bool {
    session
        .GetPlaybackInfo()
        .ok()
        .and_then(|p| p.PlaybackStatus().ok())
        .map(|s| s == GlobalSystemMediaTransportControlsSessionPlaybackStatus::Playing)
        .unwrap_or(false)
}

/// Read the album-art thumbnail from the media properties as base64 JPEG/PNG.
fn read_thumbnail(
    props: &SessionMediaProperties,
) -> windows::core::Result<String> {
    let reference = props.Thumbnail()?;
    let stream = reference.OpenReadAsync()?.get()?;
    let size = stream.Size().min(u32::MAX as u64) as u32;
    if size == 0 {
        return Err(windows::core::Error::empty());
    }
    let buffer = Buffer::Create(size)?;
    let read = stream
        .ReadAsync(&buffer, size, InputStreamOptions::None)?
        .get()?;
    let data: windows::core::Array<u8> = read.Content()?;
    Ok(base64::engine::general_purpose::STANDARD.encode(data.as_slice()))
}

/// Build the current media snapshot (also used by the initial `get_media_snapshot`).
pub fn current_payload() -> MediaPayload {
    let Some(manager) = MANAGER.get() else {
        return MediaPayload::default();
    };
    let Some(session) = pick_session(manager) else {
        return MediaPayload::default();
    };

    let props = session.GetMediaProperties().ok();
    let playing = is_playing(&session);
    let timeline = session.GetTimelineProperties().ok();

    let (title, artist, album) = match &props {
        Ok(p) => (
            p.Title().unwrap_or_default().to_string(),
            p.Artist().unwrap_or_default().to_string(),
            p.AlbumTitle().unwrap_or_default().to_string(),
        ),
        Err(_) => (String::new(), String::new(), String::new()),
    };

    let art = props.as_ref().and_then(|p| read_thumbnail(p).ok());

    let (position_ms, duration_ms) = match &timeline {
        Ok(t) => {
            let pos = t.Position();
            let end = t.EndTime();
            (
                (pos.Duration.max(0) / 10_000) as u64,
                (end.Duration.max(0) / 10_000) as u64,
            )
        }
        Err(_) => (0, 0),
    };

    MediaPayload {
        available: true,
        title,
        artist,
        album,
        art_base64: art,
        is_playing: playing,
        position_ms,
        duration_ms,
    }
}

fn with_session(f: impl FnOnce(&Session)) {
    if let Some(manager) = MANAGER.get() {
        if let Some(session) = pick_session(manager) {
            f(&session);
        }
    }
}

pub fn toggle_play() {
    with_session(|s| {
        let playing = is_playing(s);
        let result = if playing {
            s.TryPauseAsync().and_then(|op| op.get())
        } else {
            s.TryPlayAsync().and_then(|op| op.get())
        };
        if let Err(e) = result {
            eprintln!("[notch] SMTC play/pause failed: {e}");
        }
    });
}

pub fn next() {
    with_session(|s| {
        let _ = s.TrySkipNextAsync().and_then(|op| op.get());
    });
}

pub fn prev() {
    with_session(|s| {
        let _ = s.TrySkipPreviousAsync().and_then(|op| op.get());
    });
}
