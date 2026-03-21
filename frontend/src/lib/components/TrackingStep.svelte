<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { api } from "../api";
  import {
    step,
    selectedMatch,
    robotModel,
    ballModel,
    annotationFrame,
    robotAnnotations,
    hubZones,
    trackingJobId,
    currentResult,
  } from "../store";
  import type { WsMessage, WsReidentify, RobotAnnotation, HubZone } from "../types";
  import ReidentifyModal from "./ReidentifyModal.svelte";

  // ── Stores ────────────────────────────────────────────────────────────────────

  let matchKey = "";
  selectedMatch.subscribe((m) => (matchKey = m?.key ?? ""));
  let robotModelName = "";
  robotModel.subscribe((m) => (robotModelName = m?.name ?? ""));
  let ballModelName: string | null = null;
  ballModel.subscribe((m) => (ballModelName = m?.name ?? null));
  let frameNumber = 0;
  annotationFrame.subscribe((f) => (frameNumber = f));
  let robots: RobotAnnotation[] = [];
  robotAnnotations.subscribe((r) => (robots = r));
  let hubs: HubZone[] = [];
  hubZones.subscribe((h) => (hubs = h));

  // ── State ─────────────────────────────────────────────────────────────────────

  let status = "";
  let progress = 0;
  let currentFrame: number | null = null;
  let totalFrames: number | null = null;
  let error = "";

  let ws: WebSocket | null = null;
  let reidentifyEvent: WsReidentify | null = null;

  // ── Lifecycle ─────────────────────────────────────────────────────────────────

  onMount(async () => {
    await launchTracking();
  });

  onDestroy(() => ws?.close());

  async function launchTracking() {
    status = "Starting tracking job…";
    error = "";
    try {
      const { job_id } = await api.tracking.start({
        match_key: matchKey,
        robot_model: robotModelName,
        ball_model: ballModelName,
        first_frame: frameNumber,
        robots,
        hub_zones: hubs,
      });
      trackingJobId.set(job_id);
      openWebSocket(job_id);
    } catch (e: any) {
      error = e.message;
      status = "Failed to start";
    }
  }

  function openWebSocket(jobId: string) {
    ws = new WebSocket(api.tracking.wsUrl(jobId));
    status = "Connected — tracking in progress…";

    ws.onmessage = (evt) => {
      const msg: WsMessage = JSON.parse(evt.data);
      handleMessage(msg);
    };

    ws.onerror = () => {
      error = "WebSocket connection lost.";
    };

    ws.onclose = () => {
      if (status !== "completed" && !error) {
        status = "Connection closed.";
      }
    };
  }

  function handleMessage(msg: WsMessage) {
    if (msg.type === "progress") {
      progress = msg.progress;
      currentFrame = msg.frame;
      totalFrames = msg.total_frames;
      status = `Processing frame ${msg.frame} / ${msg.total_frames}…`;
    } else if (msg.type === "completed") {
      progress = 100;
      status = "completed";
      ws?.close();
      loadResult(msg.result_id);
    } else if (msg.type === "error") {
      error = msg.message;
      status = "failed";
    } else if (msg.type === "reidentify_needed") {
      reidentifyEvent = msg;
    }
  }

  function resolveReidentify(response: { new_track_id?: number | null; drawn_bbox?: import("../types").BBox }) {
    if (!ws || !reidentifyEvent) return;
    ws.send(
      JSON.stringify({
        type: "reidentify_response",
        ...response,
      })
    );
    reidentifyEvent = null;
  }

  async function loadResult(resultId: string) {
    try {
      const result = await api.results.get(resultId);
      currentResult.set(result);
      step.set("results");
    } catch (e: any) {
      error = `Tracking done but failed to load results: ${e.message}`;
    }
  }

  $: etaPct = Math.min(100, progress);
  $: isRunning = status !== "completed" && status !== "failed" && !error;
</script>

<!-- ── Modal overlay ──────────────────────────────────────────────────────── -->
{#if reidentifyEvent}
  <ReidentifyModal event={reidentifyEvent} onResolve={resolveReidentify} />
{/if}

<!-- ── Main UI ──────────────────────────────────────────────────────────────── -->
<div class="tracking-step">
  <h2>Tracking in Progress</h2>

  <div class="card">
    <div class="progress-bar">
      <div class="progress-fill" style="width:{etaPct}%"></div>
    </div>
    <p class="progress-label">{etaPct.toFixed(1)}%</p>

    <p class="status-line">
      {#if isRunning}
        <span class="spinner"></span>
      {/if}
      {status}
    </p>

    {#if currentFrame !== null && totalFrames !== null}
      <p class="muted">Frame {currentFrame} / {totalFrames}</p>
    {/if}

    {#if error}
      <p class="error">{error}</p>
    {/if}
  </div>

  {#if !isRunning && !error}
    <p class="muted">Processing complete — loading results…</p>
  {/if}
</div>

<style>
  .tracking-step {
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
    max-width: 540px;
  }

  h2 {
    font-size: 1.5rem;
    margin: 0;
  }

  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1.25rem 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
  }

  .progress-bar {
    height: 10px;
    background: var(--border);
    border-radius: 5px;
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    background: var(--accent);
    transition: width 0.5s ease;
  }

  .progress-label {
    font-size: 1.1rem;
    font-weight: 700;
    margin: 0;
    color: var(--accent);
  }

  .status-line {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.9rem;
    margin: 0;
  }

  /* CSS spinner */
  .spinner {
    display: inline-block;
    width: 14px;
    height: 14px;
    border: 2px solid var(--border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
    flex-shrink: 0;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .muted {
    color: var(--text-muted);
    font-size: 0.85rem;
    margin: 0;
  }

  .error {
    color: var(--error);
    font-size: 0.85rem;
    margin: 0;
  }
</style>
