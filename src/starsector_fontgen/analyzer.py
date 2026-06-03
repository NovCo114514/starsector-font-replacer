from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict

from .bmfont import parse_lines, read_bmfont_text, unquote
from .errors import FontGenError


CONFIG_EXTENSIONS = {
    ".json",
    ".csv",
    ".txt",
    ".ini",
    ".cfg",
    ".fnt",
    ".variant",
    ".ship",
    ".wpn",
    ".skin",
    ".system",
    ".mission",
    ".faction",
}


@dataclass(frozen=True)
class PageFileStatus:
    file: str
    exists: bool
    path: Path


@dataclass
class FontAnalysis:
    path: Path
    relative_path: str
    encoding: str
    face: str | None = None
    size: int | None = None
    line_height: int | None = None
    scale_w: int | None = None
    scale_h: int | None = None
    pages_count: int | None = None
    page_files: list[str] = field(default_factory=list)
    page_statuses: list[PageFileStatus] = field(default_factory=list)
    chars_count_declared: int | None = None
    char_ids: set[int] = field(default_factory=set)
    referenced_by: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def valid_unicode_ids(self) -> set[int]:
        return {char_id for char_id in self.char_ids if is_valid_unicode_scalar(char_id)}

    @property
    def pngs_exist(self) -> bool:
        return bool(self.page_statuses) and all(status.exists for status in self.page_statuses)

    @property
    def is_referenced(self) -> bool:
        return bool(self.referenced_by)


@dataclass(frozen=True)
class FontLibAnalysisResult:
    font_dir: Path
    config_dir: Path
    output_dir: Path
    fonts: list[FontAnalysis]
    charset_path: Path
    report_path: Path


def analyze_fontlib(font_dir: Path, config_dir: Path, output_dir: Path) -> FontLibAnalysisResult:
    validate_directory(font_dir, "--font-dir")
    validate_directory(config_dir, "--config-dir")
    output_dir.mkdir(parents=True, exist_ok=True)

    fonts = [parse_font_file(path, font_dir) for path in iter_fnt_files(font_dir)]
    reference_map = scan_config_references(config_dir, font_dir, fonts)
    for font in fonts:
        font.referenced_by = reference_map.get(font.relative_path, [])

    charset_path = output_dir / "charset_union_from_fontlib.txt"
    report_path = output_dir / "fontlib_analysis_report.md"
    charset_path.write_text(build_charset_union(fonts), encoding="utf-8")
    report_path.write_text(build_fontlib_report(font_dir, config_dir, fonts, charset_path), encoding="utf-8")

    return FontLibAnalysisResult(
        font_dir=font_dir,
        config_dir=config_dir,
        output_dir=output_dir,
        fonts=fonts,
        charset_path=charset_path,
        report_path=report_path,
    )


def validate_directory(path: Path, label: str) -> None:
    if not path.exists():
        raise FontGenError(f"{label} does not exist: {path}")
    if not path.is_dir():
        raise FontGenError(f"{label} must be a directory: {path}")


def iter_fnt_files(font_dir: Path) -> list[Path]:
    return sorted(
        (path for path in font_dir.rglob("*.fnt") if path.is_file()),
        key=lambda path: str(path.relative_to(font_dir)).lower(),
    )


