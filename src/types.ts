export interface MediaPayload {
  available: boolean;
  title: string;
  artist: string;
  album: string;
  artBase64: string | null;
  isPlaying: boolean;
  positionMs: number;
  durationMs: number;
}

export interface TelemetryPayload {
  cpu: number;
  ram: number;
  battery: number | null;
}
