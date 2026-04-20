from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(slots=True)
class DocumentContext:
    document_id: str
    stable_faculty_id: str
    faculty_token: str
    source_group_token: str
    academic_year: str
    term: str
    term_label: str


TERM_ORDER = {"Fall": 1, "Winter": 2, "Summer": 3, "Unknown": 4}


def write_bank_analysis(output_root: Path) -> dict[str, Path]:
    csv_dir = output_root / "csv"
    reports_dir = output_root / "reports"
    analysis_dir = output_root / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)

    summary_rows = read_csv(csv_dir / "swf_summary.csv")
    course_rows = read_csv(csv_dir / "course_assignments.csv")
    complementary_rows = read_csv(csv_dir / "complementary_functions.csv")
    ca_rows = read_csv(reports_dir / "ca_findings.csv")
    prep_rows = read_csv(reports_dir / "prep_type_findings.csv")
    quality_rows = read_csv(reports_dir / "quality_findings.csv")
    failure_rows = read_csv(reports_dir / "processing_failures.csv")

    group_tokens = build_group_tokens(summary_rows, ca_rows, prep_rows, quality_rows)
    document_index = build_document_index(summary_rows, group_tokens)

    term_overview_rows = build_term_overview_rows(
        summary_rows=summary_rows,
        course_rows=course_rows,
        complementary_rows=complementary_rows,
        ca_rows=ca_rows,
        prep_rows=prep_rows,
        quality_rows=quality_rows,
        document_index=document_index,
    )
    ca_rule_rows = build_rule_summary_rows(ca_rows, document_index, "ca")
    quality_rule_rows = build_rule_summary_rows(quality_rows, document_index, "quality")
    prep_rule_rows = build_rule_summary_rows(prep_rows, document_index, "prep")
    group_rows = build_group_analysis_rows(summary_rows, ca_rows, prep_rows, quality_rows, group_tokens)
    repeat_faculty_rows = build_repeat_faculty_rows(ca_rows, document_index)
    faculty_longitudinal_rows = build_faculty_longitudinal_rows(summary_rows, ca_rows, quality_rows, document_index)
    course_rollup_rows = build_course_rollup_rows(course_rows, ca_rows, document_index)
    failure_summary_rows = build_failure_summary_rows(failure_rows)

    paths = {
        "term_overview": analysis_dir / "term_overview.csv",
        "ca_rule_summary": analysis_dir / "ca_rule_summary.csv",
        "quality_rule_summary": analysis_dir / "quality_rule_summary.csv",
        "prep_rule_summary": analysis_dir / "prep_rule_summary.csv",
        "group_overview": analysis_dir / "group_overview.csv",
        "repeat_flagged_faculty": analysis_dir / "repeat_flagged_faculty.csv",
        "faculty_longitudinal_summary": analysis_dir / "faculty_longitudinal_summary.csv",
        "course_rollup": analysis_dir / "course_rollup.csv",
        "processing_failure_summary": analysis_dir / "processing_failure_summary.csv",
        "summary_markdown": analysis_dir / "summary.md",
    }

    write_csv(paths["term_overview"], TERM_OVERVIEW_FIELDS, term_overview_rows)
    write_csv(paths["ca_rule_summary"], RULE_SUMMARY_FIELDS, ca_rule_rows)
    write_csv(paths["quality_rule_summary"], RULE_SUMMARY_FIELDS, quality_rule_rows)
    write_csv(paths["prep_rule_summary"], RULE_SUMMARY_FIELDS, prep_rule_rows)
    write_csv(paths["group_overview"], GROUP_OVERVIEW_FIELDS, group_rows)
    write_csv(paths["repeat_flagged_faculty"], REPEAT_FACULTY_FIELDS, repeat_faculty_rows)
    write_csv(paths["faculty_longitudinal_summary"], FACULTY_LONGITUDINAL_FIELDS, faculty_longitudinal_rows)
    write_csv(paths["course_rollup"], COURSE_ROLLUP_FIELDS, course_rollup_rows)
    write_csv(paths["processing_failure_summary"], FAILURE_SUMMARY_FIELDS, failure_summary_rows)

    paths["summary_markdown"].write_text(
        render_summary_markdown(
            summary_rows=summary_rows,
            course_rows=course_rows,
            complementary_rows=complementary_rows,
            ca_rows=ca_rows,
            prep_rows=prep_rows,
            quality_rows=quality_rows,
            failure_rows=failure_rows,
            term_overview_rows=term_overview_rows,
            group_rows=group_rows,
            repeat_faculty_rows=repeat_faculty_rows,
            course_rollup_rows=course_rollup_rows,
        ),
        encoding="utf-8",
    )

    return paths


