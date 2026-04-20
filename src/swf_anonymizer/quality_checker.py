from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from .models import StructuredDocument


CHECK_FIELDS = [
    "source_group",
    "faculty_token",
    "stable_faculty_id",
    "document_id",
    "severity",
    "rule_id",
    "message",
    "missing_fields",
]

IMPORTANT_SUMMARY_FIELDS = [
    "assigned_teaching_contact_hours_week",
    "preparation_hours_week",
    "evaluation_feedback_hours_week",
    "complementary_hours_allowance_week",
    "total_this_period_swf",
    "total_to_end_date_contact_hours",
    "total_to_end_date_contact_days",
    "total_to_end_date_teaching_weeks",
]


def write_quality_reports(documents: list[StructuredDocument], output_root: Path) -> dict[str, Path]:
    findings = collect_findings(documents)

    report_dir = output_root / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    csv_path = report_dir / "quality_findings.csv"
    md_path = report_dir / "quality_findings.md"

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CHECK_FIELDS)
        writer.writeheader()
        writer.writerows(findings)

    md_path.write_text(render_markdown(findings, documents), encoding="utf-8")
    return {"csv": csv_path, "markdown": md_path}


def collect_findings(documents: list[StructuredDocument]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for document in documents:
        findings.extend(evaluate_document(document))
    return findings


def evaluate_document(document: StructuredDocument) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []

    if not document.faculty_token:
        findings.append(
            make_finding(
                document=document,
                severity="high",
                rule_id="missing_faculty_token",
                message="No faculty token could be assigned from the SWF text.",
            )
        )

    if not document.stable_faculty_id:
        findings.append(
            make_finding(
                document=document,
                severity="high",
                rule_id="missing_stable_faculty_id",
                message="No stable faculty ID could be assigned from the current state and SWF text.",
            )
        )

    missing_date_fields = [
        field_name
        for field_name, value in (
            ("period_start", document.period_start),
            ("period_end", document.period_end),
            ("issued_date", document.issued_date),
        )
        if not value
    ]
    if missing_date_fields:
        findings.append(
            make_finding(
                document=document,
                severity="review",
                rule_id="missing_dates",
                message="One or more SWF date fields could not be parsed.",
                missing_fields="; ".join(missing_date_fields),
            )
        )

    if document.period_start and document.period_end:
        parsed_start = parse_swf_date(document.period_start)
        parsed_end = parse_swf_date(document.period_end)
        if parsed_start and parsed_end and parsed_end < parsed_start:
            findings.append(
                make_finding(
                    document=document,
                    severity="review",
                    rule_id="period_date_order",
                    message="The SWF period end date is earlier than the start date.",
                )
            )
        elif parsed_start and parsed_end and parsed_end.year - parsed_start.year > 1:
            findings.append(
                make_finding(
                    document=document,
                    severity="review",
                    rule_id="period_date_span",
                    message="The SWF period spans more than one calendar year and should be checked.",
                )
            )

    if not document.summary_row:
        findings.append(
            make_finding(
                document=document,
                severity="review",
                rule_id="missing_summary_row",
                message="The summary section could not be parsed from this SWF.",
            )
        )
    else:
        missing_summary_fields = [
            field for field in IMPORTANT_SUMMARY_FIELDS if not document.summary_row.get(field, "").strip()
        ]
        if missing_summary_fields:
            findings.append(
                make_finding(
                    document=document,
                    severity="review",
                    rule_id="incomplete_summary_row",
                    message="The SWF summary is missing one or more key workload fields.",
                    missing_fields="; ".join(missing_summary_fields),
                )
            )

    return findings


def render_markdown(findings: list[dict[str, str]], documents: list[StructuredDocument]) -> str:
    lines = ["# Quality Findings", ""]
    lines.append(f"Documents checked: {len(documents)}")
    lines.append(f"Findings: {len(findings)}")
    lines.append("")

    if not findings:
        lines.append("No parsing-quality findings were detected by the current checks.")
        return "\n".join(lines) + "\n"

    counts = count_by_key(findings, "rule_id")
    lines.append("## Summary")
    for rule_id in sorted(counts):
        lines.append(f"- `{rule_id}`: {counts[rule_id]}")
    lines.append("")

    lines.append("## Findings")
    for finding in findings:
        detail = f" ({finding['missing_fields']})" if finding["missing_fields"] else ""
        lines.append(
            f"- `{finding['severity']}` {finding['faculty_token'] or 'unassigned'} {finding['rule_id']}: "
            f"{finding['message']}{detail}"
        )

    return "\n".join(lines) + "\n"


def make_finding(
    document: StructuredDocument,
    severity: str,
    rule_id: str,
    message: str,
    missing_fields: str = "",
) -> dict[str, str]:
    return {
        "source_group": document.source_group,
        "faculty_token": document.faculty_token,
        "stable_faculty_id": document.stable_faculty_id,
        "document_id": document.document_id,
        "severity": severity,
        "rule_id": rule_id,
        "message": message,
        "missing_fields": missing_fields,
    }


def count_by_key(rows: list[dict[str, str]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row[key]] = counts.get(row[key], 0) + 1
    return counts


def parse_swf_date(raw_value: str) -> datetime | None:
    cleaned = raw_value.strip()
    if not cleaned:
        return None
    try:
        return datetime.strptime(cleaned.title(), "%d-%b-%Y")
    except ValueError:
        return None
