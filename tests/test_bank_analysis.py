from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swf_anonymizer.bank_analysis import write_bank_analysis


class BankAnalysisTests(unittest.TestCase):
    def test_writes_token_only_analysis_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            root = Path(temp_dir_name).resolve()
            output_root = root / "output"
            (output_root / "csv").mkdir(parents=True)
            (output_root / "reports").mkdir()

            write_csv(
                output_root / "csv" / "swf_summary.csv",
                [
                    "document_id",
                    "stable_faculty_id",
                    "faculty_token",
                    "source_group",
                    "period_start",
                    "issued_date",
                    "assigned_teaching_contact_hours_week",
                    "total_this_period_swf",
                    "number_of_course_preparations",
                ],
                [
                    {
                        "document_id": "doc-1",
                        "stable_faculty_id": "FID001",
                        "faculty_token": "FAC001",
                        "source_group": "Associate Dean Alpha",
                        "period_start": "01-Sep-2025",
                        "issued_date": "15-Aug-2025",
                        "assigned_teaching_contact_hours_week": "16",
                        "total_this_period_swf": "45",
                        "number_of_course_preparations": "5",
                    },
                    {
                        "document_id": "doc-2",
                        "stable_faculty_id": "FID002",
                        "faculty_token": "FAC002",
                        "source_group": "Associate Dean Alpha",
                        "period_start": "10-Jan-2026",
                        "issued_date": "20-Dec-2025",
                        "assigned_teaching_contact_hours_week": "14",
                        "total_this_period_swf": "42",
                        "number_of_course_preparations": "3",
                    },
                ],
            )
            write_csv(
                output_root / "csv" / "course_assignments.csv",
                ["document_id", "stable_faculty_id", "faculty_token", "course_code", "contact_hours"],
                [
                    {
                        "document_id": "doc-1",
                        "stable_faculty_id": "FID001",
                        "faculty_token": "FAC001",
                        "course_code": "WRIT 100",
                        "contact_hours": "3",
                    },
                    {
                        "document_id": "doc-2",
                        "stable_faculty_id": "FID002",
                        "faculty_token": "FAC002",
                        "course_code": "WRIT 100",
                        "contact_hours": "4",
                    },
                ],
            )
            write_csv(
                output_root / "csv" / "complementary_functions.csv",
                ["document_id"],
                [{"document_id": "doc-1"}],
            )
            write_csv(
                output_root / "reports" / "ca_findings.csv",
                ["document_id", "source_group", "severity", "rule_id"],
                [
                    {
                        "document_id": "doc-1",
                        "source_group": "Associate Dean Alpha",
                        "severity": "high",
                        "rule_id": "weekly_workload_absolute_max",
                    }
                ],
            )
            write_csv(
                output_root / "reports" / "prep_type_findings.csv",
                ["document_id", "source_group", "rule_id"],
                [
                    {
                        "document_id": "doc-1",
                        "source_group": "Associate Dean Alpha",
                        "rule_id": "invalid_prep_type_code",
                    }
                ],
            )
            write_csv(
                output_root / "reports" / "quality_findings.csv",
                ["document_id", "source_group", "severity", "rule_id"],
                [
                    {
                        "document_id": "doc-2",
                        "source_group": "Associate Dean Alpha",
                        "severity": "review",
                        "rule_id": "missing_dates",
                    }
                ],
            )
            write_csv(
                output_root / "reports" / "processing_failures.csv",
                ["error"],
                [{"error": "Document stream is empty"}],
            )

            paths = write_bank_analysis(output_root)
            group_rows = read_csv(paths["group_overview"])
            course_rows = read_csv(paths["course_rollup"])
            markdown = paths["summary_markdown"].read_text(encoding="utf-8")

        self.assertEqual(group_rows[0]["group_token"], "GROUP001")
        self.assertEqual(group_rows[0]["ca_high"], "1")
        self.assertEqual(course_rows[0]["course_code"], "WRIT 100")
        self.assertIn("GROUP001", markdown)
        self.assertIn("FID001", markdown)
        self.assertNotIn("Associate Dean Alpha", markdown)


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
