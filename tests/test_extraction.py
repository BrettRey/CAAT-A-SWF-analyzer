from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swf_anonymizer.extraction import extract_html_text, extract_ocr_page_text, extract_pdf_text


class ExtractionTests(unittest.TestCase):
    def test_pdf_prefers_text_layer_when_dense_enough(self) -> None:
        dense_swf_text = "\n".join(
            [
                "No. 1 STANDARD WORKLOAD FORM (1 of 1) Date: 19-MAR-2026",
                "Teacher Name: Doe, Jane",
                "ID: N12345678",
                "Status: Full Time Group: Post-secondary",
                "Period covered by SWF From: 11-MAY-2026 To: 27-JUN-2026",
                "Course/Subject Identification",
                "Weekly Totals",
                "Summary of Weekly Total",
                "Assigned Teaching Contact Hours/week 6.00",
                "Preparation Hours/week 3.60",
                "Evaluation Feedback Hours/week 6.30",
                "Complementary Hours (assigned)/week 7.00",
                "Total this period SWF 42.90",
                "Number of different course preparations: 1",
                "Complementary Functions for Academic Year",
                "Activity Detail Attributed Hours",
                "A" * 600,
            ]
        )

        def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
            if command[0] == "pdfinfo":
                return subprocess.CompletedProcess(command, 0, stdout="Pages: 2\n", stderr="")
            if command[0] == "pdftotext":
                return subprocess.CompletedProcess(
                    command,
                    0,
                    stdout=dense_swf_text,
                    stderr="",
                )
            raise AssertionError(f"Unexpected command: {command}")

        with patch("swf_anonymizer.extraction.run_command", side_effect=fake_run):
            result = extract_pdf_text(Path("sample.pdf"))

        self.assertEqual(result.method, "pdftotext")
        self.assertIn("Teacher Name: Doe, Jane", result.text)

    def test_pdf_falls_back_to_ocr_when_text_is_sparse(self) -> None:
        with patch("swf_anonymizer.extraction.get_pdf_page_count", return_value=2), patch(
            "swf_anonymizer.extraction.run_command",
            return_value=subprocess.CompletedProcess(
                ["pdftotext"],
                0,
                stdout="Too short",
                stderr="",
            ),
        ), patch(
            "swf_anonymizer.extraction.extract_pdf_ocr_text",
            return_value="Teacher Name: Doe, Jane\nID: N12345678\n" + ("B" * 700),
        ):
            result = extract_pdf_text(Path("sample.pdf"))

        self.assertEqual(result.method, "pdftoppm+tesseract")
        self.assertIn("Teacher Name: Doe, Jane", result.text)

    def test_pdf_falls_back_to_ocr_when_text_layer_is_garbled(self) -> None:
        garbled_text = (
            "mnQonVXp" + ("ÿ" * 50) + "\n"
            "012 4 56708798 9 78 9 4 1 4\n"
            + ("A" * 600)
        )
        ocr_text = "\n".join(
            [
                "No. 1 STANDARD WORKLOAD FORM (1 of 1) Date: 19-MAR-2026",
                "Teacher Name: Doe, Jane",
                "ID: N12345678",
                "Status: Full Time Group: Post-secondary",
                "Period covered by SWF From: 11-MAY-2026 To: 27-JUN-2026",
                "Course/Subject Identification",
                "Weekly Totals",
                "Summary of Weekly Total",
                "Assigned Teaching Contact Hours/week 6.00",
                "Preparation Hours/week 3.60",
                "Evaluation Feedback Hours/week 6.30",
                "Complementary Hours (assigned)/week 7.00",
                "Total this period SWF 42.90",
                "Number of different course preparations: 1",
                "Complementary Functions for Academic Year",
                "Activity Detail Attributed Hours",
            ]
        )

        with patch("swf_anonymizer.extraction.get_pdf_page_count", return_value=2), patch(
            "swf_anonymizer.extraction.run_command",
            return_value=subprocess.CompletedProcess(
                ["pdftotext"],
                0,
                stdout=garbled_text,
                stderr="",
            ),
        ), patch(
            "swf_anonymizer.extraction.extract_pdf_ocr_text",
            return_value=ocr_text,
        ):
            result = extract_pdf_text(Path("sample.pdf"))

        self.assertEqual(result.method, "pdftoppm+tesseract")
        self.assertIn("Teacher Name: Doe, Jane", result.text)

    def test_ocr_retries_rotated_image_when_default_result_is_low_quality(self) -> None:
        class DummyRotatedImage:
            def __init__(self, angle: int) -> None:
                self.angle = angle

            def save(self, path: Path) -> None:
                return None

        class DummyImage:
            def __enter__(self) -> "DummyImage":
                return self

            def __exit__(self, exc_type, exc, traceback) -> None:
                return None

            def rotate(self, angle: int, expand: bool = True) -> DummyRotatedImage:
                return DummyRotatedImage(angle)

        good_ocr_text = "\n".join(
            [
                "No. 1 STANDARD WORKLOAD FORM (1 of 1) Date: 19-MAR-2026",
                "Teacher Name: Doe, Jane",
                "ID: N12345678",
                "Status: Full Time Group: Post-secondary",
                "Period covered by SWF From: 11-MAY-2026 To: 27-JUN-2026",
                "Summary of Weekly Total",
                "Assigned Teaching Contact Hours/week 6.00",
            ]
        )

        def fake_run_ocr(path: Path) -> str:
            if path.name == "page-1.png":
                return "sideways noise"
            if path.name == "page-1-rot270.png":
                return good_ocr_text
            return "still bad"

        with patch("swf_anonymizer.extraction.run_ocr", side_effect=fake_run_ocr), patch(
            "swf_anonymizer.extraction.Image"
        ) as mock_image:
            mock_image.open.return_value = DummyImage()
            result = extract_ocr_page_text(Path("page-1.png"), Path("/tmp"))

        self.assertEqual(result, good_ocr_text)

    def test_html_extractor_preserves_table_rows(self) -> None:
        html = """
        <html>
          <body>
            <table>
              <tr><th>Teacher Name:</th><td>Doe, Jane</td></tr>
              <tr><th>ID:</th><td>N12345678</td></tr>
            </table>
            <p>Period covered by SWF From: 01-JAN-2026 To: 01-FEB-2026</p>
          </body>
        </html>
        """
        with tempfile.TemporaryDirectory() as temp_dir_name:
            path = Path(temp_dir_name) / "sample.html"
            path.write_text(html, encoding="utf-8")
            result = extract_html_text(path)

        self.assertIn("Teacher Name: | Doe, Jane", result.text)
        self.assertIn("Period covered by SWF From: 01-JAN-2026 To: 01-FEB-2026", result.text)


if __name__ == "__main__":
    unittest.main()
