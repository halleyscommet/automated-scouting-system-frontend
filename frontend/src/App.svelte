<script lang="ts">
  import { onMount } from "svelte";
  import { step } from "./lib/store";
  import { getApiOrigin, setApiOrigin } from "./lib/api";
  import SetupStep from "./lib/components/SetupStep.svelte";
  import VideoStep from "./lib/components/VideoStep.svelte";
  import AnnotationCanvas from "./lib/components/AnnotationCanvas.svelte";
  import TrackingStep from "./lib/components/TrackingStep.svelte";
  import ResultsView from "./lib/components/ResultsView.svelte";

  const STEPS = [
    { id: "setup",    label: "Setup" },
    { id: "video",    label: "Frame Selection" },
    { id: "annotate", label: "Annotation" },
    { id: "tracking", label: "Tracking" },
    { id: "results",  label: "Results" },
  ] as const;

  $: currentIndex = STEPS.findIndex((s) => s.id === $step);

  let apiOriginInput = "";
  let apiHint = "";

  onMount(() => {
    apiOriginInput = getApiOrigin();
  });

  function saveApiOrigin() {
    try {
      const saved = setApiOrigin(apiOriginInput);
      apiOriginInput = saved;
      apiHint = "Saved. New requests will use this API URL.";
    } catch (err) {
      apiHint = err instanceof Error ? err.message : "Invalid API URL";
    }
  }

  function useLocalDefault() {
    apiOriginInput = "http://localhost:8000";
    saveApiOrigin();
  }
</script>

<div class="app">
  <!-- Header -->
  <header>
    <div class="logo">
      <span class="logo-icon">👁</span>
      <span class="logo-text">Seer AI</span>
      <span class="logo-sub">FRC 2026 Tracker</span>
    </div>

    <div class="api-config">
      <label for="api-origin" class="api-label">API URL</label>
      <div class="api-row">
        <input
          id="api-origin"
          type="url"
          class="api-input"
          bind:value={apiOriginInput}
          placeholder="https://your-host:12345"
        />
        <button class="api-btn" on:click={saveApiOrigin}>Save</button>
        <button class="api-btn ghost" on:click={useLocalDefault}>Local</button>
      </div>
      {#if apiHint}
        <p class="api-hint">{apiHint}</p>
      {/if}
    </div>

    <!-- Step breadcrumb -->
    <nav class="stepper">
      {#each STEPS as s, i}
        <div
          class="step-item"
          class:done={i < currentIndex}
          class:active={i === currentIndex}
          class:future={i > currentIndex}
        >
          <span class="step-num">{i + 1}</span>
          <span class="step-label">{s.label}</span>
        </div>
        {#if i < STEPS.length - 1}
          <div class="step-connector" class:done={i < currentIndex}></div>
        {/if}
      {/each}
    </nav>
  </header>

  <!-- Main content -->
  <main>
    {#if $step === "setup"}
      <SetupStep />
    {:else if $step === "video"}
      <VideoStep />
    {:else if $step === "annotate"}
      <AnnotationCanvas />
    {:else if $step === "tracking"}
      <TrackingStep />
    {:else if $step === "results"}
      <ResultsView />
    {/if}
  </main>
</div>

<style>
  .app {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    background: var(--bg);
    color: var(--text);
  }

  header {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 0.75rem 2rem;
    display: flex;
    align-items: center;
    gap: 2.5rem;
    flex-wrap: wrap;
  }

  .api-config {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    min-width: min(520px, 100%);
    flex: 1;
  }

  .api-label {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
  }

  .api-row {
    display: flex;
    gap: 0.4rem;
    flex-wrap: wrap;
  }

  .api-input {
    flex: 1;
    min-width: 260px;
    border: 1px solid var(--border);
    background: #0f1020;
    color: var(--text);
    border-radius: 6px;
    padding: 0.45rem 0.55rem;
    font-size: 0.85rem;
  }

  .api-btn {
    border: 1px solid var(--accent);
    background: var(--accent);
    color: #03140a;
    border-radius: 6px;
    font-weight: 700;
    padding: 0.4rem 0.7rem;
    cursor: pointer;
    font-size: 0.8rem;
  }

  .api-btn.ghost {
    background: transparent;
    color: var(--text);
    border-color: var(--border);
  }

  .api-hint {
    margin: 0;
    font-size: 0.75rem;
    color: var(--text-muted);
  }

  .logo {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
  }

  .logo-icon {
    font-size: 1.4rem;
  }

  .logo-text {
    font-size: 1.25rem;
    font-weight: 800;
    color: var(--accent);
    letter-spacing: -0.03em;
  }

  .logo-sub {
    font-size: 0.75rem;
    color: var(--text-muted);
    font-weight: 400;
  }

  /* Stepper */
  .stepper {
    display: flex;
    align-items: center;
    gap: 0;
    flex-wrap: wrap;
    row-gap: 0.4rem;
  }

  .step-item {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.2rem 0.5rem;
    border-radius: 6px;
    transition: background 0.15s;
  }

  .step-num {
    width: 22px;
    height: 22px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.75rem;
    font-weight: 700;
    flex-shrink: 0;
    background: var(--border);
    color: var(--text-muted);
  }

  .step-label {
    font-size: 0.8rem;
    color: var(--text-muted);
    white-space: nowrap;
  }

  .step-item.done .step-num {
    background: var(--accent);
    color: #000;
  }

  .step-item.done .step-label {
    color: var(--accent);
  }

  .step-item.active .step-num {
    background: var(--accent);
    color: #000;
    box-shadow: 0 0 0 3px var(--accent-glow);
  }

  .step-item.active .step-label {
    color: var(--text);
    font-weight: 600;
  }

  .step-connector {
    width: 24px;
    height: 2px;
    background: var(--border);
    flex-shrink: 0;
    transition: background 0.15s;
  }

  .step-connector.done {
    background: var(--accent);
  }

  main {
    flex: 1;
    padding: 2rem 2.5rem;
    overflow-y: auto;
  }

  @media (max-width: 600px) {
    main { padding: 1rem; }
    header { padding: 0.6rem 1rem; gap: 1rem; }
    .api-config { min-width: 100%; }
    .api-input { min-width: 100%; }
  }
</style>

