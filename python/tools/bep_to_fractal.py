"""
python/tools/bep_to_fractal.py
-------------------------------
Parses a Bazel BEP JSON file + git metrics, maps them to fractal
render parameters, and invokes the C++ renderer.

Build metrics  -> zoom, iteration depth, cache-based center selection
Git metrics    -> language-based center shift, churn zoom boost,
                  late-night detail boost, staleness color nudge
"""

import argparse
import json
import math
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import git_metrics as gm


# ── Interesting boundary points (never interior, always visually rich) ────────
# Indexed 0-7, selected by cache hit rate + dominant language
BOUNDARY_POINTS = [
    (-0.7269,  0.1889),   # 0  seahorse valley       (cpp dominant)
    (-0.5251,  0.5250),   # 1  top bulb spiral        (rust dominant)
    (-1.7499,  0.0000),   # 2  real axis tip
    (-0.1011,  0.9563),   # 3  top of the set
    (-1.2560,  0.3800),   # 4  mini-brot region
    (-0.7436,  0.1319),   # 5  deep seahorse
    ( 0.2800,  0.0085),   # 6  period-2 bulb edge
    (-1.1100, -0.2400),   # 7  lower spike           (python dominant)
]

LANGUAGE_BASE = {"cpp": 0, "rust": 1, "python": 7}
OVERVIEW_CENTER = (-0.5, 0.0)


# ── Build metrics (from BEP) ──────────────────────────────────────────────────

@dataclass
class BuildMetrics:
    wall_time_ms:     float
    cpu_time_ms:      float
    actions_executed: int
    cache_misses:     int
    cache_hits:       int
    build_success:    bool

    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0

    @property
    def cpu_wall_ratio(self) -> float:
        return self.cpu_time_ms / self.wall_time_ms if self.wall_time_ms > 0 else 1.0


