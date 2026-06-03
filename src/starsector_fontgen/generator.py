from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import math
import re

from .bmfont import BmFontReference, CharMetric
from .errors import FontGenError
from .scanner import CharsetBuildResult, build_charset, char_name, codepoint_label, describe_char


ALLOWED_ATLAS_SIZES = (512, 1024, 2048, 4096)
PADDING = 2

PREVIEW_TEXT = "\n".join(
    [
        "开始游戏  继续游戏  设置  舰船  武器  护盾  装甲  市场  任务  确认  取消",
        "这是一段用于检查中文字体行高、字距和标点显示效果的测试文本。",
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        "abcdefghijklmnopqrstuvwxyz",
        "0123456789",
        "，。！？；：“”‘’（）《》【】、·…—～￥",
        "→ ← ↑ ↓ ★ ☆ ● ◆ α β γ",
    ]
)


@dataclass(frozen=True)
class FontGenConfig:
    font: Path
    text_dir: Path
    extra_charset: Path | None
    size: int
    output: Path
    atlas_size: int = 2048
    force: bool = False


@dataclass(frozen=True)
class OutputPaths:
    fnt: Path
    atlas: Path
    preview: Path
    report: Path
    unsupported_report: Path


@dataclass
class GlyphImage:
    char: str
    image: object | None
    width: int
    height: int
    xoffset: int
    yoffset: int
    xadvance: int


@dataclass(frozen=True)
class UnsupportedChar:
    char: str
    reason: str
    sources: tuple[str, ...]


@dataclass
class PackedAtlas:
    image: object
    metrics: list[CharMetric]
    line_height: int
    base: int


@dataclass(frozen=True)
class FontGenerationResult:
    config: FontGenConfig
    outputs: OutputPaths
    glyph_count: int
    atlas_occupancy: float


@dataclass(frozen=True)
class BatchEntry:
    size: int
    outputs: OutputPaths
    glyph_count: int | None
    atlas_size: int
    atlas_occupancy: float | None
    success: bool
    unsupported_chars: bool
    error: str | None = None


@dataclass(frozen=True)
class BatchResult:
    entries: list[BatchEntry]
    summary_report: Path
    patch_instructions: Path


def generate_font(config: FontGenConfig) -> OutputPaths:
    return generate_font_result(config).outputs


def generate_font_result(
    config: FontGenConfig,
    *,
    write_patch_file: bool = True,
    skip_collision_check: bool = False,
) -> FontGenerationResult:
    validate_config(config)
    outputs = output_paths(config.output)
    reference_path = find_reference_path()
    reference = BmFontReference.load(reference_path)
    collision_paths = [outputs.fnt, outputs.atlas, outputs.preview, outputs.report]
    if write_patch_file:
        collision_paths.append(patch_instructions_path(config.output))
    if not skip_collision_check:
        check_output_collisions(collision_paths, config.force)
    outputs.fnt.parent.mkdir(parents=True, exist_ok=True)

    charset = build_charset(config.text_dir, config.extra_charset, PREVIEW_TEXT)
    font = load_pillow_font(config.font, config.size)
    cmap = load_font_cmap(config.font)

    missing = find_missing_cmap_chars(charset, cmap)
    if missing:
        write_unsupported_report(outputs.unsupported_report, missing, config.force)
        raise FontGenError(
            f"Font does not support {len(missing)} character(s). "
            f"See: {outputs.unsupported_report}"
        )

    glyphs, empty = render_glyphs(font, config.size, charset)
    if empty:
        write_unsupported_report(outputs.unsupported_report, empty, config.force)
        raise FontGenError(
            f"Font rendered {len(empty)} empty non-space glyph(s). "
            f"See: {outputs.unsupported_report}"
        )

    line_height, base = measure_line_metrics(font, glyphs)
    atlas = pack_glyphs(glyphs, config.atlas_size, reference.default_channel, line_height, base)
    atlas_occupancy = calculate_atlas_occupancy(atlas.metrics, config.atlas_size)
    page_file = outputs.atlas.name
    fnt_text = reference.render(
        face=config.font.stem,
        size=config.size,
        line_height=atlas.line_height,
        base=atlas.base,
        atlas_size=config.atlas_size,
        page_file=page_file,
        chars=atlas.metrics,
    )

    preview = render_preview(atlas.image, atlas.metrics, atlas.line_height, PREVIEW_TEXT)

    outputs.fnt.write_text(fnt_text, encoding="utf-8")
    atlas.image.save(outputs.atlas)
    preview.save(outputs.preview)
    outputs.report.write_text(
        build_report(
            config,
            outputs,
            charset,
            len(atlas.metrics),
            reference_path,
            reference.encoding,
            atlas_occupancy,
        ),
        encoding="utf-8",
    )
    if write_patch_file:
        write_patch_instructions(patch_instructions_path(config.output), [outputs], config.force)

    return FontGenerationResult(
        config=config,
        outputs=outputs,
        glyph_count=len(atlas.metrics),
        atlas_occupancy=atlas_occupancy,
    )