def parse_font_file(path: Path, font_dir: Path) -> FontAnalysis:
    relative_path = safe_relative(path, font_dir)
    try:
        text, encoding = read_bmfont_text(path, label=str(path))
    except FontGenError as exc:
        return FontAnalysis(
            path=path,
            relative_path=relative_path,
            encoding="<unreadable>",
            errors=[str(exc)],
        )

    analysis = FontAnalysis(path=path, relative_path=relative_path, encoding=encoding)
    lines = parse_lines(text.splitlines())
    kinds = {line.kind for line in lines}
    missing = [kind for kind in ("info", "common", "page", "chars") if kind not in kinds]
    if missing:
        analysis.errors.append(
            "Not a valid text AngelCode BMFont file; missing block(s): " + ", ".join(missing)
        )

    for line in lines:
        if line.kind == "info":
            analysis.face = unquote(line.fields["face"]) if "face" in line.fields else analysis.face
            analysis.size = parse_int_field(line.fields, "size", analysis.size)
        elif line.kind == "common":
            analysis.line_height = parse_int_field(line.fields, "lineHeight", analysis.line_height)
            analysis.scale_w = parse_int_field(line.fields, "scaleW", analysis.scale_w)
            analysis.scale_h = parse_int_field(line.fields, "scaleH", analysis.scale_h)
            analysis.pages_count = parse_int_field(line.fields, "pages", analysis.pages_count)
        elif line.kind == "page":
            if "file" in line.fields:
                analysis.page_files.append(unquote(line.fields["file"]))
        elif line.kind == "chars":
            analysis.chars_count_declared = parse_int_field(
                line.fields,
                "count",
                analysis.chars_count_declared,
            )
        elif line.kind == "char":
            char_id = parse_int_field(line.fields, "id", None)
            if char_id is not None:
                analysis.char_ids.add(char_id)

    analysis.page_statuses = [
        PageFileStatus(file=page_file, exists=(path.parent / page_file).is_file(), path=path.parent / page_file)
        for page_file in analysis.page_files
    ]
    if analysis.chars_count_declared is not None and analysis.chars_count_declared != len(analysis.char_ids):
        analysis.errors.append(
            f"Declared chars count {analysis.chars_count_declared} differs from parsed unique char ids {len(analysis.char_ids)}"
        )
    return analysis


def parse_int_field(fields: dict[str, str], key: str, default: int | None) -> int | None:
    if key not in fields:
        return default
    try:
        return int(unquote(fields[key]))
    except ValueError:
        return default


def scan_config_references(
    config_dir: Path,
    font_dir: Path,
    fonts: list[FontAnalysis],
) -> dict[str, list[str]]:
    config_files = iter_config_files(config_dir)
    references: dict[str, list[str]] = {font.relative_path: [] for font in fonts}
    font_needles = {font.relative_path: reference_needles(font, font_dir) for font in fonts}

    for config_file in config_files:
        text = read_config_text(config_file)
        if text is None:
            continue
        raw_lower = text.lower()
        slash_lower = raw_lower.replace("\\", "/")
        config_relative = safe_relative(config_file, config_dir)
        for font in fonts:
            needles = font_needles[font.relative_path]
            if any(needle in raw_lower or needle in slash_lower for needle in needles):
                references[font.relative_path].append(config_relative)

    return {key: sorted(values) for key, values in references.items() if values}


def iter_config_files(config_dir: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in config_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in CONFIG_EXTENSIONS
        ),
        key=lambda path: str(path.relative_to(config_dir)).lower(),
    )


def read_config_text(path: Path) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def reference_needles(font: FontAnalysis, font_dir: Path) -> set[str]:
    rel_slash = font.relative_path.replace("\\", "/").lower()
    rel_backslash = font.relative_path.replace("/", "\\").lower()
    name = font.path.name.lower()
    stem = font.path.stem.lower()
    needles = {rel_slash, rel_backslash, name}
    if font_dir.name.lower() == "fonts":
        needles.add(f"graphics/fonts/{rel_slash}")
        needles.add(f"graphics\\fonts\\{rel_backslash}")
    # The stem catches config values that omit the extension, but it is only used
    # after exact filename/path checks have already been included.
    if len(stem) >= 6:
        needles.add(stem)
    return needles


def build_charset_union(fonts: list[FontAnalysis]) -> str:
    chars = [
        chr(char_id)
        for char_id in sorted(set().union(*(font.valid_unicode_ids for font in fonts)))
    ]
    return "".join(chars)


