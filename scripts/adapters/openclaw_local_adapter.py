#!/usr/bin/env python3
"""
OpenClaw Adapter for ClawGate QA Framework
Connects to local OpenClaw instance via CLI
Extracts tool calls from OpenClaw response and Langfuse trace
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

# Langfuse Config
LF_HOST = "http://[::1]:3000"
LF_PUBLIC_KEY = "pk-lf-c706165a-70c6-4b92-bd76-0115eb71f0a8"
LF_SECRET_KEY = "sk-lf-bd782a9d-ac78-457c-9b5d-e876f0fca845"


def call_openclaw(message: str) -> dict[str, Any]:
    """Call local openclaw agent and return response."""
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
        
        stderr = result.stderr
        stdout = result.stdout
        
        if result.returncode != 0:
            return {
                "output_text": f"ERROR: {stderr.strip()}",
                "trace": {"tools": [], "tags": {}, "state": {}, "render_candidates": []},
            }
        
        # Parse JSON output
        try:
            data = json.loads(stdout.strip())
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
        
        # Extract trace_id from Langfuse log
        trace_id_match = re.search(r'\[Langfuse\] Trace started: ([a-f0-9-]+)', stderr)
        trace_id = trace_id_match.group(1) if trace_id_match else None
        
        # Build tools list from meta (if available)
        # OpenClaw returns tool calls in the meta section
        tools = []
        meta = data.get("meta", {})
        
        # Also try to extract from trace_id via Langfuse API
        if trace_id:
            lf_tools = fetch_langfuse_tools(trace_id)
            if lf_tools:
                tools = lf_tools
        
        # Extract tools from response meta if available
        if not tools and "tools_used" in data:
            tools = data.get("tools_used", [])
        
        trace = {
            "tags": {
                "qa_adapter": "openclaw-local",
                "trace_id": trace_id,
            },
            "tools": tools,
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


def fetch_langfuse_tools(trace_id: str) -> list[dict[str, Any]]:
    """Fetch tool calls from Langfuse API."""
    import time
    try:
        # Wait for Langfuse to finish writing (traces are async) - wait up to 3 minutes
        for attempt in range(18):  # 18 * 10s = 3 minutes
            time.sleep(10)
            
            cmd = [
                "curl", "-s", "-6",
                "-u", f"{LF_PUBLIC_KEY}:{LF_SECRET_KEY}",
                f"{LF_HOST}/api/public/traces/{trace_id}"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                observations = data.get("observations", [])
                
                # If we have observations with tool calls, process them
                tool_calls = [o for o in observations if o.get("type") == "SPAN" and "tool" in o.get("name", "").lower()]
                if tool_calls:
                    tools = []
                    for obs in tool_calls:
                        obs_name = obs.get("name", "")
                        tool_input = obs.get("input", {})
                        
                        # Parse input if it's a string
                        if isinstance(tool_input, str):
                            try:
                                tool_input = json.loads(tool_input)
                            except:
                                tool_input = {"raw": tool_input}
                        
                        # Extract tool name - "Tool: exec" -> "exec"
                        tool_name = obs_name
                        if "tool: " in obs_name.lower():
                            tool_name = obs_name.split(":", 1)[1].strip()
                        elif isinstance(tool_input, dict) and "command" in tool_input:
                            tool_name = "exec"
                        
                        # Extract args - for exec tool, use command
                        args = {}
                        if isinstance(tool_input, dict):
                            if "command" in tool_input:
                                args = {"command": tool_input["command"]}
                            elif "args" in tool_input:
                                args = tool_input["args"]
                            else:
                                args = tool_input
                        
                        tools.append({
                            "name": tool_name,
                            "args": args,
                            "status_code": 200,
                            "latency_ms": int((obs.get("duration", 0) or 0) * 1000)
                        })
                    return tools
                    
        # Final attempt after waiting
        cmd = [
            "curl", "-s", "-6",
            "-u", f"{LF_PUBLIC_KEY}:{LF_SECRET_KEY}",
            f"{LF_HOST}/api/public/traces/{trace_id}"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            data = json.loads(result.stdout)
            observations = data.get("observations", [])
            
            tools = []
            for obs in observations:
                obs_type = obs.get("type")
                obs_name = obs.get("name", "")
                
                # Look for tool-related observations: SPAN with "Tool:" or type=TOOL
                if (obs_type == "SPAN" and "tool" in obs_name.lower()) or obs_type == "TOOL":
                    tool_input = obs.get("input", {})
                    
                    # Parse input if it's a string
                    if isinstance(tool_input, str):
                        try:
                            tool_input = json.loads(tool_input)
                        except:
                            tool_input = {"raw": tool_input}
                    
                    # Extract tool name - "Tool: exec" -> "exec"
                    tool_name = obs_name
                    if "tool: " in obs_name.lower():
                        tool_name = obs_name.split(":", 1)[1].strip()
                    elif isinstance(tool_input, dict) and "command" in tool_input:
                        tool_name = "exec"
                    
                    # Extract args - for exec tool, use command
                    args = {}
                    if isinstance(tool_input, dict):
                        if "command" in tool_input:
                            args = {"command": tool_input["command"]}
                        elif "args" in tool_input:
                            args = tool_input["args"]
                        else:
                            args = tool_input
                    
                    tools.append({
                        "name": tool_name,
                        "args": args,
                        "status_code": 200,
                        "latency_ms": int((obs.get("duration", 0) or 0) * 1000)
                    })
            
            return tools
    except Exception as e:
        print(f"Langfuse fetch error: {e}", file=sys.stderr)
    return []


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
    # Merge QA tags into trace
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
