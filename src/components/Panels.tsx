import {
  Coffee,
  Cpu,
  File,
  Pause,
  Play,
  SkipBack,
  SkipForward,
  Sun,
  Timer,
  Trash2,
  Volume2,
  X,
} from "lucide-react";
import type { MediaPayload, TelemetryPayload } from "../types";

function fmt(secs: number): string {
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

/* ================= State 3 — Top row: SMTC media controller ================= */

export function MediaPanel({
  media,
  onPlayPause,
  onNext,
  onPrev,
}: {
  media: MediaPayload;
  onPlayPause: () => void;
  onNext: () => void;
  onPrev: () => void;
}) {
  const pct =
    media.durationMs > 0
      ? Math.min(100, (media.positionMs / media.durationMs) * 100)
      : 0;

  return (
    <div className="flex items-center gap-3">
      {media.artBase64 ? (
        <img
          src={`data:image/jpeg;base64,${media.artBase64}`}
          alt=""
          className="glow-art h-11 w-11 shrink-0 rounded-lg object-cover"
        />
      ) : (
        <div className="h-11 w-11 shrink-0 rounded-lg bg-neutral-800" />
      )}
      <div className="min-w-0 flex-1">
        <div className="truncate text-[12px] font-medium text-neutral-100 fade-mask">
          {media.available ? media.title || "Nothing playing" : "Nothing playing"}
        </div>
        <div className="truncate text-[10px] text-neutral-400 fade-mask">
          {media.available ? media.artist : "Open a media app to control it here"}
        </div>
        <div
          className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-white/10"
          title="Seek position follows the system media clock"
        >
          <div
            className="h-full rounded-full bg-indigo-400/90 transition-[width] duration-700 ease-linear"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
      <div className="flex items-center gap-1.5 text-neutral-300">
        <button
          onClick={(e) => {
            e.stopPropagation();
            onPrev();
          }}
          className="rounded-lg p-1.5 transition hover:bg-white/10 hover:text-white"
          title="Previous"
        >
          <SkipBack size={14} />
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onPlayPause();
          }}
          className="rounded-full bg-white/10 p-2 transition hover:bg-white/20 hover:text-white"
          title="Play / Pause"
        >
          {media.isPlaying ? <Pause size={15} /> : <Play size={15} />}
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onNext();
          }}
          className="rounded-lg p-1.5 transition hover:bg-white/10 hover:text-white"
          title="Next"
        >
          <SkipForward size={14} />
        </button>
      </div>
    </div>
  );
}

/* ============ State 3 — Middle row: volume, brightness, keep awake ============ */

export function SystemPanel({
  volume,
  brightness,
  awake,
  onVolume,
  onBrightness,
  onToggleAwake,
}: {
  volume: number;
  brightness: number | null;
  awake: boolean;
  onVolume: (pct: number) => void;
  onBrightness: (v: number) => void;
  onToggleAwake: () => void;
}) {
  return (
    <div className="flex items-center gap-2 rounded-xl bg-white/[0.04] px-2.5 py-2">
      <Volume2 size={13} className="shrink-0 text-neutral-400" />
      <input
        type="range"
        min={0}
        max={100}
        value={volume}
        onChange={(e) => onVolume(Number(e.target.value))}
        onClick={(e) => e.stopPropagation()}
        className="notch-slider w-[80px]"
        title={`Master volume ${volume}%`}
      />
      <Sun size={13} className="ml-1 shrink-0 text-neutral-400" />
      <input
        type="range"
        min={1}
        max={100}
        value={brightness ?? 0}
        disabled={brightness === null}
        onChange={(e) => onBrightness(Number(e.target.value))}
        onClick={(e) => e.stopPropagation()}
        className="notch-slider w-[80px]"
        title={
          brightness === null
            ? "No internal display brightness sensor found"
            : `Brightness ${brightness}%`
        }
      />
      <button
        onClick={(e) => {
          e.stopPropagation();
          onToggleAwake();
        }}
        className={`ml-auto flex shrink-0 items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[10.5px] font-medium transition ${
          awake
            ? "bg-indigo-500/25 text-indigo-200 shadow-[inset_0_0_0_1px_rgba(129,140,248,0.4)]"
            : "bg-white/[0.06] text-neutral-300 hover:bg-white/10"
        }`}
        title="Keep the display and system awake while toggled"
      >
        <Coffee size={12} />
        Awake
      </button>
    </div>
  );
}

