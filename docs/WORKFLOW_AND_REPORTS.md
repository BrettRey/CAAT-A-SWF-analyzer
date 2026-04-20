# Workflow And Reports

## Purpose

This tool processes SWFs locally, anonymizes them, and produces structured outputs that can be reviewed without exposing faculty names to an LLM.

## Execution Modes

- `python3.11 src/swf.py ...` runs the batch pipeline directly.
- `python3.11 src/swf_workflow.py` runs the guided wrapper and prompts for:
  - the current input path
  - the output directory
  - the persistent state directory
  - whether to compare against a previous output directory

## Stable IDs

There are now two identity fields in structured outputs:

- `faculty_token`: the visible anonymized token used in text and filenames, such as `FAC031`
- `stable_faculty_id`: the comparison key, such as `FID4A9C...`

`stable_faculty_id` is the field to use for term-to-term comparison. It is derived from local aliases using a salted hash stored in `.swf_state/stable_ids.json`. Reuse the same `.swf_state/` across summer, fall, and winter runs to keep this ID stable.

## Source Group / Associate Dean Breakdown

Each processed file now records `source_group`, taken from the input file's parent folder name. If the input tree is organized by Associate Dean or sender, reports automatically break down that way.

Example:

- `input/associate-dean-a/Some SWF.pdf` → `source_group = associate-dean-a`
- `input/associate-dean-b/Some SWF.pdf` → `source_group = associate-dean-b`

## Output Reports

`output/reports/` now includes:

- `ca_findings.csv` and `.md`: rule-based CA findings
- `prep_type_findings.csv` and `.md`: prep-code/factor mismatches
- `quality_findings.csv` and `.md`: missing dates, incomplete summaries, and other parsing issues
- `source_group_summary.csv` and `.md`: counts and findings grouped by `source_group`
- `comparison_summary.md`: cross-run summary when `--compare-output` is supplied
- `comparison_faculty_summary.csv`: one row per `stable_faculty_id`
- `comparison_course_changes.csv`: added/removed/changed course rows by `stable_faculty_id` and `course_code`

## Recommended Workflow

1. Run the new term with the same `.swf_state/` used for prior terms.
2. Point `--compare-output` at the earlier term's `output/` directory.
3. Review `source_group_summary.*` first for high-level triage.
4. Review `quality_findings.*` before trusting absence of CA findings.
5. Use `comparison_faculty_summary.csv` and `comparison_course_changes.csv` for term-to-term review.
6. If exporting an LLM-facing workspace, use `python3.11 src/swf_safe_bundle.py --source-output output --dest llm_safe_workspace`; that export pseudonymizes `source_group` values as `GROUP###` and refuses to overwrite an existing non-empty destination unless you pass `--force`.