def generate_batch(config: FontGenConfig, sizes: list[int]) -> BatchResult:
    validate_batch_sizes(sizes)
    batch_configs = [
        replace(config, size=size, output=batch_output_prefix(config.output, size))
        for size in sizes
    ]
    summary_path = batch_summary_path(config.output)
    patch_path = patch_instructions_path(config.output)
    collision_paths = [summary_path, patch_path]
    for batch_config in batch_configs:
        outputs = output_paths(batch_config.output)
        collision_paths.extend([outputs.fnt, outputs.atlas, outputs.preview, outputs.report])
    check_output_collisions(collision_paths, config.force)

    entries: list[BatchEntry] = []
    successful_outputs: list[OutputPaths] = []
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    for batch_config in batch_configs:
        outputs = output_paths(batch_config.output)
        try:
            result = generate_font_result(
                batch_config,
                write_patch_file=False,
                skip_collision_check=True,
            )
        except FontGenError as exc:
            entries.append(
                BatchEntry(
                    size=batch_config.size,
                    outputs=outputs,
                    glyph_count=None,
                    atlas_size=batch_config.atlas_size,
                    atlas_occupancy=None,
                    success=False,
                    unsupported_chars=outputs.unsupported_report.exists(),
                    error=str(exc),
                )
            )
            continue

        successful_outputs.append(result.outputs)
        entries.append(
            BatchEntry(
                size=batch_config.size,
                outputs=result.outputs,
                glyph_count=result.glyph_count,
                atlas_size=batch_config.atlas_size,
                atlas_occupancy=result.atlas_occupancy,
                success=True,
                unsupported_chars=False,
                error=None,
            )
        )

    summary_path.write_text(build_batch_summary(entries), encoding="utf-8")
    write_patch_instructions(patch_path, successful_outputs, config.force)
    return BatchResult(entries=entries, summary_report=summary_path, patch_instructions=patch_path)


def validate_config(config: FontGenConfig) -> None:
    if config.size <= 0:
        raise FontGenError("--size must be a positive integer")
    if config.atlas_size not in ALLOWED_ATLAS_SIZES:
        allowed = ", ".join(str(value) for value in ALLOWED_ATLAS_SIZES)
        raise FontGenError(f"--atlas-size must be one of: {allowed}")
    if not config.font.exists():
        raise FontGenError(f"--font does not exist: {config.font}")
    if not config.font.is_file():
        raise FontGenError(f"--font must be a file: {config.font}")
    if config.font.suffix.lower() not in {".ttf", ".otf"}:
        raise FontGenError("--font must point to a .ttf or .otf file")


def validate_batch_sizes(sizes: list[int]) -> None:
    if not sizes:
        raise FontGenError("--sizes must contain at least one size")
    if any(size <= 0 for size in sizes):
        raise FontGenError("--sizes must contain only positive integers")
    if len(set(sizes)) != len(sizes):
        raise FontGenError("--sizes must not contain duplicate values")


