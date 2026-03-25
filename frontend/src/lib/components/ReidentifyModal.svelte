<script lang="ts">
  /**
   * ReidentifyModal
   * ────────────────
   * Shown when the tracking pipeline loses a robot track.
   * The user can:
   *  1. Click an existing tracked robot to re-assign it
   *  2. Draw a new bounding box for the lost robot
    *  3. Temporarily skip this robot
   */

  import { onMount, tick } from "svelte";
  import type { WsReidentify, ActiveTrack, BBox } from "../types";

  export let event: WsReidentify;
  export let onResolve: (response: { new_track_id?: number | null; drawn_bbox?: BBox }) => void;

  // Selection state
  let chosen: number | null = null;      // track_id or -1 for drop
  let drawnBox: BBox | null = null;       // user-drawn bbox (image-pixel coords)
  let mode: "select" | "draw" = "select";

  // Canvas drawing state
  let canvasEl: HTMLCanvasElement;
  let ctx: CanvasRenderingContext2D;
  let bgImage = new Image();
  let scale = 1;
  let drawing = false;
  let drawStart = { x: 0, y: 0 };
  let drawCurrent = { x: 0, y: 0 };

  onMount(async () => {
    bgImage.onload = async () => {
      await tick();
      if (canvasEl) {
        ctx = canvasEl.getContext("2d")!;
        resizeCanvas();
        render();
      }
    };
    bgImage.src = `data:image/jpeg;base64,${event.frame_image}`;
  });

  function resizeCanvas() {
    if (!canvasEl) return;
    // Render at native pixel resolution so jersey numbers remain readable.
    scale = 1;
    canvasEl.width = event.frame_width;
    canvasEl.height = event.frame_height;
  }

  function render() {
    if (!ctx || !bgImage.complete) return;
    ctx.clearRect(0, 0, canvasEl.width, canvasEl.height);
    ctx.drawImage(bgImage, 0, 0, canvasEl.width, canvasEl.height);

    // Draw last-known position hint for the lost team.
    if (event.last_known_bbox) {
      const { x1, y1, x2, y2 } = event.last_known_bbox;
      ctx.strokeStyle = "#ffd84d";
      ctx.lineWidth = 3;
      ctx.setLineDash([10, 6]);
      ctx.strokeRect(x1 * scale, y1 * scale, (x2 - x1) * scale, (y2 - y1) * scale);
      ctx.setLineDash([]);
      ctx.fillStyle = "#ffd84d";
      ctx.font = `bold ${Math.max(13, 16 * scale)}px sans-serif`;
      ctx.fillText(`Last seen #${event.lost_team}`, x1 * scale + 3, y1 * scale + 15 * scale);
    }

    // Draw existing tracked boxes
    for (const t of event.active_tracks) {
      const { x1, y1, x2, y2 } = t.bbox;
      const isSelected = chosen === t.track_id;
      ctx.strokeStyle = t.alliance === "red" ? "#ff6666" : "#66aaff";
      ctx.lineWidth = isSelected ? 3 : 2;
      ctx.globalAlpha = isSelected ? 1 : 0.6;
      ctx.strokeRect(x1 * scale, y1 * scale, (x2 - x1) * scale, (y2 - y1) * scale);
      // Label
      ctx.fillStyle = ctx.strokeStyle;
      ctx.font = `bold ${Math.max(13, 16 * scale)}px sans-serif`;
      ctx.fillText(`#${t.team_number}`, x1 * scale + 3, y1 * scale + 15 * scale);
      ctx.globalAlpha = 1;
    }

    // Draw the user-drawn box
    if (drawnBox) {
      const { x1, y1, x2, y2 } = drawnBox;
      ctx.strokeStyle = "#00ff88";
      ctx.lineWidth = 3;
      ctx.setLineDash([6, 3]);
      ctx.strokeRect(x1 * scale, y1 * scale, (x2 - x1) * scale, (y2 - y1) * scale);
      ctx.setLineDash([]);
      ctx.fillStyle = "rgba(0,255,136,0.1)";
      ctx.fillRect(x1 * scale, y1 * scale, (x2 - x1) * scale, (y2 - y1) * scale);
      ctx.fillStyle = "#00ff88";
      ctx.font = `bold ${Math.max(13, 16 * scale)}px sans-serif`;
      ctx.fillText(`#${event.lost_team} (drawn)`, x1 * scale + 3, y1 * scale + 15 * scale);
    }

    // In-progress draw preview
    if (drawing) {
      const x = Math.min(drawStart.x, drawCurrent.x) * scale;
      const y = Math.min(drawStart.y, drawCurrent.y) * scale;
      const w = Math.abs(drawCurrent.x - drawStart.x) * scale;
      const h = Math.abs(drawCurrent.y - drawStart.y) * scale;
      ctx.strokeStyle = "#00ff88";
      ctx.lineWidth = 2;
      ctx.setLineDash([4, 3]);
      ctx.strokeRect(x, y, w, h);
      ctx.setLineDash([]);
    }
  }

  // ── Canvas interaction ──────────────────────────────────────────────────────

  function canvasCoord(e: MouseEvent): { x: number; y: number } {
    const r = canvasEl.getBoundingClientRect();
    return {
      x: (e.clientX - r.left) / scale,
      y: (e.clientY - r.top) / scale,
    };
  }

  function handleMouseDown(e: MouseEvent) {
    const { x, y } = canvasCoord(e);

    if (mode === "draw") {
      drawing = true;
      drawStart = { x, y };
      drawCurrent = { x, y };
      return;
    }

    // Select mode — click on an existing track box
    for (const t of [...event.active_tracks].reverse()) {
      if (x >= t.bbox.x1 && x <= t.bbox.x2 && y >= t.bbox.y1 && y <= t.bbox.y2) {
        chosen = t.track_id;
        drawnBox = null;
        render();
        return;
      }
    }
  }

  function handleMouseMove(e: MouseEvent) {
    if (!drawing) return;
    drawCurrent = canvasCoord(e);
    render();
  }

  function handleMouseUp(e: MouseEvent) {
    if (!drawing) return;
    drawing = false;
    const { x, y } = canvasCoord(e);
    const bbox: BBox = {
      x1: Math.min(drawStart.x, x),
      y1: Math.min(drawStart.y, y),
      x2: Math.max(drawStart.x, x),
      y2: Math.max(drawStart.y, y),
    };
    if (bbox.x2 - bbox.x1 > 10 && bbox.y2 - bbox.y1 > 10) {
      drawnBox = bbox;
      chosen = null; // clear any track selection
    }
    render();
  }

  function switchMode(m: "select" | "draw") {
    mode = m;
    if (m === "draw") {
      chosen = null;
    } else {
      drawnBox = null;
    }
    render();
  }

  function handleConfirm() {
    if (chosen === -1) {
      onResolve({ new_track_id: null });
    } else if (drawnBox) {
      onResolve({ drawn_bbox: drawnBox });
    } else if (chosen !== null) {
      onResolve({ new_track_id: chosen });
    }
  }

  $: canConfirm = chosen !== null || drawnBox !== null;
