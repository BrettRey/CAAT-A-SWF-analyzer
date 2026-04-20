from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swf_anonymizer.models import StructuredDocument
from swf_anonymizer.prep_type_checker import collect_findings


class PrepTypeCheckerTests(unittest.TestCase):
    def test_valid_prep_type_row_is_not_flagged(self) -> None:
        document = StructuredDocument(
            document_id="swf_fac001_example",
            faculty_token="FAC001",
            source_type="pdf",
            extraction_method="pdftotext",
            course_rows=[
                {
                    "course_code": "WRIT 100",
                    "course_name": "College Writing",
                    "delivery_type": "EB",
                    "prep_factor": ".60",
                    "contact_hours": "3.00",
                    "prep_attended_hours": "1.80",
                }
            ],
        )

        findings = collect_findings([document])
        self.assertEqual(findings, [])

    def test_mismatched_factor_suggests_likely_type(self) -> None:
        document = StructuredDocument(
            document_id="swf_fac002_example",
            faculty_token="FAC002",
            source_type="pdf",
            extraction_method="pdftotext",
            course_rows=[
                {
                    "course_code": "WRIT 100",
                    "course_name": "College Writing",
                    "delivery_type": "RB",
                    "prep_factor": ".60",
                    "contact_hours": "3.00",
                    "prep_attended_hours": "1.80",
                }
            ],
        )

        findings = collect_findings([document])
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0]["rule_id"], "prep_type_factor_mismatch")
        self.assertEqual(findings[0]["suggested_type"], "EB")
        self.assertEqual(findings[1]["rule_id"], "prep_type_hours_mismatch")
        self.assertEqual(findings[1]["suggested_type"], "EB")


if __name__ == "__main__":
    unittest.main()
