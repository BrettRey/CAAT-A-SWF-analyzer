from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import process_paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract and anonymize SWFs locally without sending raw content off-machine."
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="Input SWF files (.pdf, .html, .htm, .md, .txt).",
    )
    parser.add_argument(
        "--output",
        default="output",
        help="Root output directory for extracted text, anonymized text, and keys.",
    )
    parser.add_argument(
        "--state-dir",
        default=".swf_state",
        help="Persistent local state directory for stable faculty IDs and token reuse across runs.",
    )
    parser.add_argument(
        "--compare-output",
        default="",
        help="Optional previous output directory to compare against after the current run finishes.",
    )
    parser.add_argument(
        "--force-ocr",
        action="store_true",
        help="Use OCR even if the PDF has a text layer.",
    )
    parser.add_argument(
        "--min-chars-per-page",
        type=int,
        default=250,
        help="Minimum extracted non-space characters per PDF page before OCR fallback is triggered.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    inputs = [Path(item).expanduser().resolve() for item in args.inputs]
    output_root = Path(args.output).expanduser().resolve()
    state_root = Path(args.state_dir).expanduser().resolve()
    compare_output_root = Path(args.compare_output).expanduser().resolve() if args.compare_output else None

    results = process_paths(
        inputs=inputs,
        output_root=output_root,
        force_ocr=args.force_ocr,
        min_chars_per_page=args.min_chars_per_page,
        state_root=state_root,
        compare_output_root=compare_output_root,
    )

    for result in results:
        token = result.primary_token or "unassigned"
        print(
            f"{result.source_path.name} -> {result.anonymized_path.name} "
            f"[{result.extraction_method}, {token}]"
        )

    print(f"State written to {state_root}")
    print(f"CSV exports written to {output_root / 'csv'}")
    print(f"CA findings written to {output_root / 'reports'}")
    print(f"Prep type findings written to {output_root / 'reports'}")
    print(f"Quality findings written to {output_root / 'reports'}")
    print(f"Source-group summary written to {output_root / 'reports'}")
    if compare_output_root is not None:
        print(f"Comparison reports written to {output_root / 'reports'}")
    return 0
