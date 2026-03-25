import { writable, type Writable } from "svelte/store";
import type {
  ModelInfo,
  TBAEvent,
  TBAMatch,
  VideoInfo,
  RobotAnnotation,
  HubZone,
  TrackingResult,
} from "./types";

export type AppStep =
  | "setup"
  | "video"
  | "annotate"
  | "tracking"
  | "results";

const SESSION_KEY = "seer-session-v1";

interface SessionState {
  step: AppStep;
  robotModel: ModelInfo | null;
  ballModel: ModelInfo | null;
  selectedYear: number;
  selectedEvent: TBAEvent | null;
  selectedMatch: TBAMatch | null;
  videoInfo: VideoInfo | null;
  annotationFrame: number;
  robotAnnotations: RobotAnnotation[];
  hubZones: HubZone[];
  trackingJobId: string | null;
  currentResult: TrackingResult | null;
}

const defaultSession: SessionState = {
  step: "setup",
  robotModel: null,
  ballModel: null,
  selectedYear: new Date().getFullYear(),
  selectedEvent: null,
  selectedMatch: null,
  videoInfo: null,
  annotationFrame: 0,
  robotAnnotations: [],
  hubZones: [],
  trackingJobId: null,
  currentResult: null,
};

function loadSession(): SessionState {
  if (typeof localStorage === "undefined") return defaultSession;
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (!raw) return defaultSession;
    const parsed = JSON.parse(raw) as Partial<SessionState>;
    return { ...defaultSession, ...parsed };
  } catch {
    return defaultSession;
  }
}

const loaded = loadSession();

function createPersistedStore<K extends keyof SessionState>(
  key: K,
  initialValue: SessionState[K]
): Writable<SessionState[K]> {
  const store = writable<SessionState[K]>(initialValue);
  if (typeof localStorage !== "undefined") {
    store.subscribe((value) => {
      const base = loadSession();
      const next = { ...base, [key]: value };
      localStorage.setItem(SESSION_KEY, JSON.stringify(next));
    });
  }
  return store;
}

// ── Session state shared across all steps ─────────────────────────────────────

export const step = createPersistedStore("step", loaded.step);

export const robotModel = createPersistedStore("robotModel", loaded.robotModel);
export const ballModel = createPersistedStore("ballModel", loaded.ballModel);
export const selectedYear = createPersistedStore("selectedYear", loaded.selectedYear);
export const selectedEvent = createPersistedStore("selectedEvent", loaded.selectedEvent);
export const selectedMatch = createPersistedStore("selectedMatch", loaded.selectedMatch);

export const videoInfo = createPersistedStore("videoInfo", loaded.videoInfo);
export const annotationFrame = createPersistedStore("annotationFrame", loaded.annotationFrame);

// Annotation data collected in the annotation step
export const robotAnnotations = createPersistedStore("robotAnnotations", loaded.robotAnnotations);
export const hubZones = createPersistedStore("hubZones", loaded.hubZones);

// Tracking job ID in-flight
export const trackingJobId = createPersistedStore("trackingJobId", loaded.trackingJobId);

// Final result from a completed tracking run
export const currentResult = createPersistedStore("currentResult", loaded.currentResult);

export function resetSessionState() {
  if (typeof localStorage !== "undefined") {
    localStorage.removeItem(SESSION_KEY);
  }
  step.set(defaultSession.step);
  robotModel.set(defaultSession.robotModel);
  ballModel.set(defaultSession.ballModel);
  selectedYear.set(defaultSession.selectedYear);
  selectedEvent.set(defaultSession.selectedEvent);
  selectedMatch.set(defaultSession.selectedMatch);
  videoInfo.set(defaultSession.videoInfo);
  annotationFrame.set(defaultSession.annotationFrame);
  robotAnnotations.set(defaultSession.robotAnnotations);
  hubZones.set(defaultSession.hubZones);
  trackingJobId.set(defaultSession.trackingJobId);
  currentResult.set(defaultSession.currentResult);
}
