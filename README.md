# slopcheck

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

**A fast, deterministic quality gate for AI-assisted code.**

slopcheck finds the junk that AI coding assistants leave behind (hallucinated packages, tests that test nothing, placeholder stubs, duplicate helpers) before it gets merged.

> 🚧 **Status: early design / pre-alpha.** This README describes the problem and the plan. Code is coming. Feedback and ideas are very welcome. See [Contributing](#contributing).

---

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
| **AI code reviewers** (e.g. Claude `/code-review`) | Deep, context-aware review | Not deterministic, costs tokens, doesn't automatically check package registries, runs only when someone asks |

No single tool focuses on **the failure modes of AI-written code**, built for reviewing pull requests. That's the gap slopcheck fills.

### slopcheck vs. AI reviewers: complementary, not competing

```text
Developer + AI writes code
        │
        ▼
slopcheck            ← fast, free, same result every time; runs on every commit
        │
        ▼
AI / LLM review      ← deep reasoning about logic and design
        │
        ▼
Human review
```

AI reviewers are smart but nondeterministic and cost money on every run. slopcheck catches the objective, repeatable problems in seconds with no API keys, so reviewers (human or AI) can spend their attention on what matters.

## Who needs it

- **Teams adopting AI coding tools** that want a safety net without banning the tools.
- **Open-source maintainers** reviewing a growing number of AI-generated pull requests.
- **Security teams** worried about hallucinated or slopsquatted dependencies.
- **Tech leads** who want an objective quality gate instead of arguing over style in review.
- **Solo developers** who want to catch their AI assistant's mistakes before they commit.

## Design principles

1. **Detect patterns, not authorship.** slopcheck never tries to guess *whether AI wrote the code*. That's unreliable and leads to arguments. It flags low-quality patterns that AI commonly produces, no matter who wrote them.
2. **Deterministic by default.** Rule-based checks with no LLM required. The same input always gives the same output.
3. **Diff-first.** Check only what changed in a pull request. Nobody wants 4,000 warnings on an old codebase.
4. **Low false positives over high recall.** A noisy linter gets uninstalled. Start strict, flag only obvious cases, and make everything configurable.
5. **Fits existing workflows.** CLI, pre-commit hook, GitHub Action, and SARIF output for GitHub code scanning.

## Planned detectors

| ID | Detector | Severity |
|---|---|---|
| `SLOP001` | Import of a package that doesn't exist on PyPI / npm | 🔴 High |
| `SLOP002` | Dependency that is very new or has suspiciously few downloads (slopsquatting risk) | 🔴 High |
| `SLOP010` | Placeholder / stub comment (`In a real implementation…`, `Simplified for demo`) | 🟠 Medium |
| `SLOP011` | Function that only returns `None`, `pass`, or hardcoded fake data | 🟠 Medium |
| `SLOP020` | Test that only asserts on its own mocks | 🔴 High |
| `SLOP021` | Test with no meaningful assertion (`assert True`, `toBeDefined()` only) | 🟠 Medium |
| `SLOP022` | Test wrapped in `try/except` so it can never fail | 🔴 High |
| `SLOP030` | Near-duplicate function elsewhere in the codebase | 🟠 Medium |
| `SLOP040` | `except Exception` that silently swallows errors | 🟡 Low |
| `SLOP050` | Comment that only restates the code | 🟡 Low |
| `SLOP051` | Leftover chat text in code (`Certainly! Here's…`) | 🟠 Medium |

## What it will look like

```text
$ slopcheck --diff main

src/auth.py
  12:1   SLOP001  Package 'flask-jwt-simple-auth' not found on PyPI (possible hallucination)  🔴
  48:5   SLOP010  Placeholder: "In a real implementation, validate the token"            🟠

tests/test_user.py
  20:5   SLOP020  Test only asserts on its own Mock - doesn't test real code               🔴

src/utils/dates.py
  5:1    SLOP030  'format_date' is 94% similar to 'formatDate' in src/helpers.py:31        🟠

4 issues (2 high, 2 medium)
```

## Architecture (planned)

```text
┌─────────────┐   ┌──────────────┐   ┌──────────────┐   ┌───────────────┐
│   Files /   │──▶│    Parser    │──▶│  Rule engine │──▶│   Reporter    │
│   git diff  │   │ (tree-sitter)│   │  (detectors) │   │ CLI/JSON/SARIF│
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

- **tree-sitter** for parsing, so new languages are added without rewriting the detectors.
- **Registry lookups** cached locally to stay fast and avoid rate limits.
- **Optional LLM mode** sends only the unclear cases for a second opinion. Never required.

## Challenges (and how we plan to handle them)

| Challenge | Why it's hard | Plan |
|---|---|---|
| **False positives** | Every noisy warning erodes trust; one bad week and teams disable the tool. | Conservative rules, severity levels, `# slopcheck: ignore[SLOP0xx]` comments, and a test corpus of real-world false positives. |
| **Private / internal packages** | Internal packages look identical to hallucinated ones. | Allowlists, private registry support, and reading local lockfiles and workspace packages. |
| **Registry rate limits** | Checking every import against PyPI/npm on every run is slow and gets throttled. | Local cache with TTL, batch lookups, offline mode. |
| **"Is this really junk?"** | Some patterns (defensive code, stubs) are legitimate in context. | Flag only high-confidence cases by default; stricter checks are opt-in. |
| **Near-duplicate detection at scale** | Comparing every function with every other is expensive. | AST normalization + hashing, and only comparing changed functions against the index. |
| **Multi-language support** | Each language has different idioms and test frameworks. | Start with Python only, do it well, then JS/TS via tree-sitter. |
| **Tone and adoption** | A tool that "shames AI users" will be resisted. | Position it as a quality gate *for* AI-assisted development, not against it. |
| **Moving target** | AI tools improve and their failure modes change. | Rules are data-driven and easy to add; community-contributed detectors. |

## Roadmap

### v0.1 (MVP): Python

- [ ] CLI: `slopcheck .` and `slopcheck --diff <branch>`
- [ ] `SLOP001` invented packages (PyPI)
- [ ] `SLOP010` placeholder comments
- [ ] `SLOP020` / `SLOP021` fake tests
- [ ] `SLOP051` leftover chat text
- [ ] JSON and SARIF output
- [ ] GitHub Action

### v0.2

- [ ] Config file (`.slopcheck.toml`) and ignore comments
- [ ] Near-duplicate detection (`SLOP030`)
- [ ] pre-commit hook

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

Licensed under the [Apache License 2.0](LICENSE). See [NOTICE](NOTICE) for attribution.
