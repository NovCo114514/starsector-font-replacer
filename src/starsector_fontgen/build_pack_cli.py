from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .errors import FontGenError
from .pack_builder import BuildPackConfig, build_pack


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="starsector-fontgen-build-pack",
        description="Build a distributable core-overwrite Starsector font replacement pack.",
    )
    parser.add_argument(
        "--replacement-font-dir",
        required=True,
        type=Path,
        help="Directory containing rebuilt replacement .fnt and .png files.",
    )
    parser.add_argument(
        "--report",
        required=True,
        type=Path,
        help="Path to rebuild_fontlib_report.md.",
    )
    parser.add_argument(
        "--output-pack",
        required=True,
        type=Path,
        help="Output pack directory to create.",
    )
    parser.add_argument("--pack-name", required=True, help="Human-readable pack name.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing output pack.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = BuildPackConfig(
        replacement_font_dir=args.replacement_font_dir,
        report=args.report,
        output_pack=args.output_pack,
        pack_name=args.pack_name,
        force=args.force,
    )
    try:
        result = build_pack(config)
    except FontGenError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote pack: {result.output_pack}")
    print(f"Copied replacement files: {len(result.replacement_files)}")
    print(f"Wrote {result.manifest_path}")
    print(f"Wrote {result.install_script}")
    print(f"Wrote {result.uninstall_script}")
    print(f"Wrote {result.readme_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
