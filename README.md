# CAAT-A-SWF-analyzer

Local-only pipeline for extracting and anonymizing Humber Standard Workload Forms (SWFs) before any cloud LLM processing.

## The privacy constraint (hard)

Humber Faculty Union considers sending SWF PDFs to Anthropic, OpenAI, or any other cloud LLM a privacy violation. The workflow is therefore split:

- **Local only:** PDF/HTML/Markdown → extraction → anonymization → local key map
- **Cloud OK:** anonymized text only

The key file mapping anonymous IDs to real identities **never leaves this machine**, never gets committed to git, and should never be shared with a cloud tool.
Within this repo, treat `output/keys/keymap.json` as **human-only**. LLM analysis must not read it, reverse `FAC###` tokens, or expose faculty names; use anonymized outputs and tokens only.
The persistent state directory `.swf_state/` is also local-only. It now stores the hashed key map plus salted stable faculty IDs used for cross-run comparison.

## What is and is not protected

- `output/keys/keymap.json` no longer stores raw aliases in plaintext; persisted alias keys are hashed.
- The hash salt is stored in the same local JSON file, so this is a mitigation against casual disclosure on disk, not strong protection against an attacker who already has the file.
- This reduces accidental reverse lookup from disk, but it is **not** a complete security boundary if an LLM session can still read raw SWFs or raw extracted text.
- A true privacy boundary requires running the LLM in a separate restricted workspace that only contains anonymized outputs.

## Supported inputs

- `.pdf` via `pdftotext`, with OCR fallback through `pdftoppm` + `tesseract`
- `.html` / `.htm` via a table-aware HTML parser
- `.md` / `.txt` as pass-through text inputs for sidecar validation or local reprocessing

## Pipeline

1. **Ingest.** Drop SWFs into `input/` or point the CLI at explicit paths.
2. **Extract.** PDFs use text-layer extraction first; sparse PDFs fall back to OCR. HTML is converted to table-preserving text.
3. **Anonymize.** Replace faculty IDs, names, supervisor names, emails, phone numbers, SINs, and postal codes with stable tokens such as `[FAC001]` and `[PERSON001]`.
4. **Persist state.** Reuse `.swf_state/` across terms. It stores the hashed local key map plus salted stable faculty IDs so the same person keeps the same comparison ID across summer, fall, and winter runs.
5. **Write outputs.** Raw extracted text goes to `output/extracted/`. Safe anonymized text goes to `output/anonymized/` with non-identifying filenames such as `swf_fac001_2026-05-11_to_2026-06-27_issued_2026-03-16_ab12cd34.txt`.
6. **Export structured CSVs.** The CLI writes `output/csv/course_assignments.csv`, `output/csv/complementary_functions.csv`, and `output/csv/swf_summary.csv`. Each row includes `stable_faculty_id` and `source_group`.
7. **Write reports.** The tool writes CA findings, prep-type findings, parsing-quality findings, a source-group summary, and optional cross-run comparison reports under `output/reports/`.

## Directory layout

```
CAAT-A-SWF-analyzer/
├── README.md          (this file)
├── CLAUDE.md          (project guidance for Claude Code)
├── .gitignore         (keeps input/output out of git)
├── src/               (Python source)
├── samples/           (redacted / synthetic SWF samples for testing)
├── input/             (drop PDFs here — gitignored)
├── .swf_state/        (persistent hashed key map + stable IDs — gitignored)
├── output/
│   ├── extracted/     (raw local text — gitignored)
│   ├── anonymized/    (cloud-safe text — gitignored; optionally commit aggregated analysis only)
│   └── keys/          (anon-ID ↔ real identifier map — gitignored, never leaves this machine)
└── docs/              (notes, design docs)
```

## Requirements

- Python 3.11
- Poppler CLI tools: `pdftotext`, `pdfinfo`, `pdftoppm`
- `tesseract` available on `PATH` for OCR fallback

No third-party Python packages are required for the current implementation.

## Usage

```bash
python3.11 src/swf.py input/*.pdf input/*.html --output output --state-dir .swf_state
```

Guided workflow:

```bash
python3.11 src/swf_workflow.py
```

Installed console scripts:

```bash
caat-a-swf-analyzer ...
caat-a-swf-workflow
caat-a-swf-safe-bundle --source-output output --dest llm_safe_workspace
caat-a-swf-export-eval-bundle
caat-a-swf-analyze-bank --output-root output_dropbox_full
```

Optional flags:

