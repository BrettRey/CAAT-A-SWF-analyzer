from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swf_anonymizer.pipeline import process_paths


class PipelineTests(unittest.TestCase):
    def test_generates_safe_anonymized_filename(self) -> None:
        source_text = "\n".join(
            [
                "Date: 16-MAR-2026",
                "Teacher Name: Doe, Jane",
                "ID: N12345678",
                "Period covered by SWF From: 11-MAY-2026 To: 27-JUN-2026",
            ]
        )

        with tempfile.TemporaryDirectory() as temp_dir_name:
            root = Path(temp_dir_name)
            input_path = root / "Jane Doe SWF.md"
            input_path.write_text(source_text, encoding="utf-8")

            results = process_paths([input_path], root / "output")

            anonymized_name = results[0].anonymized_path.name
            self.assertRegex(
                anonymized_name,
                r"^swf_fac001_2026-05-11_to_2026-06-27_issued_2026-03-16_[0-9a-f]{8}\.txt$",
            )
            self.assertNotIn("Jane", anonymized_name)
            self.assertTrue((root / "output" / "keys" / "keymap.json").exists())
            self.assertTrue((root / "output" / "csv" / "course_assignments.csv").exists())
            self.assertTrue((root / "output" / "csv" / "swf_summary.csv").exists())
            self.assertTrue((root / "output" / "reports" / "source_group_summary.csv").exists())
            self.assertTrue((root / "output" / "reports" / "quality_findings.csv").exists())
            self.assertRegex(results[0].stable_faculty_id or "", r"^FID[0-9A-F]{12}$")


if __name__ == "__main__":
    unittest.main()
