from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import unicodedata

from .errors import FontGenError
from .scanner import char_name, codepoint_label


CHARSET_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "cp1252", "latin-1")


@dataclass(frozen=True)
class UnsupportedCharsetChar:
    char: str
    codepoint: int
    name: str
    reason: str


@dataclass(frozen=True)
class CharsetFilterResult:
    input_count: int
    supported_count: int
    unsupported_count: int
    unsupported_chars: list[UnsupportedCharsetChar]
    output_path: Path
    report_path: Path
    missing_cmap_count: int = 0
    empty_glyph_count: int = 0


def filter_charset_by_font(
    font_path: Path,
    charset_path: Path,
    output_path: Path,
    *,
    force: bool = False,
) -> CharsetFilterResult:
    validate_inputs(font_path, charset_path)
    report_path = output_path.with_name("charset_filter_report.txt")
    check_output_paths([output_path, report_path], force)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmap = load_font_cmap(font_path)
    pillow_font = load_pillow_font(font_path)
    chars = read_charset_chars(charset_path)
    supported: list[str] = []
    unsupported: list[UnsupportedCharsetChar] = []

    for char in chars:
        if char == " ":
            supported.append(char)
            continue
        if ord(char) not in cmap:
            unsupported.append(
                UnsupportedCharsetChar(
                    char=char,
                    codepoint=ord(char),
                    name=char_name(char),
                    reason="missing_cmap",
                )
            )
            continue
        if glyph_renders_empty(pillow_font, char):
            unsupported.append(
                UnsupportedCharsetChar(
                    char=char,
                    codepoint=ord(char),
                    name=char_name(char),
                    reason="empty_glyph",
                )
            )
            continue
        supported.append(char)

    output_path.write_text("".join(supported), encoding="utf-8")
    report_path.write_text(
        build_filter_report(font_path, charset_path, output_path, chars, supported, unsupported),
        encoding="utf-8",
    )

    return CharsetFilterResult(
        input_count=len(chars),
        supported_count=len(supported),
        unsupported_count=len(unsupported),
        unsupported_chars=unsupported,
        output_path=output_path,
        report_path=report_path,
        missing_cmap_count=count_reason(unsupported, "missing_cmap"),
        empty_glyph_count=count_reason(unsupported, "empty_glyph"),
    )


def validate_inputs(font_path: Path, charset_path: Path) -> None:
    if not font_path.exists():
        raise FontGenError(f"--font does not exist: {font_path}")
    if not font_path.is_file():
        raise FontGenError(f"--font must be a file: {font_path}")
    if not charset_path.exists():
        raise FontGenError(f"--charset does not exist: {charset_path}")
    if not charset_path.is_file():
        raise FontGenError(f"--charset must be a file: {charset_path}")


def check_output_paths(paths: list[Path], force: bool) -> None:
    if force:
        return
    existing = [path for path in paths if path.exists()]
    if existing:
        formatted = "\n".join(f"  {path}" for path in existing)
        raise FontGenError("Refusing to overwrite existing output file(s). Pass --force to overwrite:\n" + formatted)


def load_font_cmap(font_path: Path) -> set[int]:
    try:
        from fontTools.ttLib import TTFont
    except ImportError as exc:
        raise FontGenError("fontTools is required. Install dependencies with: pip install -e .") from exc

    try:
        font = TTFont(str(font_path))
    except Exception as exc:
        raise FontGenError(f"Could not read font cmap with fontTools: {font_path}") from exc

    try:
        cmap: set[int] = set()
        for table in font["cmap"].tables:
            cmap.update(table.cmap.keys())
        return cmap
    finally:
        font.close()


def load_pillow_font(font_path: Path, render_size: int = 16):
    try:
        from PIL import ImageFont
    except ImportError as exc:
        raise FontGenError("Pillow is required. Install dependencies with: pip install -e .") from exc
    try:
        return ImageFont.truetype(str(font_path), size=render_size)
    except OSError as exc:
        raise FontGenError(f"Could not load font with Pillow: {font_path}") from exc


def glyph_renders_empty(font, char: str) -> bool:
    bbox = font.getbbox(char)
    if not bbox:
        return True
    left = int(math.floor(bbox[0]))
    top = int(math.floor(bbox[1]))
    right = int(math.ceil(bbox[2]))
    bottom = int(math.ceil(bbox[3]))
    width = max(0, right - left)
    height = max(0, bottom - top)
    if width <= 0 or height <= 0:
        return True
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise FontGenError("Pillow is required. Install dependencies with: pip install -e .") from exc
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.text((-left, -top), char, font=font, fill=(255, 255, 255, 255))
    return image.getbbox() is None


def read_charset_chars(path: Path) -> list[str]:
    text = read_charset_text(path)
    seen: set[str] = set()
    chars: list[str] = []
    for char in text:
        if unicodedata.category(char)[0] == "C":
            continue
        if char in seen:
            continue
        seen.add(char)
        chars.append(char)
    return chars


def read_charset_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in CHARSET_ENCODINGS:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise FontGenError(
        f"Could not decode charset file using {', '.join(CHARSET_ENCODINGS)}: {path}"
    )


def build_filter_report(
    font_path: Path,
    charset_path: Path,
    output_path: Path,
    input_chars: list[str],
    supported_chars: list[str],
    unsupported_chars: list[UnsupportedCharsetChar],
) -> str:
    lines = [
        "# Charset Filter Report",
        "",
        f"- Font: `{font_path}`",
        f"- Input charset: `{charset_path}`",
        f"- Output charset: `{output_path}`",
        f"- Input characters: {len(input_chars)}",
        f"- Supported characters: {len(supported_chars)}",
        f"- Unsupported characters: {len(unsupported_chars)}",
        f"- missing_cmap: {count_reason(unsupported_chars, 'missing_cmap')}",
        f"- empty_glyph: {count_reason(unsupported_chars, 'empty_glyph')}",
        "",
        "## Unsupported Characters",
        "",
    ]
    if unsupported_chars:
        lines.extend(
            [
                "| Character | Code Point | Unicode Name | Reason |",
                "|---|---|---|---|",
            ]
        )
        for item in unsupported_chars:
            lines.append(
                f"| {visible_char(item.char)} | {codepoint_label(item.char)} | {item.name} | {item.reason} |"
            )
    else:
        lines.append("- <none>")
    lines.extend(
        [
            "",
            "## Warning",
            "",
            "Filtering a charset can make the generated font miss text that appears in-game. "
            "Review the unsupported list before using the filtered charset for a Starsector mod test.",
        ]
    )
    return "\n".join(lines) + "\n"


def visible_char(char: str) -> str:
    if char == " ":
        return "<space>"
    if char == "|":
        return "\\|"
    return char


def count_reason(chars: list[UnsupportedCharsetChar], reason: str) -> int:
    return sum(1 for char in chars if char.reason == reason)
