from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from .models import StructuredDocument


POST_SECONDARY_WEEKLY_WORKLOAD_MAX = 44.0
POST_SECONDARY_TEACHING_CONTACT_MAX = 18.0
POST_SECONDARY_TEACHING_CONTACT_OVERTIME_MAX = 19.0
POST_SECONDARY_ANNUAL_CONTACT_DAYS_MAX = 180
POST_SECONDARY_ANNUAL_TEACHING_HOURS_MAX = 648.0
POST_SECONDARY_TEACHING_WEEKS_MAX = 36
WEEKLY_WORKLOAD_OVERTIME_MAX = 47.0
MIN_COMPLEMENTARY_ALLOWANCE_2026 = 7.0
COMPLEMENTARY_ALLOWANCE_EFFECTIVE_DATE = datetime(2026, 1, 1)

CHECK_FIELDS = [
    "source_group",
    "faculty_token",
    "stable_faculty_id",
    "document_id",
    "severity",
    "rule_id",
    "ca_clause",
    "message",
    "actual_value",
    "limit_value",
]


def write_ca_reports(documents: list[StructuredDocument], output_root: Path) -> dict[str, Path]:
    findings = collect_findings(documents)

    report_dir = output_root / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    csv_path = report_dir / "ca_findings.csv"
    md_path = report_dir / "ca_findings.md"

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
    summary = document.summary_row
    if not summary:
        return findings

    is_post_secondary = is_post_secondary_group(document.program_group)
    probationary = document.probationary_status == "Probationary"

    weekly_workload = parse_float(summary.get("total_this_period_swf"))
    teaching_contact = parse_float(summary.get("assigned_teaching_contact_hours_week"))
    course_preparations = parse_int(summary.get("number_of_course_preparations"))
    complementary_allowance = parse_float(summary.get("complementary_hours_allowance_week"))
    accumulated_contact_days = parse_int(summary.get("total_to_end_date_contact_days"))
    accumulated_teaching_hours = parse_float(summary.get("total_to_end_date_contact_hours"))
    accumulated_teaching_weeks = parse_int(summary.get("total_to_end_date_teaching_weeks"))
    overtime_workload_hours = parse_float(document.overtime_workload_hours)

    if weekly_workload is not None:
        if weekly_workload > WEEKLY_WORKLOAD_OVERTIME_MAX:
            findings.append(
                make_finding(
                    document,
                    severity="high",
                    rule_id="weekly_workload_absolute_max",
                    ca_clause="11.01 B 1 / 11.01 J 1",
                    message="Weekly total workload exceeds the 44-hour maximum plus the 3-hour overtime ceiling.",
                    actual_value=format_number(weekly_workload),
                    limit_value=format_number(WEEKLY_WORKLOAD_OVERTIME_MAX),
                )
            )
        elif weekly_workload > POST_SECONDARY_WEEKLY_WORKLOAD_MAX:
            excess = weekly_workload - POST_SECONDARY_WEEKLY_WORKLOAD_MAX
            if probationary:
                findings.append(
                    make_finding(
                        document,
                        severity="high",
                        rule_id="probationary_weekly_workload_overtime",
                        ca_clause="11.01 J 4",
                        message="Probationary teacher exceeds the 44-hour weekly workload maximum.",
                        actual_value=format_number(weekly_workload),
                        limit_value=format_number(POST_SECONDARY_WEEKLY_WORKLOAD_MAX),
                    )
                )
            elif overtime_workload_hours is None or abs(overtime_workload_hours - excess) > 0.05:
                findings.append(
                    make_finding(
                        document,
                        severity="review",
                        rule_id="weekly_workload_overtime_documentation",
                        ca_clause="11.01 B 1 / 11.01 J 1-3",
                        message="Weekly workload exceeds 44 hours without a matching documented workload-overtime amount on the SWF.",
                        actual_value=format_number(weekly_workload),
                        limit_value=format_number(POST_SECONDARY_WEEKLY_WORKLOAD_MAX),
                    )
                )

    if teaching_contact is not None:
        if is_post_secondary and teaching_contact > POST_SECONDARY_TEACHING_CONTACT_OVERTIME_MAX:
            findings.append(
                make_finding(
                    document,
                    severity="high",
                    rule_id="weekly_teaching_contact_absolute_max",
                    ca_clause="11.01 I / 11.01 J 1",
                    message="Weekly teaching contact hours exceed the 18-hour maximum plus the 1-hour overtime ceiling.",
                    actual_value=format_number(teaching_contact),
                    limit_value=format_number(POST_SECONDARY_TEACHING_CONTACT_OVERTIME_MAX),
                )
            )
        elif is_post_secondary and teaching_contact > POST_SECONDARY_TEACHING_CONTACT_MAX:
            severity = "high" if probationary else "review"
            clause = "11.01 J 4" if probationary else "11.01 I / 11.01 J 1-3"
            message = (
                "Probationary teacher exceeds the 18-hour weekly teaching contact maximum."
                if probationary
                else "Weekly teaching contact hours exceed 18 and require voluntary overtime documentation on the SWF."
            )
            findings.append(
                make_finding(
                    document,
                    severity=severity,
                    rule_id="weekly_teaching_contact_overtime",
                    ca_clause=clause,
                    message=message,
                    actual_value=format_number(teaching_contact),
                    limit_value=format_number(POST_SECONDARY_TEACHING_CONTACT_MAX),
                )
            )

    if course_preparations is not None and course_preparations > 4:
        findings.append(
            make_finding(
                document,
                severity="review",
                rule_id="course_preparations_over_four",
                ca_clause="11.01 D 2",
                message="More than four different course preparations are assigned in the week; this requires voluntary agreement.",
                actual_value=str(course_preparations),
                limit_value="4",
            )
        )

    if (
        complementary_allowance is not None
        and complementary_allowance < MIN_COMPLEMENTARY_ALLOWANCE_2026
        and is_minimum_complementary_allowance_in_effect(document)
    ):
        findings.append(
            make_finding(
                document,
                severity="high",
                rule_id="minimum_complementary_allowance",
                ca_clause="11.01 F 1",
                message="Complementary allowance is below the seven-hour minimum in effect January 1, 2026 and later.",
                actual_value=format_number(complementary_allowance),
                limit_value=format_number(MIN_COMPLEMENTARY_ALLOWANCE_2026),
            )
        )

    if is_post_secondary:
        if accumulated_contact_days is not None and accumulated_contact_days > POST_SECONDARY_ANNUAL_CONTACT_DAYS_MAX:
            findings.append(
                make_finding(
                    document,
                    severity="review",
                    rule_id="annual_contact_days_max",
                    ca_clause="11.01 K 1 / 11.01 K 4",
                    message="Accumulated contact days exceed the 180-day annual maximum; compensation review is required.",
                    actual_value=str(accumulated_contact_days),
                    limit_value=str(POST_SECONDARY_ANNUAL_CONTACT_DAYS_MAX),
                )
            )
        if accumulated_teaching_hours is not None and accumulated_teaching_hours > POST_SECONDARY_ANNUAL_TEACHING_HOURS_MAX:
            findings.append(
                make_finding(
                    document,
                    severity="review",
                    rule_id="annual_teaching_hours_max",
                    ca_clause="11.01 K 3 / 11.01 K 4",
                    message="Accumulated teaching contact hours exceed the 648-hour annual maximum; compensation review is required.",
                    actual_value=format_number(accumulated_teaching_hours),
                    limit_value=format_number(POST_SECONDARY_ANNUAL_TEACHING_HOURS_MAX),
                )
            )
        if accumulated_teaching_weeks is not None and accumulated_teaching_weeks > POST_SECONDARY_TEACHING_WEEKS_MAX:
            findings.append(
                make_finding(
                    document,
                    severity="review",
                    rule_id="annual_teaching_weeks_max",
                    ca_clause="11.01 B 1",
                    message="Teaching contact hours extend beyond the 36 teaching-week annual limit for post-secondary teachers.",
                    actual_value=str(accumulated_teaching_weeks),
                    limit_value=str(POST_SECONDARY_TEACHING_WEEKS_MAX),
                )
            )

    return findings


