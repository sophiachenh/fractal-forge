"""
python/tools/bench.py
---------------------
Runs the Rust CLI benchmark, parses the JSON output, and writes a
Markdown summary — used by CI to track build performance over time.
"""

import json
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List


@dataclass
class BenchSummary:
    timestamp: float
    runs: int
    resolution: str
    mean_ms: float
    min_ms: float
    max_ms: float
    mpixels_per_s: float
    git_sha: str


def run_bench(fractal_cli: str, runs: int = 5, width: int = 800, height: int = 600) -> dict:
    result = subprocess.run(
        [fractal_cli, "bench", "--runs", str(runs), "--width", str(width), "--height", str(height)],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       text=True).strip()
    except Exception:
        return "unknown"


def write_markdown(summary: BenchSummary, out_path: Path) -> None:
    md = f"""# Fractal Forge — Benchmark Report

| Metric | Value |
|---|---|
| Resolution | {summary.resolution} |
| Runs | {summary.runs} |
| Mean render time | {summary.mean_ms:.1f} ms |
| Min render time  | {summary.min_ms:.1f} ms |
| Max render time  | {summary.max_ms:.1f} ms |
| Throughput       | {summary.mpixels_per_s:.1f} Mpx/s |
| Git SHA          | `{summary.git_sha}` |

_Generated at {time.strftime('%Y-%m-%d %Human:%M:%S', time.gmtime(summary.timestamp))} UTC_
"""
    out_path.write_text(md)
    print(f"Wrote benchmark report → {out_path}")


def main(argv: List[str]) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Run fractal benchmark and emit Markdown report")
    parser.add_argument("--cli",    default="bazel-bin/rust/cli/fractal_cli", help="Path to Rust CLI binary")
    parser.add_argument("--runs",   type=int, default=5)
    parser.add_argument("--width",  type=int, default=800)
    parser.add_argument("--height", type=int, default=600)
    parser.add_argument("--out",    default="bench_report.md")
    args = parser.parse_args(argv)

    print(f"Running {args.runs} renders at {args.width}x{args.height}…")
    raw = run_bench(args.cli, args.runs, args.width, args.height)

    summary = BenchSummary(
        timestamp=time.time(),
        runs=raw["runs"],
        resolution=f"{raw['width']}x{raw['height']}",
        mean_ms=raw["mean_ms"],
        min_ms=raw["min_ms"],
        max_ms=raw["max_ms"],
        mpixels_per_s=raw["mpixels_per_s"],
        git_sha=git_sha(),
    )

    write_markdown(summary, Path(args.out))
    print(json.dumps(asdict(summary), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
