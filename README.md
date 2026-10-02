# slopfence

[![PyPI](https://img.shields.io/pypi/v/slopfence?cacheSeconds=3600)](https://pypi.org/project/slopfence/)
[![Python](https://img.shields.io/pypi/pyversions/slopfence?cacheSeconds=3600)](https://pypi.org/project/slopfence/)
[![CI](https://github.com/syedmuhdahmad/slopfence/actions/workflows/ci.yml/badge.svg)](https://github.com/syedmuhdahmad/slopfence/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**A fast, deterministic quality gate for AI-assisted code.**

slopfence finds the junk that AI coding assistants leave behind (hallucinated packages, tests that test nothing, placeholder stubs, duplicate helpers) before it gets merged.

> 🚧 **Status: alpha (v0.1, Python only).** The first detectors work and are tested against 20,000+ files of real-world code for false positives. Expect rough edges. Feedback is very welcome. See [Contributing](#contributing).

---

## Quick start

```bash
pip install slopfence
```

Or run it without installing, using [uv](https://docs.astral.sh/uv/) or [pipx](https://pipx.pypa.io/):

```bash
uvx slopfence .
pipx run slopfence .
```

Check a project:

```bash
slopfence .
```

Check only what your branch changed (ideal for pull requests):

```bash
slopfence --diff main
```

### Options

| Option | What it does |
|---|---|
| `--diff REF` | Only report issues on lines changed since `REF` (plus new untracked files) |
| `--format text\|json\|sarif` | Output format. SARIF shows findings inline on GitHub pull requests |
| `-o, --output FILE` | Write the report to a file |
| `--offline` | Skip PyPI lookups (disables `SLOP001`) |
| `--select` / `--ignore` | Comma-separated rule IDs to run or skip, e.g. `--ignore SLOP051` |
| `--exclude` | Comma-separated paths or globs to skip, e.g. `--exclude migrations,*_pb2.py` |
| `--exit-zero` | Always exit 0 (report only) |
| `--list-rules` | Show all rules |

Exit codes: `0` no issues, `1` issues found, `2` error.

### Configuration

Add a `[tool.slopfence]` table to the `pyproject.toml` at your project root:

```toml
[tool.slopfence]
select = ["SLOP001", "SLOP010", "SLOP020"]  # rules to run (default: all)
ignore = ["SLOP051"]                         # rules to skip
exclude = ["migrations", "tests/fixtures/", "*_pb2.py"]
```

`exclude` works like `.gitignore`: a pattern without a `/` in the middle matches any file or folder name anywhere (`migrations`, `*_pb2.py`), and a pattern with one is relative to the project root (`tests/fixtures/`). Excluded files are never checked, but imports of excluded modules still count as your own code.

Command-line options (`--select`, `--ignore`, `--exclude`) replace the matching config values. Unknown keys and rule IDs are reported as errors (exit code `2`).

### Ignoring a finding

```python
# In a real implementation, use the cache.  # slopfence: ignore[SLOP010]
x = legacy()  # slopfence: ignore
```

Put `# slopfence: ignore-file` anywhere in a file to skip it. In `requirements.txt`, add `# slopfence: ignore` to a line.

### GitHub Action

```yaml
# .github/workflows/slopfence.yml
name: slopfence
on: pull_request
permissions:
  contents: read
jobs:
  slopfence:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
        with:
          fetch-depth: 0
      - uses: syedmuhdahmad/slopfence@v0.1.0
```

On pull requests it automatically checks only the changed lines (set `diff: none` to check everything, or `diff: <ref>` for a specific ref). To show findings inline on the pull request, set `sarif-file: slopfence.sarif` and upload it with `github/codeql-action/upload-sarif` (needs `security-events: write`).

### pre-commit

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/syedmuhdahmad/slopfence
    rev: v0.1.0
    hooks:
      - id: slopfence
```

## The problem

AI coding tools (Claude, Copilot, Cursor, Gemini, Codex and others) are now part of everyday development. They write code fast, and that code usually *looks* correct. It compiles, it's well formatted, and it has comments and tests.

But it often comes with recognizable junk:

- **Packages that don't exist.** The AI imports `flask-jwt-simple-auth` because the name sounds plausible. Attackers now register these invented names to spread malware, a technique known as **slopsquatting**.
- **Tests that test nothing.** A test creates a mock, sets a value on it, then asserts that value. It passes forever and protects nothing.
- **Placeholder code shipped as real code.** Comments like `# In a real implementation, validate the token` above a function that returns `True`.
- **Duplicate helpers.** `format_date()`, `formatDate()` and `date_formatter()` in three different files, because the AI wrote a new helper instead of finding the existing one.
- **Over-defensive code.** `try/except Exception: pass` around code that can't fail, which hides real errors.
- **Comment noise.** `# Increment counter by 1` above `counter += 1`, or leftover chat text like *"Here's the updated function:"*.

Reviewers miss these because the code *looks* fine. Each one is small. Together they add up to security holes, false confidence from green test suites, and codebases that get harder to maintain every sprint.

## Why existing tools aren't enough

| Tool | What it's good at | What it misses |
|---|---|---|
| **Ruff, ESLint, Pylint** | Style and common bugs | AI-specific patterns, invented packages |
| **Vulture, Knip** | Dead code | Fake tests, placeholders, near-duplicates |
| **jscpd** | Copy-pasted code | Code that's similar but not identical |
| **Socket, Snyk** | Supply-chain security | Code-quality patterns; mostly paid |
| **[slopcheck](https://github.com/0xToxSec/slopcheck)** (unrelated project) | Checking for hallucinated packages before you install them | Code-quality patterns such as fake tests, placeholders and chat leftovers |
| **AI code reviewers** (e.g. Claude `/code-review`) | Deep, context-aware review | Not deterministic, costs tokens, doesn't automatically check package registries, runs only when someone asks |

No single tool focuses on **the failure modes of AI-written code**, built for reviewing pull requests. That's the gap slopfence fills.

### slopfence vs. AI reviewers: complementary, not competing

```text
Developer + AI writes code
        │
        ▼
slopfence            ← fast, free, same result every time; runs on every commit
        │
        ▼
AI / LLM review      ← deep reasoning about logic and design
        │
        ▼
Human review
```

AI reviewers are smart but nondeterministic and cost money on every run. slopfence catches the objective, repeatable problems in seconds with no API keys, so reviewers (human or AI) can spend their attention on what matters.

## Who needs it

- **Teams adopting AI coding tools** that want a safety net without banning the tools.
- **Open-source maintainers** reviewing a growing number of AI-generated pull requests.
- **Security teams** worried about hallucinated or slopsquatted dependencies.
- **Tech leads** who want an objective quality gate instead of arguing over style in review.
- **Solo developers** who want to catch their AI assistant's mistakes before they commit.

## Design principles

1. **Detect patterns, not authorship.** slopfence never tries to guess *whether AI wrote the code*. That's unreliable and leads to arguments. It flags low-quality patterns that AI commonly produces, no matter who wrote them.
2. **Deterministic by default.** Rule-based checks with no LLM required. The same input always gives the same output.
3. **Diff-first.** Check only what changed in a pull request. Nobody wants 4,000 warnings on an old codebase.
4. **Low false positives over high recall.** A noisy linter gets uninstalled. Start strict, flag only obvious cases, and make everything configurable.
5. **Fits existing workflows.** CLI, pre-commit hook, GitHub Action, and SARIF output for GitHub code scanning.

## Detectors

| ID | Detector | Severity | Status |
|---|---|---|---|
| `SLOP001` | Import of a package that doesn't exist on PyPI / npm | 🔴 High | ✅ v0.1 (Python) |
| `SLOP002` | Dependency that is very new or has suspiciously few downloads (slopsquatting risk) | 🔴 High | Planned |
| `SLOP010` | Placeholder / stub comment (`In a real implementation…`, `Simplified for demo`) | 🟠 Medium | ✅ v0.1 |
| `SLOP011` | Function that only returns `None`, `pass`, or hardcoded fake data | 🟠 Medium | Planned for v0.2 ([#22](https://github.com/syedmuhdahmad/slopfence/issues/22)) |
| `SLOP020` | Test that only asserts on its own mocks | 🔴 High | ✅ v0.1 |
| `SLOP021` | Test with no meaningful assertion (`assert True`, `toBeDefined()` only) | 🟠 Medium | ✅ v0.1 |
| `SLOP022` | Test wrapped in `try/except` so it can never fail | 🔴 High | ✅ v0.1 |
| `SLOP030` | Near-duplicate function elsewhere in the codebase | 🟠 Medium | Planned for v0.2 ([#11](https://github.com/syedmuhdahmad/slopfence/issues/11)) |
| `SLOP040` | `except Exception` that silently swallows errors | 🟡 Low | Planned for v0.2 ([#21](https://github.com/syedmuhdahmad/slopfence/issues/21)) |
| `SLOP050` | Comment that only restates the code | 🟡 Low | Planned for v0.2 ([#23](https://github.com/syedmuhdahmad/slopfence/issues/23)) |
| `SLOP051` | Leftover chat text in code (`Certainly! Here's…`) | 🟠 Medium | ✅ v0.1 |

## Example output

```text
$ slopfence --diff main

src/auth.py
  12:1   SLOP001  Package 'flask-jwt-simple-auth' not found on PyPI (possible hallucination)  🔴
  48:5   SLOP010  Placeholder: "In a real implementation, validate the token"            🟠

tests/test_user.py
  20:5   SLOP020  Test only asserts on its own Mock - doesn't test real code               🔴

tests/test_billing.py
  31:5   SLOP022  Test 'test_refund' catches assertion failures without re-raising, so it can never fail  🔴

4 issues (3 high, 1 medium)
```

## Architecture

```text
┌─────────────┐   ┌──────────────┐   ┌──────────────┐   ┌───────────────┐
│   Files /   │──▶│    Parser    │──▶│  Rule engine │──▶│   Reporter    │
│   git diff  │   │ (ast / t-s)  │   │  (detectors) │   │ CLI/JSON/SARIF│
└─────────────┘   └──────────────┘   └──────┬───────┘   └───────────────┘
                                            │
                                  ┌─────────▼─────────┐
                                  │ Optional:         │
                                  │ - registry lookup │
                                  │   (cached)        │
                                  │ - LLM second      │
                                  │   opinion (--llm) │
                                  └───────────────────┘
```

- **Parser:** v0.1 uses Python's built-in `ast` and `tokenize` (no dependencies). **tree-sitter** is planned so new languages can be added without rewriting the detectors.
- **Registry lookups** are cached locally (`~/.cache/slopfence`) to stay fast and avoid rate limits. If PyPI can't be reached, nothing is flagged: an unknown answer is never treated as "missing".
- **Optional LLM mode** sends only the unclear cases for a second opinion. Never required.

## Challenges (and how we plan to handle them)

| Challenge | Why it's hard | Plan |
|---|---|---|
| **False positives** | Every noisy warning erodes trust; one bad week and teams disable the tool. | Conservative rules, severity levels, `# slopfence: ignore[SLOP0xx]` comments, and a test corpus of real-world false positives. |
| **Private / internal packages** | Internal packages look identical to hallucinated ones. | Allowlists, private registry support, and reading local lockfiles and workspace packages. |
| **Registry rate limits** | Checking every import against PyPI/npm on every run is slow and gets throttled. | Local cache with TTL, batch lookups, offline mode. |
| **"Is this really junk?"** | Some patterns (defensive code, stubs) are legitimate in context. | Flag only high-confidence cases by default; stricter checks are opt-in. |
| **Near-duplicate detection at scale** | Comparing every function with every other is expensive. | AST normalization + hashing, and only comparing changed functions against the index. |
| **Multi-language support** | Each language has different idioms and test frameworks. | Start with Python only, do it well, then JS/TS via tree-sitter. |
| **Tone and adoption** | A tool that "shames AI users" will be resisted. | Position it as a quality gate *for* AI-assisted development, not against it. |
| **Moving target** | AI tools improve and their failure modes change. | Rules are data-driven and easy to add; community-contributed detectors. |

## Roadmap

### v0.1 (MVP): Python

- [x] CLI: `slopfence .` and `slopfence --diff <branch>`
- [x] `SLOP001` packages that don't exist on PyPI (dependency files and imports)
- [x] `SLOP010` placeholder comments
- [x] `SLOP020` / `SLOP021` / `SLOP022` fake tests
- [x] `SLOP051` leftover chat text
- [x] Ignore comments
- [x] JSON and SARIF output
- [x] GitHub Action and pre-commit hook
- [x] Publish to PyPI

### v0.2

Tracked in the [v0.2.0 milestone](https://github.com/syedmuhdahmad/slopfence/milestone/2) and on the [roadmap board](https://github.com/users/syedmuhdahmad/projects/1).

#### Planned features

- [ ] Config file: `[tool.slopfence]` in `pyproject.toml` ([#10](https://github.com/syedmuhdahmad/slopfence/issues/10))
- [ ] `SLOP030` near-duplicate functions ([#11](https://github.com/syedmuhdahmad/slopfence/issues/11))
- [ ] Parallel processing for large repos ([#12](https://github.com/syedmuhdahmad/slopfence/issues/12))

#### Reliability

- [ ] Test the GitHub Action in a real workflow, including SARIF upload ([#13](https://github.com/syedmuhdahmad/slopfence/issues/13))
- [ ] Test the pre-commit hook with `pre-commit` ([#14](https://github.com/syedmuhdahmad/slopfence/issues/14))
- [ ] Allowlist for private packages ([#15](https://github.com/syedmuhdahmad/slopfence/issues/15))
- [ ] Better import-name to package-name mapping ([#16](https://github.com/syedmuhdahmad/slopfence/issues/16))
- [ ] Detect private indexes from `pip.conf`, uv and Poetry ([#17](https://github.com/syedmuhdahmad/slopfence/issues/17))
- [ ] `--fail-on` severity threshold ([#18](https://github.com/syedmuhdahmad/slopfence/issues/18))
- [ ] Option to fail on unparseable files ([#19](https://github.com/syedmuhdahmad/slopfence/issues/19))
- [ ] Fewer `SLOP010` false positives from "for demo purposes" ([#20](https://github.com/syedmuhdahmad/slopfence/issues/20))

#### New rules

- [ ] `SLOP040` `except Exception` that silently swallows errors ([#21](https://github.com/syedmuhdahmad/slopfence/issues/21))
- [ ] `SLOP011` stub functions that only `pass` or return fake data ([#22](https://github.com/syedmuhdahmad/slopfence/issues/22))
- [ ] `SLOP050` comments that only restate the code ([#23](https://github.com/syedmuhdahmad/slopfence/issues/23))

#### Project

- [ ] Demo GIF in the README ([#24](https://github.com/syedmuhdahmad/slopfence/issues/24))
- [ ] Release v0.2.0 ([#25](https://github.com/syedmuhdahmad/slopfence/issues/25))

### Later

- [ ] JavaScript / TypeScript (npm registry)
- [ ] Slopsquatting risk scoring (`SLOP002`)
- [ ] VS Code extension
- [ ] Optional `--llm` second opinion

## Contributing

The project is at the very start, which is the best time to shape it.

- 💡 **Have an example of AI-generated junk?** Open an issue with a code snippet. Real examples are the most valuable input for designing detectors.
- 🐛 **Know a pattern we're missing?** Propose a detector in an issue.
- 🗣️ **Disagree with the approach?** Open a discussion. Better now than after v1.

Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request. Everyone taking part is expected to follow our [Code of Conduct](CODE_OF_CONDUCT.md). Found a security issue? Report it privately as described in [SECURITY.md](SECURITY.md). Need help? See [SUPPORT.md](SUPPORT.md).

## License

[MIT](LICENSE)
