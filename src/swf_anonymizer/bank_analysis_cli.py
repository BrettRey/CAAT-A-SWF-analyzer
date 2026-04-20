from __future__ import annotations

import argparse
from pathlib import Path

from .bank_analysis import write_bank_analysis


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate token-only multi-year analysis tables from an existing SWF output directory."
    )
    parser.add_argument(
        "--output-root",
        default="output",
        help="Existing output directory containing csv/ and reports/ subdirectories.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_root = Path(args.output_root).expanduser().resolve()
    if not output_root.exists():
        print(f"Output root not found: {output_root}")
        return 1

    paths = write_bank_analysis(output_root)
    print(f"Analysis written to {output_root / 'analysis'}")
    for key, path in paths.items():
        print(f"{key}: {path}")
    return 0
