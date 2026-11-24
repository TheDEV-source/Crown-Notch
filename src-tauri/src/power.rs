//! "Keep Awake" toggle via `SetThreadExecutionState`.
//!
//! ES_CONTINUOUS state is per-thread, so a dedicated keeper thread owns it and
//! refreshes periodically; the toggle just flips a flag.

use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;
use windows::Win32::System::Power::{
    SetThreadExecutionState, ES_CONTINUOUS, ES_DISPLAY_REQUIRED, ES_SYSTEM_REQUIRED,
};

static AWAKE: AtomicBool = AtomicBool::new(false);

pub fn set_awake(on: bool) {
    AWAKE.store(on, Ordering::Relaxed);
    start_keeper();
}

fn start_keeper() {
    use std::sync::Once;
    static ONCE: Once = Once::new();
    ONCE.call_once(|| {
        std::thread::spawn(|| {
            let mut active = false;
            loop {
                std::thread::sleep(Duration::from_secs(2));
                let want = AWAKE.load(Ordering::Relaxed);
                unsafe {
                    if want {
                        let _ = SetThreadExecutionState(
                            ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED,
                        );
                        active = true;
                    } else if active {
                        // clear the keep-awake flags set on this thread
                        let _ = SetThreadExecutionState(ES_CONTINUOUS);
                        active = false;
                    }
                }
            }
        });
    });
}
