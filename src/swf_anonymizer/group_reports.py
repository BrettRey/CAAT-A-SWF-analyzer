from __future__ import annotations

import csv
from pathlib import Path

from .ca_checker import collect_findings as collect_ca_findings
from .models import StructuredDocument
from .prep_type_checker import collect_findings as collect_prep_findings
from .quality_checker import collect_findings as collect_quality_findings


GROUP_FIELDS = [
    "source_group",
    "documents",
    "unique_stable_faculty_ids",
    "course_rows",
    "complementary_rows",
    "ca_high",
    "ca_review",
    "prep_reviews",
    "quality_high",
    "quality_review",
]


def write_group_reports(documents: list[StructuredDocument], output_root: Path) -> dict[str, Path]:
    rows = build_group_rows(documents)

    report_dir = output_root / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    csv_path = report_dir / "source_group_summary.csv"
    md_path = report_dir / "source_group_summary.md"

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=GROUP_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    md_path.write_text(render_markdown(rows, documents), encoding="utf-8")
    return {"csv": csv_path, "markdown": md_path}


def build_group_rows(documents: list[StructuredDocument]) -> list[dict[str, str]]:
    ca_findings = collect_ca_findings(documents)
    prep_findings = collect_prep_findings(documents)
    quality_findings = collect_quality_findings(documents)

    by_group: dict[str, dict[str, object]] = {}

    def ensure_group(name: str) -> dict[str, object]:
        group_name = name or "(root)"
        if group_name not in by_group:
            by_group[group_name] = {
                "documents": 0,
                "stable_ids": set(),
                "course_rows": 0,
                "complementary_rows": 0,
                "ca_high": 0,
                "ca_review": 0,
                "prep_reviews": 0,
                "quality_high": 0,
                "quality_review": 0,
            }
        return by_group[group_name]

    for document in documents:
        group = ensure_group(document.source_group)
        group["documents"] = int(group["documents"]) + 1
        if document.stable_faculty_id:
            stable_ids = group["stable_ids"]
            assert isinstance(stable_ids, set)
            stable_ids.add(document.stable_faculty_id)
        group["course_rows"] = int(group["course_rows"]) + len(document.course_rows)
        group["complementary_rows"] = int(group["complementary_rows"]) + len(document.complementary_rows)

    for finding in ca_findings:
        group = ensure_group(finding.get("source_group", ""))
        key = "ca_high" if finding["severity"] == "high" else "ca_review"
        group[key] = int(group[key]) + 1

    for finding in prep_findings:
        group = ensure_group(finding.get("source_group", ""))
        group["prep_reviews"] = int(group["prep_reviews"]) + 1

    for finding in quality_findings:
        group = ensure_group(finding.get("source_group", ""))
        key = "quality_high" if finding["severity"] == "high" else "quality_review"
        group[key] = int(group[key]) + 1

    rows: list[dict[str, str]] = []
    for source_group in sorted(by_group):
        group = by_group[source_group]
        stable_ids = group["stable_ids"]
        assert isinstance(stable_ids, set)
        rows.append(
            {
                "source_group": source_group,
                "documents": str(group["documents"]),
                "unique_stable_faculty_ids": str(len(stable_ids)),
                "course_rows": str(group["course_rows"]),
                "complementary_rows": str(group["complementary_rows"]),
                "ca_high": str(group["ca_high"]),
                "ca_review": str(group["ca_review"]),
                "prep_reviews": str(group["prep_reviews"]),
                "quality_high": str(group["quality_high"]),
                "quality_review": str(group["quality_review"]),
            }
        )

    if rows:
        rows.append(build_overall_row(rows, documents))
    return rows


def build_overall_row(rows: list[dict[str, str]], documents: list[StructuredDocument]) -> dict[str, str]:
    total_row = {"source_group": "ALL"}
    for field in GROUP_FIELDS[1:]:
        if field == "unique_stable_faculty_ids":
            total_row[field] = str(
                len({document.stable_faculty_id for document in documents if document.stable_faculty_id})
            )
            continue
        total_row[field] = str(sum(int(row[field]) for row in rows))
    return total_row


def render_markdown(rows: list[dict[str, str]], documents: list[StructuredDocument]) -> str:
    lines = ["# Source Group Summary", ""]
    lines.append(f"Documents checked: {len(documents)}")
    lines.append("")

    if not rows:
        lines.append("No documents were processed.")
        return "\n".join(lines) + "\n"

    lines.append("| Source Group | Docs | Stable IDs | Courses | Complementary | CA High | CA Review | Prep Review | Quality High | Quality Review |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in rows:
        lines.append(
            f"| {row['source_group']} | {row['documents']} | {row['unique_stable_faculty_ids']} | "
            f"{row['course_rows']} | {row['complementary_rows']} | {row['ca_high']} | {row['ca_review']} | "
            f"{row['prep_reviews']} | {row['quality_high']} | {row['quality_review']} |"
        )

    lines.append("")
    lines.append("- `source_group` comes from the SWF file's parent folder, so it reflects the Associate Dean or sender folder when the input tree is organized that way.")
    return "\n".join(lines) + "\n"