def parse_bep(bep_path: str) -> BuildMetrics:
    wall_ms = cpu_ms = 0.0
    actions = cache_misses = 0
    success = False

    with open(bep_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            if "buildMetrics" in event:
                m      = event["buildMetrics"]
                timing = m.get("timingMetrics", {})
                wall_ms = float(timing.get("wallTimeInMs", 0))
                cpu_ms  = float(timing.get("cpuTimeInMs",  0))
                action_summary = m.get("actionSummary", {})
                actions        = int(action_summary.get("actionsExecuted", 0))
                cache_stats    = action_summary.get("actionCacheStatistics", {})
                cache_misses   = int(cache_stats.get("misses", 0))

            if "finished" in event:
                success = event["finished"].get("exitCode", {}).get("name", "") == "SUCCESS"

    cache_hits = max(0, actions - cache_misses)
    return BuildMetrics(
        wall_time_ms=wall_ms, cpu_time_ms=cpu_ms,
        actions_executed=max(actions, 1),
        cache_misses=cache_misses, cache_hits=cache_hits,
        build_success=success,
    )


# ── Fractal params ────────────────────────────────────────────────────────────

@dataclass
class FractalParams:
    width: int; height: int
    center_x: float; center_y: float
    zoom: float; max_iter: int

    def describe(self) -> str:
        return (f"center=({self.center_x:.6f}, {self.center_y:.6f})  "
                f"zoom={self.zoom:.1f}  max_iter={self.max_iter}")


def compute_params(
    build: BuildMetrics,
    git: gm.GitMetrics,
    width: int = 1200,
    height: int = 900,
) -> FractalParams:

    # ── Max iterations ────────────────────────────────────────────────────────
    # Base: scales with Bazel actions [128, 384]
    action_norm = min(build.actions_executed, 50) / 50.0
    max_iter    = int(128 + action_norm * 256)

    # Late night commit: +25% more detail
    if git.is_late_night:
        max_iter = int(max_iter * 1.25)

    # High churn commit: +10% more detail (lots of changes = more complexity)
    if git.churn > 200:
        max_iter = int(max_iter * 1.10)

    max_iter = min(max_iter, 512)

    # ── Zoom ──────────────────────────────────────────────────────────────────
    # Fast cached build = deep zoom [200, 8000]
    wall_clamped = max(1_000.0, min(build.wall_time_ms, 60_000.0))
    t    = math.log(wall_clamped / 1_000.0) / math.log(60.0)
    t    = max(0.0, min(t, 1.0))
    zoom = 8_000.0 - t * (8_000.0 - 200.0)   # fast=8000, slow=200

    # Lines added nudge zoom in, lines deleted nudge out
    churn_factor = 1.0 + (git.lines_added - git.lines_deleted) / 5_000.0
    churn_factor = max(0.7, min(churn_factor, 1.4))
    zoom *= churn_factor

    # ── Center ────────────────────────────────────────────────────────────────
    if not build.build_success:
        # Failed build always lands on the chaotic seahorse edge
        center_x, center_y = BOUNDARY_POINTS[0]
    elif build.cache_hit_rate < 0.1:
        # Nearly cold build: wide overview
        center_x, center_y = OVERVIEW_CENTER
        zoom = min(zoom, 300.0)
    else:
        # Pick base boundary point from dominant language
        lang  = git.dominant_language
        base  = LANGUAGE_BASE.get(lang, 0)

        # Cache hit rate shifts within the available points
        offset = int(build.cache_hit_rate * 3)
        idx    = (base + offset) % len(BOUNDARY_POINTS)
        center_x, center_y = BOUNDARY_POINTS[idx]

        # Parallelism fingerprint (cpu/wall ratio)
        parallel_shift = (min(build.cpu_wall_ratio, 4.0) - 1.0) * 0.003
        center_y += parallel_shift

        # Days since last commit: stale repo drifts center slightly
        drift = min(git.days_since_last, 30.0) / 30.0 * 0.002
        center_x += drift

    return FractalParams(
        width=width, height=height,
        center_x=center_x, center_y=center_y,
        zoom=zoom, max_iter=max_iter,
    )


# ── Render ────────────────────────────────────────────────────────────────────

def render(params: FractalParams, out_path: str, render_cli: str) -> None:
    with open(out_path, "wb") as f:
        result = subprocess.run(
            [render_cli,
             str(params.width), str(params.height),
             str(params.center_x), str(params.center_y),
             str(params.zoom), str(params.max_iter)],
            stdout=f, stderr=subprocess.PIPE,
        )
    if result.returncode != 0:
        raise RuntimeError(f"render_cli failed: {result.stderr.decode()}")


# ── Report ────────────────────────────────────────────────────────────────────

def print_report(b: BuildMetrics, g: gm.GitMetrics, p: FractalParams) -> None:
    hit_pct = b.cache_hit_rate * 100
    status  = "SUCCESS" if b.build_success else "FAILURE"
    print(f"""
build metrics
  status          {status}
  wall time       {b.wall_time_ms:.0f} ms
  cache hits      {b.cache_hits} ({hit_pct:.1f}%)
  actions         {b.actions_executed}

git metrics
  sha             {g.sha}
  lines added     +{g.lines_added}  deleted -{g.lines_deleted}
  files changed   {g.files_changed}  (cpp={g.cpp_files} rust={g.rust_files} py={g.python_files})
  dominant lang   {g.dominant_language}
  hour of commit  {g.hour_of_day:02d}:xx  {'(late night)' if g.is_late_night else ''}
  days since last {g.days_since_last:.1f}

fractal
  {p.describe()}
""")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bep",        required=True)
    parser.add_argument("--out",        required=True)
    parser.add_argument("--render-cli",
                        default=os.environ.get("RENDER_CLI_PATH",
                                               "bazel-bin/cpp/renderer/render_cli"))
    parser.add_argument("--width",      type=int, default=1200)
    parser.add_argument("--height",     type=int, default=900)
    parser.add_argument("--sha",        default="HEAD")
    args = parser.parse_args()

    if not Path(args.bep).exists():
        print(f"ERROR: {args.bep} not found", file=sys.stderr); return 1
    if not Path(args.render_cli).exists():
        print(f"ERROR: render_cli not found at {args.render_cli}", file=sys.stderr); return 1

    build  = parse_bep(args.bep)
    git    = gm.extract(args.sha)
    params = compute_params(build, git, args.width, args.height)

    print_report(build, git, params)

    print(f"rendering {args.out} ...")
    render(params, args.out, args.render_cli)
    print(f"done.  open {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())