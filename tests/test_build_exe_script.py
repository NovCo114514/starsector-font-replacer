from pathlib import Path
import unittest


class BuildExeScriptTests(unittest.TestCase):
    def test_build_exe_script_contains_all_entrypoints_and_no_add_data(self) -> None:
        script = Path("build_exe.ps1").read_text(encoding="utf-8")

        for name in [
            "starsector-fontgen",
            "starsector-fontgen-analyze-fontlib",
            "starsector-fontgen-filter-charset",
            "starsector-fontgen-rebuild-fontlib",
            "starsector-fontgen-build-pack",
            "starsector-fontgen-gui",
        ]:
            self.assertIn(name, script)

        self.assertIn("--onefile", script)
        self.assertIn("--windowed", script)
        self.assertIn("--distpath $DistPath", script)
        self.assertNotIn("--add-data", script)
        self.assertNotIn(".venv", script)
        self.assertNotIn("output_stage", script)


if __name__ == "__main__":
    unittest.main()
