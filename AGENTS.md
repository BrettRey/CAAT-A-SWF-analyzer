# Repository Guidelines

## Project Structure & Module Organization
This repository is a local-only privacy tool for Standard Workload Form processing. Keep executable code in `src/swf_anonymizer/`, the batch CLI entrypoint in `src/swf.py`, the guided wrapper in `src/swf_workflow.py`, design notes in `docs/`, and synthetic examples in `samples/` or `tests/`. Use `input/` for raw SWFs, `.swf_state/` for persistent hashed identity state, and `output/` for extracted text, anonymized text, reports, and generated CSVs.

## Build, Test, and Development Commands
Target Python 3.11.

- `python3.11 -m venv .venv && source .venv/bin/activate` creates the local environment.
- `python3.11 src/swf.py input/*.pdf input/*.html --output output/ --state-dir .swf_state` runs the scriptable batch pipeline with stable IDs reused across runs.
- `python3.11 src/swf_workflow.py` launches the guided workflow that prompts for input paths, output paths, state reuse, and optional comparison to a previous run.
- `python3.11 src/swf_safe_bundle.py --source-output output --dest llm_safe_workspace --force` refreshes the LLM-facing workspace; omit `--force` to refuse overwriting a non-empty destination.
- `python3.11 src/swf_export_eval_bundle.py` creates a sanitized zip for external code review that excludes raw inputs, outputs, and local state.
- `python3.11 -m unittest discover -s tests -v` runs the synthetic regression suite.
- `git status --ignored` is useful here to confirm `input/` and sensitive `output/` paths remain untracked.

If you add new setup, lint, or test commands, update both this file and `README.md`.

## Coding Style & Naming Conventions
Use 4-space indentation and standard Python naming: `snake_case` for modules, functions, and variables, `PascalCase` for classes, and UPPER_CASE only for constants. Prefer small, composable functions for extraction, OCR fallback, and anonymization stages. Keep privacy-sensitive logic explicit and readable; avoid clever shortcuts that make redaction rules hard to audit. If you add formatters or linters, prefer common Python tools such as `black` and `ruff`.

## Testing Guidelines
Do not commit tests built from real faculty data. Put synthetic fixtures in `samples/` or `tests/fixtures/`. Name test files `test_<module>.py` and cover both success paths and privacy failures, especially missed redactions, stable ID reuse, HTML table extraction, OCR fallback behavior, and cross-run comparison logic.

## Commit & Pull Request Guidelines
This repository has no commit history yet, so establish a clean baseline: use short imperative commit subjects such as `Add OCR fallback scaffold`. Keep commits focused and mention privacy-impacting changes in the body. PRs should summarize behavior changes, list any new dependencies, and note how sensitive data was protected during testing. Include screenshots only for non-sensitive docs or UI work.

## Security & Data Handling
Never commit `input/`, `.swf_state/`, `output/extracted/`, `output/anonymized/`, or `output/keys/`. Never place real names or identifiers in docs, samples, tests, or commit messages. When in doubt, use synthetic placeholders such as `Jane Doe` or `[FAC001]`.
Treat `output/keys/keymap.json` as human-only. The LLM must not open it, use it to reverse tokens, or reveal real faculty names in analysis or responses. All LLM-facing analysis should use anonymized text, CSVs, and `FAC###` tokens only.
Treat `.swf_state/stable_ids.json` as local-only state as well. It contains only salted hashed aliases, but it still belongs on the raw side of the workflow.
For future sessions, prefer exporting `llm_safe_workspace/` with `python3.11 src/swf_safe_bundle.py --source-output output --dest llm_safe_workspace` and running the LLM there instead of in the repo root.
Be explicit about the limit: a copied subdirectory is not a security boundary by itself. Real protection requires the LLM to run in a separate restricted session that only has access to `llm_safe_workspace/` and cannot read `input/`, `output/extracted/`, `output/keys/`, or the raw repo root.
