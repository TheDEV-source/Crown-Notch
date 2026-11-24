//! Screen brightness get/set for the internal display via the standard WMI
//! classes (`WmiMonitorBrightness` / `WmiMonitorBrightnessMethods`).
//!
//! Uses an out-of-process PowerShell call so we don't need a full WMI COM
//! binding for a slow-changing setting; CREATE_NO_WINDOW keeps it invisible.

use std::process::Command;

#[cfg(windows)]
use std::os::windows::process::CommandExt;

const CREATE_NO_WINDOW: u32 = 0x0800_0000;

fn powershell(script: &str) -> Option<String> {
    let output = Command::new("powershell")
        .args(["-NoProfile", "-NonInteractive", "-Command", script])
        .creation_flags(CREATE_NO_WINDOW)
        .output()
        .ok()?;
    if !output.status.success() {
        return None;
    }
    Some(String::from_utf8_lossy(&output.stdout).trim().to_string())
}

/// Current brightness 0..=100, or None when no internal panel supports WMI
/// brightness (e.g. desktop with external monitor only).
pub fn get() -> Option<f64> {
    powershell(
        "(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness).CurrentBrightness",
    )
    .and_then(|s| s.parse().ok())
}

pub fn set(v: f64) {
    let v = v.clamp(0.0, 100.0);
    powershell(&format!(
        "(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods).WmiSetBrightness(1, {v})"
    ));
}
