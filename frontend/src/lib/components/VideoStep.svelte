<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import Hls from "hls.js";
  import { api } from "../api";
  import {
    step,
    selectedMatch,
    robotModel,
    videoInfo,
    annotationFrame,
  } from "../store";
  import type { VideoInfo } from "../types";

  // ── State ──────────────────────────────────────────────────────────────────────

  let info: VideoInfo | null = null;
  videoInfo.subscribe((v) => (info = v));

  let matchKey = "";
  selectedMatch.subscribe((m) => (matchKey = m?.key ?? ""));

  // robotModel imported but currently unused in VideoStep;
  // kept in case model info is needed for display later.
  let _robotModelName = "";
  robotModel.subscribe((m) => (_robotModelName = m?.name ?? ""));

  let videoEl: HTMLVideoElement;
  let hls: Hls | null = null;

  // Frame stepping state
  let currentFrame = 0;
  let frameUrl = "";
  let stepMode = false;
  let loadingFrame = false;

  // ── HLS setup ─────────────────────────────────────────────────────────────────

  onMount(async () => {
    if (!matchKey) return;
    try {
      const hlsInfo = await api.video.hls(matchKey);
      initHls(hlsInfo.hls_url);
    } catch {
      // HLS not ready (shouldn't happen if setup completed)
    }
  });

  onDestroy(() => hls?.destroy());

  function initHls(src: string) {
    if (!videoEl) return;
    if (Hls.isSupported()) {
      hls = new Hls();
      hls.loadSource(api.video.hlsPlaybackUrl(src));
      hls.attachMedia(videoEl);
    } else if (videoEl.canPlayType("application/vnd.apple.mpegurl")) {
      videoEl.src = api.video.hlsPlaybackUrl(src);
    }
  }

  // ── Frame stepping ────────────────────────────────────────────────────────────

  function enterStepMode() {
    if (!info) return;
    // Sync frame from video's current time
    currentFrame = videoEl
      ? Math.floor(videoEl.currentTime * (info.fps || 30))
      : 0;
    stepMode = true;
    loadFrame(currentFrame);
  }

  function exitStepMode() {
    stepMode = false;
    frameUrl = "";
    // Resume the HLS player at the equivalent time
    if (videoEl && info) {
      videoEl.currentTime = currentFrame / info.fps;
    }
  }

  async function loadFrame(n: number) {
    if (!info) return;
    currentFrame = Math.max(0, Math.min(n, info.total_frames - 1));
    loadingFrame = true;
    frameUrl = api.video.frameUrl(matchKey, currentFrame);
    loadingFrame = false;
  }

  function prevFrame() {
    loadFrame(currentFrame - 1);
  }
  function nextFrame() {
    loadFrame(currentFrame + 1);
  }

  function handleKeydown(e: KeyboardEvent) {
    if (!stepMode) return;
    if (e.key === "ArrowLeft") prevFrame();
    if (e.key === "ArrowRight") nextFrame();
  }

  // ── Annotate ──────────────────────────────────────────────────────────────────

  function goAnnotate() {
    annotationFrame.set(currentFrame);
    step.set("annotate");
  }

  $: frameDisplay = info ? `Frame ${currentFrame} / ${info.total_frames - 1}` : "";
</script>

<svelte:window on:keydown={handleKeydown} />

<div class="video-step">
  <h2>Select Frame to Annotate</h2>

  {#if !stepMode}
    <!-- HLS player -->
    <div class="player-wrap">
      <!-- svelte-ignore a11y-media-has-caption -->
      <video bind:this={videoEl} controls class="video-player"></video>
    </div>
    <div class="controls">
      {#if info}
        <p class="muted">
          {info.total_frames} frames · {info.fps.toFixed(2)} fps ·
          {(info.duration / 60).toFixed(1)} min
        </p>
      {/if}
      <button class="btn-secondary" on:click={enterStepMode}>
        Switch to Frame-by-Frame Mode →
      </button>
    </div>
  {:else}
    <!-- Frame viewer -->
    <div class="frame-wrap">
      {#if frameUrl}
        <img src={frameUrl} alt="Frame {currentFrame}" class="frame-img" />
      {:else}
        <div class="frame-placeholder">Loading…</div>
      {/if}
    </div>

    <div class="frame-controls">
      <button class="btn-icon" on:click={prevFrame} disabled={currentFrame === 0}>◀</button>
      <input
        type="number"
        min="0"
        max={info ? info.total_frames - 1 : 0}
        bind:value={currentFrame}
        on:change={() => loadFrame(currentFrame)}
        class="frame-input"
      />
      <button class="btn-icon" on:click={nextFrame} disabled={!info || currentFrame >= info.total_frames - 1}>▶</button>
      <span class="muted">{frameDisplay}</span>
    </div>

    <p class="hint">Use ◀ ▶ arrow keys or buttons to step through frames.</p>

    <div class="step-actions">
      <button class="btn-secondary" on:click={exitStepMode}>← Back to Video</button>
      <button class="btn-primary" on:click={goAnnotate}>
        All Robots Visible — Annotate This Frame →
      </button>
    </div>
  {/if}
</div>

<style>
  .video-step {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    max-width: 900px;
  }

  h2 {
    font-size: 1.5rem;
    margin: 0;
  }

  .player-wrap {
    background: #000;
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid var(--border);
  }

  .video-player {
    width: 100%;
    max-height: 540px;
    display: block;
  }

  .frame-wrap {
    background: #000;
    border-radius: 8px;
    border: 1px solid var(--border);
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 400px;
  }

  .frame-img {
    max-width: 100%;
    max-height: 540px;
    display: block;
  }

  .frame-placeholder {
    color: var(--text-muted);
    font-size: 1rem;
  }

  .frame-controls {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .frame-input {
    width: 90px;
    background: var(--bg);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.35rem 0.5rem;
    font-size: 0.95rem;
    text-align: center;
  }

  .btn-icon {
    background: var(--surface);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.35rem 0.75rem;
    font-size: 1rem;
    cursor: pointer;
  }

  .btn-icon:disabled {
    opacity: 0.3;
    cursor: not-allowed;
  }

  .controls {
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .step-actions {
    display: flex;
    gap: 0.75rem;
    align-items: center;
  }

  .btn-primary {
    background: var(--accent);
    color: #000;
    border: none;
    border-radius: 6px;
    padding: 0.55rem 1.2rem;
    font-size: 0.95rem;
    font-weight: 700;
    cursor: pointer;
  }

  .btn-secondary {
    background: var(--surface);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.5rem 1rem;
    font-size: 0.9rem;
    cursor: pointer;
  }

  .muted {
    color: var(--text-muted);
    font-size: 0.85rem;
  }

  .hint {
    color: var(--text-muted);
    font-size: 0.8rem;
    margin: 0;
  }
</style>