def render_markdown(findings: list[dict[str, str]], documents: list[StructuredDocument]) -> str:
    lines = ["# CA Findings", ""]
    lines.append(f"Documents checked: {len(documents)}")
    lines.append(f"Findings: {len(findings)}")
    lines.append("")

    if not findings:
        lines.append("No Article 11 findings were detected from the rule checks currently implemented.")
        lines.append("")
        lines.append("Checks covered: weekly workload maxima, weekly teaching contact maxima, course preparation cap, minimum complementary allowance, annual contact day limit, annual teaching hour limit, and annual teaching-week limit.")
        return "\n".join(lines) + "\n"

    severity_counts = count_by_key(findings, "severity")
    lines.append("## Summary")
    for severity in ["high", "review"]:
        count = severity_counts.get(severity, 0)
        if count:
            lines.append(f"- `{severity}`: {count}")
    lines.append("")

    lines.append("## Findings")
    for finding in findings:
        lines.append(
            f"- `{finding['severity']}` {finding['faculty_token']} {finding['ca_clause']}: {finding['message']} "
            f"(actual `{finding['actual_value']}`, limit `{finding['limit_value']}`)"
        )

    lines.append("")
    lines.append("## Scope")
    lines.append("- This report only checks Article 11 rules that can be inferred from the SWF text and extracted summary data.")
    lines.append("- It does not yet verify timetable-based rules such as contact-day span, 12-hour rest, weekend assignments, or local modified workload arrangements.")
    return "\n".join(lines) + "\n"


def count_by_key(rows: list[dict[str, str]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row[key]] = counts.get(row[key], 0) + 1
    return counts


def make_finding(
    document: StructuredDocument,
    severity: str,
    rule_id: str,
    ca_clause: str,
    message: str,
    actual_value: str,
    limit_value: str,
) -> dict[str, str]:
    return {
        "source_group": document.source_group,
        "faculty_token": document.faculty_token,
        "stable_faculty_id": document.stable_faculty_id,
        "document_id": document.document_id,
        "severity": severity,
        "rule_id": rule_id,
        "ca_clause": ca_clause,
        "message": message,
        "actual_value": actual_value,
        "limit_value": limit_value,
    }


def is_post_secondary_group(group: str) -> bool:
    if not group:
        return True
    return group.strip().lower().startswith("post-secondary")


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


def parse_int(value: str | None) -> int | None:
    parsed = parse_float(value)
    if parsed is None:
        return None
    return int(round(parsed))


def format_number(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".") if value % 1 else f"{value:.0f}"


def is_minimum_complementary_allowance_in_effect(document: StructuredDocument) -> bool:
    effective_date = parse_swf_date(document.period_end) or parse_swf_date(document.issued_date)
    if effective_date is None:
        return True
    return effective_date >= COMPLEMENTARY_ALLOWANCE_EFFECTIVE_DATE


def parse_swf_date(raw_value: str) -> datetime | None:
    cleaned = raw_value.strip()
    if not cleaned:
        return None
    try:
        return datetime.strptime(cleaned.title(), "%d-%b-%Y")
    except ValueError:
        return None
