"""
python/tools/evolve_fractal.py
-------------------------------
Maintains a persistent fractal state across commits.
Each commit mutates the previous state based on its build + git metrics.
The fractal evolves over your commit history rather than starting fresh.

State is stored in fingerprints/state.json and committed to the repo.

Usage:
  python3 evolve_fractal.py \
    --bep build_events.json \
    --state fingerprints/state.json \
    --out fingerprints/latest.png \
    --render-cli bazel-bin/cpp/renderer/render_cli \
    --sha HEAD
"""

import argparse
import json
import math
import os
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

try:
    import git_metrics as gm
    HAS_GIT = True
except ImportError:
    HAS_GIT = False

from bep_to_fractal import parse_bep, BuildMetrics, render


# ── Bounds ────────────────────────────────────────────────────────────────────
ZOOM_MIN      =    400.0
ZOOM_MAX      = 50_000.0
ITER_MIN      =    128
ITER_MAX      =    768
PALETTE_COUNT =      5

# Language anchor points — each language pulls center toward its region
LANGUAGE_ANCHORS = {
    "cpp":    (-0.7269,  0.1889),
    "rust":   (-0.5251,  0.5250),
    "python": (-1.1100, -0.2400),
}

# Failure anchor — chaotic edge
FAILURE_ANCHOR = (-0.7269, 0.1889)

# Default starting state
DEFAULT_STATE = {
    "center_x":     -0.5,
    "center_y":      0.0,
    "zoom":        300.0,
    "max_iter":    256,
    "palette":       1,
    "commit_count":  0,
}


# ── State I/O ─────────────────────────────────────────────────────────────────

def load_state(path: str) -> dict:
    try:
        with open(path) as f:
            state = json.load(f)
        # fill in any missing keys from default
        for k, v in DEFAULT_STATE.items():
            state.setdefault(k, v)
        return state
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(DEFAULT_STATE)