TERM_OVERVIEW_FIELDS = [
    "academic_year",
    "term",
    "term_label",
    "documents",
    "unique_stable_faculty_ids",
    "course_rows",
    "complementary_rows",
    "ca_high",
    "ca_review",
    "prep_findings",
    "quality_high",
    "quality_review",
]

RULE_SUMMARY_FIELDS = [
    "analysis_type",
    "academic_year",
    "term",
    "term_label",
    "rule_id",
    "count",
]

GROUP_OVERVIEW_FIELDS = [
    "group_token",
    "documents",
    "unique_stable_faculty_ids",
    "ca_high",
    "ca_review",
    "prep_findings",
    "quality_high",
    "quality_review",
]

REPEAT_FACULTY_FIELDS = [
    "stable_faculty_id",
    "documents_with_ca_findings",
    "ca_high",
    "ca_review",
    "distinct_terms",
    "distinct_rules",
    "rule_ids",
]

FACULTY_LONGITUDINAL_FIELDS = [
    "stable_faculty_id",
    "documents",
    "distinct_terms",
    "first_term",
    "last_term",
    "avg_assigned_tch_week",
    "max_assigned_tch_week",
    "avg_total_workload_week",
    "max_total_workload_week",
    "max_preps",
    "ca_findings",
    "quality_findings",
]

COURSE_ROLLUP_FIELDS = [
    "course_code",
    "assignment_rows",
    "documents",
    "unique_stable_faculty_ids",
    "distinct_terms",
    "documents_with_ca_findings",
    "documents_with_high_ca_findings",
    "avg_contact_hours",
    "max_contact_hours",
]

FAILURE_SUMMARY_FIELDS = [
    "error_class",
    "count",
]


def build_group_tokens(*row_sets: list[dict[str, str]]) -> dict[str, str]:
    values: set[str] = set()
    for rows in row_sets:
        for row in rows:
            value = row.get("source_group", "").strip()
            if value:
                values.add(value)
    return {
        value: f"GROUP{index:03d}"
        for index, value in enumerate(sorted(values), start=1)
    }


def build_document_index(
    summary_rows: list[dict[str, str]],
    group_tokens: dict[str, str],
) -> dict[str, DocumentContext]:
    index: dict[str, DocumentContext] = {}
    for row in summary_rows:
        academic_year, term = classify_term(row.get("period_start", ""), row.get("issued_date", ""))
        term_label = f"{academic_year} {term}" if academic_year != "Unknown" else "Unknown"
        index[row["document_id"]] = DocumentContext(
            document_id=row["document_id"],
            stable_faculty_id=row.get("stable_faculty_id", "").strip() or row.get("faculty_token", "").strip(),
            faculty_token=row.get("faculty_token", "").strip(),
            source_group_token=group_tokens.get(row.get("source_group", "").strip(), ""),
            academic_year=academic_year,
            term=term,
            term_label=term_label,
        )
    return index


