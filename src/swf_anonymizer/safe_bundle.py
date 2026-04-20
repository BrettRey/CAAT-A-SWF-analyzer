from __future__ import annotations

import argparse
import csv
import re
import shutil
from pathlib import Path


SAFE_README = """# LLM Safe Workspace

This directory is intended to be the only workspace exposed to an LLM.

Included:
- `anonymized/`
- sanitized `csv/`
- sanitized `reports/`

Excluded:
- raw SWFs
- extracted non-anonymized text
- the reversible key map
- local persistent state such as `.swf_state/`

Notes:
- `source_group` values are pseudonymized in this workspace as `GROUP###`.
- This workspace is only LLM-safe if the LLM session cannot also read the raw repository.

Open future Codex/LLM sessions in this directory, not in the source repository that contains `input/`, `output/extracted/`, or `output/keys/`.
"""

GROUP_FIELDS = {"source_group", "current_source_group", "previous_source_group"}
PRESERVED_GROUP_VALUES = {"", "ALL", "(root)"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create an LLM-safe workspace containing anonymized outputs only."
    )
    parser.add_argument(
        "--source-output",
        default="output",
        help="Path to the source output directory containing anonymized/, csv/, and reports/.",
    )
    parser.add_argument(
        "--dest",
        default="llm_safe_workspace",
        help="Destination directory for the safe workspace.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing non-empty destination directory.",
    )
    return parser.parse_args()


def copy_required_tree(source_root: Path, dest_root: Path, relative: str) -> None:
    source = source_root / relative
    if not source.exists():
        return
    shutil.copytree(source, dest_root / relative)


def validate_destination(source_root: Path, dest_root: Path) -> None:
    if source_root == dest_root:
        raise ValueError("Destination cannot be the same path as the source output directory.")

    if is_relative_to(dest_root, source_root) or is_relative_to(source_root, dest_root):
        raise ValueError("Destination cannot be inside the source output directory or contain it.")

    dangerous_roots = {Path("/").resolve(), Path.home().resolve()}
    if dest_root in dangerous_roots:
        raise ValueError("Destination is too broad; choose a dedicated workspace directory.")


def prepare_destination(dest_root: Path, force: bool) -> None:
    if dest_root.exists():
        if not dest_root.is_dir():
            raise ValueError("Destination exists and is not a directory.")
        if any(dest_root.iterdir()):
            if not force:
                raise ValueError("Destination exists and is not empty. Re-run with --force to overwrite it.")
            shutil.rmtree(dest_root)
        else:
            shutil.rmtree(dest_root)
    dest_root.mkdir(parents=True, exist_ok=True)


def is_relative_to(path: Path, other: Path) -> bool:
    try:
        path.relative_to(other)
        return True
    except ValueError:
        return False


def build_group_mapping(source_root: Path) -> dict[str, str]:
    groups: set[str] = set()
    for csv_path in list((source_root / "csv").glob("*.csv")) + list((source_root / "reports").glob("*.csv")):
        if not csv_path.exists():
            continue
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                for field in GROUP_FIELDS:
                    value = row.get(field, "").strip()
                    if value and value not in PRESERVED_GROUP_VALUES:
                        groups.add(value)

    return {
        group_name: f"GROUP{index:03d}"
        for index, group_name in enumerate(sorted(groups), start=1)
    }


def sanitize_csv_tree(source_root: Path, dest_root: Path, relative: str, group_mapping: dict[str, str]) -> None:
    source_dir = source_root / relative
    if not source_dir.exists():
        return

    target_dir = dest_root / relative
    target_dir.mkdir(parents=True, exist_ok=True)

    for csv_path in sorted(source_dir.glob("*.csv")):
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = list(reader.fieldnames or [])
            rows = list(reader)

        sanitized_rows = [sanitize_csv_row(row, group_mapping) for row in rows]

        target_path = target_dir / csv_path.name
        with target_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(sanitized_rows)


def sanitize_csv_row(row: dict[str, str], group_mapping: dict[str, str]) -> dict[str, str]:
    sanitized = dict(row)
    for field in GROUP_FIELDS:
        if field in sanitized:
            sanitized[field] = sanitize_group_value(sanitized[field], group_mapping)
    return sanitized


def sanitize_markdown_tree(source_root: Path, dest_root: Path, relative: str, group_mapping: dict[str, str]) -> None:
    source_dir = source_root / relative
    if not source_dir.exists():
        return

    target_dir = dest_root / relative
    target_dir.mkdir(parents=True, exist_ok=True)
    replacements = [
        (raw_value, token)
        for raw_value, token in sorted(group_mapping.items(), key=lambda item: len(item[0]), reverse=True)
    ]

    for markdown_path in sorted(source_dir.glob("*.md")):
        text = markdown_path.read_text(encoding="utf-8")
        for raw_value, token in replacements:
            text = re.sub(re.escape(raw_value), token, text)
        (target_dir / markdown_path.name).write_text(text, encoding="utf-8")


def sanitize_group_value(value: str, group_mapping: dict[str, str]) -> str:
    cleaned = value.strip()
    if cleaned in PRESERVED_GROUP_VALUES:
        return cleaned
    return group_mapping.get(cleaned, cleaned)


def main() -> int:
    args = parse_args()
    source_root = Path(args.source_output).expanduser().resolve()
    dest_root = Path(args.dest).expanduser().resolve()
    validate_destination(source_root, dest_root)
    group_mapping = build_group_mapping(source_root)

    prepare_destination(dest_root, args.force)

    copy_required_tree(source_root, dest_root, "anonymized")
    sanitize_csv_tree(source_root, dest_root, "csv", group_mapping)
    sanitize_csv_tree(source_root, dest_root, "reports", group_mapping)
    sanitize_markdown_tree(source_root, dest_root, "reports", group_mapping)

    (dest_root / "README.md").write_text(SAFE_README, encoding="utf-8")
    print(f"Safe workspace written to {dest_root}")
    return 0
