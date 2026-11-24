//! Master volume get/set via Core Audio `IAudioEndpointVolume` (COM).

use windows::Win32::Media::Audio::{
    eRender, eConsole, IAudioEndpointVolume, IMMDeviceEnumerator, MMDeviceEnumerator,
};
use windows::Win32::System::Com::{CoCreateInstance, CoInitializeEx, CLSCTX_ALL, COINIT_MULTITHREADED};

fn with_endpoint<T>(
    f: impl FnOnce(&IAudioEndpointVolume) -> windows::core::Result<T>,
) -> Option<T> {
    unsafe {
        // Commands run on arbitrary threads; each call initializes COM (MTA).
        let _ = CoInitializeEx(None, COINIT_MULTITHREADED);
        let enumerator: IMMDeviceEnumerator =
            CoCreateInstance(&MMDeviceEnumerator, None, CLSCTX_ALL).ok()?;
        let device = enumerator.GetDefaultAudioEndpoint(eRender, eConsole).ok()?;
        let endpoint: IAudioEndpointVolume = device.Activate(CLSCTX_ALL, None).ok()?;
        f(&endpoint).ok()
    }
}

/// Master volume as 0.0..=1.0
pub fn get() -> Option<f32> {
    with_endpoint(|ep| unsafe { ep.GetMasterVolumeLevelScalar() })
}

pub fn set(v: f32) {
    with_endpoint(|ep| unsafe {
        ep.SetMasterVolumeLevelScalar(v.clamp(0.0, 1.0), std::ptr::null())
    });
}
