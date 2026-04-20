# Changelog

## v0.1.1 - 2026-04-20

- add GitHub Actions CI for tests, builds, and distribution metadata checks
- add GitHub Actions Trusted Publishing workflow for PyPI releases
- add maintainer publishing documentation for the GitHub-to-PyPI release path
- fix publish-workflow permissions so distribution artifacts can be downloaded in the publish job
- verify the publish workflow reaches PyPI and fails only at the expected trusted-publisher configuration step

## v0.1.0 - 2026-04-20

- initial public release of the local-only CAAT-A SWF analyzer
- local PDF, HTML, Markdown, and text ingestion with OCR fallback for sparse PDFs
- deterministic anonymization with stable faculty tokens and cross-term stable IDs
- structured CSV exports for SWF summaries, course assignments, and complementary functions
- rule-based CA checks, prep-type checks, and parsing-quality reports
- token-only analysis exports for term, course, group, and repeated-pattern review
- safe-bundle and evaluation-bundle tooling for controlled sharing of anonymous outputs and code
