# CLAUDE.md — swf-anonymizer

## Role

Editor / Developer on a small local-only privacy tool. The whole reason this tool exists is that Humber Faculty Union will not allow SWF PDFs to be sent to cloud LLMs. Do not casually relax that constraint.

## Non-negotiables (privacy)

- **Never dispatch an agent that reads an input PDF or raw extracted text through a cloud LLM tool.** No WebFetch, no Anthropic API, no OpenAI API on pre-anonymisation material. Agents that need to reason about fields should work from *schema descriptions* or *synthetic/redacted samples*, not real SWFs.
- **Never commit `input/`, `.swf_state/`, `output/extracted/`, `output/anonymized/`, or `output/keys/`** to git. The `.gitignore` must enforce this.
- **Never include real faculty names in sample data, tests, commit messages, or documentation.** Use synthetic placeholders (Jane Doe, FAC001) everywhere.
- **If uncertain whether an action would send sensitive material to a cloud service, ask Brett before doing it.**

## Tech baseline

- Python 3.11 (matches `tools/pdf-to-md/`; pymupdf is installed there under 3.11)
- Current implementation uses `pdftotext`/`pdfinfo`/`pdftoppm` plus `tesseract`, keeping Python dependencies minimal
- Prefer rule-based anonymisation and deterministic parsing; local LLM (Ollama) only if clearly needed

## Build / run

```bash
python3.11 src/swf.py input/*.pdf input/*.html --output output/ --state-dir .swf_state
python3.11 src/swf_workflow.py
python3.11 src/swf_safe_bundle.py --source-output output --dest llm_safe_workspace --force
python3.11 src/swf_export_eval_bundle.py
python3.11 -m unittest discover -s tests -v
```

## State

- Working CLI implemented on 2026-04-19
- Handles text PDFs, HTML SWFs, and text sidecars; OCR fallback is wired in for sparse PDFs
- Local output file names for anonymized text are safe to share; extracted text and key maps remain local-only
- `.swf_state/` persists hashed key-map state plus stable faculty IDs for cross-term comparisons

## Related tools

- `tools/pdf-to-md/` — text extraction patterns worth reusing (pymupdf wrapper, heading detection)
- `tools/proofread-harness/` — different purpose but similar batch-over-PDF structure
