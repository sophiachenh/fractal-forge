"""
python/tests/test_render_pipeline.py
--------------------------------------
Integration tests — verify the full C++ → Rust → Python pipeline works end to end.
Run with: bazel test //python/tests:pipeline_test
"""

import json
import os
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path


RENDER_CLI = os.environ.get("RENDER_CLI_PATH", "bazel-bin/cpp/renderer/render_cli")
FRACTAL_CLI = os.environ.get("FRACTAL_CLI_PATH", "bazel-bin/rust/cli/fractal_cli")


def read_ppm(path: str):
    """Parse a binary PPM file → (width, height, pixel_bytes)."""
    with open(path, "rb") as f:
        assert f.readline().strip() == b"P6"
        dims = f.readline().split()
        w, h = int(dims[0]), int(dims[1])
        f.readline()  # max value line
        data = f.read()
    return w, h, data


class TestCppRenderer(unittest.TestCase):
    def test_renders_correct_size(self):
        with tempfile.NamedTemporaryFile(suffix=".ppm", delete=False) as tmp:
            out = tmp.name
        try:
            subprocess.run(
                [RENDER_CLI, "400", "300", "-0.5", "0", "150", "128"],
                stdout=open(out, "wb"), check=True,
            )
            w, h, data = read_ppm(out)
            self.assertEqual(w, 400)
            self.assertEqual(h, 300)
            self.assertEqual(len(data), 400 * 300 * 3)
        finally:
            Path(out).unlink(missing_ok=True)

    def test_interior_pixels_are_black(self):
        """Center of default render is inside the set — must render black."""
        with tempfile.NamedTemporaryFile(suffix=".ppm", delete=False) as tmp:
            out = tmp.name
        try:
            subprocess.run(
                [RENDER_CLI, "100", "100", "-0.5", "0", "50", "256"],
                stdout=open(out, "wb"), check=True,
            )
            _, _, data = read_ppm(out)
            # Center pixel
            idx = (50 * 100 + 50) * 3
            r, g, b = data[idx], data[idx + 1], data[idx + 2]
            self.assertEqual((r, g, b), (0, 0, 0), "center should be black (inside set)")
        finally:
            Path(out).unlink(missing_ok=True)


class TestRustCli(unittest.TestCase):
    def test_bench_outputs_valid_json(self):
        result = subprocess.run(
            [FRACTAL_CLI, "bench", "--runs", "2", "--width", "200", "--height", "150"],
            capture_output=True, text=True, check=True,
        )
        data = json.loads(result.stdout)
        self.assertEqual(data["runs"], 2)
        self.assertEqual(data["width"], 200)
        self.assertIn("mean_ms", data)
        self.assertGreater(data["mpixels_per_s"], 0)


if __name__ == "__main__":
    unittest.main()
