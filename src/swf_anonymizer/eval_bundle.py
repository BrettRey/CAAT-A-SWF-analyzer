from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT_FILES = [
    ".gitignore",
    "CHANGELOG.md",
    "LICENSE",
    "pyproject.toml",
    "README.md",
    "AGENTS.md",
    "CLAUDE.md",
]

TREE_DIRS = [
    "src",
    "tests",
    "samples",
]

DOC_PATTERN = "docs/**/*.md"

EXCLUDED_DIR_NAMES = {
    ".git",
    ".swf_state",
    "input",
    "output",
    "llm_safe_workspace",
    "dist",
    "__pycache__",
}

EXCLUDED_FILE_NAMES = {
    ".DS_Store",
}

EXCLUDED_SUFFIXES = {
    ".pyc",
}


def default_bundle_path(repo_root: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d")
    return repo_root / "dist" / f"caat-a-swf-analyzer-eval-{stamp}.zip"


def create_eval_bundle(repo_root: Path, output_path: Path | None = None) -> Path:
    repo_root = repo_root.resolve()
    bundle_path = output_path.resolve() if output_path is not None else default_bundle_path(repo_root)
    bundle_path.parent.mkdir(parents=True, exist_ok=True)

    with ZipFile(bundle_path, "w", compression=ZIP_DEFLATED) as archive:
        for path in collect_bundle_paths(repo_root):
            archive.write(path, arcname=path.relative_to(repo_root).as_posix())
        archive.writestr("EVAL_BUNDLE_MANIFEST.txt", render_manifest(repo_root))

    return bundle_path


def collect_bundle_paths(repo_root: Path) -> list[Path]:
    repo_root = repo_root.resolve()
    selected: set[Path] = set()

    for relative_path in ROOT_FILES:
        path = repo_root / relative_path
        if path.is_file():
            selected.add(path)

    for relative_dir in TREE_DIRS:
        directory = repo_root / relative_dir
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            if path.is_file() and not should_exclude(path, repo_root):
                selected.add(path)

    for path in repo_root.glob(DOC_PATTERN):
        if path.is_file() and not should_exclude(path, repo_root):
            selected.add(path)

    return sorted(selected)


def should_exclude(path: Path, repo_root: Path) -> bool:
    relative = path.resolve().relative_to(repo_root.resolve())
    if any(part in EXCLUDED_DIR_NAMES or part.endswith(".egg-info") for part in relative.parts[:-1]):
        return True
    if relative.name in EXCLUDED_FILE_NAMES:
        return True
    if path.suffix in EXCLUDED_SUFFIXES:
        return True
    return False


def render_manifest(repo_root: Path) -> str:
    lines = [
        "CAAT-A-SWF-analyzer Evaluation Bundle",
        "",
        f"Bundle root: {repo_root.name}",
        "",
        "Included:",
        "- Root documentation files",
        "- CHANGELOG.md",
        "- src/",
        "- tests/",
        "- samples/",
        "- docs/**/*.md",
        "",
        "Excluded:",
        "- input/",
        "- output/",
        "- .swf_state/",
        "- llm_safe_workspace/",
        "- .git/",
        "- docs/*_images/",
        "",
        "Purpose:",
        "- Safe code and documentation review without raw SWFs, extracted text, anonymized run outputs, or local identity state.",
        "",
    ]
    return "\n".join(lines)
