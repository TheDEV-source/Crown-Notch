//! System telemetry: CPU %, RAM %, battery %.
//!
//! Polled only while the notch is expanded (the frontend invokes
//! `get_telemetry` every 2s), so an idle notch costs zero polling.

use serde::Serialize;
use std::sync::{Mutex, OnceLock};
use sysinfo::System;

#[derive(Debug, Clone, Serialize)]
pub struct Telemetry {
    pub cpu: f32,
    pub ram: f32,
    pub battery: Option<f32>,
}

static SYS: OnceLock<Mutex<System>> = OnceLock::new();

pub fn snapshot() -> Telemetry {
    let cell = SYS.get_or_init(|| Mutex::new(System::new()));
    let mut sys = cell.lock().unwrap();

    sys.refresh_cpu_usage();
    sys.refresh_memory();

    let cpu = sys.global_cpu_usage();
    let ram = if sys.total_memory() > 0 {
        sys.used_memory() as f32 / sys.total_memory() as f32 * 100.0
    } else {
        0.0
    };

    Telemetry {
        cpu,
        ram,
        battery: battery_percent(),
    }
}

/// Battery percentage via WinRT `Battery.Aggregate` (None on desktops without
/// a battery report).
fn battery_percent() -> Option<f32> {
    use windows::Devices::Power::{Battery, BatteryStatus};

    let battery = Battery::Aggregate().ok()?;
    let report = battery.GetReport().ok()?;
    let status = report.Status().ok()?;
    if status == BatteryStatus::NotPresent || status == BatteryStatus::Unknown {
        return None;
    }
    let remaining = report
        .RemainingCapacityInMilliwattHours()
        .ok()?
        .GetValue()
        .ok()? as f32;
    let full = report
        .FullChargeCapacityInMilliwattHours()
        .ok()?
        .GetValue()
        .ok()? as f32;
    if full <= 0.0 {
        return None;
    }
    Some((remaining / full * 100.0).clamp(0.0, 100.0))
}
