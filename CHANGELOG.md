# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.1.1]: https://github.com/shakhov-dmitrii/pytest-test-observer/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/shakhov-dmitrii/pytest-test-observer/releases/tag/v0.1.0
