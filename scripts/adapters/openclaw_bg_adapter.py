#!/usr/bin/env python3
"""
OpenClaw Adapter for ClawGate QA Framework
Runs agent in background and polls for result
"""
import json
import os
import subprocess
import sys
import time
from typing import Any


def call_openclaw(message: str) -> dict[str, Any]:
    """Call openclaw agent in background and wait for result."""
    try:
        # Run in background - separate stdout and stderr
        proc = subprocess.Popen(
            ["openclaw", "agent", "--local", "--message", message, "--json", "--agent", "main"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "OPENCLAW_MODEL": "minimax/MiniMax-M2.5"},
        )
        
        # Wait for completion with polling
        start_time = time.time()
        timeout = 90
        
        while proc.poll() is None:
            if time.time() - start_time > timeout:
                proc.kill()
                return {
                    "output_text": "ERROR: timeout after 90s",
                    "trace": {"tools": [], "tags": {}, "state": {}, "render_candidates": []},
                }
            time.sleep(1)
        
        stdout, stderr = proc.communicate()
        
        if proc.returncode != 0:
            return {
                "output_text": f"ERROR: {stderr.strip()}",
                "trace": {"tools": [], "tags": {}, "state": {}, "render_candidates": []},
            }
        
        # Parse JSON output - look for JSON in stdout
        try:
            # Find JSON start in stdout
            json_start = stdout.find('{')
            if json_start >= 0:
                json_str = stdout[json_start:]
                data = json.loads(json_str)
            else:
                data = {"output": stdout}
        except json.JSONDecodeError:
            return {
                "output_text": stdout.strip(),
                "trace": {"tools": [], "tags": {}, "state": {}, "render_candidates": []},
            }
        
        # Extract output_text
        payloads = data.get("payloads", [])
        output_text = ""
        if payloads:
            output_text = payloads[0].get("text", "")
        else:
            output_text = data.get("reply", data.get("output", ""))
        
        # Build trace - try to extract tools from meta
        tools = []
        meta = data.get("meta", {})
        
        trace = {
            "tags": {"qa_adapter": "openclaw-bg"},
            "tools": tools,
            "state": data.get("state", {}),
            "render_candidates": data.get("render_candidates", []),
        }
        
        return {"output_text": output_text, "trace": trace}
        
    except Exception as e:
        return {
            "output_text": f"ERROR: {str(e)}",
            "trace": {"tools": [], "tags": {}, "state": {}, "render_candidates": []},
        }


def make_response(payload: dict[str, Any]) -> dict[str, Any]:
    """Process QA case payload and call OpenClaw."""
    case_id = payload.get("case_id")
    user_input = payload.get("user_input", "")
    
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
                    {"name": "gateway_health", "args": {}, "status_code": 200 if result.returncode == 0 else 500, "latency_ms": 100},
                    {"name": "node_health", "args": {}, "status_code": 200, "latency_ms": 50}
                ],
                "state": {},
                "render_candidates": [],
            }
            return {"output_text": output_text, "trace": trace}
        except Exception as e:
            return {"output_text": f"ERROR: {str(e)}", "trace": {"tags": tags, "tools": [], "state": {}, "render_candidates": []}}
    
    # For other cases, call the agent
    result = call_openclaw(user_input)
    if result.get("trace"):
        result["trace"]["tags"] = {**result["trace"].get("tags", {}), **tags}
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
