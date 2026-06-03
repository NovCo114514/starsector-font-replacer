from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .errors import FontGenError


FIELD_RE = re.compile(r"(?P<key>[A-Za-z_][A-Za-z0-9_]*)=(?P<value>\"[^\"]*\"|\S+)")
REFERENCE_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "cp1252", "latin-1")


@dataclass
class BmFontLine:
    raw: str
    kind: str
    field_order: list[str]
    fields: dict[str, str]


@dataclass
class CharMetric:
    char: str
    char_id: int
    x: int
    y: int
    width: int
    height: int
    xoffset: int
    yoffset: int
    xadvance: int
    page: int = 0
    chnl: int = 15


class BmFontReference:
    def __init__(self, lines: list[BmFontLine], encoding: str = "<unknown>") -> None:
        self.lines = lines
        self.encoding = encoding
        self._validate()

    @classmethod
    def load(cls, path: Path) -> "BmFontReference":
        if not path.exists():
            raise FontGenError(
                "Missing reference/orbitron12.fnt. Put the Starsector reference "
                f"font file at: {path}"
            )
        if not path.is_file():
            raise FontGenError(f"reference/orbitron12.fnt is not a file: {path}")

        text, encoding = read_reference_text(path)
        return cls(parse_lines(text.splitlines()), encoding=encoding)

    def _validate(self) -> None:
        kinds = {line.kind for line in self.lines}
        missing = [kind for kind in ("info", "common", "page", "chars") if kind not in kinds]
        if missing:
            raise FontGenError(
                "reference/orbitron12.fnt is not a valid text AngelCode BMFont file; "
                "missing required block(s): " + ", ".join(missing)
            )

    @property
    def char_field_order(self) -> list[str]:
        for line in self.lines:
            if line.kind == "char":
                return line.field_order
        return [
            "id",
            "x",
            "y",
            "width",
            "height",
            "xoffset",
            "yoffset",
            "xadvance",
            "page",
            "chnl",
        ]

    @property
    def default_channel(self) -> int:
        for line in self.lines:
            if line.kind == "char" and "chnl" in line.fields:
                try:
                    return int(unquote(line.fields["chnl"]))
                except ValueError:
                    return 15
        return 15

    def render(
        self,
        *,
        face: str,
        size: int,
        line_height: int,
        base: int,
        atlas_size: int,
        page_file: str,
        chars: list[CharMetric],
    ) -> str:
        out: list[str] = []
        inserted_chars = False
        seen_page = False

        for line in self.lines:
            if line.kind == "info":
                out.append(
                    render_line(
                        line,
                        {
                            "face": quote(face),
                            "size": str(size),
                        },
                    )
                )
            elif line.kind == "common":
                out.append(
                    render_line(
                        line,
                        {
                            "lineHeight": str(line_height),
                            "base": str(base),
                            "scaleW": str(atlas_size),
                            "scaleH": str(atlas_size),
                            "pages": "1",
                        },
                    )
                )
            elif line.kind == "page":
                if not seen_page:
                    out.append(
                        render_line(
                            line,
                            {
                                "id": "0",
                                "file": quote(page_file),
                            },
                        )
                    )
                    seen_page = True
            elif line.kind == "chars":
                out.append(render_line(line, {"count": str(len(chars))}))
                out.extend(render_char_lines(chars, self.char_field_order, self.default_channel))
                inserted_chars = True
            elif line.kind == "char":
                continue
            elif line.kind == "kernings":
                out.append(render_line(line, {"count": "0"}))
            elif line.kind == "kerning":
                continue
            else:
                out.append(line.raw)

        if not inserted_chars:
            out.append(f"chars count={len(chars)}")
            out.extend(render_char_lines(chars, self.char_field_order, self.default_channel))

        return "\n".join(out) + "\n"


def read_reference_text(path: Path) -> tuple[str, str]:
    return read_bmfont_text(path, label="reference/orbitron12.fnt")


def read_bmfont_text(path: Path, label: str | None = None) -> tuple[str, str]:
    display = label or str(path)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise FontGenError(f"Could not read {display}: {path}") from exc

    for encoding in REFERENCE_ENCODINGS:
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue

    # latin-1 decodes every byte, so reaching this point would be surprising. Keep a
    # user-facing error here anyway in case Python codec behavior changes.
    raise FontGenError(
        f"Could not decode {display} as a text AngelCode BMFont file "
        "using utf-8-sig, utf-8, gb18030, cp1252, or latin-1."
    )


def parse_lines(raw_lines: list[str]) -> list[BmFontLine]:
    parsed: list[BmFontLine] = []
    for raw in raw_lines:
        stripped = raw.strip()
        kind = stripped.split(maxsplit=1)[0] if stripped else ""
        fields: dict[str, str] = {}
        field_order: list[str] = []
        for match in FIELD_RE.finditer(raw):
            key = match.group("key")
            fields[key] = match.group("value")
            field_order.append(key)
        parsed.append(BmFontLine(raw=raw, kind=kind, field_order=field_order, fields=fields))
    return parsed


def quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', r"\"")
    return f'"{escaped}"'


def unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1].replace(r"\"", '"').replace("\\\\", "\\")
    return value


def render_line(line: BmFontLine, updates: dict[str, str]) -> str:
    fields = dict(line.fields)
    fields.update(updates)
    order = list(line.field_order)
    for key in updates:
        if key not in order:
            order.append(key)
    rendered = " ".join(f"{key}={fields[key]}" for key in order if key in fields)
    return f"{line.kind} {rendered}".rstrip()


def render_char_lines(
    chars: list[CharMetric],
    field_order: list[str],
    default_channel: int,
) -> list[str]:
    required = [
        "id",
        "x",
        "y",
        "width",
        "height",
        "xoffset",
        "yoffset",
        "xadvance",
        "page",
        "chnl",
    ]
    order = list(field_order)
    for field in required:
        if field not in order:
            order.append(field)

    lines: list[str] = []
    for metric in chars:
        fields = {
            "id": str(metric.char_id),
            "x": str(metric.x),
            "y": str(metric.y),
            "width": str(metric.width),
            "height": str(metric.height),
            "xoffset": str(metric.xoffset),
            "yoffset": str(metric.yoffset),
            "xadvance": str(metric.xadvance),
            "page": str(metric.page),
            "chnl": str(metric.chnl if metric.chnl is not None else default_channel),
        }
        rendered = " ".join(f"{key}={fields[key]}" for key in order if key in fields)
        lines.append(f"char {rendered}")
    return lines
