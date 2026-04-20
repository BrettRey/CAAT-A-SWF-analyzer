from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swf_anonymizer.comparison import write_comparison_reports


SUMMARY_FIELDS = [
    "document_id",
    "faculty_token",
    "stable_faculty_id",
    "source_group",
    "source_type",
    "extraction_method",
    "period_start",
    "period_end",
    "issued_date",
    "number_of_course_preparations",
    "number_of_sections",
    "number_of_instruction_languages",
    "assigned_teaching_contact_hours_week",
    "preparation_hours_week",
    "evaluation_feedback_hours_week",
    "complementary_hours_allowance_week",
    "complementary_hours_assigned_week",
    "total_this_period_swf",
    "balance_from_previous_swf_contact_hours",
    "balance_from_previous_swf_contact_days",
    "balance_from_previous_swf_teaching_weeks",
    "total_this_swf_contact_hours",
    "total_this_swf_contact_days",
    "total_this_swf_teaching_weeks",
    "total_to_end_date_contact_hours",
    "total_to_end_date_contact_days",
    "total_to_end_date_teaching_weeks",
]

COURSE_FIELDS = [
    "document_id",
    "faculty_token",
    "stable_faculty_id",
    "source_group",
    "source_type",
    "extraction_method",
    "period_start",
    "period_end",
    "issued_date",
    "course_identifier",
    "course_code",
    "course_component",
    "course_name",
    "contact_hours",
    "instruction_language",
    "delivery_type",
    "prep_factor",
    "prep_attended_hours",
    "prep_additional_hours",
    "class_size",
    "eval1_type",
    "eval1_factor",
    "eval1_percent",
    "eval2_type",
    "eval2_factor",
    "eval2_percent",
    "eval3_type",
    "eval3_factor",
    "eval3_percent",
    "eval_attended_hours",
    "eval_additional_hours",
    "complement_allowance_hours",
    "complement_assigned_hours",
]


class ComparisonTests(unittest.TestCase):
    def test_writes_faculty_and_course_comparison_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            root = Path(temp_dir_name)
            previous = root / "previous"
            current = root / "current"
            for base in (previous, current):
                (base / "csv").mkdir(parents=True)
                (base / "reports").mkdir(parents=True)

            write_csv(
                previous / "csv" / "swf_summary.csv",
                SUMMARY_FIELDS,
                [
                    {
                        "document_id": "prev_doc",
                        "faculty_token": "FAC001",
                        "stable_faculty_id": "FIDABC123456",
                        "source_group": "Dean A",
                        "period_start": "01-JAN-2026",
                        "period_end": "01-MAR-2026",
                        "assigned_teaching_contact_hours_week": "12.00",
                        "total_this_period_swf": "43.20",
                        "total_to_end_date_teaching_weeks": "28",
                    }
                ],
            )
            write_csv(
                current / "csv" / "swf_summary.csv",
                SUMMARY_FIELDS,
                [
                    {
                        "document_id": "cur_doc",
                        "faculty_token": "FAC031",
                        "stable_faculty_id": "FIDABC123456",
                        "source_group": "Dean B",
                        "period_start": "11-MAY-2026",
                        "period_end": "28-JUN-2026",
                        "assigned_teaching_contact_hours_week": "14.00",
                        "total_this_period_swf": "45.00",
                        "total_to_end_date_teaching_weeks": "35",
                    }
                ],
            )
            write_csv(
                previous / "csv" / "course_assignments.csv",
                COURSE_FIELDS,
                [
                    {
                        "document_id": "prev_doc",
                        "faculty_token": "FAC001",
                        "stable_faculty_id": "FIDABC123456",
                        "source_group": "Dean A",
                        "course_code": "EAPA 107",
                        "contact_hours": "6.00",
                        "delivery_type": "EB",
                    }
                ],
            )
            write_csv(
                current / "csv" / "course_assignments.csv",
                COURSE_FIELDS,
                [
                    {
                        "document_id": "cur_doc",
                        "faculty_token": "FAC031",
                        "stable_faculty_id": "FIDABC123456",
                        "source_group": "Dean B",
                        "course_code": "WRIT 200",
                        "contact_hours": "7.00",
                        "delivery_type": "RB",
                    }
                ],
            )

            outputs = write_comparison_reports(current, previous)
            report = (current / "reports" / "comparison_summary.md").read_text(encoding="utf-8")
            faculty_rows = read_csv(current / "reports" / "comparison_faculty_summary.csv")

        self.assertIn("Faculty Changes", report)
        self.assertIn("Course Changes", report)
        self.assertEqual(outputs["faculty_csv"], current / "reports" / "comparison_faculty_summary.csv")
        self.assertEqual(len(faculty_rows), 1)
        self.assertEqual(faculty_rows[0]["stable_faculty_id"], "FIDABC123456")
        self.assertEqual(faculty_rows[0]["status"], "changed")
        self.assertEqual(faculty_rows[0]["courses_added"], "WRIT 200")
        self.assertEqual(faculty_rows[0]["courses_removed"], "EAPA 107")


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


if __name__ == "__main__":
    unittest.main()