</script>

<div class="modal-backdrop">
  <div class="modal">
    <h2>Re-identification Required</h2>
    <p class="subtitle">
      Team <strong>#{event.lost_team}</strong>
      (<span class="alliance {event.lost_alliance}">{event.lost_alliance}</span>)
      was lost for too many frames. Select an existing track, or draw a box around it.
      {#if event.last_known_bbox}
        The yellow dashed box shows the last known position.
      {/if}
    </p>

    <!-- Mode toolbar -->
    <div class="toolbar">
      <button
        class="tool-btn"
        class:active={mode === "select"}
        on:click={() => switchMode("select")}
      >Click existing track</button>
      <button
        class="tool-btn draw-tool"
        class:active={mode === "draw"}
        on:click={() => switchMode("draw")}
      >Draw bounding box</button>
    </div>

    <!-- Canvas -->
    <div class="canvas-wrap">
      <canvas
        bind:this={canvasEl}
        on:mousedown={handleMouseDown}
        on:mousemove={handleMouseMove}
        on:mouseup={handleMouseUp}
        style="cursor:{mode === 'draw' ? 'crosshair' : 'default'}"
      ></canvas>
    </div>

    <!-- Track list + drop -->
    <div class="track-list">
      {#each event.active_tracks as t}
        <button
          class="track-btn {t.alliance}"
          class:selected={chosen === t.track_id}
          on:click={() => { chosen = t.track_id; drawnBox = null; mode = "select"; render(); }}
        >
          #{t.team_number} · {t.alliance} · track {t.track_id}
        </button>
      {/each}
      {#if drawnBox}
        <button class="track-btn drawn selected">
          Drawn box for #{event.lost_team}
        </button>
      {/if}
      <button
        class="track-btn drop"
        class:selected={chosen === -1}
        on:click={() => { chosen = -1; drawnBox = null; render(); }}
      >
        Skip this robot for now
      </button>
    </div>

    <div class="modal-actions">
      <button
        class="btn-primary"
        disabled={!canConfirm}
        on:click={handleConfirm}
      >
        Confirm
      </button>
    </div>
  </div>
</div>

<style>
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
  }

  .modal {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.75rem;
    max-width: 720px;
    width: 95vw;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  h2 {
    margin: 0;
    font-size: 1.4rem;
    color: #f0a050;
  }

  .subtitle {
    font-size: 0.95rem;
    margin: 0;
    color: var(--text-muted);
  }

  .alliance {
    font-weight: 700;
  }

  .alliance.red { color: #ff6666; }
  .alliance.blue { color: #66aaff; }

  .toolbar {
    display: flex;
    gap: 0.5rem;
  }

  .tool-btn {
    background: var(--bg);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.35rem 0.75rem;
    font-size: 0.85rem;
    cursor: pointer;
  }

  .tool-btn.active {
    border-color: var(--accent);
    color: var(--accent);
  }

  .tool-btn.draw-tool.active {
    border-color: #00ff88;
    color: #00ff88;
  }

  .canvas-wrap {
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid var(--border);
    line-height: 0;
    max-height: 72vh;
    overflow: auto;
    background: #000;
  }

  canvas {
    display: block;
    user-select: none;
  }

  .track-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .track-btn {
    background: var(--bg);
    border: 2px solid var(--border);
    border-radius: 6px;
    padding: 0.4rem 0.85rem;
    font-size: 0.85rem;
    cursor: pointer;
    color: var(--text);
  }

  .track-btn.red.selected { border-color: #ff6666; color: #ff6666; }
  .track-btn.blue.selected { border-color: #66aaff; color: #66aaff; }
  .track-btn.drawn.selected { border-color: #00ff88; color: #00ff88; }
  .track-btn.drop.selected { border-color: #f0a050; color: #f0a050; }

  .modal-actions {
    display: flex;
    justify-content: flex-end;
  }

  .btn-primary {
    background: var(--accent);
    color: #000;
    border: none;
    border-radius: 6px;
    padding: 0.55rem 1.5rem;
    font-size: 0.95rem;
    font-weight: 700;
    cursor: pointer;
  }

  .btn-primary:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
</style>
