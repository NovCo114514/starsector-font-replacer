from pathlib import Path
import tempfile
import unittest

import starsector_fontgen.gui as gui


class DummyVar:
    def __init__(self, value: str) -> None:
        self.value = value

    def get(self) -> str:
        return self.value


class GuiEntryTests(unittest.TestCase):
    def test_gui_module_exposes_main(self) -> None:
        self.assertTrue(callable(gui.main))
        self.assertEqual(gui.APP_TITLE, "Starsector Font Replacer")

    def test_append_full_log_records_command_output_and_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = object.__new__(gui.FontReplacerApp)
            app.work_dir = DummyVar(str(root))
            messages: list[str] = []
            app.log_thread = messages.append

            report = root / "report.md"
            app.append_full_log(
                step="过滤字符集",
                command="filter_charset --font font.ttf",
                stdout=["supported=10"],
                stderr="empty glyph",
                return_code=1,
                report_paths=[report],
            )

            log_path = root / "starsector_font_replacer_gui.log"
            content = log_path.read_text(encoding="utf-8")
            self.assertIn("step: 过滤字符集", content)
            self.assertIn("command: filter_charset --font font.ttf", content)
            self.assertIn("supported=10", content)
            self.assertIn("empty glyph", content)
            self.assertIn("return_code: 1", content)
            self.assertIn(str(report), content)
            self.assertEqual(messages, [f"日志文件: {log_path}"])


if __name__ == "__main__":
    unittest.main()
