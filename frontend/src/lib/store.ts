import { writable } from "svelte/store";
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

// ── Session state shared across all steps ─────────────────────────────────────

export const step = writable<AppStep>("setup");

export const robotModel = writable<ModelInfo | null>(null);
export const ballModel = writable<ModelInfo | null>(null);
export const selectedYear = writable<number>(new Date().getFullYear());
export const selectedEvent = writable<TBAEvent | null>(null);
export const selectedMatch = writable<TBAMatch | null>(null);

export const videoInfo = writable<VideoInfo | null>(null);
export const annotationFrame = writable<number>(0);

// Annotation data collected in the annotation step
export const robotAnnotations = writable<RobotAnnotation[]>([]);
export const hubZones = writable<HubZone[]>([]);

// Tracking job ID in-flight
export const trackingJobId = writable<string | null>(null);

// Final result from a completed tracking run
export const currentResult = writable<TrackingResult | null>(null);
