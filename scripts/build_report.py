#!/usr/bin/env python3
import argparse
from pathlib import Path

from common import read_json, write_json


def format_rate(value: float) -> str:
    return f"{value * 100:.2f}%"


def main() -> int:
    ap = argparse.ArgumentParser(description="Build markdown + normalized json report from assertions.")
    ap.add_argument("--assertions", required=True, help="assertions.json")
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--out-json", required=True)
    args = ap.parse_args()

    payload = read_json(Path(args.assertions))
    summary = payload.get("summary", {})
    gate_result = payload.get("gate_result", "UNKNOWN")
    gate_reasons = payload.get("gate_reasons", [])
    turns = payload.get("turn_results", [])

    normalized = {
        "risk": payload.get("risk"),
        "gate_result": gate_result,
        "gate_reasons": gate_reasons,
        "summary": summary,
    }
    write_json(Path(args.out_json), normalized)

    failed_turns = [t for t in turns if not t.get("turn_passed", False)]
    lines: list[str] = []
    lines.append("# clawgate QA report")
    lines.append("")
    lines.append(f"- gate_result: `{gate_result}`")
    lines.append(f"- risk: `{payload.get('risk', 'unknown')}`")
    if gate_reasons:
        lines.append(f"- gate_reasons: {', '.join(gate_reasons)}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- cases: {summary.get('cases_passed', 0)}/{summary.get('cases_total', 0)} ({format_rate(summary.get('key_case_pass_rate', 0.0))})")
    lines.append(f"- must assertions: {summary.get('must_assert_passed', 0)}/{summary.get('must_assert_total', 0)} ({format_rate(summary.get('must_assert_pass_rate', 0.0))})")
    lines.append(f"- should assertions: {summary.get('should_assert_passed', 0)}/{summary.get('should_assert_total', 0)} ({format_rate(summary.get('should_assert_pass_rate', 0.0))})")
    lines.append(f"- tool error rate: {format_rate(summary.get('tool_error_rate', 0.0))}")
    lines.append(f"- p95 latency: {summary.get('p95_latency_ms', 0.0):.2f} ms")
    lines.append("")
    lines.append("## Top failures")
    lines.append("")
    if not failed_turns:
        lines.append("- none")
    else:
        for item in failed_turns[:15]:
            lines.append(
                f"- case `{item.get('case_id')}` turn `{item.get('turn')}` failed MUST: {', '.join(item.get('failed_must', []))}"
            )
    Path(args.out_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_md).write_text("\n".join(lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

