<script lang="ts">
  /**
   * AnnotationCanvas
   * ─────────────────
   * Displays a video frame and lets the user:
   *  1. Review / drag YOLO-detected robot bounding boxes
   *  2. Draw two Hub Zone rectangles (one per alliance)
   *  3. Assign team numbers + alliances to each robot box
   *  4. Click "Start Tracking" to kick off the pipeline
   */

  import { onMount } from "svelte";
  import { api } from "../api";
  import {
    step,
    selectedMatch,
    robotModel,
    annotationFrame,
    robotAnnotations,
    hubZones,
  } from "../store";
  import type { BBox, Alliance, RobotAnnotation, HubZone } from "../types";

  // ── Props / stores ──────────────────────────────────────────────────────────────────

  let matchKey = "";
  selectedMatch.subscribe((m) => (matchKey = m?.key ?? ""));
  let robotModelName = "";
  robotModel.subscribe((m) => (robotModelName = m?.name ?? ""));
  let frameNumber = 0;
  annotationFrame.subscribe((f) => (frameNumber = f));

  // ── Types ─────────────────────────────────────────────────────────────────────

  type BoxKind = "robot" | "hub";

  interface AnnotBox {
    id: number;
    kind: BoxKind;
    bbox: BBox;        // in image-pixel coordinates
    team?: number;
    alliance?: Alliance;
    selected: boolean;
  }

  // ── State ─────────────────────────────────────────────────────────────────────

  let canvasEl: HTMLCanvasElement;
  let ctx: CanvasRenderingContext2D;
  let bgImage = new Image();
  let imgW = 1280;
  let imgH = 720;
  let scale = 1;

  let boxes: AnnotBox[] = [];
  let nextId = 1;

  // Team / alliance lists from TBA
  let teamOptions: { number: number; alliance: Alliance }[] = [];

  // Drawing state
  type Tool = "select" | "hub" | "robot";
  let activeTool: Tool = "select";
  let drawing = false;
  let drawStart = { x: 0, y: 0 };
  let drawCurrent = { x: 0, y: 0 };

  let dragging: AnnotBox | null = null;
  let dragOffset = { x: 0, y: 0 };

  let selectedBox: AnnotBox | null = null;

  // Loading / errors
  let loading = true;
  let error = "";
  let submitError = "";
  let submitting = false;

  // ── Lifecycle ─────────────────────────────────────────────────────────────────

  onMount(async () => {
    await loadFrame();
    await loadTeams();
  });

  async function loadFrame() {
    loading = true;
    error = "";
    try {
      const result = await api.tracking.detectFrame(matchKey, robotModelName, frameNumber);
      imgW = result.frame_width;
      imgH = result.frame_height;

      // Draw image
      bgImage.onload = () => {
        // Canvas only exists in the DOM after loading becomes false,
        // so we need to wait a tick for Svelte to render it.
        loading = false;
        requestAnimationFrame(() => {
          if (canvasEl) {
            ctx = canvasEl.getContext("2d")!;
            resizeCanvas();
            render();
          }
        });
      };
      bgImage.src = `data:image/jpeg;base64,${result.frame_image}`;

      // Populate robot boxes from detections
      boxes = result.detections
        .filter((d) => d.class_name === "robot")
        .map((d) => ({
          id: nextId++,
          kind: "robot" as BoxKind,
          bbox: d.bbox,
          team: undefined,
          alliance: undefined,
          selected: false,
        }));
    } catch (e: any) {
      error = e.message;
      loading = false;
    }
  }

  async function loadTeams() {
    try {
      const alliances = await api.tba.teams(matchKey);
      teamOptions = [
        ...alliances.red.map((k) => ({ number: parseInt(k.replace("frc", "")), alliance: "red" as Alliance })),
        ...alliances.blue.map((k) => ({ number: parseInt(k.replace("frc", "")), alliance: "blue" as Alliance })),
      ];
    } catch {
      teamOptions = [];
    }
  }

  // ── Canvas sizing ─────────────────────────────────────────────────────────────

  function resizeCanvas() {
    if (!canvasEl) return;
    const maxW = canvasEl.parentElement!.clientWidth;
    scale = maxW / imgW;
    canvasEl.width = imgW * scale;
    canvasEl.height = imgH * scale;
  }

  // ── Render ────────────────────────────────────────────────────────────────────

  function render() {
    if (!ctx || !bgImage.complete) return;
    ctx.clearRect(0, 0, canvasEl.width, canvasEl.height);
    ctx.drawImage(bgImage, 0, 0, canvasEl.width, canvasEl.height);

    for (const box of boxes) {
      drawBox(box);
    }

    // In-progress rectangle (hub or robot draw)
    if (drawing && (activeTool === "hub" || activeTool === "robot")) {
      const x = Math.min(drawStart.x, drawCurrent.x) * scale;
      const y = Math.min(drawStart.y, drawCurrent.y) * scale;
      const w = Math.abs(drawCurrent.x - drawStart.x) * scale;
      const h = Math.abs(drawCurrent.y - drawStart.y) * scale;
      ctx.strokeStyle = activeTool === "hub" ? "#00ffff" : "#00ff88";
      ctx.lineWidth = 2;
      ctx.setLineDash([6, 3]);
      ctx.strokeRect(x, y, w, h);
      ctx.setLineDash([]);
      const fill = activeTool === "hub" ? "rgba(0,255,255,0.08)" : "rgba(0,255,136,0.08)";
      ctx.fillStyle = fill;
      ctx.fillRect(x, y, w, h);
    }
  }

  function colorForBox(box: AnnotBox): string {
    if (box.kind === "hub") {
      return box.alliance === "red" ? "#ff4444" : "#4488ff";
    }
    if (box.selected) return "#ffff00";
    if (box.alliance === "red") return "#ff6666";
    if (box.alliance === "blue") return "#66aaff";
    return "#ffffff";
  }

  function drawBox(box: AnnotBox) {
    const { x1, y1, x2, y2 } = box.bbox;
    const sx = x1 * scale;
    const sy = y1 * scale;
    const sw = (x2 - x1) * scale;
    const sh = (y2 - y1) * scale;

    const color = colorForBox(box);
    ctx.strokeStyle = color;
    ctx.lineWidth = box.selected ? 3 : 2;
    ctx.strokeRect(sx, sy, sw, sh);

    // Fill hub zone lightly
    if (box.kind === "hub") {
      ctx.fillStyle = box.alliance === "red" ? "rgba(255,68,68,0.12)" : "rgba(68,136,255,0.12)";
      ctx.fillRect(sx, sy, sw, sh);
    }

    // Label
    const label =
      box.kind === "hub"
        ? `${box.alliance === "red" ? "Red" : "Blue"} Hub`
        : box.team
          ? `#${box.team}`
          : "?";

    ctx.fillStyle = color;
    ctx.font = `bold ${Math.max(12, 14 * scale)}px sans-serif`;
    ctx.fillText(label, sx + 4, sy + 18 * scale);
  }

  // ── Mouse interaction ─────────────────────────────────────────────────────────

  function canvasCoord(e: MouseEvent): { x: number; y: number } {
    const r = canvasEl.getBoundingClientRect();
    return {
      x: (e.clientX - r.left) / scale,
      y: (e.clientY - r.top) / scale,
    };
  }

  function boxContains(box: AnnotBox, x: number, y: number): boolean {
    return (
      x >= box.bbox.x1 && x <= box.bbox.x2 &&
      y >= box.bbox.y1 && y <= box.bbox.y2
    );
  }

  function handleMouseDown(e: MouseEvent) {
    const { x, y } = canvasCoord(e);

    if (activeTool === "hub" || activeTool === "robot") {
      drawing = true;
      drawStart = { x, y };
      drawCurrent = { x, y };
      return;
    }

    // Select / drag existing box
    const hit = [...boxes].reverse().find((b) => boxContains(b, x, y));
    if (hit) {
      boxes = boxes.map((b) => ({ ...b, selected: b.id === hit.id }));
      selectedBox = boxes.find((b) => b.id === hit.id)!;
      dragging = selectedBox;
      dragOffset = { x: x - hit.bbox.x1, y: y - hit.bbox.y1 };
    } else {
      boxes = boxes.map((b) => ({ ...b, selected: false }));
      selectedBox = null;
    }
    render();
  }

  function handleMouseMove(e: MouseEvent) {
    const { x, y } = canvasCoord(e);

    if (drawing && (activeTool === "hub" || activeTool === "robot")) {
      drawCurrent = { x, y };
      render();
      return;
    }

    if (dragging) {
      const w = dragging.bbox.x2 - dragging.bbox.x1;
      const h = dragging.bbox.y2 - dragging.bbox.y1;
      const nx1 = Math.max(0, x - dragOffset.x);
      const ny1 = Math.max(0, y - dragOffset.y);
      dragging.bbox = { x1: nx1, y1: ny1, x2: nx1 + w, y2: ny1 + h };
      boxes = boxes.map((b) => (b.id === dragging!.id ? dragging! : b));
      render();
    }
  }

  function handleMouseUp(e: MouseEvent) {
    if (drawing && (activeTool === "hub" || activeTool === "robot")) {
      drawing = false;
      const { x, y } = canvasCoord(e);
      const bbox: BBox = {
        x1: Math.min(drawStart.x, x),
        y1: Math.min(drawStart.y, y),
        x2: Math.max(drawStart.x, x),
        y2: Math.max(drawStart.y, y),
      };
      if (bbox.x2 - bbox.x1 > 10 && bbox.y2 - bbox.y1 > 10) {
        if (activeTool === "hub") {
          const hubCount = boxes.filter((b) => b.kind === "hub").length;
          const alliance: Alliance = hubCount === 0 ? "red" : "blue";
          const newBox: AnnotBox = {
            id: nextId++,
            kind: "hub",
            bbox,
            alliance,
            selected: true,
          };
          boxes = [...boxes.map((b) => ({ ...b, selected: false })), newBox];
          selectedBox = newBox;
          activeTool = "select";
        } else {
          // New manually-drawn robot box
          const newBox: AnnotBox = {
            id: nextId++,
            kind: "robot",
            bbox,
            team: undefined,
            alliance: undefined,
            selected: true,
          };
          boxes = [...boxes.map((b) => ({ ...b, selected: false })), newBox];
          selectedBox = newBox;
          activeTool = "select";
        }
      }
      render();
      return;
    }

    dragging = null;
  }

  function deleteSelected() {
    if (!selectedBox) return;
    boxes = boxes.filter((b) => b.id !== selectedBox!.id);
    selectedBox = null;
    render();
  }

  // ── Panel: update selected box ────────────────────────────────────────────────

  function onTeamSelect(e: Event) {
    if (!selectedBox) return;
    const val = (e.target as HTMLSelectElement).value;
    const opt = teamOptions.find((t) => t.number === parseInt(val));
    if (opt) {
      selectedBox.team = opt.number;
      selectedBox.alliance = opt.alliance;
      boxes = boxes.map((b) => (b.id === selectedBox!.id ? selectedBox! : b));
      render();
    }
  }

  function onAllianceSelect(e: Event) {
    if (!selectedBox || selectedBox.kind !== "hub") return;
    selectedBox.alliance = (e.target as HTMLSelectElement).value as Alliance;
    boxes = boxes.map((b) => (b.id === selectedBox!.id ? selectedBox! : b));
    render();
  }

  // ── Validate + submit ─────────────────────────────────────────────────────────

  $: robotBoxes = boxes.filter((b) => b.kind === "robot");
  $: hubBoxes = boxes.filter((b) => b.kind === "hub");
  $: unassigned = robotBoxes.filter((b) => !b.team);
  $: canSubmit =
    robotBoxes.length > 0 &&
    hubBoxes.length === 2 &&
    unassigned.length === 0 &&
    !submitting;

  async function startTracking() {
    submitError = "";
    submitting = true;
    try {
      const robots: RobotAnnotation[] = robotBoxes.map((b) => ({
        team_number: b.team!,
        alliance: b.alliance!,
        bbox: b.bbox,
      }));
      const hubs: HubZone[] = hubBoxes.map((b) => ({
        alliance: b.alliance!,
        bbox: b.bbox,
      }));

      robotAnnotations.set(robots);
      hubZones.set(hubs);

      step.set("tracking");
    } catch (e: any) {
      submitError = e.message;
      submitting = false;
    }
  }
