from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swf_anonymizer.ca_checker import collect_findings
from swf_anonymizer.models import StructuredDocument


class CACheckerTests(unittest.TestCase):
    def make_document(self, **overrides: str) -> StructuredDocument:
        document = StructuredDocument(
            document_id="swf_fac001_2026-05-11_to_2026-06-27_issued_2026-03-16",
            faculty_token="FAC001",
            source_type="pdf",
            extraction_method="pdftotext",
            program_group="Post-secondary",
            probationary_status="Non-Probationary",
        )
        document.summary_row = {
            "document_id": document.document_id,
            "faculty_token": document.faculty_token,
            "assigned_teaching_contact_hours_week": "8.00",
            "number_of_course_preparations": "1",
            "complementary_hours_allowance_week": "7.00",
            "total_this_period_swf": "43.00",
            "total_to_end_date_contact_hours": "400.00",
            "total_to_end_date_contact_days": "170",
            "total_to_end_date_teaching_weeks": "35",
        }
        document.summary_row.update(overrides)
        return document

    def test_documented_workload_overtime_is_not_flagged(self) -> None:
        document = self.make_document(total_this_period_swf="44.08")
        document.overtime_workload_hours = ".08"

        findings = collect_findings([document])
        self.assertEqual(findings, [])

    def test_undocumented_workload_overtime_is_flagged(self) -> None:
        document = self.make_document(total_this_period_swf="44.50")

        findings = collect_findings([document])
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "weekly_workload_overtime_documentation")

    def test_absolute_weekly_workload_max_is_flagged(self) -> None:
        document = self.make_document(total_this_period_swf="47.50")

        findings = collect_findings([document])
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "weekly_workload_absolute_max")

    def test_low_complementary_allowance_is_flagged(self) -> None:
        document = self.make_document(complementary_hours_allowance_week="6.00")
        document.period_end = "27-JUN-2026"

        findings = collect_findings([document])
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "minimum_complementary_allowance")

    def test_low_complementary_allowance_is_not_flagged_before_2026(self) -> None:
        document = self.make_document(complementary_hours_allowance_week="6.00")
        document.period_end = "27-JUN-2025"

        findings = collect_findings([document])
        self.assertEqual(findings, [])

    def test_annual_limits_are_flagged(self) -> None:
        document = self.make_document(
            total_to_end_date_contact_hours="700.00",
            total_to_end_date_contact_days="181",
            total_to_end_date_teaching_weeks="37",
        )

        findings = collect_findings([document])
        self.assertEqual({finding["rule_id"] for finding in findings}, {
            "annual_contact_days_max",
            "annual_teaching_hours_max",
            "annual_teaching_weeks_max",
        })


if __name__ == "__main__":
    unittest.main()
