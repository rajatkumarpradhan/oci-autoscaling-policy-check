"""Command line interface for the autoscaling configuration auditor."""

import argparse
import json
import sys

from .rules import SEVERITY_ORDER, audit_document

EXIT_HIGH_FINDINGS = 2
EXIT_INPUT_ERROR = 1
EXIT_OK = 0


def _load(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            document = json.load(handle)
    except OSError as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(document, dict) or not isinstance(document.get("autoscaling_configs"), list):
        raise ValueError(f"{path} must contain a top-level 'autoscaling_configs' list")
    return document


def _render(findings):
    lines = []
    counts = {level: 0 for level in SEVERITY_ORDER}
    for finding in findings:
        counts[finding.severity] += 1
        lines.append(f"[{finding.severity:<6}] {finding.rule_id} {finding.config}: {finding.message}")
    lines.append(
        "summary: {high} high, {medium} medium, {low} low finding(s)".format(
            high=counts["HIGH"], medium=counts["MEDIUM"], low=counts["LOW"]
        )
    )
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="oci-autoscaling-policy-check",
        description="Offline audit of simplified OCI autoscaling configuration exports.",
    )
    parser.add_argument("paths", nargs="+", help="autoscaling JSON files to audit")
    args = parser.parse_args(argv)

    all_findings = []
    for path in args.paths:
        try:
            document = _load(path)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_INPUT_ERROR
        all_findings.extend(audit_document(document))

    all_findings.sort(key=lambda f: (SEVERITY_ORDER[f.severity], f.rule_id, f.config, f.message))
    print(_render(all_findings))
    if any(f.severity == "HIGH" for f in all_findings):
        return EXIT_HIGH_FINDINGS
    return EXIT_OK
