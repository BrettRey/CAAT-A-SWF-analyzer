from __future__ import annotations

import re

from .models import StructuredDocument


COURSE_TABLE_HEADER_PATTERN = re.compile(r"Course(?: / Number)?")
COURSE_CODE_PATTERN = re.compile(r"^(?P<code>[A-Z]{2,}\s+[A-Z]?\d{2,4}[A-Z]?)\s*(?P<rest>.*)$")
DATE_PATTERN = r"\d{2}-[A-Z]{3}-\d{4}"
PDF_METRICS_START_PATTERN = re.compile(
    r"(?<!\S)(?P<contact>\d+\.\d{2})\s+(?P<language>[A-Z]{2})\s+(?P<prep_type>[A-Z]{1,2})\s+(?P<prep_factor>\.\d+|\d+\.\d+)"
)
PERIOD_PATTERN = re.compile(
    rf"Period covered by SWF From:\s*(?P<start>{DATE_PATTERN})\s*To:\s*(?P<end>{DATE_PATTERN})"
)
ISSUED_DATE_PATTERN = re.compile(rf"\bDate:\s*(?P<date>{DATE_PATTERN})\b")
NUMBER_PATTERN = r"-?\d+(?:\.\d+)?"
OVERTIME_WORKLOAD_PATTERN = re.compile(
    r"I hereby agree one \(1\) Teaching Contact Hour or\s*(?P<hours>\.\d+|\d+(?:\.\d+)?)\s*Workload"
)

SUMMARY_FIELDS = {
    "Assigned Teaching Contact Hours/week": "assigned_teaching_contact_hours_week",
    "Preparation Hours/week": "preparation_hours_week",
    "Evaluation Feedback Hours/week": "evaluation_feedback_hours_week",
    "Complementary Hours (allowance)/week": "complementary_hours_allowance_week",
    "Complementary Hours (assigned)/week": "complementary_hours_assigned_week",
    "Total this period SWF": "total_this_period_swf",
}

ACCUMULATED_FIELDS = {
    "Balance from previous SWF": "balance_from_previous_swf",
    "Total this SWF": "total_this_swf",
    "Total to end date": "total_to_end_date",
}

PDF_LEFT_COLUMN_END = 26
PDF_TEXT_END = 54


def parse_structured_document(
    text: str,
    document_id: str,
    faculty_token: str | None,
    source_type: str,
    extraction_method: str,
    stable_faculty_id: str | None = None,
    source_group: str = "",
) -> StructuredDocument:
    period_match = PERIOD_PATTERN.search(text)
    issued_match = ISSUED_DATE_PATTERN.search(text)

    document = StructuredDocument(
        document_id=document_id,
        faculty_token=faculty_token or "",
        source_type=source_type,
        extraction_method=extraction_method,
        stable_faculty_id=stable_faculty_id or faculty_token or "",
        source_group=source_group,
        period_start=period_match.group("start") if period_match else "",
        period_end=period_match.group("end") if period_match else "",
        issued_date=issued_match.group("date") if issued_match else "",
        program_group=parse_program_group(text),
        probationary_status=parse_probationary_status(text),
        employment_status=parse_employment_status(text),
        category=parse_category(text),
        overtime_workload_hours=parse_overtime_workload_hours(text),
    )

    if has_pipe_tables(text):
        document.course_rows = parse_pipe_course_rows(text, document)
        document.complementary_rows = parse_pipe_complementary_rows(text, document)
    else:
        document.course_rows = parse_fixed_width_course_rows(text, document)
        document.complementary_rows = parse_fixed_width_complementary_rows(text, document)

    document.summary_row = parse_summary_row(text, document)
    return document


def has_pipe_tables(text: str) -> bool:
    return " | " in text and "Course/Subject Identification |" in text or "Course / Number |" in text


def parse_pipe_course_rows(text: str, document: StructuredDocument) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    in_table = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if in_table:
                break
            continue

        if line.startswith("Course / Number |"):
            in_table = True
            continue
        if not in_table:
            continue
        if line.startswith("References to Collective"):
            continue
        if line.startswith("Weekly Totals"):
            break
        if "|" not in line:
            continue

        cells = [normalize_space(cell) for cell in line.split("|")]
        row = build_course_row(cells[0], cells[1] if len(cells) > 1 else "", cells[2:], document)
        rows.append(row)

    return rows


def parse_fixed_width_course_rows(text: str, document: StructuredDocument) -> list[dict[str, str]]:
    lines = text.splitlines()
    blocks: list[list[str]] = []
    in_table = False
    current: list[str] = []

    for raw_line in lines:
        line = raw_line.rstrip("\n")
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("Agreement"):
            in_table = True
            current = []
            continue
        if not in_table:
            continue
        if stripped.startswith("Weekly Totals"):
            if current:
                blocks.append(current)
            break
        if is_pdf_course_start(line) and current:
            blocks.append(current)
            current = [line]
            continue
        current.append(line)

    rows: list[dict[str, str]] = []
    for block in blocks:
        course_identifier, course_name, metrics = split_pdf_course_block(block)
        if course_identifier or course_name or metrics:
            rows.append(build_course_row(course_identifier, course_name, metrics, document))

    return rows


