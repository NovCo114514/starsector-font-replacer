from pathlib import Path
import tempfile
import unittest

from starsector_fontgen.analyzer import analyze_fontlib, parse_font_file


def fnt_text(face: str, size: int, page_file: str, char_ids: list[int]) -> str:
    char_lines = "\n".join(
        f"char id={char_id} x=0 y=0 width=1 height=1 xoffset=0 yoffset=0 xadvance=1 page=0 chnl=15"
        for char_id in char_ids
    )
    return "\n".join(
        [
            f'info face="{face}" size={size} bold=0 italic=0 charset="" unicode=1',
            "common lineHeight=16 base=12 scaleW=256 scaleH=256 pages=1 packed=0",
            f'page id=0 file="{page_file}"',
            f"chars count={len(char_ids)}",
            char_lines,
            "kernings count=0",
            "",
        ]
    )


class AnalyzerTests(unittest.TestCase):
    def test_parse_font_file_uses_encoding_fallback_and_checks_png(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            font_dir = root / "graphics" / "fonts"
            font_dir.mkdir(parents=True)
            (font_dir / "font_a_0.png").write_bytes(b"png")
            fnt = font_dir / "font_a.fnt"
            fnt.write_bytes(fnt_text("中文字体", 16, "font_a_0.png", [32, 65, 20013]).encode("gb18030"))

            analysis = parse_font_file(fnt, font_dir)

            self.assertEqual(analysis.encoding, "gb18030")
            self.assertEqual(analysis.face, "中文字体")
            self.assertEqual(analysis.size, 16)
            self.assertEqual(analysis.line_height, 16)
            self.assertEqual(analysis.scale_w, 256)
            self.assertEqual(analysis.scale_h, 256)
            self.assertEqual(analysis.pages_count, 1)
            self.assertEqual(analysis.page_files, ["font_a_0.png"])
            self.assertTrue(analysis.pngs_exist)
            self.assertEqual(analysis.char_ids, {32, 65, 20013})

    def test_analyze_fontlib_writes_charset_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            font_dir = root / "graphics" / "fonts"
            config_dir = root / "config"
            output_dir = root / "out" / "fontlib_analysis"
            font_dir.mkdir(parents=True)
            config_dir.mkdir()
            (font_dir / "font_a_0.png").write_bytes(b"png")
            (font_dir / "font_a.fnt").write_text(
                fnt_text("FontA", 16, "font_a_0.png", [32, 65, 20013]),
                encoding="utf-8",
            )
            (font_dir / "font_b.fnt").write_text(
                fnt_text("FontB", 16, "missing_b_0.png", [32, 66, 20013]),
                encoding="utf-8",
            )
            (font_dir / "font_dup.fnt").write_text(
                fnt_text("FontDup", 16, "font_a_0.png", [32, 65, 20013]),
                encoding="utf-8",
            )
            (config_dir / "settings.json").write_text(
                '{"font": "graphics/fonts/font_a.fnt"}',
                encoding="utf-8",
            )

            result = analyze_fontlib(font_dir, config_dir, output_dir)

            charset = result.charset_path.read_text(encoding="utf-8")
            report = result.report_path.read_text(encoding="utf-8")
            self.assertEqual(len(result.fonts), 3)
            self.assertIn("A", charset)
            self.assertIn("B", charset)
            self.assertIn("中", charset)
            self.assertIn("font_a.fnt", report)
            self.assertIn("settings.json", report)
            self.assertIn("missing_b_0.png", report)
            self.assertIn("Same Unicode char-id set", report)
            self.assertIn("Total unique Unicode chars across all FNT files: 4", report)


if __name__ == "__main__":
    unittest.main()
