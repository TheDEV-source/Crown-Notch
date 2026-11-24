import { useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { getCurrentWebviewWindow } from "@tauri-apps/api/webviewWindow";
import { openPath } from "@tauri-apps/plugin-opener";
import { NotchShell } from "./components/NotchShell";
import { SIZES, type NotchState } from "./lib/motion";
import type { MediaPayload, TelemetryPayload } from "./types";

const EMPTY_MEDIA: MediaPayload = {
  available: false,
  title: "",
  artist: "",
  album: "",
  artBase64: null,
  isPlaying: false,
  positionMs: 0,
  durationMs: 0,
};

const POMODORO_SECS = 25 * 60;

export default function App() {
  const [state, setState] = useState<NotchState>("idle");
  const [hidden, setHidden] = useState(false); // fullscreen auto-hide
  const [media, setMedia] = useState<MediaPayload>(EMPTY_MEDIA);
  const [telemetry, setTelemetry] = useState<TelemetryPayload>({
    cpu: 0,
    ram: 0,
    battery: null,
  });
  const [volume, setVolume] = useState(50);
  const [brightness, setBrightness] = useState<number | null>(null);
  const [awake, setAwake] = useState(false);
  const [shelf, setShelf] = useState<string[]>([]);
  const [pomodoro, setPomodoro] = useState({
    remaining: POMODORO_SECS,
    running: false,
  });

  const hoverTimer = useRef<number | undefined>(undefined);
  const graceTimer = useRef<number | undefined>(undefined);

  // ---- Backend events + initial snapshots ----
  useEffect(() => {
    const unsubs: Array<Promise<() => void>> = [
      listen<MediaPayload>("notch://media", (e) => setMedia(e.payload)),
      listen<boolean>("notch://fullscreen", (e) => setHidden(e.payload)),
    ];
    invoke<MediaPayload>("get_media_snapshot").then(setMedia).catch(() => {});
    invoke<string[]>("get_shelf").then(setShelf).catch(() => {});
    return () => {
      unsubs.forEach((p) => p.then((u) => u()));
    };
  }, []);

  // ---- Report the active (interactive) notch rect to the native hit-tester.
  // Everything outside this rect passes mouse clicks through to windows below.
  useEffect(() => {
    const rect = hidden
      ? { x: 0, y: 0, width: 0, height: 0 }
      : {
          x: (window.innerWidth - SIZES[state].w) / 2,
          y: 0,
          width: SIZES[state].w,
          height: SIZES[state].h,
        };
    invoke("set_active_rect", rect).catch(() => {});
  }, [state, hidden]);

  // ---- Poll telemetry / volume / brightness ONLY while expanded (2s throttle)
  useEffect(() => {
    if (state !== "expanded") return;
    const pull = async () => {
      try {
        setTelemetry(await invoke<TelemetryPayload>("get_telemetry"));
        const v = await invoke<number>("get_volume");
        setVolume(Math.round(v * 100));
        const b = await invoke<number | null>("get_brightness");
        if (b !== null) setBrightness(b);
      } catch {
        /* backend unavailable; keep last values */
      }
    };
    pull();
    const id = setInterval(pull, 2000);
    return () => clearInterval(id);
  }, [state]);

  // ---- Pomodoro ticker ----
  useEffect(() => {
    if (!pomodoro.running) return;
    const id = setInterval(
      () =>
        setPomodoro((p) =>
          p.remaining <= 1
            ? { remaining: POMODORO_SECS, running: false }
            : { ...p, remaining: p.remaining - 1 },
        ),
      1000,
    );
    return () => clearInterval(id);
  }, [pomodoro.running]);

  // ---- Drag & drop file shelf ----
  useEffect(() => {
    const un = getCurrentWebviewWindow().onDragDropEvent(async (e) => {
      if (e.payload.type === "drop") {
        try {
          const paths = e.payload.paths;
          if (paths.length > 0) {
            setShelf(await invoke<string[]>("add_shelf_files", { paths }));
            setState("expanded");
          }
        } catch {
          /* ignore */
        }
      }
    });
    return () => {
      un.then((f) => f());
    };
  }, []);

  // ---- Pointer state machine ----
  const onEnter = () => {
    window.clearTimeout(graceTimer.current);
    window.clearTimeout(hoverTimer.current);
    // 150ms hover debounce before the compact peek
    if (state === "idle") {
      hoverTimer.current = window.setTimeout(
        () => setState((s) => (s === "idle" ? "peek" : s)),
        150,
      );
    }
  };

  const onLeave = () => {
    window.clearTimeout(hoverTimer.current);
    if (state === "peek") setState("idle");
    if (state === "expanded") {
      // 600ms grace period before the expanded panel collapses
      graceTimer.current = window.setTimeout(
        () => setState((s) => (s === "expanded" ? "idle" : s)),
        600,
      );
    }
  };

  const onClick = () => {
    window.clearTimeout(hoverTimer.current);
    window.clearTimeout(graceTimer.current);
    setState((s) => (s === "expanded" ? "idle" : "expanded"));
  };

  // ---- Command wrappers ----
  const setVolumePct = (pct: number) => {
    setVolume(pct);
    invoke("set_volume", { v: pct / 100 }).catch(() => {});
  };

  const setBrightnessVal = (val: number) => {
    const clamped = Math.max(1, Math.min(100, val));
    setBrightness(clamped);
    invoke("set_brightness", { v: clamped }).catch(() => {});
  };

  const toggleAwake = () => {
    const next = !awake;
    setAwake(next);
    invoke("set_awake", { on: next }).catch(() => {});
  };

  const togglePomodoro = () =>
    setPomodoro((p) => ({ ...p, running: !p.running }));

  const openShelfFile = (path: string) => {
    openPath(path).catch(() => {});
  };

  const removeShelfFile = async (path: string) => {
    try {
      setShelf(await invoke<string[]>("remove_shelf_file", { path }));
    } catch {
      /* ignore */
    }
  };

  const clearShelf = async () => {
    try {
      setShelf(await invoke<string[]>("clear_shelf"));
    } catch {
      /* ignore */
    }
  };

  return (
    <NotchShell
      state={state}
      hidden={hidden}
      media={media}
      telemetry={telemetry}
      volume={volume}
      brightness={brightness}
      awake={awake}
      shelf={shelf}
      pomodoro={pomodoro}
      onEnter={onEnter}
      onLeave={onLeave}
      onClick={onClick}
      onPlayPause={() => invoke("media_play_pause").catch(() => {})}
      onNext={() => invoke("media_next").catch(() => {})}
      onPrev={() => invoke("media_prev").catch(() => {})}
      onVolume={setVolumePct}
      onBrightness={setBrightnessVal}
      onToggleAwake={toggleAwake}
      onTogglePomodoro={togglePomodoro}
      onOpenFile={openShelfFile}
      onRemoveFile={removeShelfFile}
      onClearShelf={clearShelf}
    />
  );
}
