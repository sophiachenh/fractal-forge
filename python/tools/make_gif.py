"""
python/tools/make_gif.py
-------------------------
Stitches the last N fingerprint PNGs into an animated GIF.
Sorts by file modification time — works regardless of SHA matching.
"""

import argparse
import subprocess
import sys
from pathlib import Path


def make_gif(fingerprints_dir: str, out: str, frames: int, duration: int) -> int:
    try:
        from PIL import Image
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow", "--quiet"])
        from PIL import Image

    p = Path(fingerprints_dir)
    png_files = [f for f in p.glob("*.png") if f.stem != "latest"]

    if not png_files:
        print("No fingerprint PNGs found.")
        return 1

    # sort by modification time (oldest first)
    png_files.sort(key=lambda f: f.stat().st_mtime)
    print(f"Found {len(png_files)} fingerprints, using last {min(frames, len(png_files))}")

    # take last N
    png_files = png_files[-frames:]

    imgs = []
    for path in png_files:
        try:
            img = Image.open(path).convert("RGB")
            img = img.resize((600, 450), Image.LANCZOS)
            imgs.append(img)
            print(f"  + {path.name}")
        except Exception as e:
            print(f"  skipping {path.name}: {e}")

    if not imgs:
        print("No valid images.")
        return 1

    imgs[0].save(
        out,
        save_all=True,
        append_images=imgs[1:],
        duration=duration,
        loop=0,
        optimize=False,
    )
    print(f"Saved {out}  ({len(imgs)} frames, {duration}ms each)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fingerprints-dir", default="fingerprints")
    parser.add_argument("--out",              default="fingerprints/history.gif")
    parser.add_argument("--frames",           type=int, default=10)
    parser.add_argument("--duration",         type=int, default=800)
    args = parser.parse_args()
    return make_gif(args.fingerprints_dir, args.out, args.frames, args.duration)


if __name__ == "__main__":
    sys.exit(main())