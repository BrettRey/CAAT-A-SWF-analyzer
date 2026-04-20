from __future__ import annotations

import re
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from tempfile import TemporaryDirectory

try:
    from PIL import Image
except ImportError:  # pragma: no cover - Pillow is optional at import time.
    Image = None

from .models import ExtractionResult


BLANK_LINE_PATTERN = re.compile(r"\n{3,}")
TIMESTAMP_HEADER_PATTERN = re.compile(
    r"^\d{1,2}/\d{1,2}/\d{2},.+Standard Workload Form \(SWF\)$"
)
PDF_TEXT_QUALITY_KEYWORDS = (
    "standard workload form",
    "teacher name",
    "id:",
    "status:",
    "group:",
    "period covered by swf",
    "course/subject identification",
    "weekly totals",
    "summary of weekly total",
    "assigned teaching contact hours/week",
    "preparation hours/week",
    "evaluation feedback hours/week",
    "complementary hours",
    "total this period swf",
    "number of different course preparations",
    "complementary functions for academic year",
    "activity detail",
    "attributed hours",
)


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"Required external command `{command[0]}` is not available on PATH."
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else ""
        details = f": {stderr}" if stderr else ""
        raise RuntimeError(
            f"External command `{command[0]}` failed{details}"
        ) from exc


def extract_text(path: Path, force_ocr: bool = False, min_chars_per_page: int = 250) -> ExtractionResult:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf_text(path, force_ocr=force_ocr, min_chars_per_page=min_chars_per_page)
    if suffix in {".html", ".htm"}:
        return extract_html_text(path)
    if suffix in {".md", ".txt"}:
        return extract_plain_text(path)

    raise ValueError(f"Unsupported file type: {path.suffix}")


def extract_plain_text(path: Path) -> ExtractionResult:
    text = normalize_extracted_text(path.read_text(encoding="utf-8", errors="replace"))
    return ExtractionResult(
        source_path=path,
        source_type="text",
        method="plain_text",
        text=text,
    )


def extract_pdf_text(path: Path, force_ocr: bool = False, min_chars_per_page: int = 250) -> ExtractionResult:
    page_count = get_pdf_page_count(path)
    text_result = run_command(["pdftotext", "-layout", "-nopgbrk", str(path), "-"])
    extracted_text = normalize_pdf_text(text_result.stdout)
    method = "pdftotext"
    text_quality = score_pdf_text(extracted_text)

    if force_ocr or is_sparse_text(extracted_text, page_count, min_chars_per_page) or is_low_quality_pdf_text(extracted_text):
        ocr_text = normalize_extracted_text(extract_pdf_ocr_text(path))
        ocr_quality = score_pdf_text(ocr_text)
        if force_ocr or ocr_quality > text_quality or (
            ocr_quality == text_quality
            and len(strip_for_density(ocr_text)) > len(strip_for_density(extracted_text))
        ):
            extracted_text = ocr_text
            method = "pdftoppm+tesseract"

    return ExtractionResult(
        source_path=path,
        source_type="pdf",
        method=method,
        text=extracted_text,
        metadata={"pages": str(page_count)},
    )