def build_term_overview_rows(
    *,
    summary_rows: list[dict[str, str]],
    course_rows: list[dict[str, str]],
    complementary_rows: list[dict[str, str]],
    ca_rows: list[dict[str, str]],
    prep_rows: list[dict[str, str]],
    quality_rows: list[dict[str, str]],
    document_index: dict[str, DocumentContext],
) -> list[dict[str, str]]:
    terms: dict[tuple[str, str], dict[str, object]] = defaultdict(
        lambda: {
            "documents": 0,
            "stable_ids": set(),
            "course_rows": 0,
            "complementary_rows": 0,
            "ca_high": 0,
            "ca_review": 0,
            "prep_findings": 0,
            "quality_high": 0,
            "quality_review": 0,
        }
    )

    for row in summary_rows:
        context = document_index[row["document_id"]]
        key = (context.academic_year, context.term)
        bucket = terms[key]
        bucket["documents"] = int(bucket["documents"]) + 1
        stable_ids = bucket["stable_ids"]
        assert isinstance(stable_ids, set)
        if context.stable_faculty_id:
            stable_ids.add(context.stable_faculty_id)

    increment_term_documents(course_rows, document_index, terms, "course_rows")
    increment_term_documents(complementary_rows, document_index, terms, "complementary_rows")
    increment_findings(ca_rows, document_index, terms, "ca")
    increment_findings(prep_rows, document_index, terms, "prep")
    increment_findings(quality_rows, document_index, terms, "quality")

    rows: list[dict[str, str]] = []
    for academic_year, term in sorted(terms, key=sort_term_key):
        bucket = terms[(academic_year, term)]
        stable_ids = bucket["stable_ids"]
        assert isinstance(stable_ids, set)
        rows.append(
            {
                "academic_year": academic_year,
                "term": term,
                "term_label": f"{academic_year} {term}" if academic_year != "Unknown" else "Unknown",
                "documents": str(bucket["documents"]),
                "unique_stable_faculty_ids": str(len(stable_ids)),
                "course_rows": str(bucket["course_rows"]),
                "complementary_rows": str(bucket["complementary_rows"]),
                "ca_high": str(bucket["ca_high"]),
                "ca_review": str(bucket["ca_review"]),
                "prep_findings": str(bucket["prep_findings"]),
                "quality_high": str(bucket["quality_high"]),
                "quality_review": str(bucket["quality_review"]),
            }
        )
    return rows


def increment_term_documents(
    rows: list[dict[str, str]],
    document_index: dict[str, DocumentContext],
    terms: dict[tuple[str, str], dict[str, object]],
    field: str,
) -> None:
    for row in rows:
        context = document_index.get(row.get("document_id", ""))
        if context is None:
            continue
        key = (context.academic_year, context.term)
        terms[key][field] = int(terms[key][field]) + 1


def increment_findings(
    rows: list[dict[str, str]],
    document_index: dict[str, DocumentContext],
    terms: dict[tuple[str, str], dict[str, object]],
    analysis_type: str,
) -> None:
    for row in rows:
        context = document_index.get(row.get("document_id", ""))
        if context is None:
            continue
        key = (context.academic_year, context.term)
        bucket = terms[key]
        if analysis_type == "ca":
            severity_field = "ca_high" if row.get("severity") == "high" else "ca_review"
            bucket[severity_field] = int(bucket[severity_field]) + 1
        elif analysis_type == "prep":
            bucket["prep_findings"] = int(bucket["prep_findings"]) + 1
        elif analysis_type == "quality":
            severity_field = "quality_high" if row.get("severity") == "high" else "quality_review"
            bucket[severity_field] = int(bucket[severity_field]) + 1


def build_rule_summary_rows(
    rows: list[dict[str, str]],
    document_index: dict[str, DocumentContext],
    analysis_type: str,
) -> list[dict[str, str]]:
    counter: Counter[tuple[str, str, str]] = Counter()
    for row in rows:
        context = document_index.get(row.get("document_id", ""))
        if context is None:
            continue
        counter[(context.academic_year, context.term, row.get("rule_id", ""))] += 1

    summary_rows: list[dict[str, str]] = []
    for academic_year, term, rule_id in sorted(counter, key=lambda item: (term_sort_tuple(item[0], item[1]), item[2])):
        summary_rows.append(
            {
                "analysis_type": analysis_type,
                "academic_year": academic_year,
                "term": term,
                "term_label": f"{academic_year} {term}" if academic_year != "Unknown" else "Unknown",
                "rule_id": rule_id,
                "count": str(counter[(academic_year, term, rule_id)]),
            }
        )
    return summary_rows


