from __future__ import annotations

import csv
from pathlib import Path


FACULTY_FIELDS = [
    "stable_faculty_id",
    "status",
    "current_faculty_token",
    "previous_faculty_token",
    "current_source_group",
    "previous_source_group",
    "current_document_id",
    "previous_document_id",
    "current_period",
    "previous_period",
    "current_course_count",
    "previous_course_count",
    "courses_added",
    "courses_removed",
    "assigned_tch_delta",
    "weekly_workload_delta",
    "accumulated_weeks_delta",
]

COURSE_FIELDS = [
    "stable_faculty_id",
    "course_code",
    "status",
    "current_source_group",
    "previous_source_group",
    "current_contact_hours",
    "previous_contact_hours",
    "current_row_count",
    "previous_row_count",
    "current_delivery_types",
    "previous_delivery_types",
]


def write_comparison_reports(current_output_root: Path, previous_output_root: Path) -> dict[str, Path]:
    report_dir = current_output_root / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    current_summary_path = current_output_root / "csv" / "swf_summary.csv"
    previous_summary_path = previous_output_root / "csv" / "swf_summary.csv"
    current_courses_path = current_output_root / "csv" / "course_assignments.csv"
    previous_courses_path = previous_output_root / "csv" / "course_assignments.csv"

    md_path = report_dir / "comparison_summary.md"
    faculty_csv_path = report_dir / "comparison_faculty_summary.csv"
    course_csv_path = report_dir / "comparison_course_changes.csv"

    missing_inputs = [
        path
        for path in (
            current_summary_path,
            previous_summary_path,
            current_courses_path,
            previous_courses_path,
        )
        if not path.exists()
    ]
    if missing_inputs:
        md_path.write_text(
            "# Comparison Summary\n\n"
            "Comparison could not run because one or more required CSV files were missing.\n",
            encoding="utf-8",
        )
        return {"markdown": md_path}

    current_summary_rows = read_csv(current_summary_path)
    previous_summary_rows = read_csv(previous_summary_path)
    current_course_rows = read_csv(current_courses_path)
    previous_course_rows = read_csv(previous_courses_path)

    faculty_rows = build_faculty_comparison_rows(
        current_summary_rows=current_summary_rows,
        previous_summary_rows=previous_summary_rows,
        current_course_rows=current_course_rows,
        previous_course_rows=previous_course_rows,
    )
    course_rows = build_course_change_rows(
        current_course_rows=current_course_rows,
        previous_course_rows=previous_course_rows,
    )

    write_csv(faculty_csv_path, FACULTY_FIELDS, faculty_rows)
    write_csv(course_csv_path, COURSE_FIELDS, course_rows)
    md_path.write_text(
        render_markdown(
            faculty_rows=faculty_rows,
            course_rows=course_rows,
            current_summary_rows=current_summary_rows,
            previous_summary_rows=previous_summary_rows,
        ),
        encoding="utf-8",
    )
    return {
        "markdown": md_path,
        "faculty_csv": faculty_csv_path,
        "course_csv": course_csv_path,
    }


