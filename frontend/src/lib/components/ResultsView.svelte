<script lang="ts">
  import { onMount } from "svelte";
  import { api } from "../api";
  import { step, currentResult } from "../store";
  import type { TrackingResult, ResultSummary } from "../types";

  // ── State ─────────────────────────────────────────────────────────────────────

  let result: TrackingResult | null = null;
  currentResult.subscribe((r) => (result = r));

  let pastResults: ResultSummary[] = [];
  let loadingPast = false;
  let showPast = false;
  let loadingDetailId: string | null = null;

  // ── Lifecycle ─────────────────────────────────────────────────────────────────

  onMount(async () => {
    loadingPast = true;
    try {
      pastResults = await api.results.list();
    } catch {
      pastResults = [];
    } finally {
      loadingPast = false;
    }
  });

  // ── Helpers ───────────────────────────────────────────────────────────────────

  async function loadPastResult(resultId: string) {
    loadingDetailId = resultId;
    try {
      const r = await api.results.get(resultId);
      currentResult.set(r);
      result = r;
    } finally {
      loadingDetailId = null;
      showPast = false;
    }
  }

  async function exportJson() {
    if (!result) return;
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${result.match_key}_results.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function teamColor(alliance: string) {
    return alliance === "red" ? "#ff6666" : "#66aaff";
  }

  function formatDate(iso: string) {
    return new Date(iso).toLocaleString();
  }

  $: redTeams = result
    ? Object.entries(result.robots).filter(([, r]) => r.alliance === "red")
    : [];
  $: blueTeams = result
    ? Object.entries(result.robots).filter(([, r]) => r.alliance === "blue")
    : [];
  $: redTotal = redTeams.reduce((s, [, r]) => s + r.score, 0);
  $: blueTotal = blueTeams.reduce((s, [, r]) => s + r.score, 0);
</script>

<div class="results-view">
  <div class="results-header">
    <h2>Results{result ? ` — ${result.match_key}` : ""}</h2>
    <div class="header-actions">
      {#if result}
        <button class="btn-secondary" on:click={exportJson}>Export JSON</button>
      {/if}
      <button class="btn-secondary" on:click={() => (showPast = !showPast)}>
        {showPast ? "Hide" : "View Past Results"}
      </button>
      <button class="btn-secondary" on:click={() => step.set("setup")}>New Session</button>
    </div>
  </div>

  <!-- Past results drawer -->
  {#if showPast}
    <section class="card past-results">
      <h3>Past Results</h3>
      {#if loadingPast}
        <p class="muted">Loading…</p>
      {:else if pastResults.length === 0}
        <p class="muted">No saved results yet.</p>
      {:else}
        <ul class="past-list">
          {#each pastResults as pr}
            <li>
              <button
                class="past-btn"
                on:click={() => loadPastResult(pr.result_id)}
                disabled={loadingDetailId === pr.result_id}
              >
                <span class="past-match">{pr.match_key}</span>
                <span class="past-date muted">{formatDate(pr.timestamp)}</span>
              </button>
            </li>
          {/each}
        </ul>
      {/if}
    </section>
  {/if}

  {#if !result}
    <p class="muted">No result loaded.</p>
  {:else}
    <!-- Score comparison -->
    <section class="card score-banner">
      <div class="alliance-score red-side">
        <span class="alliance-label" style="color:#ff6666">Red Alliance</span>
        <span class="score-big" style="color:#ff6666">{redTotal}</span>
      </div>
      <div class="vs-divider">vs</div>
      <div class="alliance-score blue-side">
        <span class="alliance-label" style="color:#66aaff">Blue Alliance</span>
        <span class="score-big" style="color:#66aaff">{blueTotal}</span>
      </div>
    </section>

    <!-- Per-robot breakdown -->
    <div class="robot-grid">
      {#each [...redTeams, ...blueTeams] as [team, data]}
        <section class="card robot-card">
          <div class="robot-header">
            <span class="team-tag" style="border-color:{teamColor(data.alliance)};color:{teamColor(data.alliance)}">
              #{team}
            </span>
            <span class="alliance-chip" style="background:{teamColor(data.alliance)}22;color:{teamColor(data.alliance)}">
              {data.alliance}
            </span>
            <span class="robot-score">{data.score} pts</span>
          </div>

          {#if data.heatmap_url}
            <img
              src={`http://localhost:8000${data.heatmap_url}`}
              alt="Team {team} heatmap"
              class="heatmap-img"
            />
          {:else}
            <div class="heatmap-placeholder muted">No heatmap</div>
          {/if}

          <p class="position-count muted">{data.position_count.toLocaleString()} position samples</p>
        </section>
      {/each}
    </div>

    <!-- Meta -->
    <section class="card meta-card">
      <p class="muted">Model: <strong>{result.model_name}</strong></p>
      <p class="muted">Run at: <strong>{formatDate(result.timestamp)}</strong></p>
      <p class="muted">Result ID: <code>{result.result_id}</code></p>
    </section>
  {/if}
</div>

<style>
  .results-view {
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
    max-width: 1000px;
    width: 100%;
  }

  .results-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
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
    margin: 0 0 0.6rem;
  }

  .header-actions {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1.25rem 1.5rem;
  }

  /* Score banner */
  .score-banner {
    display: flex;
    align-items: center;
    justify-content: space-around;
    gap: 1rem;
  }

  .alliance-score {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.25rem;
  }

  .alliance-label {
    font-size: 0.9rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .score-big {
    font-size: 3rem;
    font-weight: 800;
    line-height: 1;
  }

  .vs-divider {
    font-size: 1.25rem;
    color: var(--text-muted);
    font-weight: 300;
  }

  /* Robot grid */
  .robot-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 1rem;
  }

  .robot-card {
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .robot-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .team-tag {
    font-size: 1.1rem;
    font-weight: 700;
    border: 2px solid;
    border-radius: 6px;
    padding: 0.1rem 0.5rem;
  }

  .alliance-chip {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    border-radius: 4px;
    padding: 0.15rem 0.45rem;
  }

  .robot-score {
    margin-left: auto;
    font-size: 1.2rem;
    font-weight: 700;
    color: var(--text);
  }

  .heatmap-img {
    width: 100%;
    border-radius: 6px;
    border: 1px solid var(--border);
  }

  .heatmap-placeholder {
    height: 120px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1px dashed var(--border);
    border-radius: 6px;
    font-size: 0.85rem;
  }

  .position-count {
    margin: 0;
    font-size: 0.8rem;
  }

  /* Past results */
  .past-results {
    max-height: 260px;
    overflow-y: auto;
  }

  .past-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
  }

  .past-btn {
    background: none;
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.45rem 0.75rem;
    width: 100%;
    text-align: left;
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.5rem;
    color: var(--text);
  }

  .past-btn:hover {
    background: var(--bg);
  }

  .past-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .past-match {
    font-weight: 600;
    font-size: 0.9rem;
  }

  .past-date {
    font-size: 0.8rem;
  }

  /* Meta */
  .meta-card {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    padding: 0.85rem 1.25rem;
  }

  .meta-card p {
    margin: 0;
    font-size: 0.85rem;
  }

  code {
    font-size: 0.8rem;
    background: var(--bg);
    border-radius: 4px;
    padding: 0.1rem 0.35rem;
  }

  .btn-secondary {
    background: var(--surface);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.45rem 0.85rem;
    font-size: 0.85rem;
    cursor: pointer;
  }

  .muted {
    color: var(--text-muted);
    font-size: 0.85rem;
  }
</style>
