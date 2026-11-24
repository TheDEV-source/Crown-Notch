import { AnimatePresence, motion } from "framer-motion";
import { SPRING, SIZES, type NotchState } from "../lib/motion";
import type { MediaPayload, TelemetryPayload } from "../types";
import { Equalizer, StatusDot, IdleContent, PeekContent } from "./IdlePeek";
import { MediaPanel, SystemPanel, UtilityBar } from "./Panels";

interface NotchShellProps {
  state: NotchState;
  hidden: boolean;
  media: MediaPayload;
  telemetry: TelemetryPayload;
  volume: number;
  brightness: number | null;
  awake: boolean;
  shelf: string[];
  pomodoro: { remaining: number; running: boolean };
  onEnter: () => void;
  onLeave: () => void;
  onClick: () => void;
  onPlayPause: () => void;
  onNext: () => void;
  onPrev: () => void;
  onVolume: (pct: number) => void;
  onBrightness: (v: number) => void;
  onToggleAwake: () => void;
  onTogglePomodoro: () => void;
  onOpenFile: (path: string) => void;
  onRemoveFile: (path: string) => void;
  onClearShelf: () => void;
}

/**
 * The morphing notch container. Width/height interpolate with the shared
 * spring so all three states (idle pill -> peek -> command center) morph
 * without layout jitter. Border radius is constant (flat top, 18px bottom)
 * because it fuses with the screen bezel in every state.
 */
export function NotchShell(props: NotchShellProps) {
  const { state, hidden } = props;
  const size = SIZES[state];

  return (
    <motion.div
      className="notch-glass fixed left-1/2 top-0 z-50 overflow-hidden"
      initial={false}
      animate={{
        x: "-50%",
        y: hidden ? -(size.h + 30) : 0,
        opacity: hidden ? 0 : 1,
        width: size.w,
        height: size.h,
      }}
      transition={SPRING}
      onMouseEnter={props.onEnter}
      onMouseLeave={props.onLeave}
      onClick={props.onClick}
    >
      <AnimatePresence mode="popLayout" initial={false}>
        <motion.div
          key={state}
          className="h-full w-full"
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.98 }}
          transition={{ duration: 0.14 }}
        >
          {state === "idle" && (
            <IdleContent media={props.media} telemetry={props.telemetry} />
          )}
          {state === "peek" && (
            <PeekContent media={props.media} telemetry={props.telemetry} />
          )}
          {state === "expanded" && (
            <div className="flex h-full w-full flex-col gap-2 p-3">
              <MediaPanel
                media={props.media}
                onPlayPause={props.onPlayPause}
                onNext={props.onNext}
                onPrev={props.onPrev}
              />
              <SystemPanel
                volume={props.volume}
                brightness={props.brightness}
                awake={props.awake}
                onVolume={props.onVolume}
                onBrightness={props.onBrightness}
                onToggleAwake={props.onToggleAwake}
              />
              <UtilityBar
                telemetry={props.telemetry}
                pomodoro={props.pomodoro}
                shelf={props.shelf}
                onTogglePomodoro={props.onTogglePomodoro}
                onOpenFile={props.onOpenFile}
                onRemoveFile={props.onRemoveFile}
                onClearShelf={props.onClearShelf}
              />
            </div>
          )}
        </motion.div>
      </AnimatePresence>
    </motion.div>
  );
}

export { Equalizer, StatusDot };
