"""
python/tools/bep_to_fractal.py
-------------------------------
Parses a Bazel Build Event Protocol (BEP) JSON file, extracts build
performance metrics, maps them to fractal render parameters, and
invokes the C++ renderer to produce a fractal image that visually
encodes the build's health.

Metric → Fractal parameter mapping:
  wall_time_ms    → zoom   (FAST build = deep zoom into spiral detail)
                           (SLOW build = wide overview, more structure visible)
  cache_hit_rate  → center (high cache = stable deep point, low cache = chaotic edge)
  actions_executed→ max_iter (more actions = more iteration depth)
  build_success   → palette anchor (failure always lands on a known chaotic edge)
  cpu_wall_ratio  → subtle center_y shift (parallelism fingerprint)
"""

import argparse
import json
import math
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


# ── Interesting fractal coordinates (always on the boundary, never interior) ──
# Each is a known visually rich point on the Mandelbrot boundary.
DEEP_POINTS = [
    (-0.7269,  0.1889),   # classic seahorse valley spiral
    (-0.5251,  0.5250),   # top bulb spiral
    (-1.7499,  0.0000),   # tip of the real axis
    (-0.1011,  0.9563),   # top of the set
    (-1.2560,  0.3800),   # mini-brot region
    (-0.7436,  0.1319),   # deep seahorse
    ( 0.2800,  0.0085),   # period-2 bulb edge
    (-1.1100, -0.2400),   # lower spike
]

# Wide overview center — always shows the full set structure
OVERVIEW_CENTER = (-0.5, 0.0)


# ── BEP parsing ───────────────────────────────────────────────────────────────

@dataclass
class BuildMetrics:
    wall_time_ms:    float
    cpu_time_ms:     float
    actions_executed: int
    cache_misses:    int
    cache_hits:      int
    build_success:   bool
    git_sha:         str = "unknown"

    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0

    @property
    def cpu_wall_ratio(self) -> float:
        return self.cpu_time_ms / self.wall_time_ms if self.wall_time_ms > 0 else 1.0


def parse_bep(bep_path: str) -> BuildMetrics:
    wall_ms = 0.0
    cpu_ms  = 0.0
    actions = 0
    cache_misses = 0
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
                m       = event["buildMetrics"]
                timing  = m.get("timingMetrics", {})
                wall_ms = float(timing.get("wallTimeInMs", 0))
                cpu_ms  = float(timing.get("cpuTimeInMs",  0))
                action_summary = m.get("actionSummary", {})
                actions = int(action_summary.get("actionsExecuted", 0))
                cache_stats  = action_summary.get("actionCacheStatistics", {})
                cache_misses = int(cache_stats.get("misses", 0))

            if "finished" in event:
                exit_code = event["finished"].get("exitCode", {})
                success   = exit_code.get("name", "") == "SUCCESS"

    cache_hits = max(0, actions - cache_misses)
    return BuildMetrics(
        wall_time_ms=wall_ms,
        cpu_time_ms=cpu_ms,
        actions_executed=max(actions, 1),
        cache_misses=cache_misses,
        cache_hits=cache_hits,
        build_success=success,
    )


# ── Metric → fractal parameter mapping ───────────────────────────────────────

@dataclass
class FractalParams:
    width:    int
    height:   int
    center_x: float
    center_y: float
    zoom:     float
    max_iter: int

    def describe(self) -> str:
        return (
            f"center=({self.center_x:.6f}, {self.center_y:.6f})  "
            f"zoom={self.zoom:.1f}  max_iter={self.max_iter}"
        )