def parse_sizes_argument(value: str) -> list[int]:
    parts = [part.strip() for part in value.split(",")]
    if any(part == "" for part in parts):
        raise FontGenError("--sizes must be a comma-separated list like 12,16,20,24")
    try:
        sizes = [int(part) for part in parts]
    except ValueError as exc:
        raise FontGenError("--sizes must contain only integers, e.g. 12,16,20,24") from exc
    validate_batch_sizes(sizes)
    return sizes


def output_paths(prefix: Path) -> OutputPaths:
    return OutputPaths(
        fnt=prefix.with_suffix(".fnt"),
        atlas=prefix.with_name(f"{prefix.name}_0.png"),
        preview=prefix.with_name(f"{prefix.name}_preview.png"),
        report=prefix.with_name(f"{prefix.name}_report.txt"),
        unsupported_report=prefix.with_name(f"{prefix.name}_unsupported_chars_report.txt"),
    )


def batch_summary_path(prefix: Path) -> Path:
    return prefix.parent / "batch_summary_report.txt"


def patch_instructions_path(prefix: Path) -> Path:
    return prefix.parent / "patch_instructions.txt"


def batch_output_prefix(prefix: Path, size: int) -> Path:
    match = re.match(r"^(?P<base>.*?)(?P<size>\d+)$", prefix.name)
    base = match.group("base") if match and match.group("base") else prefix.name
    return prefix.with_name(f"{base}{size}")


def check_output_collisions(paths: list[Path], force: bool) -> None:
    if force:
        return
    existing = [path for path in paths if path.exists()]
    if existing:
        formatted = "\n".join(f"  {path}" for path in existing)
        raise FontGenError(
            "Refusing to overwrite existing output file(s). "
            "Pass --force to overwrite:\n" + formatted
        )


