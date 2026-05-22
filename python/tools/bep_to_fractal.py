"""
python/tools/bep_to_fractal.py
-------------------------------
Maps Bazel BEP + git metrics to fractal render parameters.

Palettes (driven by cache hit rate + build success):
  0  gold    high cache hit rate (>80%)
  1  blue    moderate cache (40-80%)
  2  green   low cache but successful (<40%)
  3  red     build failure
  4  plasma  late night commit (any cache rate)

Boundary points have tuned zoom ranges so spirals actually appear.
"""

import argparse
import json
import math
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# safely import git_metrics — may not be available in all environments
try:
    import git_metrics as gm
    HAS_GIT = True
except ImportError:
    HAS_GIT = False


# ── Boundary points with tuned zoom ranges ────────────────────────────────────
# Each entry: (center_x, center_y, zoom_min, zoom_max)
# zoom range is where the spiral structure is actually visible
BOUNDARY_POINTS = [
    (-0.7269,  0.1889,  2_000,  12_000),   # 0  seahorse valley spiral
    (-0.5251,  0.5250,  1_500,   8_000),   # 1  top bulb spiral
    (-1.7499,  0.0000,    800,   4_000),   # 2  real axis tip
    (-0.1011,  0.9563,  1_000,   6_000),   # 3  top of set
    (-1.2560,  0.3800,  2_000,  10_000),   # 4  mini-brot
    (-0.7436,  0.1319,  4_000,  20_000),   # 5  deep seahorse
    ( 0.2800,  0.0085,  1_200,   7_000),   # 6  period-2 bulb edge
    (-1.1100, -0.2400,  1_000,   5_000),   # 7  lower spike
]

LANGUAGE_BASE = {"cpp": 0, "rust": 1, "python": 7}
OVERVIEW_CENTER = (-0.5, 0.0, 200, 400)


# ── Default git metrics when git is unavailable ───────────────────────────────

@dataclass
class DefaultGitMetrics:
    sha:             str   = "unknown"
    lines_added:     int   = 0
    lines_deleted:   int   = 0
    files_changed:   int   = 0
    cpp_files:       int   = 0
    rust_files:      int   = 0
    python_files:    int   = 0
    hour_of_day:     int   = 12
    days_since_last: float = 0.0
    commit_msg_len:  int   = 0

    @property
    def churn(self): return 0
    @property
    def is_late_night(self): return False
    @property
    def dominant_language(self): return "cpp"


# ── BEP parsing ───────────────────────────────────────────────────────────────

@dataclass
class BuildMetrics:
    wall_time_ms:     float
    cpu_time_ms:      float
    actions_executed: int
    cache_misses:     int
    cache_hits:       int
    build_success:    bool

    @property
    def cache_hit_rate(self):
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0

    @property
    def cpu_wall_ratio(self):
        return self.cpu_time_ms / self.wall_time_ms if self.wall_time_ms > 0 else 1.0


def parse_bep(bep_path: str) -> BuildMetrics:
    """Parse BEP file — returns safe defaults if file is missing or malformed."""
    wall_ms = cpu_ms = 0.0
    actions = cache_misses = 0
    success = False

    try:
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

    except (FileNotFoundError, OSError):
        print(f"WARNING: could not read {bep_path}, using defaults", file=sys.stderr)

    cache_hits = max(0, actions - cache_misses)
    return BuildMetrics(
        wall_time_ms=max(wall_ms, 100.0),
        cpu_time_ms=cpu_ms,
        actions_executed=max(actions, 1),
        cache_misses=cache_misses,
        cache_hits=cache_hits,
        build_success=success,
    )


# ── Palette selection ─────────────────────────────────────────────────────────

def select_palette(build: BuildMetrics, git) -> int:
    if not build.build_success:
        return 3   # red — failure
    if git.is_late_night:
        return 4   # plasma — late night
    if build.cache_hit_rate >= 0.8:
        return 0   # gold — well cached
    if build.cache_hit_rate >= 0.4:
        return 1   # blue — moderate
    return 2       # green — cold but successful


# ── Fractal params ────────────────────────────────────────────────────────────

@dataclass
class FractalParams:
    width: int; height: int
    center_x: float; center_y: float
    zoom: float; max_iter: int; palette: int

    def describe(self):
        palette_names = ["gold", "blue", "green", "red", "plasma"]
        return (f"center=({self.center_x:.6f}, {self.center_y:.6f})  "
                f"zoom={self.zoom:.0f}  iter={self.max_iter}  "
                f"palette={palette_names[self.palette % 5]}")


