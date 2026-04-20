from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swf_anonymizer.structured import parse_structured_document


class StructuredParserTests(unittest.TestCase):
    def test_parses_pipe_table_course_and_complementary_rows(self) -> None:
        text = "\n".join(
            [
                "No. 1 | STANDARD WORKLOAD FORM (1 of 1) | Date: 27-MAR-2026",
                "Period covered by SWF From: 09-MAR-2026 To: 26-APR-2026",
                "Course/Subject Identification | Preparation | Evaluation Feedback | Complement",
                "Course / Number | CRN | Sec | Course Name | Cntct / Hours | In / st | Type | Fac- / tor | Att'd / Hours | Add'l / Hours | Class / Size | Type | Fac- / tor | Per- / cent | Att'd / Hours | Add'l / Hours | Allow | Assgn",
                "References to Collective / Agreement | 11.01 (B,C) | 11.01 (D) | 11.01 (E) | 11.01 (F) | 11.01 D,F,G",
                "EAPA 107 Classroom Instruction/Online | Comm & Academic Strategies 7 | 6.00 | EN | EB | .60 | 3.60 | .00 | 30 | E | .035 | 100.00 | 6.30 | .00 | .00 | .00",
                "Weekly Totals | 6.00 | 3.60 | .00 | 6.30 | .00 | 7.00 | 20.00",
                "",
                "Summary of Weekly Total | Hours",
                "Assigned Teaching Contact Hours/week | 6.00",
                "Preparation Hours/week | 3.60",
                "Evaluation Feedback Hours/week | 6.30",
                "Complementary Hours (allowance)/week | 7.00",
                "Complementary Hours (assigned)/week | 20.00",
                "Total this period SWF | 42.90",
                "Accumulated Totals To / SWF Period End Date | Teaching / Contact Hrs | Contact / Days | Teaching / Weeks",
                "Balance from previous SWF | 168.00 | 102 | 21",
                "Total this SWF | 42.00 | 35 | 7",
                "Total to end date | 210.00 | 137 | 28",
                "Number of different course preparations: / Number of different sections: / Number of language of instructions: | 1 / 1 / 1",
                "",
                "Complementary Functions for Academic Year",
                "Description | Activity Detail | Attributed Hours",
                "Minimum Complementary Hours (Allowance) | 7.00",
                "Curriculum Development (Assigned) | EAP Levels 1-4 | 20.00",
            ]
        )

        document = parse_structured_document(
            text=text,
            document_id="swf_fac001_2026-03-09_to_2026-04-26_issued_2026-03-27",
            faculty_token="FAC001",
            source_type="html",
            extraction_method="html.parser",
        )

        self.assertEqual(len(document.course_rows), 1)
        self.assertEqual(document.course_rows[0]["course_code"], "EAPA 107")
        self.assertEqual(document.course_rows[0]["course_name"], "Comm & Academic Strategies 7")
        self.assertEqual(document.course_rows[0]["contact_hours"], "6.00")
        self.assertEqual(document.summary_row["number_of_sections"], "1")
        self.assertEqual(len(document.complementary_rows), 2)
        self.assertEqual(document.complementary_rows[1]["activity_detail"], "EAP Levels 1-4")

    def test_parses_fixed_width_pdf_course_rows(self) -> None:
        text = "\n".join(
            [
                "No. 1                                                                 STANDARD WORKLOAD FORM (1 of 1)                                                                    Date: 16-MAR-2026",
                "  Period covered by SWF From: 11-MAY-2026 To: 27-JUN-2026",
                "  References to Collective                          11.01                                                                                                                      11.01 11.01",
                "                                                                       11.01 (D)                                                  11.01 (E)",
                "  Agreement                                         (B,C)                                                                                                                       (F) D,F,G",
                "  EAPA 107                  Comm &",
                "  Classroom                 Academic                  6.00 EN EB       .60       3.60   .00      25   E    .035 100.00                                            5.25      .00        .00     .00",
                "  Instruction/Online        Strategies 7",
                "  Weekly Totals                                      12.00                       5.70   .00                                                                      10.50      .00       7.00   8.00",
                "",
                "      Assigned Teaching Contact Hours/week                    12.00",
                "      Preparation Hours/week                                   5.70",
                "      Evaluation Feedback Hours/week                          10.50",
                "      Complementary Hours (allowance)/week                     7.00",
                "      Complementary Hours (assigned)/week                      8.00",
                "      Total this period SWF                                   43.20",
                "  Balance from previous SWF                                 210.00          137                      28",
                "  Total this SWF                                             84.00            34                      7",
                "  Total to end date                                         294.00          171                      35",
                "  Number of different course preparations:                     1",
                "  Number of different sections:                                2",
                "  Number of language of instructions:                          1",
                "                    Description                                           Activity Detail                          Attributed Hours",
                "  Curriculum Development (Assigned)             COSSID updates/curriculum revisions for assigned courses                       3.00",
            ]
        )

        document = parse_structured_document(
            text=text,
            document_id="swf_fac001_2026-05-11_to_2026-06-27_issued_2026-03-16",
            faculty_token="FAC001",
            source_type="pdf",
            extraction_method="pdftotext",
        )

        self.assertEqual(len(document.course_rows), 1)
        self.assertEqual(
            document.course_rows[0]["course_identifier"],
            "EAPA 107 Classroom Instruction/Online",
        )
        self.assertEqual(document.course_rows[0]["course_code"], "EAPA 107")
        self.assertEqual(document.course_rows[0]["course_component"], "Classroom Instruction/Online")
        self.assertEqual(document.course_rows[0]["eval_attended_hours"], "5.25")
        self.assertEqual(document.summary_row["number_of_sections"], "2")
        self.assertEqual(len(document.complementary_rows), 1)

    def test_parses_wrapped_fixed_width_rows_with_letter_digit_course_codes(self) -> None:
        text = "\n".join(
            [
                "No. 1                                                                 STANDARD WORKLOAD FORM (1 of 1)                                                                      Date: 23-MAR-2026",
                "  Period covered by SWF From: 11-MAY-2026 To: 26-JUN-2026",
                "  References to Collective                       11.01                                                                                                                            11.01 11.01",
                "                                                                       11.01 (D)                                                 11.01 (E)",
                "  Agreement                                      (B,C)                                                                                                                             (F) D,F,G",
                "  ACEC A10                  ACE Skl",
                "  Classroom                 Success                   4.00 EN EB       .60     2.40    .00      35   E    .035 100.00                                                4.90     .00        .00     .00",
                "  Instruction/Online        Advising Sem",
                "  Weekly Totals                                       8.00                     3.80    .00                                                                           9.80     .00       7.00 13.00",
                "      Assigned Teaching Contact Hours/week                     8.00",
                "      Preparation Hours/week                                   3.80",
                "      Evaluation Feedback Hours/week                           9.80",
                "      Complementary Hours (allowance)/week                     7.00",
                "      Complementary Hours (assigned)/week                     13.00",
                "      Total this period SWF                                   41.60",
                "  Balance from previous SWF                                    378.00           137                     28",
                "  Total this SWF                                                56.00             34                     7",
                "  Total to end date                                            434.00           171                     35",
                "  Number of different course preparations:                        1",
                "  Number of different sections:                                   2",
                "  Number of language of instructions:                             1",
            ]
        )

        document = parse_structured_document(
            text=text,
            document_id="swf_fac007_2026-05-11_to_2026-06-26_issued_2026-03-23",
            faculty_token="FAC007",
            source_type="pdf",
            extraction_method="pdftotext",
        )

        self.assertEqual(len(document.course_rows), 1)
        self.assertEqual(document.course_rows[0]["course_code"], "ACEC A10")
        self.assertEqual(document.course_rows[0]["course_component"], "Classroom Instruction/Online")
        self.assertEqual(document.course_rows[0]["course_name"], "ACE Skl Success Advising Sem")

    def test_parses_wrapped_fixed_width_rows_when_metrics_start_inside_name_column(self) -> None:
        text = "\n".join(
            [
                "No. 1                                                                 STANDARD WORKLOAD FORM (1 of 1)                                                                    Date: 15-MAR-2026",
                "  Period covered by SWF From: 11-MAY-2026 To: 27-JUN-2026",
                "  References to Collective                      11.01                                                                                                                      11.01 11.01",
                "                                                                 11.01 (D)                                                   11.01 (E)",
                "  Agreement                                     (B,C)                                                                                                                       (F) D,F,G",
                "  GCHM 100",
                "  Classroom               Chemistry               3.00 EN EB      .60      1.80   .00      40   E      .035 70.00 R      .015 30.00                           3.48       .00        .00     .00",
                "  Instruction",
                "  Weekly Totals                                   3.00                     1.80   .00                                                                         3.48       .00       7.00 10.00",
                "      Assigned Teaching Contact Hours/week                 3.00",
                "      Preparation Hours/week                               1.80",
                "      Evaluation Feedback Hours/week                       3.48",
                "      Complementary Hours (allowance)/week                 7.00",
                "      Complementary Hours (assigned)/week                 10.00",
                "      Total this period SWF                               25.28",
                "  Balance from previous SWF                                 336.00          137                      28",
                "  Total this SWF                                             21.00            34                      7",
                "  Total to end date                                         357.00          171                      35",
                "  Number of different course preparations:                     1",
                "  Number of different sections:                                1",
                "  Number of language of instructions:                          1",
            ]
        )

        document = parse_structured_document(
            text=text,
            document_id="swf_fac006_2026-05-11_to_2026-06-27_issued_2026-03-15",
            faculty_token="FAC006",
            source_type="pdf",
            extraction_method="pdftotext",
        )

        self.assertEqual(len(document.course_rows), 1)
        self.assertEqual(document.course_rows[0]["course_code"], "GCHM 100")
        self.assertEqual(document.course_rows[0]["course_component"], "Classroom Instruction")
        self.assertEqual(document.course_rows[0]["course_name"], "Chemistry")
        self.assertEqual(document.course_rows[0]["contact_hours"], "3.00")
        self.assertEqual(document.course_rows[0]["instruction_language"], "EN")
        self.assertEqual(document.course_rows[0]["delivery_type"], "EB")
        self.assertEqual(document.course_rows[0]["prep_factor"], ".60")
        self.assertEqual(document.course_rows[0]["eval1_type"], "E")
        self.assertEqual(document.course_rows[0]["eval2_type"], "R")
        self.assertEqual(document.course_rows[0]["eval2_percent"], "30.00")


if __name__ == "__main__":
    unittest.main()