def get_pdf_page_count(path: Path) -> int:
    info = run_command(["pdfinfo", str(path)]).stdout
    for line in info.splitlines():
        if line.startswith("Pages:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except ValueError:
                break
    return 1


def extract_pdf_ocr_text(path: Path) -> str:
    with TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        prefix = temp_dir / "page"
        run_command(["pdftoppm", "-png", "-r", "300", str(path), str(prefix)])

        images = sorted(temp_dir.glob("page-*.png"))
        if not images:
            raise RuntimeError(f"OCR fallback failed to render pages for {path}")

        page_texts: list[str] = []
        for image in images:
            page_texts.append(extract_ocr_page_text(image, temp_dir))

    return "\n\n".join(page_texts)


def normalize_pdf_text(text: str) -> str:
    cleaned_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue
        if stripped.startswith("https://"):
            continue
        if TIMESTAMP_HEADER_PATTERN.match(stripped):
            continue
        cleaned_lines.append(line)

    return normalize_extracted_text("\n".join(cleaned_lines))


def normalize_extracted_text(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    normalized = "\n".join(lines).strip()
    return BLANK_LINE_PATTERN.sub("\n\n", normalized)


def strip_for_density(text: str) -> str:
    return re.sub(r"\s+", "", text)


def is_sparse_text(text: str, page_count: int, min_chars_per_page: int) -> bool:
    if not text.strip():
        return True
    return len(strip_for_density(text)) < max(page_count, 1) * min_chars_per_page


def count_quality_keywords(text: str) -> int:
    normalized = text.lower()
    return sum(1 for keyword in PDF_TEXT_QUALITY_KEYWORDS if keyword in normalized)


def count_suspicious_characters(text: str) -> int:
    return sum(1 for char in text if char not in "\n\r\t" and (ord(char) < 32 or ord(char) > 126))


def score_pdf_text(text: str) -> int:
    keyword_score = count_quality_keywords(text) * 200
    density_score = min(len(strip_for_density(text)), 2000) // 20
    suspicious_penalty = count_suspicious_characters(text) * 5
    return keyword_score + density_score - suspicious_penalty


def is_low_quality_pdf_text(text: str) -> bool:
    compact_length = max(len(strip_for_density(text)), 1)
    suspicious_ratio = count_suspicious_characters(text) / compact_length
    return count_quality_keywords(text) < 4 or suspicious_ratio > 0.02


def extract_ocr_page_text(image_path: Path, temp_dir: Path) -> str:
    default_text = run_ocr(image_path)
    best_text = default_text
    best_score = score_pdf_text(default_text)
    if best_score >= 400 or Image is None:
        return best_text

    with Image.open(image_path) as image:
        for angle in (90, 180, 270):
            rotated_path = temp_dir / f"{image_path.stem}-rot{angle}.png"
            image.rotate(angle, expand=True).save(rotated_path)
            rotated_text = run_ocr(rotated_path)
            rotated_score = score_pdf_text(rotated_text)
            if rotated_score > best_score or (
                rotated_score == best_score
                and len(strip_for_density(rotated_text)) > len(strip_for_density(best_text))
            ):
                best_text = rotated_text
                best_score = rotated_score

    return best_text


def run_ocr(image_path: Path) -> str:
    ocr_result = run_command(["tesseract", str(image_path), "stdout", "--psm", "6"])
    return normalize_extracted_text(ocr_result.stdout)


class SWFHTMLParser(HTMLParser):
    BLOCK_TAGS = {"div", "p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "title"}
    SKIP_TAGS = {"script", "style"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self.text_buffer: list[str] = []
        self.current_row: list[str] = []
        self.current_cell: list[str] = []
        self.in_table = 0
        self.in_cell = False
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return

        if tag == "table":
            self.flush_text_buffer()
            self.in_table += 1
            return
        if tag == "tr" and self.in_table:
            self.flush_text_buffer()
            self.current_row = []
            return
        if tag in {"td", "th"} and self.in_table:
            self.in_cell = True
            self.current_cell = []
            return
        if tag == "br":
            self.append_text("\n")
            return
        if tag in self.BLOCK_TAGS and not self.in_table:
            self.flush_text_buffer()

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP_TAGS:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if self.skip_depth:
            return

        if tag in {"td", "th"} and self.in_table and self.in_cell:
            cell = normalize_html_inline("".join(self.current_cell))
            self.current_row.append(cell)
            self.current_cell = []
            self.in_cell = False
            return
        if tag == "tr" and self.in_table:
            row = " | ".join(cell for cell in self.current_row if cell)
            if row:
                self.blocks.append(row)
            self.current_row = []
            return
        if tag == "table" and self.in_table:
            if self.current_row:
                row = " | ".join(cell for cell in self.current_row if cell)
                if row:
                    self.blocks.append(row)
                self.current_row = []
            self.in_table -= 1
            self.blocks.append("")
            return
        if tag in self.BLOCK_TAGS and not self.in_table:
            self.flush_text_buffer()

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        self.append_text(data)

    def append_text(self, data: str) -> None:
        target = self.current_cell if self.in_cell else self.text_buffer
        target.append(data)

    def flush_text_buffer(self) -> None:
        block = normalize_html_block("".join(self.text_buffer))
        if block:
            self.blocks.extend(block.splitlines())
        self.text_buffer = []

    def rendered_text(self) -> str:
        self.flush_text_buffer()
        return normalize_extracted_text("\n".join(self.blocks))


def normalize_html_inline(value: str) -> str:
    pieces = []
    for part in value.splitlines():
        cleaned = re.sub(r"\s+", " ", part).replace("\xa0", " ").strip()
        if cleaned:
            pieces.append(cleaned)
    return " / ".join(pieces)


def normalize_html_block(value: str) -> str:
    lines = []
    for part in value.splitlines():
        cleaned = re.sub(r"\s+", " ", part).replace("\xa0", " ").strip()
        if cleaned:
            lines.append(cleaned)
    return "\n".join(lines)


def extract_html_text(path: Path) -> ExtractionResult:
    parser = SWFHTMLParser()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    parser.close()
    return ExtractionResult(
        source_path=path,
        source_type="html",
        method="html.parser",
        text=parser.rendered_text(),
    )
