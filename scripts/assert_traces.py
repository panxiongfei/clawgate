#!/usr/bin/env python3
import argparse
import math
from pathlib import Path
from typing import Any

from common import read_jsonl, read_yaml, write_json


def _get_tool_calls(trace: dict[str, Any]) -> list[dict[str, Any]]:
    tools = trace.get("tools", [])
    return tools if isinstance(tools, list) else []


def _has_tool(trace: dict[str, Any], tool_name: str) -> bool:
    for item in _get_tool_calls(trace):
        if isinstance(item, dict) and item.get("name") == tool_name:
            return True
    return False


def _tool_arg_contains(trace: dict[str, Any], tool_name: str, key: str, expected: str) -> bool:
    for item in _get_tool_calls(trace):
        if not isinstance(item, dict) or item.get("name") != tool_name:
            continue
        args = item.get("args", {})
        if not isinstance(args, dict):
            continue
        value = str(args.get(key, ""))
        if expected in value:
            return True
    return False


def _state_exists(trace: dict[str, Any], key: str) -> bool:
    state = trace.get("state", {})
    return isinstance(state, dict) and key in state


def _trace_tag_exists(trace: dict[str, Any], key: str) -> bool:
    tags = trace.get("tags", {})
    if not isinstance(tags, dict):
        return False
    return key in tags and str(tags.get(key, "")).strip() != ""


def _text_contains_any(text: str, values: list[str]) -> bool:
    if not values:
        return True
    lower_text = text.lower()
    for value in values:
        if str(value).lower() in lower_text:
            return True
    return False


def _evaluate(assertion: dict[str, Any], record: dict[str, Any]) -> tuple[bool, str]:
    atype = assertion.get("type")
    trace = record.get("trace", {})
    text = str(record.get("output_text", ""))
    if atype == "tool_called":
        tool = str(assertion.get("tool", ""))
        ok = _has_tool(trace, tool)
        return ok, f"tool_called({tool})"
    if atype == "tool_arg_contains":
        tool = str(assertion.get("tool", ""))
        key = str(assertion.get("key", ""))
        value = str(assertion.get("value", ""))
        ok = _tool_arg_contains(trace, tool, key, value)
        return ok, f"tool_arg_contains({tool}.{key} contains {value})"
    if atype in {"state_exists", "state_kept"}:
        key = str(assertion.get("key", ""))
        ok = _state_exists(trace, key)
        return ok, f"state_exists({key})"
    if atype == "trace_tag_exists":
        key = str(assertion.get("key", ""))
        ok = _trace_tag_exists(trace, key)
        return ok, f"trace_tag_exists({key})"
    if atype == "text_contains_any":
        values = assertion.get("values", [])
        values = values if isinstance(values, list) else []
        ok = _text_contains_any(text, [str(v) for v in values])
        return ok, "text_contains_any"
    return False, f"unsupported_assertion_type({atype})"


def _tool_error_count(record: dict[str, Any]) -> int:
    count = 0
    for tool in _get_tool_calls(record.get("trace", {})):
        if not isinstance(tool, dict):
            continue
        code = tool.get("status_code")
        if isinstance(code, int) and code >= 400:
            count += 1
        elif isinstance(code, str) and code.isdigit() and int(code) >= 400:
            count += 1
    return count


def _latencies_ms(record: dict[str, Any]) -> list[float]:
    values: list[float] = []
    for tool in _get_tool_calls(record.get("trace", {})):
        if not isinstance(tool, dict):
            continue
        raw = tool.get("latency_ms")
        if isinstance(raw, (int, float)):
            values.append(float(raw))
        elif isinstance(raw, str):
            try:
                values.append(float(raw))
            except ValueError:
                continue
    return values


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    idx = min(len(values) - 1, max(0, math.ceil((p / 100.0) * len(values)) - 1))
    return values[idx]


