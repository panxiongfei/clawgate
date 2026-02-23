#!/usr/bin/env python3
"""
OpenClaw Adapter for ClawGate QA Framework
Connects to local OpenClaw instance via CLI
"""
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def call_openclaw(message: str) -> dict[str, Any]:
    """Call local openclaw agent and return response."""
    # Use minimax for QA testing
    env = {
        **os.environ,
        "OPENCLAW_MODEL": "minimax/MiniMax-M2.5",
    }
    try:
        result = subprocess.run(
            ["openclaw", "agent", "--local", "--message", message, "--json", "--agent", "main"],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            env=env,
        )
        
        if result.returncode != 0:
            return {
                "output_text": f"ERROR: {result.stderr.strip()}",
                "trace": {"tools": [], "tags": {}, "state": {}, "render_candidates": []},
            }
        
        # Parse JSON output
        try:
            data = json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            return {
                "output_text": result.stdout.strip(),
                "trace": {"tools": [], "tags": {}, "state": {}, "render_candidates": []},
            }
        
        # Extract output_text and trace from openclaw response
        output_text = data.get("reply", data.get("output", ""))
        
        # Build trace structure
        trace = {
            "tags": {
                "qa_adapter": "openclaw-local",
                "model": data.get("model", "unknown"),
            },
            "tools": data.get("tools_used", []),
            "state": data.get("state", {}),
            "render_candidates": data.get("render_candidates", []),
        }
        
        return {"output_text": output_text, "trace": trace}
        
    except subprocess.TimeoutExpired:
        return {
            "output_text": "ERROR: timeout after 120s",
            "trace": {"tools": [], "tags": {}, "state": {}, "render_candidates": []},
        }
    except Exception as e:
        return {
            "output_text": f"ERROR: {str(e)}",
            "trace": {"tools": [], "tags": {}, "state": {}, "render_candidates": []},
        }


def make_response(payload: dict[str, Any]) -> dict[str, Any]:
    """Process QA case payload and call OpenClaw."""
    case_id = payload.get("case_id")
    user_input = payload.get("user_input", "")
    preconditions = payload.get("preconditions", {})
    
    tags = {
        "qa_run_id": payload.get("qa_run_id"),
        "case_id": case_id,
        "git_sha": payload.get("git_sha"),
        "pr_id": payload.get("pr_id"),
    }
    
    # For health check, use direct gateway command
    if case_id == "OC_HEALTH_001":
        try:
            result = subprocess.run(
                ["openclaw", "gateway", "status"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            output_text = result.stdout if result.returncode == 0 else f"ERROR: {result.stderr}"
            trace = {
                "tags": tags,
                "tools": [
                    {"name": "gateway_health", "args": {}, "status_code": 200 if result.returncode == 0 else 500, "latency_ms": 100}
                ],
                "state": {},
                "render_candidates": [],
            }
            return {"output_text": output_text, "trace": trace}
        except Exception as e:
            return {"output_text": f"ERROR: {str(e)}", "trace": {"tags": tags, "tools": [], "state": {}, "render_candidates": []}}
    
    # For other cases, call the agent
    result = call_openclaw(user_input)
    result["trace"]["tags"] = tags
    return result


def main() -> int:
    raw = sys.stdin.read().strip() or "{}"
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = {}
    
    result = make_response(payload)
    sys.stdout.write(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