/* ======== State 3 — Bottom row: telemetry pill, pomodoro, file shelf ======== */

export function UtilityBar({
  telemetry,
  pomodoro,
  shelf,
  onTogglePomodoro,
  onOpenFile,
  onRemoveFile,
  onClearShelf,
}: {
  telemetry: TelemetryPayload;
  pomodoro: { remaining: number; running: boolean };
  shelf: string[];
  onTogglePomodoro: () => void;
  onOpenFile: (path: string) => void;
  onRemoveFile: (path: string) => void;
  onClearShelf: () => void;
}) {
  const fresh = pomodoro.remaining === 25 * 60 && !pomodoro.running;

  return (
    <div className="mt-auto flex items-center gap-2">
      <div className="flex shrink-0 items-center gap-2 rounded-lg bg-white/[0.05] px-2.5 py-1.5 text-[10px] tabular-nums text-neutral-300">
        <Cpu size={11} className="text-indigo-300" />
        {Math.round(telemetry.cpu)}%
        <span className="h-2.5 w-px bg-white/10" />
        RAM {Math.round(telemetry.ram)}%
        {telemetry.battery !== null && (
          <>
            <span className="h-2.5 w-px bg-white/10" />
            {Math.round(telemetry.battery)}%
          </>
        )}
      </div>

      <button
        onClick={(e) => {
          e.stopPropagation();
          onTogglePomodoro();
        }}
        className={`flex shrink-0 items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[10.5px] font-medium tabular-nums transition ${
          pomodoro.running
            ? "bg-emerald-500/20 text-emerald-200"
            : "bg-white/[0.06] text-neutral-300 hover:bg-white/10"
        }`}
        title="1-click Pomodoro focus timer (25:00)"
      >
        <Timer size={12} className={pomodoro.running ? "animate-pulse" : ""} />
        {fresh ? "25:00" : fmt(pomodoro.remaining)}
      </button>

      <div className="no-scrollbar flex min-w-0 flex-1 items-center gap-1 overflow-x-auto">
        {shelf.map((path) => {
          const name = path.split(/[\\/]/).pop() ?? path;
          return (
            <span
              key={path}
              className="flex shrink-0 items-center gap-0.5 rounded-md bg-white/[0.06] pl-1.5 pr-0.5 py-1 text-[10px] text-neutral-300"
            >
              <File size={10} className="text-neutral-500" />
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onOpenFile(path);
                }}
                onDoubleClick={(e) => {
                  e.stopPropagation();
                  onRemoveFile(path);
                }}
                className="max-w-[84px] truncate hover:text-white"
                title={`Open ${path}\n(Double-click to remove)`}
              >
                {name}
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onRemoveFile(path);
                }}
                className="rounded p-0.5 text-neutral-500 hover:bg-white/10 hover:text-white"
                title="Remove from shelf"
              >
                <X size={9} />
              </button>
            </span>
          );
        })}
      </div>

      {shelf.length > 0 && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onClearShelf();
          }}
          className="shrink-0 rounded-md p-1 text-neutral-500 hover:bg-white/10 hover:text-white"
          title="Clear file shelf"
        >
          <Trash2 size={11} />
        </button>
      )}
      {shelf.length === 0 && (
        <span className="truncate text-[9.5px] text-neutral-600">
          Drop files here to shelve them
        </span>
      )}
    </div>
  );
}
