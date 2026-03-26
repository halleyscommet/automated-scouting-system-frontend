import type {
  ModelInfo,
  TBAEvent,
  TBAMatch,
  VideoInfo,
  HLSInfo,
  DownloadJob,
  DetectFrameResult,
  TrackingJob,
  TrackingResult,
  ResultSummary,
} from "./types";

const DEFAULT_API_ORIGIN = "http://localhost:8000";
const API_ORIGIN_KEY = "seer-api-origin-v1";

function normalizeOrigin(value: string): string {
  const trimmed = value.trim().replace(/\/+$/, "");
  if (!trimmed) return DEFAULT_API_ORIGIN;
  if (!/^https?:\/\//i.test(trimmed)) {
    throw new Error("API origin must start with http:// or https://");
  }
  try {
    const url = new URL(trimmed);
    return url.origin;
  } catch {
    throw new Error("Invalid API origin URL");
  }
}

function readStoredOrigin(): string {
  if (typeof localStorage === "undefined") return DEFAULT_API_ORIGIN;
  const raw = localStorage.getItem(API_ORIGIN_KEY);
  if (!raw) return DEFAULT_API_ORIGIN;
  try {
    return normalizeOrigin(raw);
  } catch {
    return DEFAULT_API_ORIGIN;
  }
}

let apiOrigin = readStoredOrigin();

export function getApiOrigin(): string {
  return apiOrigin;
}

export function setApiOrigin(nextOrigin: string): string {
  const normalized = normalizeOrigin(nextOrigin);
  apiOrigin = normalized;
  if (typeof localStorage !== "undefined") {
    localStorage.setItem(API_ORIGIN_KEY, normalized);
  }
  return normalized;
}

function apiPath(path: string): string {
  return `/api${path}`;
}

function apiUrl(path: string): string {
  return `${apiOrigin}${apiPath(path)}`;
}

export function backendUrl(path: string): string {
  return `${apiOrigin}${path}`;
}

function wsUrl(path: string): string {
  const protocol = apiOrigin.startsWith("https://") ? "wss://" : "ws://";
  const host = apiOrigin.replace(/^https?:\/\//, "");
  return `${protocol}${host}${apiPath(path)}`;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(apiUrl(path));
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail ?? res.statusText);
  }
  return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(apiUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail ?? res.statusText);
  }
  return res.json();
}

// ── Models ────────────────────────────────────────────────────────────────────

export const api = {
  models: {
    list: () => get<ModelInfo[]>("/models/"),
    upload: async (file: File): Promise<ModelInfo> => {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(apiUrl("/models/upload"), { method: "POST", body: form });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(detail.detail ?? res.statusText);
      }
      return res.json();
    },
    delete: (name: string) =>
      fetch(apiUrl(`/models/${encodeURIComponent(name)}`), { method: "DELETE" }),
  },

  // ── TBA ─────────────────────────────────────────────────────────────────────

  tba: {
    events: (year: number) => get<TBAEvent[]>(`/tba/events/${year}`),
    matches: (eventKey: string) => get<TBAMatch[]>(`/tba/event/${eventKey}/matches`),
    teams: (matchKey: string) =>
      get<{ red: string[]; blue: string[] }>(`/tba/match/${matchKey}/teams`),
  },

  // ── Video ────────────────────────────────────────────────────────────────────

  video: {
    download: (matchKey: string, youtubeKey: string) =>
      post<{ job_id: string }>("/video/download", {
        match_key: matchKey,
        youtube_key: youtubeKey,
      }),
    status: (jobId: string) => get<DownloadJob>(`/video/download-status/${jobId}`),
    info: (matchKey: string) => get<VideoInfo>(`/video/info/${matchKey}`),
    hls: (matchKey: string) => get<HLSInfo>(`/video/hls/${matchKey}`),
    frameUrl: (matchKey: string, frame: number) =>
      apiUrl(`/video/frame/${matchKey}/${frame}`),
    hlsPlaybackUrl: (path: string) => backendUrl(path),
  },

  // ── Tracking ─────────────────────────────────────────────────────────────────

  tracking: {
    detectFrame: (matchKey: string, robotModel: string, frameNumber: number) =>
      post<DetectFrameResult>("/tracking/detect-frame", {
        match_key: matchKey,
        robot_model: robotModel,
        frame_number: frameNumber,
      }),
    start: (body: {
      match_key: string;
      robot_model: string;
      ball_model?: string | null;
      first_frame: number;
      robots: unknown[];
      hub_zones: unknown[];
    }) => post<{ job_id: string }>("/tracking/start", body),
    status: (jobId: string) => get<TrackingJob>(`/tracking/status/${jobId}`),
    wsUrl: (jobId: string) => wsUrl(`/tracking/ws/${jobId}`),
  },

  // ── Results ──────────────────────────────────────────────────────────────────

  results: {
    list: () => get<ResultSummary[]>("/results/"),
    get: (resultId: string) => get<TrackingResult>(`/results/${resultId}`),
    heatmapUrl: (resultId: string, team: number) =>
      backendUrl(`/results-static/${resultId}/heatmap_${team}.png`),
    heatmapPathUrl: (heatmapPath: string) => backendUrl(heatmapPath),
    delete: (resultId: string) =>
      fetch(apiUrl(`/results/${encodeURIComponent(resultId)}`), { method: "DELETE" }),
  },
};
