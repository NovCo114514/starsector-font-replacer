from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .charset_filter import filter_charset_by_font
from .errors import FontGenError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="starsector-fontgen-filter-charset",
        description="Filter a charset file down to characters supported by a TTF/OTF font cmap.",
    )
    parser.add_argument("--font", required=True, type=Path, help="Path to the target .ttf or .otf font.")
    parser.add_argument("--charset", required=True, type=Path, help="Path to charset_union_from_fontlib.txt.")
    parser.add_argument("--output", required=True, type=Path, help="Path to write supported charset text.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing output/report files.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = filter_charset_by_font(
            args.font,
            args.charset,
            args.output,
            force=args.force,
        )
    except FontGenError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Input characters: {result.input_count}")
    print(f"Supported characters: {result.supported_count}")
    print(f"Unsupported characters: {result.unsupported_count}")
    print(f"Wrote {result.output_path}")
    print(f"Wrote {result.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
