# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Bumped the PyPI development-status classifier from Alpha to Beta
- `mypy` now runs in CI and pre-commit; the plugin stores its instance on `config.stash` (typed `StashKey`) instead of an ad-hoc `config._test_observer` attribute
- Unit tests moved from the `pre-commit` hook to `pre-push`, so committing stays fast (formatting, lint and type-check still run on commit)

## [0.2.0] - 2026-06-13

### Added

- Custom events: record diagnostic key/value events from a test with the new `record_event` fixture, written to a companion `{ch_table}_events` table, buffered to disk on failure and replayable like result rows. Off by default — enable with `--custom-events=true` (or env / `pyproject.toml`)
- "Events for this test" panel on the test-detail Grafana dashboard
- "Cross-run flaky tests" panel on the overview dashboard
- `unknown` test status surfaced in the dashboard status breakdowns

### Changed

- Replay type-matching is now whitespace-robust and raises on an unregistered column type instead of silently backfilling an empty string
- Reworked the README install instructions (unpinned, `pip` and `uv` shown together) and added a Custom events section
- Slimmed the custom-events example to a few deterministic cases

### Fixed

- Schema migration no longer treats `String` vs `LowCardinality(String)` / `Nullable(...)` as incompatible — these are insert-compatible in ClickHouse, and the old behavior aborted every flush against such tables
- Overview run-duration stats (median / p90 / pipeline) no longer skewed by rows with a missing start time

### Security

- `ch_table` is validated as a plain SQL identifier before interpolation into `CREATE` / `ALTER` DDL

## [0.1.1] - 2026-05-23

### Added

- PyPI classifiers to `pyproject.toml` (license, Python versions, `Framework :: Pytest`)
- New widgets to the Grafana overview dashboard
- Smoke replay tests for better integration coverage
- Pre-commit hooks with `ruff` for linting and formatting
- `SECURITY.md` with vulnerability reporting policy
- `CODE_OF_CONDUCT.md`
- GitHub issue templates

### Fixed

- CI workflow permissions for publish and test jobs

## [0.1.0] - 2026-05-17

### Added

- Initial implementation of the pytest plugin
- ClickHouse integration for storing test execution events
- Allure optional integration (`allure-pytest`)
- Grafana overview dashboard
- `pytest11` entry point registration

[0.2.0]: https://github.com/shakhov-dmitrii/pytest-test-observer/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/shakhov-dmitrii/pytest-test-observer/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/shakhov-dmitrii/pytest-test-observer/releases/tag/v0.1.0
