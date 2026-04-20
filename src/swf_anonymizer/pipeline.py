from __future__ import annotations

from pathlib import Path

from .anonymizer import anonymize_text
from .ca_checker import write_ca_reports
from .csv_export import write_csv_exports
from .extraction import extract_text
from .keymap import KeyMap
from .models import ProcessResult
from .output import build_safe_output_path, local_output_name, write_text
from .prep_type_checker import write_prep_type_reports
from .stable_ids import StableFacultyIds
from .structured import parse_structured_document
from .group_reports import write_group_reports
from .comparison import write_comparison_reports
from .quality_checker import write_quality_reports


def process_paths(
    inputs: list[Path],
    output_root: Path,
    force_ocr: bool = False,
    min_chars_per_page: int = 250,
    state_root: Path | None = None,
    compare_output_root: Path | None = None,
) -> list[ProcessResult]:
    if state_root is None:
        keymap_path = output_root / "keys" / "keymap.json"
        stable_ids_path = output_root / "keys" / "stable_ids.json"
    else:
        keymap_path = state_root / "keymap.json"
        stable_ids_path = state_root / "stable_ids.json"
    keymap = KeyMap.load(keymap_path)
    stable_ids = StableFacultyIds.load(stable_ids_path)
    results: list[ProcessResult] = []
    structured_documents = []

    extracted_dir = output_root / "extracted"
    anonymized_dir = output_root / "anonymized"
    extracted_dir.mkdir(parents=True, exist_ok=True)
    anonymized_dir.mkdir(parents=True, exist_ok=True)
    keymap_path.parent.mkdir(parents=True, exist_ok=True)

    for path in inputs:
        source_group = path.parent.name
        extraction = extract_text(path, force_ocr=force_ocr, min_chars_per_page=min_chars_per_page)
        extracted_path = extracted_dir / local_output_name(path)
        write_text(extracted_path, extraction.text)

        anonymized = anonymize_text(extraction.text, keymap, stable_ids=stable_ids)
        anonymized_path = build_safe_output_path(
            anonymized_dir,
            anonymized.text,
            anonymized.primary_token,
            path,
        )
        write_text(anonymized_path, anonymized.text)
        structured_documents.append(
            parse_structured_document(
                text=anonymized.text,
                document_id=anonymized_path.stem,
                faculty_token=anonymized.primary_token,
                stable_faculty_id=anonymized.stable_faculty_id,
                source_group=source_group,
                source_type=extraction.source_type,
                extraction_method=extraction.method,
            )
        )

        results.append(
            ProcessResult(
                source_path=path,
                extracted_path=extracted_path,
                anonymized_path=anonymized_path,
                extraction_method=extraction.method,
                primary_token=anonymized.primary_token,
                stable_faculty_id=anonymized.stable_faculty_id,
                source_group=source_group,
            )
        )

    keymap.save()
    stable_ids.save()
    write_csv_exports(structured_documents, output_root)
    write_ca_reports(structured_documents, output_root)
    write_prep_type_reports(structured_documents, output_root)
    write_quality_reports(structured_documents, output_root)
    write_group_reports(structured_documents, output_root)
    if compare_output_root is not None:
        write_comparison_reports(output_root, compare_output_root)
    return results
