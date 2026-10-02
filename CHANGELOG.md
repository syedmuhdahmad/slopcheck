# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Demo GIF in the README, recorded with VHS from `docs/demo/demo.tape` ([#24](https://github.com/syedmuhdahmad/slopfence/issues/24))
- `known-packages` config and `--known-packages` option: private packages that `SLOP001` accepts without a PyPI lookup, with glob support ([#15](https://github.com/syedmuhdahmad/slopfence/issues/15))
- `fail-on` config and `--fail-on` option to choose which severities fail the run ([#18](https://github.com/syedmuhdahmad/slopfence/issues/18))
- `check-imports` config and `--check-imports` / `--no-check-imports` options ([#34](https://github.com/syedmuhdahmad/slopfence/issues/34))
- `strict` config and `--strict` option: unparseable Python files exit with code 2. Parse errors are now also reported in SARIF as tool notifications, and JSON/SARIF use project-relative paths for them ([#19](https://github.com/syedmuhdahmad/slopfence/issues/19))

### Changed

- **Privacy:** `SLOP001` no longer sends import names from your source code to PyPI by default, because they can reveal private package names. Dependency files are still checked. Use `--check-imports` or `check-imports = true` to also look up imports. The README explains exactly what is sent ([#34](https://github.com/syedmuhdahmad/slopfence/issues/34))
- The source distribution only contains the package, tests and docs needed to build it (about 40 KB instead of 410 KB) ([#35](https://github.com/syedmuhdahmad/slopfence/issues/35))
- README no longer claims duplicate-helper detection, which isn't built yet ([#36](https://github.com/syedmuhdahmad/slopfence/issues/36))
- Colour output: rule IDs are coloured by severity, locations are dimmed, and the summary counts are coloured. Plain output (`--no-color`, pipes, files) is unchanged

### Fixed

- `SLOP010` false positives from "for demo purposes" in human-written docs. It now needs "only" or placeholder wording nearby, and demo/example code is skipped ([#20](https://github.com/syedmuhdahmad/slopfence/issues/20))

## [0.1.1] - 2026-10-02

### Fixed

- GitHub Action: install into a private virtualenv instead of the runner's system Python, which recent runners reject (PEP 668), and pick a Python 3.10+ interpreter (`python3` or `python`, so it also works on Windows) ([#13](https://github.com/syedmuhdahmad/slopfence/issues/13))
- Crash on Windows when a finding quotes non-ASCII text such as an emoji: output is now always UTF-8. The crash exited with code 1, the same as "issues found" ([#13](https://github.com/syedmuhdahmad/slopfence/issues/13))
- PyPI version and Python badges on the PyPI page ([#9](https://github.com/syedmuhdahmad/slopfence/pull/9))

### Added

- `[tool.slopfence]` configuration in `pyproject.toml` with `select`, `ignore` and `exclude` ([#10](https://github.com/syedmuhdahmad/slopfence/issues/10))
- `--exclude` option
- End-to-end CI tests for the GitHub Action (Linux, macOS, Windows, including SARIF upload to code scanning) and the pre-commit hook ([#13](https://github.com/syedmuhdahmad/slopfence/issues/13), [#14](https://github.com/syedmuhdahmad/slopfence/issues/14))

## [0.1.0] - 2026-10-02

### Added

- Published to PyPI as `slopfence` (the project was originally named slopcheck, but that PyPI name belongs to an unrelated project)
- `slopfence` CLI with `--diff`, `--format text|json|sarif`, `--select`, `--ignore`, `--offline` and `--exit-zero`
- `SLOP001`: dependencies and imports that don't exist on PyPI, with a local cache
- `SLOP010`: placeholder comments left in finished-looking code
- `SLOP020`: tests that only assert on their own mocks
- `SLOP021`: tests whose only assertions are always true
- `SLOP022`: tests whose assertions are swallowed by try/except
- `SLOP051`: leftover AI chat text in comments and docstrings
- `# slopfence: ignore[...]` and `# slopfence: ignore-file` directives
- GitHub Action (`action.yml`) and pre-commit hook

### Project setup

- Project README describing the problem, design principles, planned detectors and roadmap
- Community health files: Code of Conduct, Contributing guide, Security policy, Support, Governance
- Issue templates, pull request template, CODEOWNERS, Dependabot and CI

[Unreleased]: https://github.com/syedmuhdahmad/slopfence/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/syedmuhdahmad/slopfence/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/syedmuhdahmad/slopfence/releases/tag/v0.1.0
