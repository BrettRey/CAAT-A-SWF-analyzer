# Evaluation Bundle

## Goal

Create a zip that can be shared with ChatGPT Pro or another evaluator without exposing raw SWFs, extracted raw text, anonymized batch outputs, or local identity state.

## Included In The Bundle

The evaluation bundle contains only code and documentation:

- root docs such as `README.md`, `AGENTS.md`, and `CLAUDE.md`
- `CHANGELOG.md`
- `src/`
- `tests/`
- `samples/`
- Markdown files under `docs/`

## Excluded From The Bundle

The bundle deliberately excludes:

- `input/`
- `output/`
- `.swf_state/`
- `llm_safe_workspace/`
- `.git/`
- generated binary/image folders such as `docs/*_images/`

That means the bundle contains no raw faculty files, no extracted raw text, no anonymized run outputs, and no reversible or persistent local identity state.

## Regenerate The Bundle

```bash
python3.11 src/swf_export_eval_bundle.py
```

Optional:

```bash
python3.11 src/swf_export_eval_bundle.py --output dist/my-eval-bundle.zip
python3.11 src/swf_export_eval_bundle.py --repo-root /path/to/repo --output /tmp/review.zip
```

Installed console script:

```bash
caat-a-swf-export-eval-bundle
```

## What The Evaluator Should Use

For evaluation, the external reviewer should look at:

- `README.md`
- `docs/WORKFLOW_AND_REPORTS.md`
- `src/swf_anonymizer/`
- `tests/`

If they need to understand the current CA checks, they can also read:

- `src/swf_anonymizer/ca_checker.py`
- `docs/2024_Academic_Collective_Agreement__EN_Signed.md`

## Important Limit

This bundle is safe for code and documentation review. It is not a substitute for the stricter `llm_safe_workspace/` workflow used when sharing anonymized run outputs.