- `--force-ocr` to OCR PDFs even when a text layer exists
- `--min-chars-per-page 250` to tune the sparse-text fallback threshold
- `--state-dir .swf_state` to reuse stable IDs across terms and comparisons
- `--compare-output /path/to/previous/output` to generate term-to-term comparison reports after a run

Generate token-only analysis tables from an existing output directory:

```bash
python3.11 src/swf_analyze_bank.py --output-root output_dropbox_full
```

## Additional documentation

- `docs/WORKFLOW_AND_REPORTS.md`: guided workflow, stable IDs, source-group breakdown, and report inventory
- `docs/EVALUATION_BUNDLE.md`: safe packaging rules for external code review
- `docs/PUBLISHING.md`: GitHub release and PyPI Trusted Publishing setup

## LLM-safe workspace

To make future LLM sessions unable to access raw SWFs, extracted raw text, or the reversible key map, create a separate workspace that contains only anonymized outputs:

```bash
python3.11 src/swf_safe_bundle.py --source-output output --dest llm_safe_workspace
```

Then start the LLM in `llm_safe_workspace/`, not in this repository root.
Within that export, `source_group` values are pseudonymized as `GROUP###` so parent-folder names are not exposed to the LLM.
The helper refuses to overwrite an existing non-empty destination unless you add `--force`.

Required operational rule:

1. Run extraction and anonymization in this repo.
2. Export `llm_safe_workspace/`.
3. Start the LLM in a separate session, container, or sandbox that mounts only `llm_safe_workspace/`.
4. Do not expose `input/`, `output/extracted/`, `output/keys/`, or the repo root to that LLM session.

Without step 3, `llm_safe_workspace/` is only a convenience copy, not a hard security boundary.

## Shareable Evaluation Bundle

To create a zip that contains only code and documentation, with no `input/`, `output/`, `.swf_state/`, or `llm_safe_workspace/` content:

```bash
python3.11 src/swf_export_eval_bundle.py
```

By default this writes `dist/caat-a-swf-analyzer-eval-YYYYMMDD.zip`.
If you use the installed console script instead of the repo checkout, run it from the repo root or pass `--repo-root /path/to/repo`.

## Testing

```bash
python3.11 -m unittest discover -s tests -v
```

Tests use synthetic strings and fixtures only. Do not commit real faculty data.

## CSV outputs

- `output/csv/course_assignments.csv`: one row per course assignment, suitable for pivoting by course code, faculty token, or SWF period
- `output/csv/complementary_functions.csv`: one row per complementary workload item
- `output/csv/swf_summary.csv`: one row per SWF with weekly totals, accumulated totals, section/preparation counts, `stable_faculty_id`, and `source_group`

## CA checks

- `output/reports/ca_findings.csv`: one row per detected Article 11 finding
- `output/reports/ca_findings.md`: human-readable summary of the same findings
- Current checks cover weekly workload maxima, weekly teaching contact maxima, preparation-count cap, minimum complementary allowance, annual contact-day limit, annual teaching-hour limit, annual teaching-week limit, and workload-overtime documentation where detectable from the SWF text
- `output/reports/prep_type_findings.csv`: review queue for mismatches between prep type codes (`NW`, `EA`, `EB`, `RA`, `RB`) and their expected factors/hours
- `output/reports/prep_type_findings.md`: human-readable summary of prep type findings
- `output/reports/quality_findings.csv`: parsing and completeness issues such as missing dates or incomplete summary rows
- `output/reports/source_group_summary.csv`: counts by parent folder, which works as an Associate Dean breakdown when the input tree is organized that way
- `output/reports/comparison_*.csv` and `comparison_summary.md`: optional prior-run comparison outputs keyed by `stable_faculty_id`
- `output/analysis/*.csv` and `summary.md`: token-only multi-year rollups by term, rule, course, group token, and `stable_faculty_id`

## Status

Working local CLI implemented for text PDFs, HTML exports, and text sidecars. Current anonymization is rule-based and tuned to the SWF layouts in `input/`; OCR support exists but has not yet been calibrated against poor-quality scans.

## License

This project is released under the MIT License. See `LICENSE`.

## Publishing

The repo includes:

- `.github/workflows/ci.yml` for tests and distribution checks on pushes and pull requests
- `.github/workflows/publish-pypi.yml` for Trusted Publishing to PyPI from GitHub Actions

Live PyPI publication still requires one PyPI-side setup step: configure `BrettRey/CAAT-A-SWF-analyzer` as a Trusted Publisher for the `caat-a-swf-analyzer` project using the workflow file `.github/workflows/publish-pypi.yml` and environment `pypi`.
