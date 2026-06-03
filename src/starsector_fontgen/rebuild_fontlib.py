from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .analyzer import iter_fnt_files, parse_font_file, safe_relative, validate_directory
from .bmfont import BmFontReference, parse_lines, read_bmfont_text
from .charset_filter import read_charset_chars
from .errors import FontGenError
from .generator import (
    calculate_atlas_occupancy,
    check_output_collisions,
    load_font_cmap,
    load_pillow_font,
    measure_line_metrics,
    pack_glyphs,
    render_glyphs,
    validate_batch_sizes,
)
from .scanner import CharsetBuildResult


@dataclass(frozen=True)
class RebuildConfig:
    font: Path
    source_font_dir: Path
    charset: Path
    output_font_dir: Path
    atlas_size: int
    force: bool = False


@dataclass(frozen=True)
class RebuildEntry:
    source_fnt: Path
    original_size: int | None
    output_fnt: Path | None
    output_png: Path | None
    success: bool
    glyph_count: int | None
    atlas_occupancy: float | None
    unsupported_chars: bool
    error: str | None = None
    render_size: int | None = None
    status: str = "success"


@dataclass(frozen=True)
class RebuildResult:
    entries: list[RebuildEntry]
    report_path: Path


def rebuild_fontlib(config: RebuildConfig) -> RebuildResult:
    validate_rebuild_config(config)
    chars = read_charset_chars(config.charset)
    cmap = load_font_cmap(config.font)
    source_files = iter_fnt_files(config.source_font_dir)
    planned_outputs = [config.output_font_dir / "rebuild_fontlib_report.md"]
    for source_fnt in source_files:
        relative = source_fnt.relative_to(config.source_font_dir)
        output_fnt = config.output_font_dir / relative
        planned_outputs.append(output_fnt)
        analysis = parse_font_file(source_fnt, config.source_font_dir)
        if analysis.page_files:
            planned_outputs.append(output_fnt.parent / analysis.page_files[0])
    check_output_collisions(planned_outputs, config.force)
    config.output_font_dir.mkdir(parents=True, exist_ok=True)

    entries = [
        rebuild_one_font(source_fnt, config, chars, cmap)
        for source_fnt in source_files
    ]
    report_path = config.output_font_dir / "rebuild_fontlib_report.md"
    report_path.write_text(build_rebuild_report(config, entries), encoding="utf-8")
    return RebuildResult(entries=entries, report_path=report_path)


def validate_rebuild_config(config: RebuildConfig) -> None:
    if not config.font.exists():
        raise FontGenError(f"--font does not exist: {config.font}")
    if not config.font.is_file():
        raise FontGenError(f"--font must be a file: {config.font}")
    if config.font.suffix.lower() not in {".ttf", ".otf"}:
        raise FontGenError("--font must point to a .ttf or .otf file")
    if not config.charset.exists():
        raise FontGenError(f"--charset does not exist: {config.charset}")
    if not config.charset.is_file():
        raise FontGenError(f"--charset must be a file: {config.charset}")
    validate_directory(config.source_font_dir, "--source-font-dir")
    validate_batch_sizes([config.atlas_size])
    if config.atlas_size not in {512, 1024, 2048, 4096}:
        raise FontGenError("--atlas-size must be one of: 512, 1024, 2048, 4096")
    try:
        if config.source_font_dir.resolve() == config.output_font_dir.resolve():
            raise FontGenError("--output-font-dir must be different from --source-font-dir")
    except OSError:
        pass


