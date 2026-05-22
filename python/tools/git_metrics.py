"""
python/tools/git_metrics.py
----------------------------
Extracts git metrics from the current repo and returns them as a
dataclass. Used by bep_to_fractal.py to add commit-level fingerprinting
on top of build metrics.

No dependencies outside stdlib — just shells out to git.
"""

import subprocess
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List


@dataclass
class GitMetrics:
    sha:                  str
    lines_added:          int
    lines_deleted:        int
    files_changed:        int
    cpp_files:            int
    rust_files:           int
    python_files:         int
    hour_of_day:          int    # 0-23
    days_since_last:      float  # days between last two commits
    commit_msg_len:       int

    @property
    def churn(self) -> int:
        return self.lines_added + self.lines_deleted

    @property
    def is_late_night(self) -> bool:
        return self.hour_of_day >= 22 or self.hour_of_day <= 4

    @property
    def dominant_language(self) -> str:
        counts = {
            "cpp":    self.cpp_files,
            "rust":   self.rust_files,
            "python": self.python_files,
        }
        return max(counts, key=counts.get)


def _run(cmd: List[str], fallback: str = "") -> str:
    try:
        return subprocess.check_output(
            cmd, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return fallback


def extract(sha: str = "HEAD") -> GitMetrics:
    """Extract git metrics for a given commit SHA (defaults to HEAD)."""

    resolved_sha = _run(["git", "rev-parse", "--short", sha], fallback="unknown")

    # Lines added/deleted and file counts from diff to parent
    diff_out = _run(["git", "diff", "--numstat", f"{sha}^", sha])
    lines_added = lines_deleted = files_changed = 0
    cpp_files = rust_files = python_files = 0

    for line in diff_out.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        added_str, deleted_str, filename = parts
        # Binary files show '-' — skip them
        if added_str == "-" or deleted_str == "-":
            continue
        try:
            added   = int(added_str)
            deleted = int(deleted_str)
        except ValueError:
            continue
        lines_added   += added
        lines_deleted += deleted
        files_changed += 1
        if re.search(r"\.(cc|cpp|h|hpp)$", filename):
            cpp_files += 1
        elif re.search(r"\.rs$", filename):
            rust_files += 1
        elif re.search(r"\.py$", filename):
            python_files += 1

    # Commit timestamp
    ts_str = _run(["git", "log", "-1", "--format=%ct", sha], fallback="0")
    try:
        ts = int(ts_str)
        dt = datetime.fromtimestamp(ts)
        hour_of_day = dt.hour
    except Exception:
        hour_of_day = 12

    # Days since previous commit
    timestamps = _run(
        ["git", "log", "-2", "--format=%ct", sha], fallback=""
    ).splitlines()
    try:
        if len(timestamps) == 2:
            days_since_last = (int(timestamps[0]) - int(timestamps[1])) / 86400.0
        else:
            days_since_last = 0.0
    except Exception:
        days_since_last = 0.0

    # Commit message length
    msg = _run(["git", "log", "-1", "--format=%s", sha], fallback="")
    commit_msg_len = len(msg)

    return GitMetrics(
        sha=resolved_sha,
        lines_added=lines_added,
        lines_deleted=lines_deleted,
        files_changed=files_changed,
        cpp_files=cpp_files,
        rust_files=rust_files,
        python_files=python_files,
        hour_of_day=hour_of_day,
        days_since_last=days_since_last,
        commit_msg_len=commit_msg_len,
    )
