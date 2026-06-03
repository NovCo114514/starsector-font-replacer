import unittest
from pathlib import Path
import tempfile

from starsector_fontgen.bmfont import BmFontReference, CharMetric, parse_lines
from starsector_fontgen.errors import FontGenError


REFERENCE = """info face="Orbitron" size=12 bold=0 italic=0 charset="" unicode=0
common lineHeight=15 base=12 scaleW=256 scaleH=256 pages=1 packed=0
page id=0 file="orbitron12_0.png"
chars count=2
char id=32 x=0 y=0 width=0 height=0 xoffset=0 yoffset=0 xadvance=4 page=0 chnl=15
char id=65 x=1 y=2 width=3 height=4 xoffset=0 yoffset=1 xadvance=5 page=0 chnl=15
kernings count=0
"""


class BmFontTests(unittest.TestCase):
    def test_render_preserves_block_order_and_kernings_block(self) -> None:
        reference = BmFontReference(parse_lines(REFERENCE.splitlines()))
        rendered = reference.render(
            face="MyFont",
            size=16,
            line_height=20,
            base=15,
            atlas_size=2048,
            page_file="myfont16_0.png",
            chars=[
                CharMetric(
                    char=" ",
                    char_id=32,
                    x=0,
                    y=0,
                    width=0,
                    height=0,
                    xoffset=0,
                    yoffset=0,
                    xadvance=6,
                ),
                CharMetric(
                    char="A",
                    char_id=65,
                    x=2,
                    y=2,
                    width=9,
                    height=10,
                    xoffset=0,
                    yoffset=3,
                    xadvance=11,
                ),
            ],
        )

        self.assertIn('info face="MyFont" size=16 bold=0 italic=0 charset="" unicode=0', rendered)
        self.assertIn("common lineHeight=20 base=15 scaleW=2048 scaleH=2048 pages=1 packed=0", rendered)
        self.assertIn('page id=0 file="myfont16_0.png"', rendered)
        self.assertIn("chars count=2", rendered)
        self.assertIn("char id=32 x=0 y=0 width=0 height=0 xoffset=0 yoffset=0 xadvance=6 page=0 chnl=15", rendered)
        self.assertIn("kernings count=0", rendered)
        self.assertEqual(rendered.count("\nchar "), 2)

    def test_reference_load_falls_back_to_gb18030(self) -> None:
        reference_text = REFERENCE.replace("Orbitron", "中文字体")
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "orbitron12.fnt"
            path.write_bytes(reference_text.encode("gb18030"))

            reference = BmFontReference.load(path)

            self.assertEqual(reference.encoding, "gb18030")
            self.assertEqual(reference.lines[0].kind, "info")

    def test_reference_load_falls_back_to_cp1252(self) -> None:
        reference_text = REFERENCE.replace("Orbitron", "Orbitron™")
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "orbitron12.fnt"
            path.write_bytes(reference_text.encode("cp1252"))

            reference = BmFontReference.load(path)

            self.assertEqual(reference.encoding, "cp1252")

    def test_reference_load_reports_non_text_bmfont(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "orbitron12.fnt"
            path.write_bytes(b"\x00\x01\x02not-a-text-bmfont")

            with self.assertRaises(FontGenError) as raised:
                BmFontReference.load(path)

            self.assertIn("not a valid text AngelCode BMFont", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