def is_pdf_course_start(line: str) -> bool:
    return re.match(r"^\s*[A-Z]{2,}\s+[A-Z]?\d{2,4}[A-Z]?", line) is not None


def join_pdf_segments(lines: list[str], start: int, end: int) -> str:
    parts: list[str] = []
    for line in lines:
        segment = normalize_space(line[start:end].strip()) if len(line) > start else ""
        if segment:
            parts.append(segment)
    return " ".join(parts)


def split_pdf_course_block(block: list[str]) -> tuple[str, str, list[str]]:
    identifier_parts: list[str] = []
    name_parts: list[str] = []
    metrics: list[str] = []

    for line in block:
        left_segment = normalize_space(line[:PDF_LEFT_COLUMN_END].strip()) if line else ""
        if left_segment:
            identifier_parts.append(left_segment)

        metrics_match = PDF_METRICS_START_PATTERN.search(line)
        if metrics_match:
            name_end = metrics_match.start()
            if len(line) > PDF_LEFT_COLUMN_END:
                name_segment = normalize_space(line[PDF_LEFT_COLUMN_END:name_end].strip())
                if name_segment:
                    name_parts.append(name_segment)
            if not metrics:
                metrics = line[metrics_match.start() :].split()
            continue

        if len(line) > PDF_LEFT_COLUMN_END:
            name_segment = normalize_space(line[PDF_LEFT_COLUMN_END:].strip())
            if name_segment:
                name_parts.append(name_segment)

    if not metrics:
        metrics_line = next(
            (line[PDF_TEXT_END:] for line in block if len(line) > PDF_TEXT_END and line[PDF_TEXT_END:].strip()),
            "",
        )
        metrics = metrics_line.split()

    return " ".join(identifier_parts), " ".join(name_parts), metrics


def build_course_row(
    course_identifier: str,
    course_name: str,
    metrics: list[str],
    document: StructuredDocument,
) -> dict[str, str]:
    course_code, course_component = split_course_identifier(course_identifier)
    normalized_identifier = normalize_space(
        f"{course_code} {course_component}".strip() if course_code else course_identifier
    )

    row = base_row(document)
    row.update(
        {
            "course_identifier": normalized_identifier,
            "course_code": course_code,
            "course_component": course_component,
            "course_name": normalize_space(course_name),
            "contact_hours": "",
            "instruction_language": "",
            "delivery_type": "",
            "prep_factor": "",
            "prep_attended_hours": "",
            "prep_additional_hours": "",
            "class_size": "",
            "eval1_type": "",
            "eval1_factor": "",
            "eval1_percent": "",
            "eval2_type": "",
            "eval2_factor": "",
            "eval2_percent": "",
            "eval3_type": "",
            "eval3_factor": "",
            "eval3_percent": "",
            "eval_attended_hours": "",
            "eval_additional_hours": "",
            "complement_allowance_hours": "",
            "complement_assigned_hours": "",
        }
    )

    first_fields = [
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
    ]
    trailing_fields = [
        "eval_attended_hours",
        "eval_additional_hours",
        "complement_allowance_hours",
        "complement_assigned_hours",
    ]

    metrics = [normalize_space(value) for value in metrics if normalize_space(value)]
    for field, value in zip(first_fields, metrics[:10]):
        row[field] = value

    if len(metrics) >= 14:
        middle = metrics[10:-4]
        for field, value in zip(["eval2_type", "eval2_factor", "eval2_percent"], middle[:3]):
            row[field] = value
        for field, value in zip(["eval3_type", "eval3_factor", "eval3_percent"], middle[3:6]):
            row[field] = value
        for field, value in zip(trailing_fields, metrics[-4:]):
            row[field] = value

    return row


def split_course_identifier(value: str) -> tuple[str, str]:
    normalized = normalize_space(value)
    match = COURSE_CODE_PATTERN.match(normalized)
    if not match:
        return "", normalized
    rest = normalize_space(match.group("rest")).lstrip("/").strip()
    return match.group("code"), rest


def parse_pipe_complementary_rows(text: str, document: StructuredDocument) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    in_table = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if in_table:
                break
            continue

        if line == "Description | Activity Detail | Attributed Hours":
            in_table = True
            continue
        if not in_table:
            continue
        if line.startswith("Dates of discussion"):
            break
        if "|" not in line:
            continue

        cells = [normalize_space(cell) for cell in line.split("|")]
        hours = cells[-1] if cells else ""
        detail = cells[1] if len(cells) >= 3 else ""
        rows.append(
            {
                **base_row(document),
                "description": cells[0] if cells else "",
                "activity_detail": detail,
                "attributed_hours": hours,
            }
        )

    return rows


