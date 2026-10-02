# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-10-02

### Added

- `slopcheck` CLI with `--diff`, `--format text|json|sarif`, `--select`, `--ignore`, `--offline` and `--exit-zero`
- `SLOP001`: dependencies and imports that don't exist on PyPI, with a local cache
- `SLOP010`: placeholder comments left in finished-looking code
- `SLOP020`: tests that only assert on their own mocks
- `SLOP021`: tests whose only assertions are always true
- `SLOP022`: tests whose assertions are swallowed by try/except
- `SLOP051`: leftover AI chat text in comments and docstrings
- `# slopcheck: ignore[...]` and `# slopcheck: ignore-file` directives
- GitHub Action (`action.yml`) and pre-commit hook

### Project setup

- Project README describing the problem, design principles, planned detectors and roadmap
- Community health files: Code of Conduct, Contributing guide, Security policy, Support, Governance
- Issue templates, pull request template, CODEOWNERS, Dependabot and CI
