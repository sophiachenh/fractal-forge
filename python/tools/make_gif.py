"""
python/tools/make_gif.py
-------------------------
Stitches the last N fingerprint PNGs into an animated GIF.
Reads fingerprints/<sha>.png files sorted by git commit order.

Usage:
  python3 make_gif.py \
    --fingerprints-dir fingerprints \
    --out fingerprints/history.gif \
    --frames 10 \
    --duration 800
"""

import argparse
import subprocess
import sys
from pathlib import Path


def get_commit_order(fingerprints_dir: str) -> list:
    """Return SHA list in chronological order using git log."""
    try:
        log = subprocess.check_output(
            ["git", "log", "--format=%H", "--no-merges"],
            text=True
        ).strip().splitlines()
        return [sha[:40] for sha in log]
    except Exception:
        return []


def make_gif(fingerprints_dir: str, out: str, frames: int, duration: int) -> int:
    try:
        from PIL import Image
    except ImportError:
        print("Installing Pillow...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow", "--quiet"])
        from PIL import Image

    p = Path(fingerprints_dir)
    png_files = {f.stem: f for f in p.glob("*.png")
                 if f.stem not in ("latest",) and len(f.stem) >= 7}

    if not png_files:
        print("No fingerprint PNGs found.")
        return 1

    # sort by git commit order (most recent last = plays forward in time)
    ordered_shas = get_commit_order(fingerprints_dir)
    ordered = []
    for sha in reversed(ordered_shas):   # oldest first
        for stem, path in png_files.items():
            if sha.startswith(stem) or stem.startswith(sha[:7]):
                ordered.append(path)
                break

    # fallback: sort by filename if git order unavailable
    if not ordered:
        ordered = sorted(png_files.values())

    # take last N frames
    ordered = ordered[-frames:]

    if not ordered:
        print("No frames to stitch.")
        return 1

    print(f"Stitching {len(ordered)} frames → {out}")

    imgs = []
    for path in ordered:
        try:
            img = Image.open(path).convert("RGB")
            # resize to reasonable GIF size (600px wide)
            w, h = img.size
            new_w = 600
            new_h = int(h * new_w / w)
            img = img.resize((new_w, new_h), Image.LANCZOS)
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
        loop=0,         # loop forever
        optimize=False,
    )
    print(f"Saved {out}  ({len(imgs)} frames, {duration}ms each)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fingerprints-dir", default="fingerprints")
    parser.add_argument("--out",              default="fingerprints/history.gif")
    parser.add_argument("--frames",           type=int, default=10)
    parser.add_argument("--duration",         type=int, default=800,
                        help="ms per frame")
    args = parser.parse_args()
    return make_gif(args.fingerprints_dir, args.out, args.frames, args.duration)


if __name__ == "__main__":
    sys.exit(main())
