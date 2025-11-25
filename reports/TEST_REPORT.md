# Test Report

- **Date**: 2025-11-25
- **Command**: `python -m pytest --cov=app --cov-config=.coveragerc --cov-report=term-missing --cov-report=xml`
- **Result**: 31 tests passed in ~2.2s.
- **Coverage**: 85% line coverage for `app` (see `reports/coverage.xml`).

## Notes
- Coverage excludes the Azure-specific Uvicorn entrypoint (`app/server.py`).
- Network-bound WGER adapter functions are marked `# pragma: no cover`; associated helpers are unit-tested via `tests/test_external.py`.
- Rerun the command above before each release to refresh `reports/coverage.xml`.