def build_fontlib_report(
    font_dir: Path,
    config_dir: Path,
    fonts: list[FontAnalysis],
    charset_path: Path,
) -> str:
    union_ids = set().union(*(font.valid_unicode_ids for font in fonts)) if fonts else set()
    duplicate_groups = possible_duplicate_groups(fonts)
    missing_pngs = [
        (font, status)
        for font in fonts
        for status in font.page_statuses
        if not status.exists
    ]

    lines = [
        "# Font Library Analysis Report",
        "",
        f"- Font dir: `{font_dir}`",
        f"- Config dir: `{config_dir}`",
        f"- FNT files scanned: {len(fonts)}",
        f"- Total unique Unicode chars across all FNT files: {len(union_ids)}",
        f"- Charset union: `{charset_path}`",
        "",
        "## FNT Files",
        "",
        "| File | Referenced | Face | Size | Line Height | Atlas | Pages | Page Files | PNG Exists | Declared Chars | Parsed Char IDs | Unique-Only Chars | Encoding | Errors |",
        "|---|---|---|---:|---:|---|---:|---|---|---:|---:|---:|---|---|",
    ]

    unique_counts = unique_char_counts(fonts)
    for font in fonts:
        page_files = "<br>".join(font.page_files) if font.page_files else "-"
        png_exists = "<br>".join(
            f"{status.file}: {'yes' if status.exists else 'missing'}" for status in font.page_statuses
        ) or "-"
        referenced = "<br>".join(font.referenced_by) if font.referenced_by else "no"
        errors = "<br>".join(sanitize_table_cell(error) for error in font.errors) if font.errors else "-"
        atlas = atlas_label(font)
        lines.append(
            "| "
            + " | ".join(
                [
                    sanitize_table_cell(font.relative_path),
                    sanitize_table_cell(referenced),
                    sanitize_table_cell(font.face or "-"),
                    str_or_dash(font.size),
                    str_or_dash(font.line_height),
                    atlas,
                    str_or_dash(font.pages_count),
                    sanitize_table_cell(page_files),
                    sanitize_table_cell(png_exists),
                    str_or_dash(font.chars_count_declared),
                    str(len(font.char_ids)),
                    str(unique_counts.get(font.relative_path, 0)),
                    font.encoding,
                    errors,
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Config References",
            "",
        ]
    )
    for font in fonts:
        if font.referenced_by:
            lines.append(f"- `{font.relative_path}` is referenced by: {', '.join(f'`{item}`' for item in font.referenced_by)}")
        else:
            lines.append(f"- `{font.relative_path}` is not referenced by scanned config text.")

    lines.extend(
        [
            "",
            "## Possible Duplicate Fonts",
            "",
        ]
    )
    if duplicate_groups:
        for group in duplicate_groups:
            files = ", ".join(f"`{font.relative_path}`" for font in group)
            lines.append(f"- Same Unicode char-id set: {files}")
    else:
        lines.append("- No exact duplicate char-id sets found.")

    lines.extend(
        [
            "",
            "## Missing PNGs",
            "",
        ]
    )
    if missing_pngs:
        for font, status in missing_pngs:
            lines.append(f"- `{font.relative_path}` references missing PNG `{status.file}`.")
    else:
        lines.append("- No missing page PNGs found.")

    lines.extend(
        [
            "",
            "## Retention Suggestions",
            "",
            "These are conservative suggestions only. Do not delete files automatically.",
        ]
    )
    for font in fonts:
        reason = retention_reason(font)
        lines.append(f"- `{font.relative_path}`: {reason}")

    return "\n".join(lines) + "\n"


def unique_char_counts(fonts: list[FontAnalysis]) -> dict[str, int]:
    owners: dict[int, list[str]] = defaultdict(list)
    for font in fonts:
        for char_id in font.valid_unicode_ids:
            owners[char_id].append(font.relative_path)
    counts = {font.relative_path: 0 for font in fonts}
    for file_names in owners.values():
        if len(file_names) == 1:
            counts[file_names[0]] += 1
    return counts


def possible_duplicate_groups(fonts: list[FontAnalysis]) -> list[list[FontAnalysis]]:
    groups: dict[tuple[int, ...], list[FontAnalysis]] = defaultdict(list)
    for font in fonts:
        if font.valid_unicode_ids:
            groups[tuple(sorted(font.valid_unicode_ids))].append(font)
    return [group for group in groups.values() if len(group) > 1]


def retention_reason(font: FontAnalysis) -> str:
    parts: list[str] = []
    if font.is_referenced:
        parts.append("must keep for now; referenced by scanned config")
    else:
        parts.append("not referenced by scanned config; suspected backup/alternate, verify manually")
    if not font.pngs_exist:
        parts.append("has missing PNG page file")
    if font.errors:
        parts.append("has parse/report warnings")
    return "; ".join(parts)


def atlas_label(font: FontAnalysis) -> str:
    if font.scale_w is None or font.scale_h is None:
        return "-"
    return f"{font.scale_w}x{font.scale_h}"


def str_or_dash(value: int | None) -> str:
    return str(value) if value is not None else "-"


def sanitize_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def safe_relative(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def is_valid_unicode_scalar(char_id: int) -> bool:
    return 0 <= char_id <= 0x10FFFF and not (0xD800 <= char_id <= 0xDFFF)