def parse_fixed_width_complementary_rows(text: str, document: StructuredDocument) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    in_table = False

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped.startswith("Description") and "Attributed Hours" in stripped:
            in_table = True
            continue
        if not in_table:
            continue
        if stripped.startswith("Dates of discussion"):
            break

        match = re.search(rf"(?P<hours>{NUMBER_PATTERN})$", stripped)
        if not match:
            continue
        hours = match.group("hours")
        body = stripped[: match.start()].rstrip()
        parts = re.split(r"\s{2,}", body, maxsplit=1)
        rows.append(
            {
                **base_row(document),
                "description": normalize_space(parts[0]),
                "activity_detail": normalize_space(parts[1]) if len(parts) > 1 else "",
                "attributed_hours": hours,
            }
        )

    return rows


def parse_summary_row(text: str, document: StructuredDocument) -> dict[str, str]:
    row = base_row(document)

    for label, field in SUMMARY_FIELDS.items():
        row[field] = find_single_value(text, label)

    counts = parse_count_fields(text)
    row.update(counts)

    for label, stem in ACCUMULATED_FIELDS.items():
        hours, days, weeks = find_triplet_values(text, label)
        row[f"{stem}_contact_hours"] = hours
        row[f"{stem}_contact_days"] = days
        row[f"{stem}_teaching_weeks"] = weeks

    return row


def parse_count_fields(text: str) -> dict[str, str]:
    combined_match = re.search(
        r"Number of different course preparations:.*?\|\s*(?P<preps>\d+)\s*/\s*(?P<sections>\d+)\s*/\s*(?P<langs>\d+)",
        text,
        flags=re.DOTALL,
    )
    if combined_match:
        return {
            "number_of_course_preparations": combined_match.group("preps"),
            "number_of_sections": combined_match.group("sections"),
            "number_of_instruction_languages": combined_match.group("langs"),
        }

    return {
        "number_of_course_preparations": find_single_value(
            text, "Number of different course preparations:"
        ),
        "number_of_sections": find_single_value(text, "Number of different sections:"),
        "number_of_instruction_languages": find_single_value(
            text, "Number of language of instructions:"
        ),
    }


def find_single_value(text: str, label: str) -> str:
    patterns = [
        re.compile(rf"{re.escape(label)}\s*\|\s*(?P<value>{NUMBER_PATTERN})"),
        re.compile(rf"{re.escape(label)}\s+(?P<value>{NUMBER_PATTERN})"),
    ]
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group("value")
    return ""


def find_triplet_values(text: str, label: str) -> tuple[str, str, str]:
    patterns = [
        re.compile(
            rf"{re.escape(label)}\s*\|\s*(?P<hours>{NUMBER_PATTERN})\s*\|\s*(?P<days>\d+)\s*\|\s*(?P<weeks>\d+)"
        ),
        re.compile(
            rf"{re.escape(label)}\s+(?P<hours>{NUMBER_PATTERN})\s+(?P<days>\d+)\s+(?P<weeks>\d+)"
        ),
    ]
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group("hours"), match.group("days"), match.group("weeks")
    return "", "", ""


def base_row(document: StructuredDocument) -> dict[str, str]:
    return {
        "document_id": document.document_id,
        "faculty_token": document.faculty_token,
        "stable_faculty_id": document.stable_faculty_id,
        "source_group": document.source_group,
        "source_type": document.source_type,
        "extraction_method": document.extraction_method,
        "period_start": document.period_start,
        "period_end": document.period_end,
        "issued_date": document.issued_date,
    }


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def parse_program_group(text: str) -> str:
    if "Post-secondary" in text:
        return "Post-secondary"
    match = re.search(r"Group:\s*(?P<group>[A-Za-z][A-Za-z -]+)", text)
    return normalize_space(match.group("group")) if match else ""


def parse_probationary_status(text: str) -> str:
    if "Non-Probationary" in text:
        return "Non-Probationary"
    if re.search(r"\bProbationary\b", text):
        return "Probationary"
    return ""


def parse_employment_status(text: str) -> str:
    if "Full Time" in text:
        return "Full Time"
    match = re.search(r"Status:\s*(?P<status>[A-Za-z ]+)", text)
    return normalize_space(match.group("status")) if match else ""


def parse_category(text: str) -> str:
    match = re.search(r"Category:\s*(?P<category>[A-Z]+)", text)
    return match.group("category") if match else ""


def parse_overtime_workload_hours(text: str) -> str:
    match = OVERTIME_WORKLOAD_PATTERN.search(text)
    return match.group("hours").lstrip("0") or "0" if match else ""