def build_group_analysis_rows(
    summary_rows: list[dict[str, str]],
    ca_rows: list[dict[str, str]],
    prep_rows: list[dict[str, str]],
    quality_rows: list[dict[str, str]],
    group_tokens: dict[str, str],
) -> list[dict[str, str]]:
    groups: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "documents": 0,
            "stable_ids": set(),
            "ca_high": 0,
            "ca_review": 0,
            "prep_findings": 0,
            "quality_high": 0,
            "quality_review": 0,
        }
    )

    for row in summary_rows:
        token = group_tokens.get(row.get("source_group", "").strip(), "")
        bucket = groups[token]
        bucket["documents"] = int(bucket["documents"]) + 1
        stable_ids = bucket["stable_ids"]
        assert isinstance(stable_ids, set)
        stable_value = row.get("stable_faculty_id", "").strip() or row.get("faculty_token", "").strip()
        if stable_value:
            stable_ids.add(stable_value)

    for row in ca_rows:
        token = group_tokens.get(row.get("source_group", "").strip(), "")
        key = "ca_high" if row.get("severity") == "high" else "ca_review"
        groups[token][key] = int(groups[token][key]) + 1

    for row in prep_rows:
        token = group_tokens.get(row.get("source_group", "").strip(), "")
        groups[token]["prep_findings"] = int(groups[token]["prep_findings"]) + 1

    for row in quality_rows:
        token = group_tokens.get(row.get("source_group", "").strip(), "")
        key = "quality_high" if row.get("severity") == "high" else "quality_review"
        groups[token][key] = int(groups[token][key]) + 1

    output_rows: list[dict[str, str]] = []
    for token in sorted(groups):
        bucket = groups[token]
        stable_ids = bucket["stable_ids"]
        assert isinstance(stable_ids, set)
        output_rows.append(
            {
                "group_token": token or "GROUP000",
                "documents": str(bucket["documents"]),
                "unique_stable_faculty_ids": str(len(stable_ids)),
                "ca_high": str(bucket["ca_high"]),
                "ca_review": str(bucket["ca_review"]),
                "prep_findings": str(bucket["prep_findings"]),
                "quality_high": str(bucket["quality_high"]),
                "quality_review": str(bucket["quality_review"]),
            }
        )
    output_rows.sort(key=lambda row: (-int(row["ca_high"]) - int(row["ca_review"]), row["group_token"]))
    return output_rows


def build_repeat_faculty_rows(
    ca_rows: list[dict[str, str]],
    document_index: dict[str, DocumentContext],
) -> list[dict[str, str]]:
    buckets: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "documents": set(),
            "terms": set(),
            "rules": Counter(),
            "ca_high": 0,
            "ca_review": 0,
        }
    )

    for row in ca_rows:
        context = document_index.get(row.get("document_id", ""))
        if context is None or not context.stable_faculty_id:
            continue
        bucket = buckets[context.stable_faculty_id]
        documents = bucket["documents"]
        terms = bucket["terms"]
        rules = bucket["rules"]
        assert isinstance(documents, set)
        assert isinstance(terms, set)
        assert isinstance(rules, Counter)
        documents.add(context.document_id)
        terms.add(context.term_label)
        rules[row.get("rule_id", "")] += 1
        key = "ca_high" if row.get("severity") == "high" else "ca_review"
        bucket[key] = int(bucket[key]) + 1

    rows: list[dict[str, str]] = []
    for stable_faculty_id, bucket in buckets.items():
        documents = bucket["documents"]
        terms = bucket["terms"]
        rules = bucket["rules"]
        assert isinstance(documents, set)
        assert isinstance(terms, set)
        assert isinstance(rules, Counter)
        rows.append(
            {
                "stable_faculty_id": stable_faculty_id,
                "documents_with_ca_findings": str(len(documents)),
                "ca_high": str(bucket["ca_high"]),
                "ca_review": str(bucket["ca_review"]),
                "distinct_terms": str(len(terms)),
                "distinct_rules": str(len(rules)),
                "rule_ids": ", ".join(rule_id for rule_id, _ in rules.most_common()),
            }
        )

    rows.sort(key=lambda row: (-int(row["ca_high"]) - int(row["ca_review"]), -int(row["distinct_terms"]), row["stable_faculty_id"]))
    return rows