def rebuild_one_font(
    source_fnt: Path,
    config: RebuildConfig,
    chars: list[str],
    cmap: set[int],
) -> RebuildEntry:
    relative = source_fnt.relative_to(config.source_font_dir)
    output_fnt = config.output_font_dir / relative
    analysis = parse_font_file(source_fnt, config.source_font_dir)
    original_size = analysis.size
    render_size = abs(original_size) if original_size is not None else None

    if original_size is None or original_size == 0:
        return failed_entry(
            source_fnt,
            original_size,
            render_size,
            output_fnt,
            None,
            "Could not parse info size",
            status="failed_parse_size",
        )
    if not analysis.page_files:
        return failed_entry(
            source_fnt,
            original_size,
            render_size,
            output_fnt,
            None,
            "Could not parse page file",
            status="failed_parse_size",
        )
    if len(analysis.page_files) != 1:
        return failed_entry(
            source_fnt,
            original_size,
            render_size,
            output_fnt,
            None,
            "MVP rebuild supports only one page file per source .fnt",
            status="failed_parse_size",
        )

    page_file = analysis.page_files[0]
    output_png = output_fnt.parent / page_file

    try:
        text, encoding = read_bmfont_text(source_fnt, label=str(source_fnt))
        reference = BmFontReference(parse_lines(text.splitlines()), encoding=encoding)
        charset = charset_result(chars)
        missing = [
            char
            for char in charset.chars
            if char != " " and ord(char) not in cmap
        ]
        if missing:
            return failed_entry(
                source_fnt,
                original_size,
                render_size,
                output_fnt,
                output_png,
                f"Font does not support {len(missing)} charset character(s)",
                unsupported_chars=True,
                status="missing_cmap",
            )

        font = load_pillow_font(config.font, render_size)
        glyphs, empty = render_glyphs(font, render_size, charset)
        if empty:
            return failed_entry(
                source_fnt,
                original_size,
                render_size,
                output_fnt,
                output_png,
                f"Font rendered {len(empty)} empty non-space glyph(s)",
                unsupported_chars=True,
                status="empty_glyph",
            )

        line_height, base = measure_line_metrics(font, glyphs)
        atlas = pack_glyphs(glyphs, config.atlas_size, reference.default_channel, line_height, base)
        occupancy = calculate_atlas_occupancy(atlas.metrics, config.atlas_size)
        fnt_text = reference.render(
            face=config.font.stem,
            size=original_size,
            line_height=atlas.line_height,
            base=atlas.base,
            atlas_size=config.atlas_size,
            page_file=page_file,
            chars=atlas.metrics,
        )

        output_fnt.parent.mkdir(parents=True, exist_ok=True)
        output_png.parent.mkdir(parents=True, exist_ok=True)
        output_fnt.write_text(fnt_text, encoding="utf-8")
        atlas.image.save(output_png)
        return RebuildEntry(
            source_fnt=source_fnt,
            original_size=original_size,
            output_fnt=output_fnt,
            output_png=output_png,
            success=True,
            glyph_count=len(atlas.metrics),
            atlas_occupancy=occupancy,
            unsupported_chars=False,
            render_size=render_size,
            status="success",
        )
    except FontGenError as exc:
        status = "atlas_overflow" if "single atlas" in str(exc) else "failed"
        return failed_entry(
            source_fnt,
            original_size,
            render_size,
            output_fnt,
            output_png,
            str(exc),
            status=status,
        )


def charset_result(chars: list[str]) -> CharsetBuildResult:
    return CharsetBuildResult(
        chars=chars,
        char_sources={char: {"charset"} for char in chars},
        ignored_chars={},
        read_records=[],
        source_unique_counts={"charset": len(chars)},
    )


def failed_entry(
    source_fnt: Path,
    original_size: int | None,
    render_size: int | None,
    output_fnt: Path | None,
    output_png: Path | None,
    error: str,
    unsupported_chars: bool = False,
    status: str = "failed",
) -> RebuildEntry:
    return RebuildEntry(
        source_fnt=source_fnt,
        original_size=original_size,
        output_fnt=output_fnt,
        output_png=output_png,
        success=False,
        glyph_count=None,
        atlas_occupancy=None,
        unsupported_chars=unsupported_chars,
        error=error,
        render_size=render_size,
        status=status,
    )


def build_rebuild_report(config: RebuildConfig, entries: list[RebuildEntry]) -> str:
    lines = [
        "# Rebuild Font Library Report",
        "",
        f"- Target font: `{config.font}`",
        f"- Source font dir: `{config.source_font_dir}`",
        f"- Charset: `{config.charset}`",
        f"- Output font dir: `{config.output_font_dir}`",
        f"- Atlas size: {config.atlas_size}x{config.atlas_size}",
        "",
        "This command does not modify Starsector core and does not overwrite the source font directory.",
        "",
        "| Source .fnt | Original Size | Render Size | Output .fnt | Output PNG | Status | Glyph Count | Atlas Occupancy | Unsupported Chars | Error |",
        "|---|---:|---:|---|---|---|---:|---:|---|---|",
    ]
    for entry in entries:
        source = safe_relative(entry.source_fnt, config.source_font_dir)
        output_fnt = str(entry.output_fnt) if entry.output_fnt else "-"
        output_png = str(entry.output_png) if entry.output_png else "-"
        glyph_count = str(entry.glyph_count) if entry.glyph_count is not None else "-"
        occupancy = f"{entry.atlas_occupancy * 100:.2f}%" if entry.atlas_occupancy is not None else "-"
        unsupported = "yes" if entry.unsupported_chars else "no"
        error = sanitize_table_cell(entry.error or "")
        lines.append(
            "| "
            + " | ".join(
                [
                    sanitize_table_cell(source),
                    str(entry.original_size) if entry.original_size is not None else "-",
                    str(entry.render_size) if entry.render_size is not None else "-",
                    sanitize_table_cell(output_fnt),
                    sanitize_table_cell(output_png),
                    entry.status,
                    glyph_count,
                    occupancy,
                    unsupported,
                    error,
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def sanitize_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\r", " ").replace("\n", " ")
