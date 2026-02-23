#!/usr/bin/env python3
import json
import sys
from typing import Any


def make_response(payload: dict[str, Any]) -> dict[str, Any]:
    case_id = payload.get("case_id")
    turn = int(payload.get("turn", 1))
    pre = payload.get("preconditions", {})
    tags = {
        "qa_run_id": payload.get("qa_run_id"),
        "case_id": payload.get("case_id"),
        "git_sha": payload.get("git_sha"),
        "pr_id": payload.get("pr_id"),
    }
    trace = {"tags": tags, "tools": [], "state": {}, "render_candidates": []}
    output_text = "ok"

    if case_id == "OC_HEALTH_001":
        output_text = "gateway and node are healthy and running."
        trace["tools"] = [
            {"name": "gateway_health", "args": {}, "status_code": 200, "latency_ms": 40},
            {"name": "node_health", "args": {}, "status_code": 200, "latency_ms": 55},
        ]

    elif case_id == "OC_TOOL_001":
        path = pre.get("workspace", "/tmp")
        output_text = f"workspace files listed for {path}"
        trace["tools"] = [
            {"name": "workspace_list", "args": {"path": path}, "status_code": 200, "latency_ms": 88}
        ]

    elif case_id == "OC_DISAMB_001":
        if turn == 1:
            output_text = "I found multiple config candidates. Select one."
            trace["tools"] = [
                {"name": "workspace_search", "args": {"query": "openclaw config"}, "status_code": 200, "latency_ms": 120}
            ]
            trace["state"] = {"candidate_list": ["/tmp/openclaw.yml", "/tmp/openclaw.local.yml"]}
            trace["render_candidates"] = [
                {"id": "1", "name": "/tmp/openclaw.yml"},
                {"id": "2", "name": "/tmp/openclaw.local.yml"},
            ]
        else:
            output_text = "selected path opened successfully."
            trace["tools"] = [
                {"name": "workspace_open", "args": {"path": "/tmp/openclaw.local.yml"}, "status_code": 200, "latency_ms": 70}
            ]
            trace["state"] = {"candidate_list": ["/tmp/openclaw.yml", "/tmp/openclaw.local.yml"]}

    elif case_id == "OC_GIT_001":
        if turn == 1:
            output_text = "branch main is clean."
            trace["tools"] = [
                {"name": "git_status", "args": {}, "status_code": 200, "latency_ms": 64}
            ]
        else:
            output_text = "latest commit diff with files changed."
            trace["tools"] = [
                {"name": "git_show", "args": {"target": "HEAD"}, "status_code": 200, "latency_ms": 72}
            ]

    elif case_id == "OC_TRACE_001":
        output_text = "trace tags validated."
        trace["tools"] = [
            {"name": "trace_meta", "args": {}, "status_code": 200, "latency_ms": 22}
        ]

    return {"output_text": output_text, "trace": trace}


def main() -> int:
    raw = sys.stdin.read().strip() or "{}"
    payload = json.loads(raw)
    result = make_response(payload)
    sys.stdout.write(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

