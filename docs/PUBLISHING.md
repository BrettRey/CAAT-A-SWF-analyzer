# Publishing

This repo is set up for GitHub-based Trusted Publishing to PyPI.

## Current state

- Package name: `caat-a-swf-analyzer`
- GitHub release: `v0.1.0`
- Publishing workflow: `.github/workflows/publish-pypi.yml`
- GitHub environment: `pypi`

## One-time PyPI setup

Create the `caat-a-swf-analyzer` project on PyPI, then add a Trusted Publisher for:

- Owner: `BrettRey`
- Repository: `CAAT-A-SWF-analyzer`
- Workflow file: `.github/workflows/publish-pypi.yml`
- Environment: `pypi`

This matches PyPI's Trusted Publishing flow for GitHub Actions using OIDC.

## Publish flow

1. Update `CHANGELOG.md` and bump `version` in `pyproject.toml`.
2. Commit and push to `main`.
3. Create a GitHub release tag such as `v0.1.1`.
4. Publish the GitHub release.
5. GitHub Actions builds the sdist/wheel and uploads them to PyPI.

You can also trigger the same workflow manually from the Actions tab with `workflow_dispatch`.

## Local verification before release

```bash
python3.11 -m unittest discover -s tests -v
python3.11 -m build
python3.11 -m twine check dist/*.whl dist/*.tar.gz
```

## Notes

- No PyPI API token is stored in the repo or expected in GitHub secrets.
- Trusted Publishing requires the PyPI-side publisher configuration before the workflow can succeed.
- Until that exists, the workflow will build successfully and fail only at the publish step.
