from __future__ import annotations

import csv
from pathlib import Path

from .models import StructuredDocument


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

COMPLEMENTARY_FIELDS = [
    "document_id",
    "faculty_token",
    "stable_faculty_id",
    "source_group",
    "source_type",
    "extraction_method",
    "period_start",
    "period_end",
    "issued_date",
    "description",
    "activity_detail",
    "attributed_hours",
]

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


def write_csv_exports(documents: list[StructuredDocument], output_root: Path) -> dict[str, Path]:
    csv_dir = output_root / "csv"
    csv_dir.mkdir(parents=True, exist_ok=True)

    course_rows = [row for document in documents for row in document.course_rows]
    complementary_rows = [row for document in documents for row in document.complementary_rows]
    summary_rows = [document.summary_row for document in documents if document.summary_row]

    course_path = csv_dir / "course_assignments.csv"
    complementary_path = csv_dir / "complementary_functions.csv"
    summary_path = csv_dir / "swf_summary.csv"

    write_csv(course_path, COURSE_FIELDS, course_rows)
    write_csv(complementary_path, COMPLEMENTARY_FIELDS, complementary_rows)
    write_csv(summary_path, SUMMARY_FIELDS, summary_rows)

    return {
        "course_assignments": course_path,
        "complementary_functions": complementary_path,
        "swf_summary": summary_path,
    }


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