def compute_params(build: BuildMetrics, git, width=1200, height=900) -> FractalParams:

    palette = select_palette(build, git)

    # ── Max iterations ────────────────────────────────────────────────────────
    action_norm = min(build.actions_executed, 50) / 50.0
    max_iter    = int(128 + action_norm * 256)
    if git.is_late_night:
        max_iter = int(max_iter * 1.25)
    if git.churn > 200:
        max_iter = int(max_iter * 1.10)
    max_iter = min(max_iter, 512)

    # ── Select boundary point ─────────────────────────────────────────────────
    if not build.build_success:
        pt = BOUNDARY_POINTS[0]   # seahorse valley — chaotic
    elif build.cache_hit_rate < 0.1:
        pt = OVERVIEW_CENTER
    else:
        lang   = git.dominant_language
        base   = LANGUAGE_BASE.get(lang, 0)
        offset = int(build.cache_hit_rate * 3)
        idx    = (base + offset) % len(BOUNDARY_POINTS)
        pt     = BOUNDARY_POINTS[idx]

    center_x, center_y = pt[0], pt[1]
    zoom_min, zoom_max  = pt[2], pt[3]

    # ── Zoom within the point's spiral-visible range ──────────────────────────
    wall_clamped = max(1_000.0, min(build.wall_time_ms, 60_000.0))
    t    = math.log(wall_clamped / 1_000.0) / math.log(60.0)
    t    = max(0.0, min(t, 1.0))
    # fast build = deep zoom (zoom_max), slow = shallow (zoom_min)
    zoom = zoom_max - t * (zoom_max - zoom_min)

    # churn nudge
    churn_factor = 1.0 + (git.lines_added - git.lines_deleted) / 5_000.0
    churn_factor = max(0.7, min(churn_factor, 1.3))
    zoom *= churn_factor
    zoom  = max(zoom_min, min(zoom, zoom_max))

    # parallelism + staleness fingerprint
    if build.build_success and build.cache_hit_rate >= 0.1:
        parallel_shift = (min(build.cpu_wall_ratio, 4.0) - 1.0) * 0.003
        center_y      += parallel_shift
        drift          = min(git.days_since_last, 30.0) / 30.0 * 0.002
        center_x      += drift

    return FractalParams(
        width=width, height=height,
        center_x=center_x, center_y=center_y,
        zoom=zoom, max_iter=max_iter, palette=palette,
    )


# ── Render ────────────────────────────────────────────────────────────────────

def render(params: FractalParams, out_path: str, render_cli: str) -> None:
    with open(out_path, "wb") as f:
        result = subprocess.run(
            [render_cli,
             str(params.width), str(params.height),
             str(params.center_x), str(params.center_y),
             str(params.zoom), str(params.max_iter), str(params.palette)],
            stdout=f, stderr=subprocess.PIPE,
        )
    if result.returncode != 0:
        raise RuntimeError(f"render_cli failed: {result.stderr.decode()}")


# ── Report ────────────────────────────────────────────────────────────────────

def print_report(b: BuildMetrics, g, p: FractalParams) -> None:
    hit_pct = b.cache_hit_rate * 100
    status  = "SUCCESS" if b.build_success else "FAILURE"
    sha     = getattr(g, 'sha', 'unknown')
    lang    = getattr(g, 'dominant_language', 'unknown')
    added   = getattr(g, 'lines_added', 0)
    deleted = getattr(g, 'lines_deleted', 0)
    hour    = getattr(g, 'hour_of_day', 0)
    late    = getattr(g, 'is_late_night', False)

    print(f"""
build   {status}  {b.wall_time_ms:.0f}ms  cache={hit_pct:.0f}%  actions={b.actions_executed}
git     {sha}  +{added}/-{deleted}  lang={lang}  hour={hour:02d}{'  (late night)' if late else ''}
fractal {p.describe()}
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

    if not Path(args.render_cli).exists():
        print(f"ERROR: render_cli not found: {args.render_cli}", file=sys.stderr)
        return 1

    build = parse_bep(args.bep)   # hardened — never crashes on bad/missing BEP

    if HAS_GIT:
        git = gm.extract(args.sha)
    else:
        git = DefaultGitMetrics(sha=args.sha)

    params = compute_params(build, git, args.width, args.height)
    print_report(build, git, params)

    print(f"rendering {args.out} ...")
    render(params, args.out, args.render_cli)
    print(f"done.  open {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())