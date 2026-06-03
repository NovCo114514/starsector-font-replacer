from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .analyzer import analyze_fontlib
from .errors import FontGenError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="starsector-fontgen-analyze-fontlib",
        description="Analyze an existing Starsector AngelCode BMFont library without modifying it.",
    )
    parser.add_argument(
        "--font-dir",
        required=True,
        type=Path,
        help="Directory containing existing .fnt and PNG font files, e.g. graphics/fonts.",
    )
    parser.add_argument(
        "--config-dir",
        required=True,
        type=Path,
        help="Directory containing settings.json or other text config files to scan for font references.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output directory for fontlib_analysis_report.md and charset_union_from_fontlib.txt.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = analyze_fontlib(args.font_dir, args.config_dir, args.output)
    except FontGenError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Scanned {len(result.fonts)} .fnt file(s)")
    print(f"Wrote {result.charset_path}")
    print(f"Wrote {result.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