def build_faculty_longitudinal_rows(
    summary_rows: list[dict[str, str]],
    ca_rows: list[dict[str, str]],
    quality_rows: list[dict[str, str]],
    document_index: dict[str, DocumentContext],
) -> list[dict[str, str]]:
    ca_counts = Counter()
    quality_counts = Counter()
    for row in ca_rows:
        context = document_index.get(row.get("document_id", ""))
        if context is not None and context.stable_faculty_id:
            ca_counts[context.stable_faculty_id] += 1
    for row in quality_rows:
        context = document_index.get(row.get("document_id", ""))
        if context is not None and context.stable_faculty_id:
            quality_counts[context.stable_faculty_id] += 1

    buckets: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "documents": 0,
            "terms": set(),
            "term_keys": [],
            "assigned_tch": [],
            "total_workload": [],
            "preps": [],
        }
    )

    for row in summary_rows:
        stable_id = row.get("stable_faculty_id", "").strip()
        if not stable_id:
            continue
        context = document_index[row["document_id"]]
        bucket = buckets[stable_id]
        bucket["documents"] = int(bucket["documents"]) + 1
        terms = bucket["terms"]
        term_keys = bucket["term_keys"]
        assigned_tch = bucket["assigned_tch"]
        total_workload = bucket["total_workload"]
        preps = bucket["preps"]
        assert isinstance(terms, set)
        assert isinstance(term_keys, list)
        assert isinstance(assigned_tch, list)
        assert isinstance(total_workload, list)
        assert isinstance(preps, list)
        terms.add(context.term_label)
        term_keys.append(term_sort_tuple(context.academic_year, context.term))
        append_if_number(assigned_tch, row.get("assigned_teaching_contact_hours_week", ""))
        append_if_number(total_workload, row.get("total_this_period_swf", ""))
        append_if_number(preps, row.get("number_of_course_preparations", ""))

    rows: list[dict[str, str]] = []
    for stable_id, bucket in buckets.items():
        term_keys = bucket["term_keys"]
        assert isinstance(term_keys, list)
        rows.append(
            {
                "stable_faculty_id": stable_id,
                "documents": str(bucket["documents"]),
                "distinct_terms": str(len(bucket["terms"])),
                "first_term": format_term_sort_tuple(min(term_keys)) if term_keys else "Unknown",
                "last_term": format_term_sort_tuple(max(term_keys)) if term_keys else "Unknown",
                "avg_assigned_tch_week": format_average(bucket["assigned_tch"]),
                "max_assigned_tch_week": format_max(bucket["assigned_tch"]),
                "avg_total_workload_week": format_average(bucket["total_workload"]),
                "max_total_workload_week": format_max(bucket["total_workload"]),
                "max_preps": format_max(bucket["preps"]),
                "ca_findings": str(ca_counts[stable_id]),
                "quality_findings": str(quality_counts[stable_id]),
            }
        )

    rows.sort(
        key=lambda row: (
            -int(row["documents"]),
            -parse_number(row["ca_findings"]),
            row["stable_faculty_id"],
        )
    )
    return rows


