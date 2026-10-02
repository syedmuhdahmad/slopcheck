# Contributing to slopfence

Thanks for your interest in slopfence! This project is at an early stage, which is the best time to shape it. Every kind of contribution helps: code, detector ideas, real-world examples, docs, and bug reports.

By participating, you agree to follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## Ways to contribute

| You want to… | Do this |
|---|---|
| Share an example of AI-generated junk | Open an issue with the **AI junk example** template |
| Report a false positive | Open an issue with the **False positive** template |
| Propose a new detector | Open an issue with the **Detector proposal** template |
| Report a bug | Open an issue with the **Bug report** template |
| Ask a question or discuss an idea | Start a [Discussion](https://github.com/syedmuhdahmad/slopfence/discussions) |
| Report a security vulnerability | **Don't open an issue.** See [SECURITY.md](SECURITY.md) |
| Fix something or add a feature | Read on |

New here? Look for issues labelled [`good first issue`](https://github.com/syedmuhdahmad/slopfence/labels/good%20first%20issue) or [`help wanted`](https://github.com/syedmuhdahmad/slopfence/labels/help%20wanted).

## Before you start coding

- **Small fixes** (typos, docs, obvious bugs): open a pull request directly.
- **Anything bigger** (new detectors, new features, behaviour changes): open an issue first and wait for a maintainer to agree on the approach. This avoids wasted work.
- Comment on an issue to say you're working on it, so others don't duplicate effort.

## Development workflow

`main` is protected: **nobody pushes to it directly**, maintainers included. All changes go through pull requests.

1. **Fork** the repository and clone your fork.
2. **Create a branch** from `main` with a descriptive name:
   - `feat/slop001-pypi-lookup`
   - `fix/false-positive-mock-assert`
   - `docs/contributing-typo`
3. **Make your changes.** Keep each pull request focused on one thing.
4. **Add tests** for any behaviour change. Detectors need both:
   - cases that **should** be flagged, and
   - similar-looking cases that **should not** be flagged (false-positive guards).
5. **Run checks locally** (see below) and make sure they pass.
6. **Push** to your fork and **open a pull request** against `main`. Fill in the template.

### What happens to your pull request

- CI must pass.
- At least **one maintainer approval** is required.
- All review conversations must be resolved.
- Pull requests are **squash-merged**, so `main` has a clean, linear history with one commit per pull request. The pull request title becomes the commit message, so make it clear.
- Your branch is deleted automatically after merge.

## Local checks

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e '.[dev]'

pytest                           # tests
ruff check . && ruff format --check .
slopfence src tests              # slopfence must pass on its own code
npx markdownlint-cli2 "**/*.md" "!.venv/**"
```

If you change `.pre-commit-hooks.yaml`, also run the end-to-end hook test (needs `pip install pre-commit`):

```bash
.github/scripts/test-pre-commit-hook.sh .
```

### Adding a detector

1. Add the rule to `RULES` in `src/slopfence/models.py`.
2. Write the detector in `src/slopfence/detectors/` and register it in `detectors/__init__.py`.
3. Add tests with **both** flagged and not-flagged cases. Real-world code that must stay quiet is the most valuable test.
4. Run it against a large codebase (for example your Python install's standard library) and check for false positives before opening the pull request.

## Commit and pull request style

- Use the imperative mood: "Add PyPI lookup cache", not "Added" or "Adds".
- Pull request titles follow [Conventional Commits](https://www.conventionalcommits.org/) style where it fits:
  - `feat: add SLOP010 placeholder comment detector`
  - `fix: ignore mocks used as fixtures in SLOP020`
  - `docs: clarify ignore comment syntax`
  - `chore: bump actions/checkout`
- Reference related issues: `Closes #12`.

## Writing a good detector

A detector is only useful if people trust it. Before proposing or writing one, check:

1. **Is it objective?** Could two reviewers agree on whether a given snippet matches?
2. **Is it high-confidence?** It's better to miss some cases than to flag correct code.
3. **Is it actionable?** The message should tell the user what's wrong and how to fix it.
4. **Is it about the pattern, not the author?** slopfence never tries to guess whether AI wrote the code.

## Licensing of contributions

By submitting a pull request, you agree that your contribution is licensed under the [MIT License](LICENSE), the same license as the project.

## Recognition

All contributors are credited in release notes. Thank you for helping make AI-assisted code better!
