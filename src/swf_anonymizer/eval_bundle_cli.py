from __future__ import annotations

import argparse
from pathlib import Path

from .eval_bundle import create_eval_bundle, default_bundle_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a sanitized zip containing only code and documentation for external evaluation."
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root to package. Defaults to the current working directory.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional path for the output zip. Defaults to dist/caat-a-swf-analyzer-eval-YYYYMMDD.zip under repo-root.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).expanduser().resolve()
    output_path = Path(args.output).expanduser() if args.output else default_bundle_path(repo_root)
    bundle_path = create_eval_bundle(repo_root=repo_root, output_path=output_path)
    print(f"Evaluation bundle written to {bundle_path}")
    return 0