def find_reference_path() -> Path:
    candidates = [
        Path.cwd() / "reference" / "orbitron12.fnt",
        Path(__file__).resolve().parents[2] / "reference" / "orbitron12.fnt",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def load_pillow_font(font_path: Path, size: int):
    try:
        from PIL import ImageFont
    except ImportError as exc:
        raise FontGenError("Pillow is required. Install dependencies with: pip install -e .") from exc

    try:
        return ImageFont.truetype(str(font_path), size=size)
    except OSError as exc:
        raise FontGenError(f"Could not load font with Pillow: {font_path}") from exc


def load_font_cmap(font_path: Path) -> set[int]:
    try:
        from fontTools.ttLib import TTFont
    except ImportError as exc:
        raise FontGenError(
            "fontTools is required for cmap checks. Install dependencies with: pip install -e ."
        ) from exc

    try:
        font = TTFont(str(font_path))
    except Exception as exc:  # fontTools raises several parse-specific exceptions.
        raise FontGenError(f"Could not read font cmap with fontTools: {font_path}") from exc

    try:
        cmap: set[int] = set()
        for table in font["cmap"].tables:
            cmap.update(table.cmap.keys())
        return cmap
    finally:
        font.close()


def find_missing_cmap_chars(
    charset: CharsetBuildResult,
    cmap: set[int],
) -> list[UnsupportedChar]:
    missing: list[UnsupportedChar] = []
    for char in charset.chars:
        if char == " ":
            continue
        if ord(char) not in cmap:
            missing.append(
                UnsupportedChar(
                    char=char,
                    reason="missing_cmap",
                    sources=tuple(sorted(charset.char_sources.get(char, ()))),
                )
            )
    return missing


def render_glyphs(
    font,
    size: int,
    charset: CharsetBuildResult,
) -> tuple[list[GlyphImage], list[UnsupportedChar]]:
    glyphs: list[GlyphImage] = []
    empty: list[UnsupportedChar] = []
    space_advance = measure_space_advance(font, size)

    for char in charset.chars:
        if char == " ":
            glyphs.append(
                GlyphImage(
                    char=char,
                    image=None,
                    width=0,
                    height=0,
                    xoffset=0,
                    yoffset=0,
                    xadvance=space_advance,
                )
            )
            continue

        bbox = font.getbbox(char)
        if not bbox:
            empty.append(empty_glyph_record(char, charset))
            continue

        left = int(math.floor(bbox[0]))
        top = int(math.floor(bbox[1]))
        right = int(math.ceil(bbox[2]))
        bottom = int(math.ceil(bbox[3]))
        width = max(0, right - left)
        height = max(0, bottom - top)
        if width <= 0 or height <= 0:
            empty.append(empty_glyph_record(char, charset))
            continue

        try:
            from PIL import Image, ImageDraw
        except ImportError as exc:
            raise FontGenError("Pillow is required. Install dependencies with: pip install -e .") from exc

        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.text((-left, -top), char, font=font, fill=(255, 255, 255, 255))
        if image.getbbox() is None:
            empty.append(empty_glyph_record(char, charset))
            continue

        glyphs.append(
            GlyphImage(
                char=char,
                image=image,
                width=width,
                height=height,
                xoffset=left,
                yoffset=top,
                xadvance=max(1, int(round(font.getlength(char)))),
            )
        )

    return glyphs, empty


def empty_glyph_record(char: str, charset: CharsetBuildResult) -> UnsupportedChar:
    return UnsupportedChar(
        char=char,
        reason="empty_glyph",
        sources=tuple(sorted(charset.char_sources.get(char, ()))),
    )


def measure_space_advance(font, size: int) -> int:
    for char in (" ", "n"):
        try:
            advance = int(round(font.getlength(char)))
        except Exception:
            advance = 0
        if advance > 0:
            return advance
    return max(1, int(round(size * 0.5)))


def pack_glyphs(
    glyphs: list[GlyphImage],
    atlas_size: int,
    default_channel: int,
    line_height: int,
    base: int,
) -> PackedAtlas:
    try:
        from PIL import Image
    except ImportError as exc:
        raise FontGenError("Pillow is required. Install dependencies with: pip install -e .") from exc

    atlas = Image.new("RGBA", (atlas_size, atlas_size), (0, 0, 0, 0))
    x = PADDING
    y = PADDING
    row_height = 0
    metrics: list[CharMetric] = []

    for glyph in glyphs:
        if glyph.width == 0 and glyph.height == 0:
            metrics.append(
                CharMetric(
                    char=glyph.char,
                    char_id=ord(glyph.char),
                    x=0,
                    y=0,
                    width=0,
                    height=0,
                    xoffset=glyph.xoffset,
                    yoffset=glyph.yoffset,
                    xadvance=glyph.xadvance,
                    chnl=default_channel,
                )
            )
            continue

        if glyph.width + (PADDING * 2) > atlas_size or glyph.height + (PADDING * 2) > atlas_size:
            raise_atlas_full(atlas_size)

        if x + glyph.width + PADDING > atlas_size:
            x = PADDING
            y += row_height + PADDING
            row_height = 0

        if y + glyph.height + PADDING > atlas_size:
            raise_atlas_full(atlas_size)

        atlas.alpha_composite(glyph.image, (x, y))
        metrics.append(
            CharMetric(
                char=glyph.char,
                char_id=ord(glyph.char),
                x=x,
                y=y,
                width=glyph.width,
                height=glyph.height,
                xoffset=glyph.xoffset,
                yoffset=glyph.yoffset,
                xadvance=glyph.xadvance,
                chnl=default_channel,
            )
        )
        x += glyph.width + PADDING
        row_height = max(row_height, glyph.height)

    return PackedAtlas(
        image=atlas,
        metrics=metrics,
        line_height=max(1, line_height),
        base=max(1, base),
    )


def measure_line_metrics(font, glyphs: list[GlyphImage]) -> tuple[int, int]:
    try:
        ascent, descent = font.getmetrics()
    except Exception:
        ascent, descent = infer_line_metrics(glyphs)

    visible = [glyph for glyph in glyphs if glyph.height > 0]
    max_bottom = max((glyph.yoffset + glyph.height for glyph in visible), default=ascent)
    line_height = max(1, int(math.ceil(ascent + descent)), int(math.ceil(max_bottom)))
    base = max(1, int(math.ceil(ascent)))
    return line_height, base


def infer_line_metrics(glyphs: list[GlyphImage]) -> tuple[int, int]:
    visible = [glyph for glyph in glyphs if glyph.height > 0]
    if not visible:
        return 1, 0
    top = min(glyph.yoffset for glyph in visible)
    bottom = max(glyph.yoffset + glyph.height for glyph in visible)
    ascent = max(1, bottom if top >= 0 else bottom - top)
    descent = max(0, int(round(ascent * 0.25)))
    return ascent, descent


def raise_atlas_full(atlas_size: int) -> None:
    raise FontGenError(
        "Characters do not fit in a single atlas. Try increasing --atlas-size "
        f"(for example 4096), reducing the charset, or lowering --size. "
        f"Current atlas: {atlas_size}x{atlas_size}. MVP does not support multi-page atlases."
    )


def calculate_atlas_occupancy(metrics: list[CharMetric], atlas_size: int) -> float:
    used_area = sum(metric.width * metric.height for metric in metrics)
    atlas_area = atlas_size * atlas_size
    if atlas_area <= 0:
        return 0.0
    return used_area / atlas_area


def render_preview(atlas_image, metrics: list[CharMetric], line_height: int, text: str):
    try:
        from PIL import Image
    except ImportError as exc:
        raise FontGenError("Pillow is required. Install dependencies with: pip install -e .") from exc

    by_char = {metric.char: metric for metric in metrics}
    lines = text.splitlines()
    margin = 24
    line_gap = max(6, line_height // 3)
    line_widths = [sum(by_char[char].xadvance for char in line if char in by_char) for line in lines]
    width = max(640, max(line_widths, default=0) + (margin * 2))
    height = max(160, margin * 2 + len(lines) * line_height + max(0, len(lines) - 1) * line_gap)
    preview = Image.new("RGBA", (width, height), (30, 34, 40, 255))

    y = margin
    for line in lines:
        x = margin
        for char in line:
            metric = by_char.get(char)
            if metric is None:
                continue
            if metric.width > 0 and metric.height > 0:
                glyph = atlas_image.crop(
                    (metric.x, metric.y, metric.x + metric.width, metric.y + metric.height)
                )
                safe_alpha_composite(
                    preview,
                    glyph,
                    x + metric.xoffset,
                    y + metric.yoffset,
                )
            x += metric.xadvance
        y += line_height + line_gap

    return preview


def safe_alpha_composite(base, overlay, x: int, y: int) -> None:
    if x >= base.width or y >= base.height:
        return
    crop_left = max(0, -x)
    crop_top = max(0, -y)
    crop_right = min(overlay.width, base.width - x)
    crop_bottom = min(overlay.height, base.height - y)
    if crop_left >= crop_right or crop_top >= crop_bottom:
        return
    if crop_left or crop_top or crop_right != overlay.width or crop_bottom != overlay.height:
        overlay = overlay.crop((crop_left, crop_top, crop_right, crop_bottom))
    base.alpha_composite(overlay, (max(0, x), max(0, y)))


def write_unsupported_report(
    path: Path,
    records: list[UnsupportedChar],
    force: bool,
) -> None:
    if path.exists() and not force:
        raise FontGenError(
            f"Refusing to overwrite existing unsupported report: {path}. Pass --force to overwrite."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Unsupported or Empty Glyph Report",
        "",
        f"Count: {len(records)}",
        "",
    ]
    for record in records:
        source_text = ", ".join(record.sources) if record.sources else "<unknown>"
        lines.append(
            f"- {record.char} {codepoint_label(record.char)} {char_name(record.char)} "
            f"reason={record.reason} sources={source_text}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_report(
    config: FontGenConfig,
    outputs: OutputPaths,
    charset: CharsetBuildResult,
    glyph_count: int,
    reference_path: Path,
    reference_encoding: str,
    atlas_occupancy: float,
) -> str:
    damaged = [record for record in charset.read_records if record.damaged_encoding]
    lines = [
        "# Starsector FontGen Report",
        "",
        f"Font: {config.font}",
        f"Text dir: {config.text_dir}",
        f"Extra charset: {config.extra_charset if config.extra_charset else '<none>'}",
        f"Reference: {reference_path}",
        f"Reference encoding: {reference_encoding}",
        f"Output prefix: {config.output}",
        f"Size: {config.size}",
        f"Atlas: {config.atlas_size}x{config.atlas_size}",
        f"Glyph count: {glyph_count}",
        f"Atlas occupancy: {format_percent(atlas_occupancy)}",
        "",
        "## Outputs",
        f"- FNT: {outputs.fnt}",
        f"- Atlas: {outputs.atlas}",
        f"- Preview: {outputs.preview}",
        "",
        "## Character Sources",
    ]
    for source in ("text-dir", "extra-charset", "preview text"):
        lines.append(f"- {source}: {charset.source_unique_counts.get(source, 0)} unique chars")

    lines.extend(
        [
            "",
            "## Read Files",
            f"Scanned/read files: {len(charset.read_records)}",
        ]
    )
    for record in charset.read_records:
        suffix = " damaged_encoding" if record.damaged_encoding else ""
        lines.append(f"- {record.path} encoding={record.encoding}{suffix}")

    lines.extend(
        [
            "",
            "## Damaged Encoding Files",
        ]
    )
    if damaged:
        for record in damaged:
            lines.append(f"- {record.path}")
    else:
        lines.append("- <none>")

    lines.extend(
        [
            "",
            "## Ignored Characters",
        ]
    )
    if charset.ignored_chars:
        for char in sorted(charset.ignored_chars, key=ord):
            record = charset.ignored_chars[char]
            sources = ", ".join(sorted(record.sources))
            lines.append(f"- {describe_char(char)} count={record.count} sources={sources}")
    else:
        lines.append("- <none>")

    return "\n".join(lines) + "\n"


def build_batch_summary(entries: list[BatchEntry]) -> str:
    lines = [
        "# Batch Summary Report",
        "",
        "| Size | Status | Glyph Count | Atlas Size | Atlas Occupancy | FNT | Atlas PNG | Preview | Report | Unsupported Chars | Error |",
        "|---:|---|---:|---|---:|---|---|---|---|---|---|",
    ]
    for entry in entries:
        status = "success" if entry.success else "failed"
        glyph_count = str(entry.glyph_count) if entry.glyph_count is not None else "-"
        occupancy = format_percent(entry.atlas_occupancy) if entry.atlas_occupancy is not None else "-"
        unsupported = "yes" if entry.unsupported_chars else "no"
        error = sanitize_table_cell(entry.error or "")
        lines.append(
            "| "
            + " | ".join(
                [
                    str(entry.size),
                    status,
                    glyph_count,
                    f"{entry.atlas_size}x{entry.atlas_size}",
                    occupancy,
                    str(entry.outputs.fnt),
                    str(entry.outputs.atlas),
                    str(entry.outputs.preview),
                    str(entry.outputs.report),
                    unsupported,
                    error,
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def write_patch_instructions(path: Path, outputs: list[OutputPaths], force: bool) -> None:
    if path.exists() and not force:
        raise FontGenError(
            f"Refusing to overwrite existing patch instructions: {path}. Pass --force to overwrite."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "Starsector Font Patch Instructions",
        "",
        "This generator does not modify Starsector core files and does not install runtime hooks.",
        "",
        "1. Copy the generated .fnt and _0.png files into your mod folder:",
        "   YourMod/graphics/fonts/",
        "",
        "2. In settings.json or the relevant font configuration, point the font path to the .fnt file.",
        "   Use paths like graphics/fonts/myfontXX.fnt.",
        "",
        "Generated font files:",
    ]
    if outputs:
        for output in outputs:
            lines.append(f"- {output.fnt.name} + {output.atlas.name}")
            lines.append(f"  settings path: graphics/fonts/{output.fnt.name}")
    else:
        lines.append("- No successful font outputs were generated in this run.")
    lines.extend(
        [
            "",
            "Do not overwrite Starsector core files by default. Prefer mod-level configuration.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def format_percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def sanitize_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\r", " ").replace("\n", " ")