def save_state(state: dict, path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


# ── Delta computation ─────────────────────────────────────────────────────────

def apply_deltas(state: dict, build: BuildMetrics, git) -> dict:
    """Mutate fractal state based on current commit's metrics."""
    s = dict(state)

    lines_added   = getattr(git, "lines_added",   0)
    lines_deleted = getattr(git, "lines_deleted",  0)
    lang          = getattr(git, "dominant_language", "cpp")
    is_late       = getattr(git, "is_late_night",  False)
    days_since    = getattr(git, "days_since_last", 0.0)
    sha           = getattr(git, "sha", "unknown")

    # ── Zoom: lines added zooms in, lines deleted zooms out ───────────────────
    zoom_delta  = 1.0 + (lines_added  / 1_200.0)
    zoom_delta *= 1.0 - (lines_deleted / 1_800.0)
    zoom_delta  = max(0.6, min(zoom_delta, 1.8))   # cap single-commit change

    # fast cached build nudges zoom in, slow cold build nudges out
    cache_zoom = 1.0 + (build.cache_hit_rate - 0.5) * 0.3
    zoom_delta *= cache_zoom

    s["zoom"] *= zoom_delta
    s["zoom"]  = max(ZOOM_MIN, min(s["zoom"], ZOOM_MAX))

    # ── Center: nudge toward dominant language anchor ─────────────────────────
    anchor_x, anchor_y = LANGUAGE_ANCHORS.get(lang, LANGUAGE_ANCHORS["cpp"])
    pull_strength = 0.08   # how fast center moves toward anchor per commit

    if not build.build_success:
        # failure: hard snap toward chaotic edge
        anchor_x, anchor_y = FAILURE_ANCHOR
        pull_strength = 0.35

    s["center_x"] += (anchor_x - s["center_x"]) * pull_strength
    s["center_y"] += (anchor_y - s["center_y"]) * pull_strength

    # staleness drift — long gap since last commit adds small deterministic drift
    if days_since > 1.0:
        # use sha hash for deterministic but unique drift per commit
        sha_int   = int(sha[:6], 16) if sha != "unknown" else 0
        drift_x   = math.sin(sha_int) * 0.003 * min(days_since, 14.0) / 14.0
        drift_y   = math.cos(sha_int) * 0.003 * min(days_since, 14.0) / 14.0
        s["center_x"] += drift_x
        s["center_y"] += drift_y

    # ── Max iterations: drifts toward cache-rate-driven target ───────────────
    target_iter = int(ITER_MIN + build.cache_hit_rate * (ITER_MAX - ITER_MIN))
    if is_late:
        target_iter = min(target_iter + 100, ITER_MAX)
    # smooth convergence — move 20% toward target each commit
    s["max_iter"] = int(s["max_iter"] + (target_iter - s["max_iter"]) * 0.2)
    s["max_iter"] = max(ITER_MIN, min(s["max_iter"], ITER_MAX))

    # ── Palette: cycles on late night, snaps to red on failure ───────────────
    if not build.build_success:
        s["palette"] = 3   # red
    elif is_late:
        s["palette"] = (s["palette"] + 1) % PALETTE_COUNT
    elif build.cache_hit_rate >= 0.8:
        s["palette"] = 0   # gold — well cached
    elif build.cache_hit_rate >= 0.4:
        s["palette"] = 1   # blue
    else:
        s["palette"] = 2   # green — cold

    s["commit_count"] = state.get("commit_count", 0) + 1

    return s


# ── Report ────────────────────────────────────────────────────────────────────

def print_report(old: dict, new: dict, build: BuildMetrics, git) -> None:
    palette_names = ["gold", "blue", "green", "red", "plasma"]
    print(f"""
evolution  commit #{new['commit_count']}  sha={getattr(git, 'sha', '?')}
build      {'SUCCESS' if build.build_success else 'FAILURE'}  {build.wall_time_ms:.0f}ms  cache={build.cache_hit_rate*100:.0f}%
git        +{getattr(git,'lines_added',0)}/-{getattr(git,'lines_deleted',0)}  lang={getattr(git,'dominant_language','?')}  late={getattr(git,'is_late_night',False)}

           center  ({old['center_x']:.5f}, {old['center_y']:.5f})  ->  ({new['center_x']:.5f}, {new['center_y']:.5f})
           zoom    {old['zoom']:.0f}  ->  {new['zoom']:.0f}
           iter    {old['max_iter']}  ->  {new['max_iter']}
           palette {palette_names[old['palette']]}  ->  {palette_names[new['palette']]}
""")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bep",        required=True)
    parser.add_argument("--state",      default="fingerprints/state.json")
    parser.add_argument("--out",        required=True)
    parser.add_argument("--render-cli",
                        default=os.environ.get("RENDER_CLI_PATH",
                                               "bazel-bin/cpp/renderer/render_cli"))
    parser.add_argument("--sha",        default="HEAD")
    parser.add_argument("--width",      type=int, default=1200)
    parser.add_argument("--height",     type=int, default=900)
    args = parser.parse_args()

    if not Path(args.render_cli).exists():
        print(f"ERROR: render_cli not found: {args.render_cli}", file=sys.stderr)
        return 1

    # load persistent state
    old_state = load_state(args.state)

    # get current commit's metrics
    build = parse_bep(args.bep)
    git   = gm.extract(args.sha) if HAS_GIT else type("G", (), {
        "sha": args.sha, "lines_added": 0, "lines_deleted": 0,
        "dominant_language": "cpp", "is_late_night": False,
        "days_since_last": 0.0,
    })()

    # mutate state
    new_state = apply_deltas(old_state, build, git)
    print_report(old_state, new_state, build, git)

    # render with new state
    from bep_to_fractal import FractalParams
    params = FractalParams(
        width=args.width, height=args.height,
        center_x=new_state["center_x"],
        center_y=new_state["center_y"],
        zoom=new_state["zoom"],
        max_iter=new_state["max_iter"],
        palette=new_state["palette"],
    )

    print(f"rendering {args.out} ...")
    render(params, args.out, args.render_cli)

    # save updated state
    save_state(new_state, args.state)
    print(f"state saved to {args.state}")
    print(f"done.  open {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
