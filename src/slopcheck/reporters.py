from __future__ import annotations

import json
from collections import Counter
from itertools import groupby

from slopcheck import __version__
from slopcheck.engine import Result
from slopcheck.models import RULES, Severity

_SEVERITY_ORDER = [Severity.HIGH, Severity.MEDIUM, Severity.LOW]
_SARIF_LEVEL = {Severity.HIGH: "error", Severity.MEDIUM: "warning", Severity.LOW: "note"}
_COLOR = {Severity.HIGH: "\033[31m", Severity.MEDIUM: "\033[33m", Severity.LOW: "\033[36m"}
_RESET, _BOLD = "\033[0m", "\033[1m"


def text(result: Result, color: bool = False) -> str:
    def paint(s: str, code: str) -> str:
        return f"{code}{s}{_RESET}" if color else s

    out: list[str] = []
    for path, group in groupby(result.findings, key=lambda f: f.path):
        out.append(paint(path, _BOLD))
        for f in group:
            loc = f"{f.line}:{f.col}"
            sev = paint(f.severity.value, _COLOR[f.severity])
            out.append(f"  {loc:<8} {f.rule}  {f.message}  [{sev}]")
        out.append("")

    counts = Counter(f.severity for f in result.findings)
    if result.findings:
        parts = [f"{counts[s]} {s.value}" for s in _SEVERITY_ORDER if counts[s]]
        total = len(result.findings)
        out.append(f"{total} issue{'s' if total != 1 else ''} ({', '.join(parts)})")
    else:
        out.append(f"No issues found in {result.files_checked} files.")
    for path in result.parse_errors:
        out.append(f"warning: skipped {path} (not valid Python)")
    return "\n".join(out)


def as_json(result: Result) -> str:
    return json.dumps(
        {
            "version": __version__,
            "files_checked": result.files_checked,
            "findings": [
                {
                    "rule": f.rule,
                    "name": RULES[f.rule].name,
                    "severity": f.severity.value,
                    "path": f.path,
                    "line": f.line,
                    "column": f.col,
                    "message": f.message,
                }
                for f in result.findings
            ],
            "parse_errors": result.parse_errors,
        },
        indent=2,
    )


def sarif(result: Result) -> str:
    rules = [
        {
            "id": rule.id,
            "name": rule.name,
            "shortDescription": {"text": rule.summary},
            "helpUri": "https://github.com/syedmuhdahmad/slopcheck#planned-detectors",
            "defaultConfiguration": {"level": _SARIF_LEVEL[rule.severity]},
        }
        for rule in RULES.values()
    ]
    rule_index = {rule["id"]: i for i, rule in enumerate(rules)}
    results = [
        {
            "ruleId": f.rule,
            "ruleIndex": rule_index[f.rule],
            "level": _SARIF_LEVEL[f.severity],
            "message": {"text": f.message},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": f.path, "uriBaseId": "%SRCROOT%"},
                        "region": {"startLine": f.line, "startColumn": f.col},
                    }
                }
            ],
        }
        for f in result.findings
    ]
    doc = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "slopcheck",
                        "version": __version__,
                        "informationUri": "https://github.com/syedmuhdahmad/slopcheck",
                        "rules": rules,
                    }
                },
                "results": results,
            }
        ],
    }
    return json.dumps(doc, indent=2)
