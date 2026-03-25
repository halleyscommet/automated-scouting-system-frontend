<script lang="ts">
  import { onMount } from "svelte";
  import { get } from "svelte/store";
  import { api } from "../api";
  import {
    step,
    robotModel,
    ballModel,
    selectedYear,
    selectedEvent,
    selectedMatch,
    videoInfo,
  } from "../store";
  import type { ModelInfo, TBAEvent, TBAMatch } from "../types";

  // ── State ────────────────────────────────────────────────────────────────────

  let models: ModelInfo[] = [];
  let events: TBAEvent[] = [];
  let matches: TBAMatch[] = [];

  let modelValue1 = "";
  let modelValue2 = "";
  let yearValue = new Date().getFullYear();
  let eventKey = "";
  let matchKey = "";

  let loadingEvents = false;
  let loadingMatches = false;
  let downloadJobId: string | null = null;
  let downloadStatus = "";
  let downloadProgress = 0;
  let downloadError = "";
  let downloading = false;

  let uploadInput: HTMLInputElement;
  let uploadError = "";

  const YEAR_OPTIONS = Array.from({ length: 7 }, (_, i) => 2020 + i);

  // ── Lifecycle ─────────────────────────────────────────────────────────────────

  onMount(async () => {
    const savedRobot = get(robotModel);
    const savedBall = get(ballModel);
    const savedYear = get(selectedYear);
    const savedEvent = get(selectedEvent);
    const savedMatch = get(selectedMatch);

    modelValue1 = savedRobot?.name ?? "";
    modelValue2 = savedBall?.name ?? "";
    yearValue = savedYear;

    await refreshModels();

    await onYearChange(savedEvent?.key, savedMatch?.key);
  });

  async function refreshModels() {
    try {
      models = await api.models.list();
    } catch {
      models = [];
    }
  }

  // ── Events ────────────────────────────────────────────────────────────────────

  async function onYearChange(preferredEventKey?: string | Event, preferredMatchKey?: string) {
    const preferredEvent = typeof preferredEventKey === "string" ? preferredEventKey : undefined;
    events = [];
    matches = [];
    eventKey = "";
    matchKey = "";
    loadingEvents = true;
    try {
      events = await api.tba.events(Number(yearValue));
      selectedYear.set(Number(yearValue));

      if (events.length === 0) {
        selectedEvent.set(null);
        selectedMatch.set(null);
        return;
      }

      const nextEvent = preferredEvent && events.some((e) => e.key === preferredEvent)
        ? preferredEvent
        : events[0].key;

      eventKey = nextEvent;
      await onEventChange(preferredMatchKey);
    } catch (e: any) {
      events = [];
      selectedEvent.set(null);
      selectedMatch.set(null);
    } finally {
      loadingEvents = false;
    }
  }

  async function onEventChange(preferredMatchKey?: string | Event) {
    const preferredMatch = typeof preferredMatchKey === "string" ? preferredMatchKey : undefined;
    matches = [];
    matchKey = "";
    if (!eventKey) return;
    loadingMatches = true;
    try {
      matches = await api.tba.matches(eventKey);
      selectedEvent.set(events.find((e) => e.key === eventKey) ?? null);

      if (matches.length === 0) {
        selectedMatch.set(null);
        return;
      }

      const nextMatch = preferredMatch && matches.some((m) => m.key === preferredMatch)
        ? preferredMatch
        : matches[0].key;

      matchKey = nextMatch;
      onMatchChange();
    } catch {
      matches = [];
      selectedMatch.set(null);
    } finally {
      loadingMatches = false;
    }
  }

  function onMatchChange() {
    const m = matches.find((m) => m.key === matchKey) ?? null;
    selectedMatch.set(m);
  }

  // ── Model upload ──────────────────────────────────────────────────────────────

  async function handleUpload() {
    uploadError = "";
    const file = uploadInput.files?.[0];
    if (!file) return;
    try {
      const info = await api.models.upload(file);
      models = [...models, info];
      modelValue1 = info.name;
    } catch (e: any) {
      uploadError = e.message;
    } finally {
      uploadInput.value = "";
    }
  }

  // ── Download video ────────────────────────────────────────────────────────────

  async function startDownload() {
    if (!matchKey || !modelValue1) return;
    const match = matches.find((m) => m.key === matchKey);
    if (!match) return;
    const yt = match.videos.find((v) => v.type === "youtube");
    if (!yt) return;

    downloading = true;
    downloadError = "";
    downloadStatus = "Starting download…";
    downloadProgress = 0;

    try {
      const { job_id } = await api.video.download(matchKey, yt.key);
      downloadJobId = job_id;
      await pollDownload(job_id);
    } catch (e: any) {
      downloadError = e.message;
      downloading = false;
    }
  }

  async function pollDownload(jobId: string) {
    while (true) {
      await sleep(1500);
      const job = await api.video.status(jobId);
      downloadProgress = job.progress;
      downloadStatus =
        job.status === "downloading"
          ? "Downloading from YouTube…"
          : job.status === "converting"
            ? "Converting to HLS…"
            : job.status === "completed"
              ? "Done!"
              : job.status === "failed"
                ? "Failed"
                : job.status;

      if (job.status === "completed") {
        const info = await api.video.info(matchKey);
        videoInfo.set(info);
        robotModel.set(models.find((m) => m.name === modelValue1) ?? null);
        if (modelValue2 && modelValue2 !== modelValue1) {
          ballModel.set(models.find((m) => m.name === modelValue2) ?? null);
        } else {
          ballModel.set(null);
        }
        downloading = false;
        return;
      }
      if (job.status === "failed") {
        downloadError = job.error ?? "Unknown error";
        downloading = false;
        return;
      }
    }
  }

  function sleep(ms: number) {
    return new Promise((r) => setTimeout(r, ms));
  }

  function goNext() {
    step.set("video");
  }

  $: canDownload = !!matchKey && !!modelValue1 && !downloading;
  $: downloadComplete = downloadStatus === "Done!";
