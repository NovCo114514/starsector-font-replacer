from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from starsector_fontgen.bmfont import CharMetric
from starsector_fontgen.generator import PackedAtlas
from starsector_fontgen.rebuild_fontlib import RebuildConfig, rebuild_fontlib


SOURCE_FNT = """info face="Orbitron" size=16 bold=0 italic=0 charset="" unicode=1
common lineHeight=18 base=14 scaleW=512 scaleH=512 pages=1 packed=0
page id=0 file="orbitron16_0.png"
chars count=1
char id=65 x=0 y=0 width=1 height=1 xoffset=0 yoffset=0 xadvance=1 page=0 chnl=15
kernings count=0
"""


class FakeImage:
    def save(self, path: Path) -> None:
        path.write_bytes(b"fake png")


class RebuildFontlibTests(unittest.TestCase):
    def test_rebuild_fontlib_preserves_source_filenames_and_page_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root / "existing" / "graphics" / "fonts"
            output_dir = root / "replacement_fonts"
            source_dir.mkdir(parents=True)
            source_fnt = source_dir / "orbitron16.fnt"
            source_fnt.write_text(SOURCE_FNT.replace("size=16", "size=-16"), encoding="utf-8")
            font = root / "Uranus.ttf"
            font.write_bytes(b"fake font")
            charset = root / "charset_supported.txt"
            charset.write_text(" A", encoding="utf-8")
            atlas = PackedAtlas(
                image=FakeImage(),
                metrics=[
                    CharMetric(
                        char="A",
                        char_id=65,
                        x=2,
                        y=2,
                        width=4,
                        height=5,
                        xoffset=0,
                        yoffset=1,
                        xadvance=6,
                    )
                ],
                line_height=20,
                base=15,
            )
            config = RebuildConfig(
                font=font,
                source_font_dir=source_dir,
                charset=charset,
                output_font_dir=output_dir,
                atlas_size=4096,
                force=False,
            )

            with patch("starsector_fontgen.rebuild_fontlib.load_font_cmap", return_value={32, 65}):
                with patch("starsector_fontgen.rebuild_fontlib.load_pillow_font", return_value=object()) as load_font:
                    with patch("starsector_fontgen.rebuild_fontlib.render_glyphs", return_value=([], [])):
                        with patch("starsector_fontgen.rebuild_fontlib.measure_line_metrics", return_value=(20, 15)):
                            with patch("starsector_fontgen.rebuild_fontlib.pack_glyphs", return_value=atlas):
                                result = rebuild_fontlib(config)

            self.assertEqual(len(result.entries), 1)
            self.assertTrue(result.entries[0].success)
            self.assertEqual(result.entries[0].original_size, -16)
            self.assertEqual(result.entries[0].render_size, 16)
            self.assertEqual(load_font.call_args.args[1], 16)
            output_fnt = output_dir / "orbitron16.fnt"
            output_png = output_dir / "orbitron16_0.png"
            self.assertTrue(output_fnt.exists())
            self.assertTrue(output_png.exists())
            fnt_text = output_fnt.read_text(encoding="utf-8")
            self.assertIn('page id=0 file="orbitron16_0.png"', fnt_text)
            self.assertIn('info face="Uranus" size=-16', fnt_text)
            self.assertIn("scaleW=4096 scaleH=4096", fnt_text)
            report = (output_dir / "rebuild_fontlib_report.md").read_text(encoding="utf-8")
            self.assertIn("orbitron16.fnt", report)
            self.assertIn("success", report)
            self.assertIn("| orbitron16.fnt | -16 | 16 |", report)

    def test_rebuild_fontlib_skips_unparseable_size(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root / "fonts"
            output_dir = root / "out"
            source_dir.mkdir()
            (source_dir / "bad.fnt").write_text(SOURCE_FNT.replace("size=16", "size=bad"), encoding="utf-8")
            font = root / "font.ttf"
            font.write_bytes(b"fake font")
            charset = root / "charset.txt"
            charset.write_text("A", encoding="utf-8")
            config = RebuildConfig(
                font=font,
                source_font_dir=source_dir,
                charset=charset,
                output_font_dir=output_dir,
                atlas_size=4096,
            )

            with patch("starsector_fontgen.rebuild_fontlib.load_font_cmap", return_value={65}):
                result = rebuild_fontlib(config)

            self.assertFalse(result.entries[0].success)
            self.assertEqual(result.entries[0].status, "failed_parse_size")
            self.assertIn("Could not parse info size", result.entries[0].error)
            self.assertFalse((output_dir / "bad.fnt").exists())


if __name__ == "__main__":
    unittest.main()