def build_faculty_comparison_rows(
    current_summary_rows: list[dict[str, str]],
    previous_summary_rows: list[dict[str, str]],
    current_course_rows: list[dict[str, str]],
    previous_course_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    current_summary = {faculty_key(row): row for row in current_summary_rows}
    previous_summary = {faculty_key(row): row for row in previous_summary_rows}
    current_course_sets = aggregate_courses_by_faculty(current_course_rows)
    previous_course_sets = aggregate_courses_by_faculty(previous_course_rows)

    rows: list[dict[str, str]] = []
    for stable_id in sorted(set(current_summary) | set(previous_summary) | set(current_course_sets) | set(previous_course_sets)):
        current_row = current_summary.get(stable_id)
        previous_row = previous_summary.get(stable_id)
        current_courses = current_course_sets.get(stable_id, set())
        previous_courses = previous_course_sets.get(stable_id, set())

        if current_row and not previous_row:
            status = "added"
        elif previous_row and not current_row:
            status = "removed"
        else:
            status = "changed" if rows_differ(current_row or {}, previous_row or {}, current_courses, previous_courses) else "unchanged"

        rows.append(
            {
                "stable_faculty_id": stable_id,
                "status": status,
                "current_faculty_token": (current_row or {}).get("faculty_token", ""),
                "previous_faculty_token": (previous_row or {}).get("faculty_token", ""),
                "current_source_group": (current_row or {}).get("source_group", ""),
                "previous_source_group": (previous_row or {}).get("source_group", ""),
                "current_document_id": (current_row or {}).get("document_id", ""),
                "previous_document_id": (previous_row or {}).get("document_id", ""),
                "current_period": build_period_label(current_row or {}),
                "previous_period": build_period_label(previous_row or {}),
                "current_course_count": str(len(current_courses)),
                "previous_course_count": str(len(previous_courses)),
                "courses_added": ", ".join(sorted(current_courses - previous_courses)),
                "courses_removed": ", ".join(sorted(previous_courses - current_courses)),
                "assigned_tch_delta": format_delta(
                    parse_float((current_row or {}).get("assigned_teaching_contact_hours_week")),
                    parse_float((previous_row or {}).get("assigned_teaching_contact_hours_week")),
                ),
                "weekly_workload_delta": format_delta(
                    parse_float((current_row or {}).get("total_this_period_swf")),
                    parse_float((previous_row or {}).get("total_this_period_swf")),
                ),
                "accumulated_weeks_delta": format_delta(
                    parse_float((current_row or {}).get("total_to_end_date_teaching_weeks")),
                    parse_float((previous_row or {}).get("total_to_end_date_teaching_weeks")),
                ),
            }
        )
    return rows


def build_course_change_rows(
    current_course_rows: list[dict[str, str]],
    previous_course_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    current = aggregate_course_rows(current_course_rows)
    previous = aggregate_course_rows(previous_course_rows)
    rows: list[dict[str, str]] = []

    for stable_id, course_code in sorted(set(current) | set(previous)):
        current_row = current.get((stable_id, course_code))
        previous_row = previous.get((stable_id, course_code))

        if current_row and not previous_row:
            status = "added"
        elif previous_row and not current_row:
            status = "removed"
        else:
            changed = (
                abs(parse_float(current_row["contact_hours"]) - parse_float(previous_row["contact_hours"])) > 0.05
                or current_row["row_count"] != previous_row["row_count"]
                or current_row["delivery_types"] != previous_row["delivery_types"]
            )
            status = "changed" if changed else "unchanged"

        rows.append(
            {
                "stable_faculty_id": stable_id,
                "course_code": course_code,
                "status": status,
                "current_source_group": current_row["source_group"] if current_row else "",
                "previous_source_group": previous_row["source_group"] if previous_row else "",
                "current_contact_hours": current_row["contact_hours"] if current_row else "",
                "previous_contact_hours": previous_row["contact_hours"] if previous_row else "",
                "current_row_count": str(current_row["row_count"]) if current_row else "",
                "previous_row_count": str(previous_row["row_count"]) if previous_row else "",
                "current_delivery_types": ", ".join(sorted(current_row["delivery_types"])) if current_row else "",
                "previous_delivery_types": ", ".join(sorted(previous_row["delivery_types"])) if previous_row else "",
            }
        )
    return rows


def aggregate_courses_by_faculty(rows: list[dict[str, str]]) -> dict[str, set[str]]:
    courses: dict[str, set[str]] = {}
    for row in rows:
        stable_id = faculty_key(row)
        course_code = row.get("course_code", "").strip()
        if not stable_id or not course_code:
            continue
        courses.setdefault(stable_id, set()).add(course_code)
    return courses


def aggregate_course_rows(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, object]]:
    aggregated: dict[tuple[str, str], dict[str, object]] = {}
    for row in rows:
        stable_id = faculty_key(row)
        course_code = row.get("course_code", "").strip()
        if not stable_id or not course_code:
            continue
        key = (stable_id, course_code)
        bucket = aggregated.setdefault(
            key,
            {
                "source_group": row.get("source_group", ""),
                "contact_hours": 0.0,
                "row_count": 0,
                "delivery_types": set(),
            },
        )
        bucket["contact_hours"] = float(bucket["contact_hours"]) + parse_float(row.get("contact_hours"))
        bucket["row_count"] = int(bucket["row_count"]) + 1
        delivery_types = bucket["delivery_types"]
        assert isinstance(delivery_types, set)
        delivery_type = row.get("delivery_type", "").strip()
        if delivery_type:
            delivery_types.add(delivery_type)

    normalized: dict[tuple[str, str], dict[str, object]] = {}
    for key, value in aggregated.items():
        normalized[key] = {
            "source_group": str(value["source_group"]),
            "contact_hours": format_number(float(value["contact_hours"])),
            "row_count": int(value["row_count"]),
            "delivery_types": set(value["delivery_types"]),
        }
    return normalized


def render_markdown(
    faculty_rows: list[dict[str, str]],
    course_rows: list[dict[str, str]],
    current_summary_rows: list[dict[str, str]],
    previous_summary_rows: list[dict[str, str]],
) -> str:
    lines = ["# Comparison Summary", ""]
    lines.append(f"Current faculty rows: {len(current_summary_rows)}")
    lines.append(f"Previous faculty rows: {len(previous_summary_rows)}")
    lines.append("")

    status_counts = count_by_key(faculty_rows, "status")
    if not faculty_rows:
        lines.append("No comparable faculty rows were found.")
        return "\n".join(lines) + "\n"

    lines.append("## Faculty Changes")
    for status in ("added", "removed", "changed", "unchanged"):
        if status_counts.get(status):
            lines.append(f"- `{status}`: {status_counts[status]}")
    lines.append("")

    course_status_counts = count_by_key(course_rows, "status")
    lines.append("## Course Changes")
    for status in ("added", "removed", "changed", "unchanged"):
        if course_status_counts.get(status):
            lines.append(f"- `{status}`: {course_status_counts[status]}")
    lines.append("")

    if uses_token_fallback(current_summary_rows) or uses_token_fallback(previous_summary_rows):
        lines.append("## Note")
        lines.append("- One or both runs were compared with `faculty_token` fallback because `stable_faculty_id` was missing on some rows. Reusing the same state directory improves cross-run reliability.")

    return "\n".join(lines) + "\n"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def faculty_key(row: dict[str, str]) -> str:
    stable_id = row.get("stable_faculty_id", "").strip()
    if stable_id:
        return stable_id
    faculty_token = row.get("faculty_token", "").strip()
    if faculty_token:
        return faculty_token
    return row.get("document_id", "").strip()


def rows_differ(
    current_row: dict[str, str],
    previous_row: dict[str, str],
    current_courses: set[str],
    previous_courses: set[str],
) -> bool:
    fields = [
        "assigned_teaching_contact_hours_week",
        "total_this_period_swf",
        "total_to_end_date_teaching_weeks",
        "source_group",
    ]
    for field in fields:
        if (current_row.get(field, "") or "").strip() != (previous_row.get(field, "") or "").strip():
            return True
    return current_courses != previous_courses


def build_period_label(row: dict[str, str]) -> str:
    start = row.get("period_start", "").strip()
    end = row.get("period_end", "").strip()
    if start and end:
        return f"{start} to {end}"
    return start or end


def parse_float(value: str | None) -> float:
    if value is None:
        return 0.0
    cleaned = value.strip()
    if not cleaned:
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def format_delta(current_value: float, previous_value: float) -> str:
    return format_number(current_value - previous_value)


def format_number(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".") if value % 1 else f"{value:.0f}"


def count_by_key(rows: list[dict[str, str]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row[key]] = counts.get(row[key], 0) + 1
    return counts


def uses_token_fallback(rows: list[dict[str, str]]) -> bool:
    return any(not row.get("stable_faculty_id", "").strip() and row.get("faculty_token", "").strip() for row in rows)
