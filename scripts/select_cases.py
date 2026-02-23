#!/usr/bin/env python3
import argparse
import fnmatch
from pathlib import Path
from typing import Any

from common import discover_case_files, read_yaml, write_json


def normalize_path(path: str) -> str:
    return path.replace("\\", "/").strip()


def read_changed_paths(args: argparse.Namespace) -> list[str]:
    paths = [normalize_path(p) for p in (args.changed_path or [])]
    if args.changed_path_file:
        fp = Path(args.changed_path_file)
        if fp.exists():
            lines = [normalize_path(x) for x in fp.read_text(encoding="utf-8").splitlines()]
            paths.extend([x for x in lines if x])
    return sorted(set([p for p in paths if p]))


def select_suites(mapping: dict[str, Any], changed_paths: list[str], focus_suites: list[str]) -> tuple[list[str], list[str]]:
    selected: set[str] = set(mapping.get("defaults", {}).get("add_suites", []))
    reasons: list[str] = []
    rules = mapping.get("rules", [])
    for rule in rules:
        patterns = rule.get("match_paths", [])
        add_suites = rule.get("add_suites", [])
        matched = False
        for path in changed_paths:
            for pattern in patterns:
                if fnmatch.fnmatch(path, pattern):
                    matched = True
                    break
            if matched:
                break
        if matched:
            for suite in add_suites:
                if suite not in selected:
                    reasons.append(f"suite={suite} matched by {patterns}")
                selected.add(suite)
    for suite in focus_suites:
        if suite not in selected:
            reasons.append(f"suite={suite} added by --focus-suite")
        selected.add(suite)
    return sorted(selected), reasons


def main() -> int:
    ap = argparse.ArgumentParser(description="Select QA cases by changed paths and suite mapping.")
    ap.add_argument("--cases-root", default="qa/cases")
    ap.add_argument("--mapping", default="qa/mappings/diff_to_suite.yaml")
    ap.add_argument("--changed-path", action="append", default=[])
    ap.add_argument("--changed-path-file")
    ap.add_argument("--focus-suite", action="append", default=[])
    ap.add_argument("--pr-id", default="local")
    ap.add_argument("--base-sha", default="")
    ap.add_argument("--head-sha", default="")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    changed_paths = read_changed_paths(args)
    mapping = read_yaml(Path(args.mapping))
    suites, reasons = select_suites(mapping, changed_paths, args.focus_suite)

    cases_root = Path(args.cases_root)
    case_entries: list[dict[str, Any]] = []
    for case_file in discover_case_files(cases_root):
        payload = read_yaml(case_file)
        if not payload.get("enabled", True):
            continue
        if payload.get("suite") not in suites:
            continue
        case_entries.append(
            {
                "id": payload.get("id"),
                "suite": payload.get("suite"),
                "priority": payload.get("priority", "P1"),
                "path": str(case_file),
            }
        )

    if not case_entries:
        # Fallback to P0 enabled cases if mapping selected nothing.
        for case_file in discover_case_files(cases_root):
            payload = read_yaml(case_file)
            if payload.get("enabled", True) and payload.get("priority") == "P0":
                case_entries.append(
                    {
                        "id": payload.get("id"),
                        "suite": payload.get("suite"),
                        "priority": payload.get("priority", "P1"),
                        "path": str(case_file),
                    }
                )
        reasons.append("fallback: no suite match; selected all enabled P0 cases")

    output = {
        "pr_id": args.pr_id,
        "base_sha": args.base_sha,
        "head_sha": args.head_sha,
        "changed_paths": changed_paths,
        "selected_suites": suites,
        "selection_reasons": reasons,
        "cases": sorted(case_entries, key=lambda x: (x["suite"], x["id"])),
    }
    write_json(Path(args.out), output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

