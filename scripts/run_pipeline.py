#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], cwd: Path) -> None:
    completed = subprocess.run(cmd, cwd=str(cwd), check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def main() -> int:
    ap = argparse.ArgumentParser(description="Run clawgate end-to-end pipeline.")
    ap.add_argument("--qa-run-id", required=True)
    ap.add_argument("--changed-path", action="append", default=[])
    ap.add_argument("--adapter", default="")
    ap.add_argument("--risk", default="medium")
    ap.add_argument("--pr-id", default="local")
    ap.add_argument("--git-sha", default="local")
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    run_dir = root / "qa" / "runs" / args.qa_run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    selected = run_dir / "selected_cases.json"
    records = run_dir / "records.jsonl"
    assertions = run_dir / "assertions.json"
    report_json = run_dir / "report.json"
    report_md = run_dir / "report.md"

    cmd = [sys.executable, "scripts/select_cases.py", "--out", str(selected), "--pr-id", args.pr_id]
    for p in args.changed_path:
        cmd.extend(["--changed-path", p])
    run(cmd, root)

    cmd = [
        sys.executable,
        "scripts/run_cases.py",
        "--selected",
        str(selected),
        "--run-id",
        args.qa_run_id,
        "--out-dir",
        str(run_dir),
        "--pr-id",
        args.pr_id,
        "--git-sha",
        args.git_sha,
    ]
    if args.adapter:
        cmd.extend(["--adapter", args.adapter])
    run(cmd, root)

    run(
        [
            sys.executable,
            "scripts/assert_traces.py",
            "--records",
            str(records),
            "--risk",
            args.risk,
            "--out",
            str(assertions),
        ],
        root,
    )

    run(
        [
            sys.executable,
            "scripts/build_report.py",
            "--assertions",
            str(assertions),
            "--out-json",
            str(report_json),
            "--out-md",
            str(report_md),
        ],
        root,
    )
    print(str(report_md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