def build_course_rollup_rows(
    course_rows: list[dict[str, str]],
    ca_rows: list[dict[str, str]],
    document_index: dict[str, DocumentContext],
) -> list[dict[str, str]]:
    ca_by_document = defaultdict(list)
    for row in ca_rows:
        ca_by_document[row.get("document_id", "")].append(row)

    buckets: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "assignment_rows": 0,
            "documents": set(),
            "stable_ids": set(),
            "terms": set(),
            "ca_docs": set(),
            "high_ca_docs": set(),
            "contact_hours": [],
        }
    )

    for row in course_rows:
        course_code = row.get("course_code", "").strip()
        if not course_code:
            continue
        bucket = buckets[course_code]
        bucket["assignment_rows"] = int(bucket["assignment_rows"]) + 1
        documents = bucket["documents"]
        stable_ids = bucket["stable_ids"]
        terms = bucket["terms"]
        ca_docs = bucket["ca_docs"]
        high_ca_docs = bucket["high_ca_docs"]
        contact_hours = bucket["contact_hours"]
        assert isinstance(documents, set)
        assert isinstance(stable_ids, set)
        assert isinstance(terms, set)
        assert isinstance(ca_docs, set)
        assert isinstance(high_ca_docs, set)
        assert isinstance(contact_hours, list)
        document_id = row.get("document_id", "")
        documents.add(document_id)
        stable_id = row.get("stable_faculty_id", "").strip() or row.get("faculty_token", "").strip()
        if stable_id:
            stable_ids.add(stable_id)
        context = document_index.get(document_id)
        if context is not None:
            terms.add(context.term_label)
        if document_id in ca_by_document:
            ca_docs.add(document_id)
            if any(finding.get("severity") == "high" for finding in ca_by_document[document_id]):
                high_ca_docs.add(document_id)
        append_if_number(contact_hours, row.get("contact_hours", ""))

    rows: list[dict[str, str]] = []
    for course_code, bucket in buckets.items():
        rows.append(
            {
                "course_code": course_code,
                "assignment_rows": str(bucket["assignment_rows"]),
                "documents": str(len(bucket["documents"])),
                "unique_stable_faculty_ids": str(len(bucket["stable_ids"])),
                "distinct_terms": str(len(bucket["terms"])),
                "documents_with_ca_findings": str(len(bucket["ca_docs"])),
                "documents_with_high_ca_findings": str(len(bucket["high_ca_docs"])),
                "avg_contact_hours": format_average(bucket["contact_hours"]),
                "max_contact_hours": format_max(bucket["contact_hours"]),
            }
        )

    rows.sort(
        key=lambda row: (
            -int(row["assignment_rows"]),
            -int(row["documents_with_ca_findings"]),
            row["course_code"],
        )
    )
    return rows