</script>

<div class="annot-wrap">
  <div class="annot-main">
    <h2>Annotate Frame {frameNumber}</h2>

    {#if loading}
      <p class="muted">Running YOLO detection on frame…</p>
    {:else if error}
      <p class="error">{error}</p>
    {:else}
      <!-- Toolbar -->
      <div class="toolbar">
        <button
          class="tool-btn"
          class:active={activeTool === "select"}
          on:click={() => (activeTool = "select")}
        >Select / Move</button>
        <button
          class="tool-btn draw-robot"
          class:active={activeTool === "robot"}
          on:click={() => (activeTool = "robot")}
        >+ Draw Robot</button>
        <button
          class="tool-btn"
          class:active={activeTool === "hub"}
          on:click={() => (activeTool = "hub")}
          disabled={hubBoxes.length >= 2}
        >+ Draw Hub Zone {hubBoxes.length}/2</button>
        {#if selectedBox}
          <button class="tool-btn danger" on:click={deleteSelected}>Delete Selected</button>
        {/if}
      </div>

      <!-- Canvas -->
      <div class="canvas-container">
        <canvas
          bind:this={canvasEl}
          aria-label="Annotation canvas — use the toolbar to select and draw boxes"
          on:mousedown={handleMouseDown}
          on:mousemove={handleMouseMove}
          on:mouseup={handleMouseUp}
          style="cursor:{activeTool === 'hub' || activeTool === 'robot' ? 'crosshair' : 'default'}"
        ></canvas>
      </div>
    {/if}
  </div>

  <!-- Right panel -->
  <div class="annot-panel">
    <!-- Selected box editor -->
    {#if selectedBox}
      <section class="panel-card">
        <h3>{selectedBox.kind === "hub" ? "Hub Zone" : "Robot Box"}</h3>

        {#if selectedBox.kind === "robot"}
          <label class="field-label" for="team-select">Team Number</label>
          <select id="team-select" on:change={onTeamSelect} value={selectedBox.team ?? ""}>
            <option value="">— assign team —</option>
            {#each teamOptions as t}
              <option value={t.number}>#{t.number} ({t.alliance})</option>
            {/each}
          </select>
        {/if}

        {#if selectedBox.kind === "hub"}
          <label class="field-label" for="alliance-select">Alliance</label>
          <select id="alliance-select" on:change={onAllianceSelect} value={selectedBox.alliance ?? "red"}>
            <option value="red">Red</option>
            <option value="blue">Blue</option>
          </select>
        {/if}
      </section>
    {/if}

    <!-- Summary -->
    <section class="panel-card">
      <h3>Summary</h3>
      <ul class="summary-list">
        {#each robotBoxes as b}
          <li class:unassigned={!b.team}>
            <span class="dot" style="background:{b.alliance === 'red' ? '#ff6666' : b.alliance === 'blue' ? '#66aaff' : '#aaa'}"></span>
            {b.team ? `#${b.team} (${b.alliance})` : "Unassigned robot"}
          </li>
        {/each}
        {#each hubBoxes as b}
          <li>
            <span class="dot" style="background:{b.alliance === 'red' ? '#ff4444' : '#4488ff'}"></span>
            {b.alliance} Hub zone
          </li>
        {/each}
      </ul>
      {#if unassigned.length > 0}
        <p class="warn">Assign team numbers to all {unassigned.length} robot(s).</p>
      {/if}
      {#if hubBoxes.length < 2}
        <p class="warn">Draw {2 - hubBoxes.length} more Hub Zone(s).</p>
      {/if}
    </section>

    {#if submitError}
      <p class="error">{submitError}</p>
    {/if}

    <button class="btn-primary" disabled={!canSubmit} on:click={startTracking}>
      {submitting ? "Starting…" : "Start Tracking →"}
    </button>
  </div>
</div>

<style>
  .annot-wrap {
    display: flex;
    gap: 1.25rem;
    align-items: flex-start;
    width: 100%;
  }

  .annot-main {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .annot-panel {
    width: 240px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  h2 {
    font-size: 1.5rem;
    margin: 0;
  }

  h3 {
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
    margin: 0 0 0.5rem;
  }

  .toolbar {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .tool-btn {
    background: var(--surface);
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

  .tool-btn.draw-robot.active {
    border-color: #00ff88;
    color: #00ff88;
  }

  .tool-btn.danger {
    border-color: var(--error);
    color: var(--error);
  }

  .tool-btn:disabled {
    opacity: 0.35;
    cursor: not-allowed;
  }

  .canvas-container {
    background: #000;
    border-radius: 8px;
    border: 1px solid var(--border);
    overflow: hidden;
    line-height: 0;
  }

  canvas {
    display: block;
    user-select: none;
  }

  .panel-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 0.85rem 1rem;
  }

  .field-label {
    display: block;
    font-size: 0.8rem;
    color: var(--text-muted);
    margin-bottom: 0.25rem;
  }

  select {
    width: 100%;
    background: var(--bg);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.35rem 0.5rem;
    font-size: 0.9rem;
  }

  .summary-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }

  .summary-list li {
    font-size: 0.9rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .summary-list li.unassigned {
    color: var(--error);
  }

  .dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .warn {
    font-size: 0.8rem;
    color: #f0a050;
    margin: 0.4rem 0 0;
  }

  .btn-primary {
    background: var(--accent);
    color: #000;
    border: none;
    border-radius: 6px;
    padding: 0.6rem 1rem;
    font-size: 0.95rem;
    font-weight: 700;
    cursor: pointer;
    width: 100%;
  }

  .btn-primary:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .muted {
    color: var(--text-muted);
    font-size: 0.9rem;
  }

  .error {
    color: var(--error);
    font-size: 0.85rem;
  }
</style>
