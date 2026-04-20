from __future__ import annotations

import re

from .keymap import KeyMap
from .models import AnonymizationResult
from .stable_ids import StableFacultyIds


EMPLOYEE_ID_PATTERN = re.compile(r"\bN\d{8}\b")
EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_PATTERN = re.compile(
    r"(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b"
)
SIN_PATTERN = re.compile(r"\b\d{3}[- ]?\d{3}[- ]?\d{3}\b")
POSTAL_CODE_PATTERN = re.compile(r"\b[ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z][ -]?\d[ABCEGHJ-NPRSTV-Z]\d\b", re.IGNORECASE)
LETTER = r"[^\W\d_]"
NAME_BODY_CHAR = rf"(?:{LETTER}|[.'’-])"
NAME_TOKEN = rf"{LETTER}{NAME_BODY_CHAR}*"
NAME_SIDE = rf"{NAME_TOKEN}(?: {NAME_TOKEN})*"
PERIOD_PATTERN = re.compile(
    r"Period covered by SWF From:\s*(?P<start>\d{2}-[A-Z]{3}-\d{4})\s*To:\s*(?P<end>\d{2}-[A-Z]{3}-\d{4})"
)
ISSUED_DATE_PATTERN = re.compile(r"\bDate:\s*(?P<date>\d{2}-[A-Z]{3}-\d{4})\b")


def anonymize_text(
    text: str,
    keymap: KeyMap,
    stable_ids: StableFacultyIds | None = None,
) -> AnonymizationResult:
    aliases_for_text: dict[str, str] = {}
    primary_token: str | None = None
    faculty_aliases: list[str] = []

    employee_ids = list(dict.fromkeys(EMPLOYEE_ID_PATTERN.findall(text)))
    if employee_ids:
        faculty_aliases.extend(employee_ids)
        primary_token = keymap.ensure_alias(employee_ids[0], "FAC")
        aliases_for_text[employee_ids[0]] = primary_token
        for employee_id in employee_ids[1:]:
            aliases_for_text[employee_id] = keymap.ensure_alias(employee_id, "FAC")

    teacher_name = find_teacher_name(text)
    if teacher_name:
        faculty_aliases.append(teacher_name)
        if primary_token is None:
            primary_token = keymap.ensure_alias(teacher_name, "FAC")
        else:
            keymap.link_alias(teacher_name, primary_token)
        aliases_for_text[teacher_name] = primary_token

    faculty_signature_name = find_labeled_person(text, "Faculty member's signature")
    if faculty_signature_name:
        faculty_aliases.append(faculty_signature_name)
        if primary_token is None:
            primary_token = keymap.ensure_alias(faculty_signature_name, "FAC")
        else:
            keymap.link_alias(faculty_signature_name, primary_token)
        aliases_for_text[faculty_signature_name] = primary_token

    stable_faculty_id = (
        stable_ids.resolve(faculty_aliases)
        if stable_ids is not None
        else primary_token
    )

    supervisor_name = find_labeled_person(text, "Supervisor's signature")
    if supervisor_name:
        aliases_for_text[supervisor_name] = keymap.ensure_alias(supervisor_name, "PERSON")

    for alias, token in keymap.aliases_present_in(text).items():
        if is_safe_alias_reuse(alias):
            aliases_for_text.setdefault(alias, token)

    text = apply_aliases(text, aliases_for_text)

    text, aliases_for_text = replace_pattern(text, EMAIL_PATTERN, "EMAIL", keymap, aliases_for_text)
    text, aliases_for_text = replace_pattern(text, PHONE_PATTERN, "PHONE", keymap, aliases_for_text)
    text, aliases_for_text = replace_pattern(text, SIN_PATTERN, "SIN", keymap, aliases_for_text)
    text, aliases_for_text = replace_pattern(text, POSTAL_CODE_PATTERN, "POSTAL", keymap, aliases_for_text)

    text = apply_aliases(text, aliases_for_text)

    metadata = {}
    period = PERIOD_PATTERN.search(text)
    if period:
        metadata["period_start"] = period.group("start")
        metadata["period_end"] = period.group("end")
    issued = ISSUED_DATE_PATTERN.search(text)
    if issued:
        metadata["issued_date"] = issued.group("date")

    return AnonymizationResult(
        text=text,
        aliases=dict(sorted(aliases_for_text.items())),
        primary_token=primary_token,
        stable_faculty_id=stable_faculty_id,
        metadata=metadata,
    )


def replace_pattern(
    text: str,
    pattern: re.Pattern[str],
    prefix: str,
    keymap: KeyMap,
    aliases_for_text: dict[str, str],
) -> tuple[str, dict[str, str]]:
    def replacement(match: re.Match[str]) -> str:
        raw_value = match.group(0)
        token = keymap.ensure_alias(raw_value, prefix)
        aliases_for_text[raw_value] = token
        return f"[{token}]"

    return pattern.sub(replacement, text), aliases_for_text


def apply_aliases(text: str, aliases: dict[str, str]) -> str:
    for raw_value, token in sorted(aliases.items(), key=lambda item: len(item[0]), reverse=True):
        text = re.sub(re.escape(raw_value), f"[{token}]", text)
    return text


def find_teacher_name(text: str) -> str | None:
    return find_labeled_person(text, "Teacher Name")


def find_labeled_person(text: str, label: str) -> str | None:
    patterns = [
        re.compile(
            rf"{re.escape(label)}:\s*(?:\|\s*)?(?P<value>{NAME_SIDE}, {NAME_SIDE})"
        ),
        re.compile(
            rf"{re.escape(label)}:\s*\n\s*(?P<value>{NAME_SIDE}, {NAME_SIDE})"
        ),
    ]
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group("value")
    return None


def is_safe_alias_reuse(alias: str) -> bool:
    return "," not in alias
