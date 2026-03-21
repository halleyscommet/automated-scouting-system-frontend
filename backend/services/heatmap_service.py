"""
Heatmap Service
===============
Generates per-robot position heatmaps from the position history collected by
the tracking pipeline, and persists the full result bundle to disk.

Output structure for a single job
-----------------------------------
results/<result_id>/
    results.json          – complete result manifest
    heatmap_<team>.png    – one file per robot
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import gaussian_filter

from config import RESULTS_DIR


class HeatmapService:

    def save_results(
        self,
        job_id: str,
        match_key: str,
        model_name: str,
        scores: dict[int, int],
        positions: dict[int, list[tuple[float, float, int]]],  # team → [(cx, cy, frame), ...]
        team_alliance: dict[int, str],
        hub_zones: list[dict],
        frame_shape: tuple[int, int],  # (height, width)
    ) -> str:
        result_id = str(uuid.uuid4())
        out_dir = RESULTS_DIR / result_id
        out_dir.mkdir(parents=True, exist_ok=True)

        heatmap_paths: dict[int, str] = {}
        for team, pts in positions.items():
            if pts:
                path = self._generate_heatmap(team, pts, frame_shape, out_dir)
                heatmap_paths[team] = f"/results-static/{result_id}/heatmap_{team}.png"

        # Assemble scoring dict keyed by alliance
        scoring: dict[str, dict[str, int]] = {"red": {}, "blue": {}}
        for team, score in scores.items():
            alliance = team_alliance.get(team, "unknown")
            scoring.setdefault(alliance, {})[str(team)] = score

        manifest = {
            "result_id": result_id,
            "job_id": job_id,
            "match_key": match_key,
            "model_name": model_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scoring": scoring,
            "robots": {
                str(team): {
                    "alliance": team_alliance.get(team, "unknown"),
                    "score": scores.get(team, 0),
                    "heatmap_url": heatmap_paths.get(team),
                    "position_count": len(positions.get(team, [])),
                }
                for team in scores
            },
            "hub_zones": hub_zones,
            # Extensibility: additional scoring methods can append their own keys here
            "extra_scoring": {},
        }

        with open(out_dir / "results.json", "w") as f:
            json.dump(manifest, f, indent=2)

        return result_id

    # ── Heatmap generation ────────────────────────────────────────────────────

    def _generate_heatmap(
        self,
        team: int,
        positions: list[tuple[float, float, int]],
        frame_shape: tuple[int, int],
        out_dir: Path,
    ) -> Path:
        height, width = frame_shape
        xs = [p[0] for p in positions]
        ys = [p[1] for p in positions]

        # Build a 2-D histogram at a sensible resolution
        bins_x = min(80, width // 10)
        bins_y = min(50, height // 10)
        heatmap, _, _ = np.histogram2d(
            xs, ys,
            bins=[bins_x, bins_y],
            range=[[0, width], [0, height]],
        )
        heatmap = gaussian_filter(heatmap.T, sigma=2)

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.set_facecolor("#1a1a2e")
        fig.patch.set_facecolor("#0f0f1a")

        im = ax.imshow(
            heatmap,
            extent=[0, width, height, 0],
            cmap="hot",
            alpha=0.85,
            aspect="auto",
            interpolation="bilinear",
        )
        ax.set_title(f"Team {team} – Position Heatmap", color="white", fontsize=14, pad=12)
        ax.set_xlabel("X (px)", color="#888")
        ax.set_ylabel("Y (px)", color="#888")
        ax.tick_params(colors="#666")
        for spine in ax.spines.values():
            spine.set_edgecolor("#333")

        cbar = fig.colorbar(im, ax=ax)
        cbar.set_label("Time on field (frames)", color="#888")
        cbar.ax.yaxis.set_tick_params(color="#666")
        plt.setp(cbar.ax.yaxis.get_ticklabels(), color="#666")

        plt.tight_layout()
        out_path = out_dir / f"heatmap_{team}.png"
        plt.savefig(str(out_path), dpi=120, facecolor=fig.get_facecolor())
        plt.close(fig)
        return out_path