def gate_eval(summary: dict[str, Any], gate_cfg: dict[str, Any], risk: str) -> tuple[str, list[str]]:
    cfg = gate_cfg.get(risk, gate_cfg.get("medium", {}))
    reasons: list[str] = []
    result = "PASS"

    if summary["key_case_pass_rate"] < cfg.get("key_case_pass_rate_min", 0):
        result = "BLOCK"
        reasons.append("key_case_pass_rate below threshold")
    if summary["must_assert_pass_rate"] < cfg.get("must_assert_pass_rate_min", 0):
        result = "BLOCK"
        reasons.append("must_assert_pass_rate below threshold")
    if summary["tool_error_rate"] > cfg.get("tool_error_rate_max", 1):
        result = "BLOCK"
        reasons.append("tool_error_rate above threshold")
    if summary["pii_leak_count"] > cfg.get("pii_leak_allow", 0):
        result = "BLOCK"
        reasons.append("pii_leak_count above threshold")
    if result == "PASS" and summary["should_assert_pass_rate"] < 0.85:
        result = "WARN"
        reasons.append("should_assert_pass_rate below 0.85")
    return result, reasons


def main() -> int:
    ap = argparse.ArgumentParser(description="Assert MUST/SHOULD checks from run records.")
    ap.add_argument("--records", required=True)
    ap.add_argument("--gate", default="qa/config/gate.yaml")
    ap.add_argument("--risk", default="medium")
    ap.add_argument("--out", required=True, help="assertions.json")
    args = ap.parse_args()

    records = read_jsonl(Path(args.records))
    gate_cfg = read_yaml(Path(args.gate))

    turn_results: list[dict[str, Any]] = []
    must_total = 0
    must_passed = 0
    should_total = 0
    should_passed = 0
    all_lat_ms: list[float] = []
    total_tool_calls = 0
    tool_errors = 0
    case_turn_ok: dict[str, list[bool]] = {}

    for record in records:
        must = record.get("must", [])
        should = record.get("should", [])
        must = must if isinstance(must, list) else []
        should = should if isinstance(should, list) else []

        failed_must: list[str] = []
        failed_should: list[str] = []

        for assertion in must:
            must_total += 1
            ok, label = _evaluate(assertion, record)
            if ok:
                must_passed += 1
            else:
                failed_must.append(label)

        for assertion in should:
            should_total += 1
            ok, label = _evaluate(assertion, record)
            if ok:
                should_passed += 1
            else:
                failed_should.append(label)

        turn_ok = len(failed_must) == 0
        case_id = str(record.get("case_id", ""))
        case_turn_ok.setdefault(case_id, []).append(turn_ok)
        turn_results.append(
            {
                "qa_run_id": record.get("qa_run_id"),
                "case_id": case_id,
                "suite": record.get("suite"),
                "turn": record.get("turn"),
                "turn_passed": turn_ok,
                "failed_must": failed_must,
                "failed_should": failed_should,
                "output_text": record.get("output_text", ""),
            }
        )

        calls = _get_tool_calls(record.get("trace", {}))
        total_tool_calls += len(calls)
        tool_errors += _tool_error_count(record)
        all_lat_ms.extend(_latencies_ms(record))

    cases_total = len(case_turn_ok)
    cases_passed = sum(1 for _, flags in case_turn_ok.items() if all(flags))

    summary = {
        "turns_total": len(records),
        "turns_passed": sum(1 for r in turn_results if r["turn_passed"]),
        "cases_total": cases_total,
        "cases_passed": cases_passed,
        "key_case_pass_rate": (cases_passed / cases_total) if cases_total else 0.0,
        "must_assert_total": must_total,
        "must_assert_passed": must_passed,
        "must_assert_pass_rate": (must_passed / must_total) if must_total else 0.0,
        "should_assert_total": should_total,
        "should_assert_passed": should_passed,
        "should_assert_pass_rate": (should_passed / should_total) if should_total else 1.0,
        "tool_calls_total": total_tool_calls,
        "tool_errors_total": tool_errors,
        "tool_error_rate": (tool_errors / total_tool_calls) if total_tool_calls else 0.0,
        "p95_latency_ms": _percentile(all_lat_ms, 95),
        "pii_leak_count": 0,
    }

    gate_result, gate_reasons = gate_eval(summary, gate_cfg, args.risk)
    payload = {
        "risk": args.risk,
        "summary": summary,
        "gate_result": gate_result,
        "gate_reasons": gate_reasons,
        "turn_results": turn_results,
    }
    write_json(Path(args.out), payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

