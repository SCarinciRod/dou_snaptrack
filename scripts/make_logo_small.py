#!/usr/bin/env python3
"""Small utility to create reduced logo PNGs for the app.

Usage examples:
  python scripts/make_logo_small.py                    # uses assets/logo.png, creates 48px and logo-small.png
  python scripts/make_logo_small.py --src path/to/orig.png --sizes 32 48 64

This script center-crops to a square and resizes with a high-quality filter.
Requires Pillow: `pip install Pillow`.
"""
from pathlib import Path
from PIL import Image
import argparse
import sys


def center_crop_square(im: Image.Image) -> Image.Image:
    w, h = im.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    return im.crop((left, top, left + side, top + side))


def make_variants(src: Path, out_dir: Path, sizes: list[int], default_name: int = 48) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    with Image.open(src) as im:
        # Convert to RGBA to preserve transparency when present
        im = im.convert("RGBA")
        im_c = center_crop_square(im)
        for s in sizes:
            im_small = im_c.resize((s, s), Image.LANCZOS)
            out_path = out_dir / f"logo-{s}.png"
            im_small.save(out_path, optimize=True)
            saved.append(out_path)
        # create canonical `logo-small.png`
        canonical = out_dir / "logo-small.png"
        default_path = out_dir / f"logo-{default_name}.png"
        if default_path.exists():
            canonical.write_bytes(default_path.read_bytes())
            saved.append(canonical)
    return saved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create small logo variants for Streamlit app")
    parser.add_argument("--src", type=Path, default=Path("assets/logo.png"), help="Source PNG path")
    parser.add_argument("--out", type=Path, default=Path("assets"), help="Output directory")
    parser.add_argument("--sizes", type=int, nargs="+", default=[48], help="Sizes (px) to generate")
    parser.add_argument("--default", type=int, default=48, help="Which size becomes logo-small.png")
    args = parser.parse_args(argv)

    if not args.src.exists():
        print(f"Source file not found: {args.src}", file=sys.stderr)
        return 2
    try:
        saved = make_variants(args.src, args.out, args.sizes, args.default)
    except Exception as exc:  # pragma: no cover - simple CLI helper
        print(f"Failed to process image: {exc}", file=sys.stderr)
        return 3
    for p in saved:
        print("Saved", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