def metrics_to_fractal(m: BuildMetrics, width: int = 1200, height: int = 900) -> FractalParams:
    """
    Map build metrics to fractal render parameters.

    Fast cached build  → deep zoom into a spiral (beautiful, detailed)
    Slow cold build    → wide zoom showing full set structure (more overview-y)
    Build failure      → always lands on the seahorse valley edge (visually chaotic)
    Cache hit rate     → selects which interesting boundary point to zoom into
    Actions executed   → iteration depth (more actions = more detail rendered)
    """

    # ── Max iterations: scales with actions, clamped [128, 512] ──────────────
    action_norm = min(m.actions_executed, 50) / 50.0   # normalize to [0,1]
    max_iter    = int(128 + action_norm * (512 - 128))

    # ── Zoom: fast build = deep, slow build = wide ────────────────────────────
    # Wall time clamped to [1s, 60s] → zoom mapped [200, 8000]
    wall_clamped = max(1_000.0, min(m.wall_time_ms, 60_000.0))
    # log scale: fast (1s) → t≈1.0, slow (60s) → t≈0.0
    t    = 1.0 - math.log(wall_clamped / 1_000.0) / math.log(60.0)
    t    = max(0.0, min(t, 1.0))
    zoom = 200.0 + t * (8_000.0 - 200.0)

    # ── Center: failure always → seahorse valley (known chaotic boundary) ─────
    if not m.build_success:
        center_x, center_y = DEEP_POINTS[0]   # -0.7269, 0.1889
    else:
        # Cache hit rate picks which interesting boundary point to zoom into
        # 0% cache hits → overview center (wide, undetailed)
        # 100% cache hits → deepest spiral point
        if m.cache_hit_rate < 0.1:
            # Almost no cache — show the wide overview
            center_x, center_y = OVERVIEW_CENTER
            zoom = min(zoom, 300.0)   # don't zoom deep into the overview
        else:
            # Pick a boundary point based on cache hit rate
            idx      = int(m.cache_hit_rate * (len(DEEP_POINTS) - 1))
            idx      = max(0, min(idx, len(DEEP_POINTS) - 1))
            center_x, center_y = DEEP_POINTS[idx]

        # Subtle parallelism fingerprint on center_y
        parallel_shift = (min(m.cpu_wall_ratio, 4.0) - 1.0) * 0.003
        center_y      += parallel_shift

    return FractalParams(
        width=width, height=height,
        center_x=center_x, center_y=center_y,
        zoom=zoom, max_iter=max_iter,
    )


# ── Render ────────────────────────────────────────────────────────────────────

def render(params: FractalParams, out_path: str, render_cli: str) -> None:
    with open(out_path, "wb") as out_file:
        result = subprocess.run(
            [
                render_cli,
                str(params.width), str(params.height),
                str(params.center_x), str(params.center_y),
                str(params.zoom),    str(params.max_iter),
            ],
            stdout=out_file,
            stderr=subprocess.PIPE,
        )
    if result.returncode != 0:
        raise RuntimeError(f"render_cli failed: {result.stderr.decode()}")


# ── Report ────────────────────────────────────────────────────────────────────

def print_report(m: BuildMetrics, p: FractalParams) -> None:
    hit_pct = m.cache_hit_rate * 100
    status  = "SUCCESS" if m.build_success else "FAILURE"
    print(f"""
┌─ Build Metrics ──────────────────────────────────┐
│  Status          {status:<32}│
│  Wall time       {m.wall_time_ms:>8.0f} ms                      │
│  CPU time        {m.cpu_time_ms:>8.0f} ms                      │
│  CPU/wall ratio  {m.cpu_wall_ratio:>8.2f}x                       │
│  Actions         {m.actions_executed:>8d}                         │
│  Cache hits      {m.cache_hits:>8d}  ({hit_pct:5.1f}%)              │
│  Cache misses    {m.cache_misses:>8d}                         │
│  Git SHA         {m.git_sha:<32}│
├─ Fractal Parameters ─────────────────────────────┤
│  {p.describe():<49}│
└──────────────────────────────────────────────────┘""")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Map Bazel build metrics → fractal render parameters → image"
    )
    parser.add_argument("--bep",        required=True)
    parser.add_argument("--out",        required=True)
    parser.add_argument("--render-cli",
                        default=os.environ.get(
                            "RENDER_CLI_PATH", "bazel-bin/cpp/renderer/render_cli"))
    parser.add_argument("--width",      type=int, default=1200)
    parser.add_argument("--height",     type=int, default=900)
    parser.add_argument("--git-sha",    default="unknown")
    args = parser.parse_args()

    if not Path(args.bep).exists():
        print(f"ERROR: BEP file not found: {args.bep}", file=sys.stderr)
        return 1
    if not Path(args.render_cli).exists():
        print(f"ERROR: render_cli not found: {args.render_cli}", file=sys.stderr)
        return 1

    print(f"Parsing {args.bep} ...")
    metrics = parse_bep(args.bep)
    metrics.git_sha = args.git_sha

    params = metrics_to_fractal(metrics, args.width, args.height)
    print_report(metrics, params)

    print(f"\nRendering → {args.out} ...")
    render(params, args.out, args.render_cli)
    print(f"Done.  open {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())