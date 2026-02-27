#!/usr/bin/env python3
import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from common import read_json, read_yaml, write_jsonl


def run_adapter(adapter_cmd: str, payload: dict[str, Any]) -> dict[str, Any]:
    completed = subprocess.run(
        adapter_cmd,
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        shell=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        return {
            "output_text": f"ADAPTER_ERROR: {completed.stderr.strip()}",
            "trace": {"tools": [], "tags": {}, "state": {}, "render_candidates": []},
        }
    stdout = completed.stdout.strip() or "{}"
    try:
        result = json.loads(stdout)
    except json.JSONDecodeError:
        result = {"output_text": stdout, "trace": {}}
    if not isinstance(result, dict):
        result = {"output_text": str(result), "trace": {}}
    result.setdefault("output_text", "")
    result.setdefault("trace", {})
    return result


def build_default_trace(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "tags": {
            "qa_run_id": payload["qa_run_id"],
            "case_id": payload["case_id"],
            "pr_id": payload["pr_id"],
            "git_sha": payload["git_sha"],
        },
        "tools": [],
        "state": {},
        "render_candidates": [],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Execute selected QA cases using a pluggable adapter.")
    ap.add_argument("--selected", required=True, help="selected_cases.json")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--adapter", default="", help="Command that accepts JSON on stdin and returns JSON on stdout")
    ap.add_argument("--pr-id", default="local")
    ap.add_argument("--git-sha", default="local")
    args = ap.parse_args()

    selected = read_json(Path(args.selected))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    for case_item in selected.get("cases", []):
        case_path = Path(case_item["path"])
        # Use case_id from selected_cases.json (already extracted from multi-doc YAML)
        case_id = case_item.get("id")
        case_payload = read_yaml(case_path)
        
        # Handle multi-document YAML: find the matching document
        if isinstance(case_payload, dict) and case_payload.get("_multi_doc"):
            # Find the document with matching id
            matching_doc = None
            for doc in case_payload.get("documents", []):
                if doc.get("id") == case_id:
                    matching_doc = doc
                    break
            if matching_doc:
                case_payload = matching_doc
            else:
                case_payload = {}
        
        suite = case_payload.get("suite", case_item.get("suite"))
        preconditions = case_payload.get("preconditions", {})
        for turn in case_payload.get("turns", []):
            payload = {
                "qa_run_id": args.run_id,
                "case_id": case_id,
                "suite": suite,
                "turn": turn.get("turn"),
                "user_input": turn.get("user_input", ""),
                "preconditions": preconditions,
                "pr_id": args.pr_id,
                "git_sha": args.git_sha,
            }
            if args.adapter:
                result = run_adapter(args.adapter, payload)
            else:
                result = {
                    "output_text": "NOT_EXECUTED: no adapter provided",
                    "trace": build_default_trace(payload),
                }
            trace = result.get("trace") or {}
            if not isinstance(trace, dict):
                trace = {}
            tags = trace.get("tags")
            if not isinstance(tags, dict):
                tags = {}
            tags.setdefault("qa_run_id", args.run_id)
            tags.setdefault("case_id", case_id)
            tags.setdefault("pr_id", args.pr_id)
            tags.setdefault("git_sha", args.git_sha)
            trace["tags"] = tags
            trace.setdefault("tools", [])
            trace.setdefault("state", {})
            trace.setdefault("render_candidates", [])
            records.append(
                {
                    "qa_run_id": args.run_id,
                    "pr_id": args.pr_id,
                    "git_sha": args.git_sha,
                    "case_id": case_id,
                    "suite": suite,
                    "priority": case_payload.get("priority", "P1"),
                    "turn": turn.get("turn"),
                    "user_input": turn.get("user_input", ""),
                    "must": turn.get("must", []),
                    "should": turn.get("should", []),
                    "output_text": result.get("output_text", ""),
                    "trace": trace,
                }
            )
    write_jsonl(out_dir / "records.jsonl", records)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

