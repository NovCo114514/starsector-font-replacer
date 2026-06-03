from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .errors import FontGenError
from .generator import (
    ALLOWED_ATLAS_SIZES,
    FontGenConfig,
    generate_batch,
    generate_font_result,
    parse_sizes_argument,
    patch_instructions_path,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="starsector-fontgen",
        description="Generate Starsector-compatible AngelCode BMFont files from TTF/OTF fonts.",
    )
    parser.add_argument("--font", required=True, type=Path, help="Path to a .ttf or .otf font.")
    parser.add_argument(
        "--text-dir",
        required=True,
        type=Path,
        help="Directory containing Starsector or mod text data.",
    )
    parser.add_argument(
        "--extra-charset",
        type=Path,
        default=None,
        help="Optional extra charset text file.",
    )
    parser.add_argument("--size", type=int, default=16, help="Font size in pixels.")
    parser.add_argument(
        "--sizes",
        default=None,
        help="Comma-separated batch sizes, e.g. 12,16,20,24. Overrides --size when provided.",
    )
    parser.add_argument(
        "--atlas-size",
        type=int,
        choices=ALLOWED_ATLAS_SIZES,
        default=2048,
        help="Square atlas size. Allowed: 512, 1024, 2048, 4096.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output file prefix, e.g. output/fonts/myfont16.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing output files.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = FontGenConfig(
        font=args.font,
        text_dir=args.text_dir,
        extra_charset=args.extra_charset,
        size=args.size,
        output=args.output,
        atlas_size=args.atlas_size,
        force=args.force,
    )

    try:
        if args.sizes is not None:
            sizes = parse_sizes_argument(args.sizes)
            batch = generate_batch(config, sizes)
        else:
            result = generate_font_result(config)
    except FontGenError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.sizes is not None:
        for entry in batch.entries:
            status = "OK" if entry.success else "FAILED"
            print(f"[{status}] size {entry.size}")
            if entry.error:
                print(f"  {entry.error}")
        print(f"Wrote {batch.summary_report}")
        print(f"Wrote {batch.patch_instructions}")
        if any(not entry.success for entry in batch.entries):
            return 1
    else:
        print(f"Wrote {result.outputs.fnt}")
        print(f"Wrote {result.outputs.atlas}")
        print(f"Wrote {result.outputs.preview}")
        print(f"Wrote {result.outputs.report}")
        print(f"Wrote {patch_instructions_path(config.output)}")
    return 0
