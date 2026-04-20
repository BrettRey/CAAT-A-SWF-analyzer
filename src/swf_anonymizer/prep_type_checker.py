from __future__ import annotations

import csv
from pathlib import Path

from .models import StructuredDocument


PREP_TYPE_FACTORS = {
    "NW": 1.10,
    "EA": 0.85,
    "EB": 0.60,
    "RA": 0.45,
    "RB": 0.35,
}

CHECK_FIELDS = [
    "source_group",
    "faculty_token",
    "stable_faculty_id",
    "document_id",
    "course_code",
    "course_name",
    "severity",
    "rule_id",
    "message",
    "delivery_type",
    "prep_factor",
    "expected_factor",
    "suggested_type",
    "contact_hours",
    "prep_attended_hours",
    "expected_prep_attended_hours",
]


def write_prep_type_reports(documents: list[StructuredDocument], output_root: Path) -> dict[str, Path]:
    findings = collect_findings(documents)

    report_dir = output_root / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    csv_path = report_dir / "prep_type_findings.csv"
    md_path = report_dir / "prep_type_findings.md"

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CHECK_FIELDS)
        writer.writeheader()
        writer.writerows(findings)

    md_path.write_text(render_markdown(findings, documents), encoding="utf-8")
    return {"csv": csv_path, "markdown": md_path}


def collect_findings(documents: list[StructuredDocument]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for document in documents:
        for row in document.course_rows:
            findings.extend(evaluate_course_row(document, row))
    return findings


def evaluate_course_row(document: StructuredDocument, row: dict[str, str]) -> list[dict[str, str]]:
    delivery_type = row.get("delivery_type", "").strip().upper()
    prep_factor = parse_float(row.get("prep_factor"))
    contact_hours = parse_float(row.get("contact_hours"))
    prep_attended_hours = parse_float(row.get("prep_attended_hours"))
    expected_factor = PREP_TYPE_FACTORS.get(delivery_type)
    findings: list[dict[str, str]] = []

    if not any(row.get(field, "").strip() for field in ("delivery_type", "prep_factor", "prep_attended_hours")):
        return findings

    if delivery_type and expected_factor is None:
        findings.append(
            make_finding(
                document=document,
                row=row,
                rule_id="invalid_prep_type_code",
                message=f"Preparation type `{delivery_type}` is not a recognized SWF prep code.",
                expected_factor="",
                suggested_type="",
                expected_prep_attended_hours="",
            )
        )
        return findings

    if expected_factor is None:
        return findings

    suggested_type = infer_type_from_factor(prep_factor)
    expected_prep_hours = (
        round(contact_hours * expected_factor, 2)
        if contact_hours is not None
        else None
    )

    if prep_factor is not None and abs(prep_factor - expected_factor) > 0.02:
        if suggested_type and suggested_type != delivery_type:
            message = (
                f"Preparation type `{delivery_type}` normally uses factor `{format_number(expected_factor)}`, "
                f"but this row uses `{format_number(prep_factor)}`, which matches `{suggested_type}`."
            )
        else:
            message = (
                f"Preparation type `{delivery_type}` normally uses factor `{format_number(expected_factor)}`, "
                f"but this row uses `{format_number(prep_factor)}`."
            )
        findings.append(
            make_finding(
                document=document,
                row=row,
                rule_id="prep_type_factor_mismatch",
                message=message,
                expected_factor=format_number(expected_factor),
                suggested_type=suggested_type if suggested_type and suggested_type != delivery_type else "",
                expected_prep_attended_hours=format_number(expected_prep_hours) if expected_prep_hours is not None else "",
            )
        )

    if (
        contact_hours is not None
        and prep_attended_hours is not None
        and expected_prep_hours is not None
        and abs(prep_attended_hours - expected_prep_hours) > 0.05
    ):
        inferred_factor = prep_attended_hours / contact_hours if contact_hours else None
        implied_type = infer_type_from_factor(inferred_factor)
        if implied_type and implied_type != delivery_type:
            message = (
                f"Preparation hours `{format_number(prep_attended_hours)}` do not align with prep type `{delivery_type}`; "
                f"for `{format_number(contact_hours)}` contact hours they imply `{implied_type}` instead."
            )
        else:
            message = (
                f"Preparation hours `{format_number(prep_attended_hours)}` do not match `{format_number(contact_hours)}` "
                f"contact hours at prep type `{delivery_type}`."
            )
        findings.append(
            make_finding(
                document=document,
                row=row,
                rule_id="prep_type_hours_mismatch",
                message=message,
                expected_factor=format_number(expected_factor),
                suggested_type=implied_type if implied_type and implied_type != delivery_type else "",
                expected_prep_attended_hours=format_number(expected_prep_hours),
            )
        )

    return findings


def render_markdown(findings: list[dict[str, str]], documents: list[StructuredDocument]) -> str:
    lines = ["# Prep Type Findings", ""]
    lines.append(f"Documents checked: {len(documents)}")
    lines.append(f"Findings: {len(findings)}")
    lines.append("")

    if not findings:
        lines.append("No preparation type anomalies were detected from the currently parsed course rows.")
        return "\n".join(lines) + "\n"

    lines.append("## Findings")
    for finding in findings:
        lines.append(
            f"- `{finding['faculty_token']}` {finding['course_code']}: {finding['message']} "
            f"(type `{finding['delivery_type']}`, factor `{finding['prep_factor']}`, expected `{finding['expected_factor']}`)"
        )

    return "\n".join(lines) + "\n"


def make_finding(
    document: StructuredDocument,
    row: dict[str, str],
    rule_id: str,
    message: str,
    expected_factor: str,
    suggested_type: str,
    expected_prep_attended_hours: str,
) -> dict[str, str]:
    return {
        "source_group": document.source_group,
        "faculty_token": document.faculty_token,
        "stable_faculty_id": document.stable_faculty_id,
        "document_id": document.document_id,
        "course_code": row.get("course_code", ""),
        "course_name": row.get("course_name", ""),
        "severity": "review",
        "rule_id": rule_id,
        "message": message,
        "delivery_type": row.get("delivery_type", ""),
        "prep_factor": row.get("prep_factor", ""),
        "expected_factor": expected_factor,
        "suggested_type": suggested_type,
        "contact_hours": row.get("contact_hours", ""),
        "prep_attended_hours": row.get("prep_attended_hours", ""),
        "expected_prep_attended_hours": expected_prep_attended_hours,
    }


def infer_type_from_factor(value: float | None) -> str:
    if value is None:
        return ""
    for prep_type, factor in PREP_TYPE_FACTORS.items():
        if abs(value - factor) <= 0.02:
            return prep_type
    return ""


def parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def format_number(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".") if value % 1 else f"{value:.0f}"
