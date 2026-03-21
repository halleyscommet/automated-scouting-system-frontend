import type {
  ModelInfo,
  TBAEvent,
  TBAMatch,
  VideoInfo,
  HLSInfo,
  DownloadJob,
  DetectFrameResult,
  TrackingResult,
  ResultSummary,
} from "./types";

const BASE = "http://localhost:8000/api";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail ?? res.statusText);
  }
  return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
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
      const res = await fetch(`${BASE}/models/upload`, { method: "POST", body: form });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(detail.detail ?? res.statusText);
      }
      return res.json();
    },
    delete: (name: string) =>
      fetch(`${BASE}/models/${encodeURIComponent(name)}`, { method: "DELETE" }),
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
      `http://localhost:8000/api/video/frame/${matchKey}/${frame}`,
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
    wsUrl: (jobId: string) => `ws://localhost:8000/api/tracking/ws/${jobId}`,
  },

  // ── Results ──────────────────────────────────────────────────────────────────

  results: {
    list: () => get<ResultSummary[]>("/results/"),
    get: (resultId: string) => get<TrackingResult>(`/results/${resultId}`),
    heatmapUrl: (resultId: string, team: number) =>
      `http://localhost:8000/results-static/${resultId}/heatmap_${team}.png`,
    delete: (resultId: string) =>
      fetch(`${BASE}/results/${encodeURIComponent(resultId)}`, { method: "DELETE" }),
  },
};
