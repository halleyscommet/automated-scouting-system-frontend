// ── Model ─────────────────────────────────────────────────────────────────────

export interface ModelInfo {
  name: string;
  size_mb: number;
}

// ── TBA ───────────────────────────────────────────────────────────────────────

export interface TBAEvent {
  key: string;
  name: string;
  event_code: string;
  start_date: string;
  city: string;
  state_prov: string;
  country: string;
}

export interface TBAMatch {
  key: string;
  comp_level: "qm" | "ef" | "qf" | "sf" | "f";
  match_number: number;
  set_number: number;
  videos: { type: string; key: string }[];
  alliances: {
    red: { team_keys: string[]; score: number };
    blue: { team_keys: string[]; score: number };
  };
}

// ── Video ─────────────────────────────────────────────────────────────────────

export interface VideoInfo {
  fps: number;
  total_frames: number;
  width: number;
  height: number;
  duration: number;
}

export interface HLSInfo {
  hls_url: string;
  match_key: string;
}

export interface DownloadJob {
  job_id: string;
  match_key: string;
  status: "pending" | "downloading" | "converting" | "completed" | "failed";
  progress: number;
  error: string | null;
}

// ── Annotation ────────────────────────────────────────────────────────────────

export interface BBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface Detection {
  class_id: number;
  class_name: "robot" | "ball";
  confidence: number;
  bbox: BBox;
}

export interface DetectFrameResult {
  frame_number: number;
  frame_image: string; // base64 JPEG
  detections: Detection[];
  frame_width: number;
  frame_height: number;
}

export type Alliance = "red" | "blue";

export interface RobotAnnotation {
  team_number: number;
  alliance: Alliance;
  bbox: BBox;
}

export interface HubZone {
  alliance: Alliance;
  bbox: BBox;
}

// ── Tracking ──────────────────────────────────────────────────────────────────

export interface TrackingJob {
  job_id: string;
  status: "pending" | "running" | "paused_reidentify" | "completed" | "failed";
  progress: number;
  current_frame: number | null;
  total_frames: number | null;
  error: string | null;
  result_id?: string | null;
}

export interface WsProgress {
  type: "progress";
  progress: number;
  frame: number;
  total_frames: number;
}

export interface WsCompleted {
  type: "completed";
  job_id: string;
  result_id: string;
}

export interface WsError {
  type: "error";
  job_id: string;
  message: string;
}

export interface ActiveTrack {
  track_id: number;
  team_number: number;
  alliance: Alliance;
  bbox: BBox;
}

export interface WsReidentify {
  type: "reidentify_needed";
  job_id: string;
  lost_team: number;
  lost_alliance: Alliance;
  frame_number: number;
  frame_image: string; // base64 JPEG
  frame_width: number;
  frame_height: number;
  last_known_bbox?: BBox | null;
  active_tracks: ActiveTrack[];
}

export type WsMessage = WsProgress | WsCompleted | WsError | WsReidentify;

// ── Results ───────────────────────────────────────────────────────────────────

export interface RobotResult {
  alliance: Alliance;
  score: number;
  heatmap_url: string;
  position_count: number;
}

export interface TrackingResult {
  result_id: string;
  job_id: string;
  match_key: string;
  model_name: string;
  timestamp: string;
  scoring: {
    red: Record<string, number>;
    blue: Record<string, number>;
  };
  robots: Record<string, RobotResult>;
  hub_zones: HubZone[];
  extra_scoring: Record<string, unknown>;
}

export interface ResultSummary {
  result_id: string;
  match_key: string;
  timestamp: string;
  scoring: TrackingResult["scoring"];
}
