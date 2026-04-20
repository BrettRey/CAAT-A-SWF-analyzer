from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path


PERIOD_PATTERN = re.compile(
    r"Period covered by SWF From:\s*(?P<start>\d{2}-[A-Z]{3}-\d{4})\s*To:\s*(?P<end>\d{2}-[A-Z]{3}-\d{4})"
)
ISSUED_DATE_PATTERN = re.compile(r"\bDate:\s*(?P<date>\d{2}-[A-Z]{3}-\d{4})\b")


def local_output_name(source_path: Path) -> str:
    suffix = source_path.suffix.lower().lstrip(".") or "txt"
    return f"{source_path.stem}.{suffix}.txt"


def build_safe_output_path(
    output_dir: Path,
    anonymized_text: str,
    primary_token: str | None,
    source_path: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = build_safe_stem(anonymized_text, primary_token, source_path)
    return output_dir / f"{stem}.txt"


def build_safe_stem(anonymized_text: str, primary_token: str | None, source_path: Path) -> str:
    parts = ["swf"]
    parts.append((primary_token or "document").lower())

    period = PERIOD_PATTERN.search(anonymized_text)
    if period:
        parts.append(convert_date_to_slug(period.group("start")))
        parts.append("to")
        parts.append(convert_date_to_slug(period.group("end")))

    issued = ISSUED_DATE_PATTERN.search(anonymized_text)
    if issued:
        parts.append("issued")
        parts.append(convert_date_to_slug(issued.group("date")))

    parts.append(source_hash(source_path))
    return "_".join(parts)


def convert_date_to_slug(raw_date: str) -> str:
    parsed = datetime.strptime(raw_date, "%d-%b-%Y")
    return parsed.strftime("%Y-%m-%d")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def source_hash(source_path: Path) -> str:
    digest = hashlib.sha1(str(source_path.resolve()).encode("utf-8")).hexdigest()
    return digest[:8]
