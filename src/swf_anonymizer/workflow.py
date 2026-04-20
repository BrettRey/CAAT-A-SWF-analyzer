from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import process_paths


SUPPORTED_SUFFIXES = {".pdf", ".html", ".htm", ".md", ".txt"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Guided SWF workflow for extraction, anonymization, grouped reports, and optional prior-run comparison."
    )
    parser.add_argument("--input", help="Input file or directory. If omitted, the workflow prompts for it.")
    parser.add_argument("--output", help="Output directory. Default prompt value: output")
    parser.add_argument(
        "--state-dir",
        help="Persistent state directory for stable IDs and token reuse. Default prompt value: .swf_state",
    )
    parser.add_argument(
        "--compare-output",
        help="Previous output directory to compare against. Omit to skip comparison.",
    )
    parser.add_argument(
        "--recursive",
        dest="recursive",
        action="store_true",
        help="Recurse into input subfolders when the input is a directory.",
    )
    parser.add_argument(
        "--no-recursive",
        dest="recursive",
        action="store_false",
        help="Do not recurse into input subfolders when the input is a directory.",
    )
    parser.set_defaults(recursive=None)
    parser.add_argument(
        "--force-ocr",
        action="store_true",
        help="Force OCR for all PDF inputs.",
    )
    parser.add_argument(
        "--min-chars-per-page",
        type=int,
        default=None,
        help="Minimum extracted non-space characters per page before OCR fallback.",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Require all needed arguments on the command line instead of prompting.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_target = resolve_path(
        args.input or prompt_text("Input file or directory", "input", allow_blank=False),
    )
    if not input_target.exists():
        print(f"Input path not found: {input_target}")
        return 1

    if input_target.is_file():
        recursive = False
    else:
        recursive = args.recursive
        if recursive is None:
            recursive = True if args.non_interactive else prompt_bool("Recurse into subfolders", default=True)

    output_root = resolve_path(
        args.output or prompt_text("Output directory", "output", allow_blank=False),
    )
    state_root = resolve_path(
        args.state_dir or prompt_text("State directory for stable IDs", ".swf_state", allow_blank=False),
    )

    compare_output = args.compare_output
    if compare_output is None and not args.non_interactive:
        compare_output = prompt_text(
            "Previous output directory to compare against (leave blank to skip)",
            "",
            allow_blank=True,
        )
    compare_output_root = resolve_path(compare_output) if compare_output else None
    if compare_output_root is not None and not compare_output_root.exists():
        print(f"Previous output directory not found: {compare_output_root}")
        return 1

    force_ocr = args.force_ocr or (False if args.non_interactive else prompt_bool("Force OCR for all PDFs", default=False))
    if args.min_chars_per_page is not None:
        min_chars_per_page = args.min_chars_per_page
    elif args.non_interactive:
        min_chars_per_page = 250
    else:
        min_chars_per_page = prompt_int("Minimum text characters per PDF page before OCR fallback", 250)

    inputs = discover_inputs(input_target, recursive=recursive)
    if not inputs:
        print("No supported SWF inputs were found.")
        return 1

    print("")
    print(f"Processing {len(inputs)} input files.")
    print(f"Output directory: {output_root}")
    print(f"State directory: {state_root}")
    if compare_output_root is not None:
        print(f"Comparing against: {compare_output_root}")
    print("Stable IDs remain consistent when you reuse the same state directory across runs.")
    print("")

    results = process_paths(
        inputs=inputs,
        output_root=output_root,
        force_ocr=force_ocr,
        min_chars_per_page=min_chars_per_page,
        state_root=state_root,
        compare_output_root=compare_output_root,
    )

    print(f"Processed {len(results)} files.")
    print(f"CSV exports: {output_root / 'csv'}")
    print(f"Reports: {output_root / 'reports'}")
    if compare_output_root is not None:
        print(f"Comparison summary: {output_root / 'reports' / 'comparison_summary.md'}")
    print(f"Grouped summary: {output_root / 'reports' / 'source_group_summary.md'}")
    return 0


def discover_inputs(input_target: Path, recursive: bool) -> list[Path]:
    if input_target.is_file():
        return [input_target.resolve()] if input_target.suffix.lower() in SUPPORTED_SUFFIXES else []

    glob_pattern = "**/*" if recursive else "*"
    return sorted(
        path.resolve()
        for path in input_target.glob(glob_pattern)
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )


def prompt_text(prompt: str, default: str, allow_blank: bool) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        value = input(f"{prompt}{suffix}: ").strip()
        if value:
            return value
        if default:
            return default
        if allow_blank:
            return ""


def prompt_bool(prompt: str, default: bool) -> bool:
    default_label = "Y/n" if default else "y/N"
    while True:
        value = input(f"{prompt} [{default_label}]: ").strip().lower()
        if not value:
            return default
        if value in {"y", "yes"}:
            return True
        if value in {"n", "no"}:
            return False


def prompt_int(prompt: str, default: int) -> int:
    while True:
        value = input(f"{prompt} [{default}]: ").strip()
        if not value:
            return default
        try:
            return int(value)
        except ValueError:
            print("Enter a whole number.")


def resolve_path(raw_value: str) -> Path:
    return Path(raw_value).expanduser().resolve()
