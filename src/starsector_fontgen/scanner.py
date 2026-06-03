from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
import unicodedata

from .errors import FontGenError


TEXT_EXTENSIONS = {
    ".csv",
    ".json",
    ".txt",
    ".fnt",
    ".variant",
    ".ship",
    ".wpn",
}

READ_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030")
ZERO_WIDTH_CODEPOINTS = {0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF}


@dataclass
class FileReadRecord:
    path: Path
    encoding: str
    damaged_encoding: bool = False


@dataclass
class IgnoredCharRecord:
    char: str
    count: int = 0
    sources: set[str] = field(default_factory=set)


@dataclass
class CharsetBuildResult:
    chars: list[str]
    char_sources: dict[str, set[str]]
    ignored_chars: dict[str, IgnoredCharRecord]
    read_records: list[FileReadRecord]
    source_unique_counts: dict[str, int]


def codepoint_label(char: str) -> str:
    return f"U+{ord(char):04X}"


def char_name(char: str) -> str:
    return unicodedata.name(char, "<unnamed>")


def describe_char(char: str) -> str:
    if char == " ":
        visible = "<space>"
    elif char == "\t":
        visible = r"\t"
    elif char == "\n":
        visible = r"\n"
    elif char == "\r":
        visible = r"\r"
    elif char == "\0":
        visible = r"\0"
    else:
        visible = char
    return f"{visible} ({codepoint_label(char)}, {char_name(char)})"


def is_ignored_char(char: str) -> bool:
    if char == " ":
        return False
    codepoint = ord(char)
    if codepoint in ZERO_WIDTH_CODEPOINTS:
        return True
    return unicodedata.category(char)[0] == "C"


def read_text_with_fallback(path: Path) -> tuple[str, FileReadRecord]:
    for encoding in READ_ENCODINGS:
        try:
            return path.read_text(encoding=encoding), FileReadRecord(path, encoding)
        except UnicodeDecodeError:
            continue

    raw = path.read_bytes()
    text = raw.decode("gb18030", errors="ignore")
    return text, FileReadRecord(path, "gb18030/errors=ignore", damaged_encoding=True)


def iter_text_files(text_dir: Path) -> list[Path]:
    if not text_dir.exists():
        raise FontGenError(f"--text-dir does not exist: {text_dir}")
    if not text_dir.is_dir():
        raise FontGenError(f"--text-dir must be a directory: {text_dir}")
    return sorted(
        (
            path
            for path in text_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS
        ),
        key=lambda p: str(p).lower(),
    )


def add_text_to_charset(
    text: str,
    source: str,
    char_sources: dict[str, set[str]],
    ignored: dict[str, IgnoredCharRecord],
    source_chars: dict[str, set[str]],
) -> None:
    for char in text:
        if is_ignored_char(char):
            record = ignored.setdefault(char, IgnoredCharRecord(char))
            record.count += 1
            record.sources.add(source)
            continue
        char_sources[char].add(source)
        source_chars[source].add(char)


def build_charset(
    text_dir: Path,
    extra_charset: Path | None,
    preview_text: str,
) -> CharsetBuildResult:
    char_sources: dict[str, set[str]] = defaultdict(set)
    ignored: dict[str, IgnoredCharRecord] = {}
    source_chars: dict[str, set[str]] = defaultdict(set)
    read_records: list[FileReadRecord] = []

    for path in iter_text_files(text_dir):
        text, record = read_text_with_fallback(path)
        read_records.append(record)
        add_text_to_charset(text, "text-dir", char_sources, ignored, source_chars)

    if extra_charset is not None:
        if not extra_charset.exists():
            raise FontGenError(f"--extra-charset does not exist: {extra_charset}")
        if not extra_charset.is_file():
            raise FontGenError(f"--extra-charset must be a file: {extra_charset}")
        text, record = read_text_with_fallback(extra_charset)
        read_records.append(record)
        add_text_to_charset(text, "extra-charset", char_sources, ignored, source_chars)

    add_text_to_charset(preview_text, "preview text", char_sources, ignored, source_chars)

    chars = sorted(char_sources.keys(), key=ord)
    source_unique_counts = {
        source: len(chars_for_source) for source, chars_for_source in source_chars.items()
    }
    return CharsetBuildResult(
        chars=chars,
        char_sources={char: set(sources) for char, sources in char_sources.items()},
        ignored_chars=ignored,
        read_records=read_records,
        source_unique_counts=source_unique_counts,
    )
