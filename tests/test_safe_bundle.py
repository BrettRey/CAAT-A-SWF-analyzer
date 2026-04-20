from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swf_anonymizer.safe_bundle import (
    build_group_mapping,
    copy_required_tree,
    prepare_destination,
    sanitize_csv_tree,
    sanitize_markdown_tree,
    validate_destination,
)


class SafeBundleTests(unittest.TestCase):
    def test_validate_destination_rejects_same_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            root = Path(temp_dir_name).resolve()
            with self.assertRaises(ValueError):
                validate_destination(root, root)

    def test_prepare_destination_requires_force_for_nonempty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            dest_root = Path(temp_dir_name).resolve() / "safe"
            dest_root.mkdir()
            (dest_root / "existing.txt").write_text("x\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                prepare_destination(dest_root, force=False)

            prepare_destination(dest_root, force=True)
            self.assertTrue(dest_root.is_dir())
            self.assertEqual(list(dest_root.iterdir()), [])

    def test_sanitizes_source_group_fields_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            root = Path(temp_dir_name).resolve()
            source_root = root / "output"
            dest_root = root / "safe"
            (source_root / "anonymized").mkdir(parents=True)
            (source_root / "csv").mkdir()
            (source_root / "reports").mkdir()

            (source_root / "anonymized" / "swf_fac001.txt").write_text("[FAC001]\n", encoding="utf-8")
            write_csv(
                source_root / "csv" / "swf_summary.csv",
                ["stable_faculty_id", "source_group", "faculty_token"],
                [
                    {
                        "stable_faculty_id": "FID123",
                        "source_group": "Associate Dean Alpha",
                        "faculty_token": "FAC001",
                    }
                ],
            )
            write_csv(
                source_root / "reports" / "source_group_summary.csv",
                ["source_group", "documents"],
                [
                    {"source_group": "Associate Dean Alpha", "documents": "1"},
                    {"source_group": "ALL", "documents": "1"},
                ],
            )
            (source_root / "reports" / "source_group_summary.md").write_text(
                "# Source Group Summary\n\nAssociate Dean Alpha\n",
                encoding="utf-8",
            )

            mapping = build_group_mapping(source_root)
            copy_required_tree(source_root, dest_root, "anonymized")
            sanitize_csv_tree(source_root, dest_root, "csv", mapping)
            sanitize_csv_tree(source_root, dest_root, "reports", mapping)
            sanitize_markdown_tree(source_root, dest_root, "reports", mapping)

            summary_rows = read_csv(dest_root / "csv" / "swf_summary.csv")
            report_rows = read_csv(dest_root / "reports" / "source_group_summary.csv")
            markdown = (dest_root / "reports" / "source_group_summary.md").read_text(encoding="utf-8")

        self.assertEqual(summary_rows[0]["source_group"], "GROUP001")
        self.assertEqual(report_rows[0]["source_group"], "GROUP001")
        self.assertEqual(report_rows[1]["source_group"], "ALL")
        self.assertNotIn("Associate Dean Alpha", markdown)
        self.assertIn("GROUP001", markdown)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


if __name__ == "__main__":
    unittest.main()
