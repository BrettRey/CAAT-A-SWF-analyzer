from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swf_anonymizer.eval_bundle import collect_bundle_paths, create_eval_bundle


class EvalBundleTests(unittest.TestCase):
    def test_bundle_excludes_sensitive_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            root = Path(temp_dir_name).resolve()
            (root / "src").mkdir()
            (root / "tests").mkdir()
            (root / "docs").mkdir()
            (root / "input").mkdir()
            (root / "output" / "csv").mkdir(parents=True)
            (root / ".swf_state").mkdir()
            (root / "llm_safe_workspace").mkdir()
            (root / "docs" / "guide_images").mkdir()

            for relative_path in ("README.md", "AGENTS.md", "CLAUDE.md", ".gitignore", "pyproject.toml"):
                (root / relative_path).write_text("ok\n", encoding="utf-8")
            (root / "src" / "tool.py").write_text("print('ok')\n", encoding="utf-8")
            (root / "tests" / "test_tool.py").write_text("pass\n", encoding="utf-8")
            (root / "docs" / "WORKFLOW.md").write_text("# Docs\n", encoding="utf-8")
            (root / "docs" / "guide_images" / "image.png").write_bytes(b"png")
            (root / "input" / "secret.pdf").write_text("secret\n", encoding="utf-8")
            (root / "output" / "csv" / "report.csv").write_text("secret\n", encoding="utf-8")
            (root / ".swf_state" / "stable_ids.json").write_text("{}\n", encoding="utf-8")

            bundle_paths = [path.relative_to(root).as_posix() for path in collect_bundle_paths(root)]
            bundle_path = create_eval_bundle(root, root / "dist" / "bundle.zip")

            with ZipFile(bundle_path) as archive:
                archive_names = set(archive.namelist())
                manifest = archive.read("EVAL_BUNDLE_MANIFEST.txt").decode("utf-8")

        self.assertIn("README.md", bundle_paths)
        self.assertIn("pyproject.toml", bundle_paths)
        self.assertIn("src/tool.py", bundle_paths)
        self.assertIn("docs/WORKFLOW.md", bundle_paths)
        self.assertNotIn("input/secret.pdf", bundle_paths)
        self.assertNotIn("output/csv/report.csv", bundle_paths)
        self.assertNotIn(".swf_state/stable_ids.json", bundle_paths)
        self.assertNotIn("docs/guide_images/image.png", bundle_paths)
        self.assertIn("EVAL_BUNDLE_MANIFEST.txt", archive_names)
        self.assertIn("src/tool.py", archive_names)
        self.assertNotIn("input/secret.pdf", archive_names)
        self.assertNotIn(str(root), manifest)


if __name__ == "__main__":
    unittest.main()