</script>

<!-- ── Markup ──────────────────────────────────────────────────────────────── -->

<div class="setup">
  <h2>Match Setup</h2>

  <!-- Model selector -->
  <section class="card">
    <h3>Models</h3>
    <p class="muted" style="margin:0 0 0.5rem">Select a robot detection model (required) and optionally a dedicated ball detection model.</p>
    <div class="row">
      <select bind:value={modelValue1} disabled={downloading}>
        <option value="">— robot model (required) —</option>
        {#each models as m}
          <option value={m.name}>{m.name} ({m.size_mb} MB)</option>
        {/each}
      </select>

      <select bind:value={modelValue2} disabled={downloading}>
        <option value="">— ball model (optional) —</option>
        {#each models.filter(m => m.name !== modelValue1) as m}
          <option value={m.name}>{m.name} ({m.size_mb} MB)</option>
        {/each}
      </select>

      <label class="upload-btn" for="model-upload">Upload .pt</label>
      <input
        id="model-upload"
        type="file"
        accept=".pt"
        bind:this={uploadInput}
        on:change={handleUpload}
        style="display:none"
      />
    </div>
    {#if uploadError}
      <p class="error">{uploadError}</p>
    {/if}
  </section>

  <!-- Year selector -->
  <section class="card">
    <h3>Year</h3>
    <select bind:value={yearValue} on:change={onYearChange} disabled={downloading}>
      {#each YEAR_OPTIONS as y}
        <option value={y}>{y}</option>
      {/each}
    </select>
  </section>

  <!-- Event selector -->
  <section class="card">
    <h3>Event</h3>
    {#if loadingEvents}
      <p class="muted">Loading events…</p>
    {:else}
      <select bind:value={eventKey} on:change={onEventChange} disabled={downloading || events.length === 0}>
        <option value="">— select an event —</option>
        {#each events as e}
          <option value={e.key}>{e.name} ({e.start_date})</option>
        {/each}
      </select>
    {/if}
  </section>

  <!-- Match selector -->
  <section class="card">
    <h3>Match</h3>
    {#if loadingMatches}
      <p class="muted">Loading matches…</p>
    {:else}
      <select bind:value={matchKey} on:change={onMatchChange} disabled={downloading || matches.length === 0}>
        <option value="">— select a match —</option>
        {#each matches as m}
          <option value={m.key}>
            {m.comp_level.toUpperCase()}
            {#if m.comp_level !== "qm"}Set {m.set_number} –{/if}
            Match {m.match_number}
          </option>
        {/each}
      </select>
      {#if matches.length === 0 && eventKey}
        <p class="muted">No matches with videos found for this event.</p>
      {/if}
    {/if}
  </section>

  <!-- Download -->
  <section class="card">
    <h3>Download &amp; Convert</h3>
    <button on:click={startDownload} disabled={!canDownload} class="btn-primary">
      {downloading ? "Working…" : "Download Match Video"}
    </button>

    {#if downloadStatus}
      <div class="progress-wrap">
        <p class="status-text">{downloadStatus}</p>
        <div class="progress-bar">
          <div class="progress-fill" style="width:{downloadProgress}%"></div>
        </div>
        <p class="muted">{downloadProgress}%</p>
      </div>
    {/if}
    {#if downloadError}
      <p class="error">{downloadError}</p>
    {/if}
  </section>

  {#if downloadComplete}
    <button class="btn-primary btn-next" on:click={goNext}>
      Continue to Frame Selection →
    </button>
  {/if}
</div>

<!-- ── Styles ──────────────────────────────────────────────────────────────── -->

<style>
  .setup {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    max-width: 640px;
  }

  h2 {
    font-size: 1.5rem;
    margin: 0 0 0.5rem;
  }

  h3 {
    font-size: 0.9rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
    margin: 0 0 0.5rem;
  }

  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1rem 1.25rem;
  }

  .row {
    display: flex;
    gap: 0.75rem;
    align-items: center;
  }

  select {
    flex: 1;
    background: var(--bg);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.4rem 0.6rem;
    font-size: 0.95rem;
  }

  .upload-btn {
    cursor: pointer;
    background: var(--accent);
    color: #000;
    padding: 0.4rem 0.85rem;
    border-radius: 6px;
    font-size: 0.85rem;
    font-weight: 600;
    white-space: nowrap;
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

  .btn-primary:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  .btn-next {
    align-self: flex-end;
    font-size: 1rem;
    padding: 0.65rem 1.5rem;
  }

  .progress-wrap {
    margin-top: 0.75rem;
  }

  .progress-bar {
    height: 8px;
    background: var(--border);
    border-radius: 4px;
    overflow: hidden;
    margin: 0.25rem 0;
  }

  .progress-fill {
    height: 100%;
    background: var(--accent);
    transition: width 0.4s ease;
  }

  .status-text {
    font-size: 0.85rem;
    margin: 0;
  }

  .muted {
    color: var(--text-muted);
    font-size: 0.85rem;
    margin: 0.25rem 0 0;
  }

  .error {
    color: var(--error);
    font-size: 0.85rem;
    margin: 0.35rem 0 0;
  }
</style>
