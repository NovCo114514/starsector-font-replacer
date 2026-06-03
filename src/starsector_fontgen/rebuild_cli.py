from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .errors import FontGenError
from .generator import ALLOWED_ATLAS_SIZES
from .rebuild_fontlib import RebuildConfig, rebuild_fontlib


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="starsector-fontgen-rebuild-fontlib",
        description="Rebuild an existing Starsector font library with matching .fnt and PNG filenames.",
    )
    parser.add_argument("--font", required=True, type=Path, help="Path to target .ttf or .otf font.")
    parser.add_argument(
        "--source-font-dir",
        required=True,
        type=Path,
        help="Existing CN font library graphics/fonts directory to mirror.",
    )
    parser.add_argument("--charset", required=True, type=Path, help="Filtered charset text file.")
    parser.add_argument(
        "--output-font-dir",
        required=True,
        type=Path,
        help="Directory where replacement .fnt and PNG files will be written.",
    )
    parser.add_argument(
        "--atlas-size",
        type=int,
        choices=ALLOWED_ATLAS_SIZES,
        default=4096,
        help="Square atlas size. Default: 4096.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing output files.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = RebuildConfig(
        font=args.font,
        source_font_dir=args.source_font_dir,
        charset=args.charset,
        output_font_dir=args.output_font_dir,
        atlas_size=args.atlas_size,
        force=args.force,
    )
    try:
        result = rebuild_fontlib(config)
    except FontGenError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    for entry in result.entries:
        status = "OK" if entry.success else "FAILED"
        print(f"[{status}] {entry.source_fnt.name}")
        if entry.error:
            print(f"  {entry.error}")
    print(f"Wrote {result.report_path}")
    return 1 if any(not entry.success for entry in result.entries) else 0


if __name__ == "__main__":
    raise SystemExit(main())
