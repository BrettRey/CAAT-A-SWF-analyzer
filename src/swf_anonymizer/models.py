from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class ExtractionResult:
    source_path: Path
    source_type: str
    method: str
    text: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class AnonymizationResult:
    text: str
    aliases: dict[str, str]
    primary_token: str | None = None
    stable_faculty_id: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class ProcessResult:
    source_path: Path
    extracted_path: Path
    anonymized_path: Path
    extraction_method: str
    primary_token: str | None = None
    stable_faculty_id: str | None = None
    source_group: str = ""


@dataclass(slots=True)
class StructuredDocument:
    document_id: str
    faculty_token: str
    source_type: str
    extraction_method: str
    stable_faculty_id: str = ""
    source_group: str = ""
    period_start: str = ""
    period_end: str = ""
    issued_date: str = ""
    program_group: str = ""
    probationary_status: str = ""
    employment_status: str = ""
    category: str = ""
    overtime_workload_hours: str = ""
    course_rows: list[dict[str, str]] = field(default_factory=list)
    complementary_rows: list[dict[str, str]] = field(default_factory=list)
    summary_row: dict[str, str] = field(default_factory=dict)
