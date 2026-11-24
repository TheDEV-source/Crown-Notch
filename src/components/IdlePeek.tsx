import { useEffect, useState } from "react";
import type { MediaPayload, TelemetryPayload } from "../types";

/** Minimal live audio equalizer visualizer (CSS keyframes, GPU-cheap). */
export function Equalizer({ playing }: { playing: boolean }) {
  return (
    <div className="flex h-3.5 items-end gap-[2.5px]">
      {[0.55, 0.95, 0.7, 1, 0.8].map((_, i) => (
        <span
          key={i}
          className="eq-bar w-[2.5px] rounded-full bg-indigo-300/80"
          style={{
            height: "100%",
            animationDelay: `${i * 0.13}s`,
            animationPlayState: playing ? "running" : "paused",
            transform: playing ? undefined : "scaleY(0.25)",
          }}
        />
      ))}
    </div>
  );
}

/** Minimal battery / status dot shown on the right of the idle pill. */
export function StatusDot({ battery }: { battery: number | null }) {
  if (battery === null) {
    return <span className="h-1.5 w-1.5 rounded-full bg-neutral-500" />;
  }
  const color =
    battery > 20 ? "bg-emerald-400" : battery > 10 ? "bg-amber-400" : "bg-rose-400";
  return (
    <span className="flex items-center gap-1.5">
      <span className={`h-1.5 w-1.5 rounded-full ${color}`} />
      <span className="text-[10px] tabular-nums text-neutral-400">
        {Math.round(battery)}%
      </span>
    </span>
  );
}

/** State 1 — idle / collapsed pill: clock left, equalizer or status dot right. */
export function IdleContent({
  media,
  telemetry,
}: {
  media: MediaPayload;
  telemetry: TelemetryPayload;
}) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  const time = now.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

  return (
    <div className="flex h-full w-full items-center justify-between px-3.5 text-[11px] text-neutral-200">
      <span className="font-medium tabular-nums">{time}</span>
      {media.available && media.isPlaying ? (
        <Equalizer playing />
      ) : (
        <StatusDot battery={telemetry.battery} />
      )}
    </div>
  );
}

/** State 2 — hover / compact peek: media track or quick system telemetry. */
export function PeekContent({
  media,
  telemetry,
}: {
  media: MediaPayload;
  telemetry: TelemetryPayload;
}) {
  if (media.available) {
    return (
      <div className="flex h-full w-full items-center gap-2.5 px-3">
        {media.artBase64 ? (
          <img
            src={`data:image/jpeg;base64,${media.artBase64}`}
            alt=""
            className="h-6 w-6 shrink-0 rounded-md object-cover"
          />
        ) : (
          <div className="h-6 w-6 shrink-0 rounded-md bg-neutral-800" />
        )}
        <div className="min-w-0 flex-1 fade-mask">
          <div className="truncate text-[11px] font-medium leading-tight text-neutral-100">
            {media.title || "Nothing playing"}
          </div>
          <div className="truncate text-[9.5px] leading-tight text-neutral-400">
            {media.artist}
          </div>
        </div>
        {media.isPlaying && <Equalizer playing />}
      </div>
    );
  }

  return (
    <div className="flex h-full w-full items-center gap-3 px-3.5 text-[10.5px] tabular-nums text-neutral-300">
      <span className="flex items-center gap-1.5">
        <span className="h-1.5 w-1.5 rounded-full bg-indigo-400" />
        CPU {Math.round(telemetry.cpu)}%
      </span>
      <span className="h-3 w-px bg-white/10" />
      <span className="flex items-center gap-1.5">
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
        RAM {Math.round(telemetry.ram)}%
      </span>
    </div>
  );
}