def build_failure_summary_rows(failure_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    counter = Counter()
    for row in failure_rows:
        counter[classify_error(row.get("error", ""))] += 1
    return [
        {"error_class": error_class, "count": str(count)}
        for error_class, count in counter.most_common()
    ]


def render_summary_markdown(
    *,
    summary_rows: list[dict[str, str]],
    course_rows: list[dict[str, str]],
    complementary_rows: list[dict[str, str]],
    ca_rows: list[dict[str, str]],
    prep_rows: list[dict[str, str]],
    quality_rows: list[dict[str, str]],
    failure_rows: list[dict[str, str]],
    term_overview_rows: list[dict[str, str]],
    group_rows: list[dict[str, str]],
    repeat_faculty_rows: list[dict[str, str]],
    course_rollup_rows: list[dict[str, str]],
) -> str:
    lines = ["# Multi-Year Bank Analysis", ""]
    lines.append(f"Processed SWFs: {len(summary_rows)}")
    lines.append(f"Course rows: {len(course_rows)}")
    lines.append(f"Complementary rows: {len(complementary_rows)}")
    lines.append(f"CA findings: {len(ca_rows)}")
    lines.append(f"Prep findings: {len(prep_rows)}")
    lines.append(f"Quality findings: {len(quality_rows)}")
    lines.append(f"Processing failures: {len(failure_rows)}")
    lines.append("")

    lines.append("## Term Overview")
    for row in top_rows(term_overview_rows, 9):
        lines.append(
            f"- `{row['term_label']}`: `{row['documents']}` docs, `{row['unique_stable_faculty_ids']}` stable IDs, "
            f"`{row['ca_high']}` high CA, `{row['ca_review']}` review CA, `{row['quality_high']}` high quality, "
            f"`{row['quality_review']}` review quality"
        )
    lines.append("")

    lines.append("## Top Group Tokens By CA Findings")
    for row in top_rows(sorted(group_rows, key=lambda item: (-int(item["ca_high"]) - int(item["ca_review"]), item["group_token"])), 10):
        lines.append(
            f"- `{row['group_token']}`: `{row['documents']}` docs, `{row['ca_high']}` high CA, "
            f"`{row['ca_review']}` review CA, `{row['quality_high']}` high quality, `{row['quality_review']}` review quality"
        )
    lines.append("")

    lines.append("## Repeat Flagged Stable IDs")
    for row in top_rows(repeat_faculty_rows, 10):
        lines.append(
            f"- `{row['stable_faculty_id']}`: `{row['documents_with_ca_findings']}` flagged docs across "
            f"`{row['distinct_terms']}` terms, `{row['ca_high']}` high and `{row['ca_review']}` review findings"
        )
    lines.append("")

    lines.append("## Top Course Codes")
    for row in top_rows(course_rollup_rows, 10):
        lines.append(
            f"- `{row['course_code']}`: `{row['assignment_rows']}` assignment rows, "
            f"`{row['unique_stable_faculty_ids']}` stable IDs, `{row['documents_with_ca_findings']}` docs with CA findings"
        )
    lines.append("")

    lines.append("## Notes")
    lines.append("- Group identifiers are tokenized as `GROUP###` in this analysis output.")
    lines.append("- Faculty are identified only by `stable_faculty_id` and `FAC###` tokens.")
    return "\n".join(lines) + "\n"


def classify_term(period_start: str, issued_date: str) -> tuple[str, str]:
    date_value = parse_date(period_start) or parse_date(issued_date)
    if date_value is None:
        return "Unknown", "Unknown"
    year = date_value.year
    month = date_value.month
    if month >= 9:
        return f"{year}-{year + 1}", "Fall"
    if month <= 4:
        return f"{year - 1}-{year}", "Winter"
    return f"{year - 1}-{year}", "Summer"


def parse_date(raw_value: str) -> datetime | None:
    cleaned = raw_value.strip()
    if not cleaned:
        return None
    try:
        return datetime.strptime(cleaned.title(), "%d-%b-%Y")
    except ValueError:
        return None


def sort_term_key(item: tuple[str, str]) -> tuple[int, int, int]:
    return term_sort_tuple(item[0], item[1])


def term_sort_tuple(academic_year: str, term: str) -> tuple[int, int, int]:
    if academic_year == "Unknown":
        return (9999, 9999, TERM_ORDER.get(term, 4))
    start_year = int(academic_year.split("-", 1)[0])
    return (start_year, TERM_ORDER.get(term, 4), 0)


def format_term_sort_tuple(value: tuple[int, int, int]) -> str:
    start_year = value[0]
    if start_year == 9999:
        return "Unknown"
    term = next((name for name, order in TERM_ORDER.items() if order == value[1]), "Unknown")
    return f"{start_year}-{start_year + 1} {term}"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def append_if_number(values: object, raw_value: str) -> None:
    if not isinstance(values, list):
        return
    parsed = parse_number(raw_value)
    if parsed is not None:
        values.append(parsed)


def parse_number(raw_value: str) -> float | None:
    cleaned = raw_value.strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def format_average(values: object) -> str:
    if not isinstance(values, list) or not values:
        return ""
    return format_number(sum(values) / len(values))


def format_max(values: object) -> str:
    if not isinstance(values, list) or not values:
        return ""
    return format_number(max(values))


def format_number(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".") if value % 1 else f"{value:.0f}"


def classify_error(error: str) -> str:
    lowered = error.lower()
    if "document stream is empty" in lowered:
        return "empty_pdf_stream"
    if "may not be a pdf file" in lowered or "couldn't read xref table" in lowered:
        return "malformed_pdf"
    return "other"


def top_rows(rows: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    return rows[:limit]
