from pathlib import Path
import tempfile
import unittest

from starsector_fontgen.scanner import build_charset


class ScannerTests(unittest.TestCase):
    def test_build_charset_reads_gb18030_and_tracks_ignored_chars(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            text_dir = root / "data"
            text_dir.mkdir()
            (text_dir / "strings.csv").write_bytes("舰船,武器\n".encode("gb18030"))
            extra = root / "extra.txt"
            extra.write_text("★\ufeff\t", encoding="utf-8")

            result = build_charset(text_dir, extra, "开始游戏 A")

            self.assertIn("舰", result.chars)
            self.assertIn("★", result.chars)
            self.assertIn(" ", result.chars)
            self.assertNotIn("\t", result.chars)
            self.assertNotIn("\ufeff", result.chars)
            self.assertIn("\t", result.ignored_chars)
            self.assertIn("\ufeff", result.ignored_chars)
            self.assertEqual(result.read_records[0].encoding, "gb18030")
            self.assertGreater(result.source_unique_counts["preview text"], 0)

    def test_damaged_encoding_is_marked_after_decode_failures(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            text_dir = root / "data"
            text_dir.mkdir()
            (text_dir / "broken.txt").write_bytes(b"\xff\xfe\xfd")

            result = build_charset(text_dir, None, "A")

            self.assertEqual(len(result.read_records), 1)
            self.assertTrue(result.read_records[0].damaged_encoding)
            self.assertEqual(result.read_records[0].encoding, "gb18030/errors=ignore")


if __name__ == "__main__":
    unittest.main()
