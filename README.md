# clawgate

`clawgate` is a PR-gated QA harness for Openclaw-style agent systems.
It enforces two-layer assertions:

- `MUST`: deterministic checks from trace evidence (tools, args, status, tags, state)
- `SHOULD`: robust semantic checks on text output

This scaffold includes:

- core Openclaw test cases
- suite selection by diff mapping
- case execution via pluggable adapter
- trace assertion + report generation

## Project layout

```text
clawgate/
  pyproject.toml
  README.md
  qa/
    cases/core/*.yaml
    config/gate.yaml
    mappings/diff_to_suite.yaml
    runs/
  scripts/
    select_cases.py
    run_cases.py
    assert_traces.py
    build_report.py
    run_pipeline.py
    adapters/mock_openclaw_adapter.py
```

## Quick start (mock run)

```bash
cd clawgate
python scripts/run_pipeline.py \
  --qa-run-id qa-local-001 \
  --changed-path src/agent/planner.py \
  --adapter "python scripts/adapters/mock_openclaw_adapter.py"
```

Output:

- `qa/runs/<qa_run_id>/selected_cases.json`
- `qa/runs/<qa_run_id>/records.jsonl`
- `qa/runs/<qa_run_id>/assertions.json`
- `qa/runs/<qa_run_id>/report.json`
- `qa/runs/<qa_run_id>/report.md`

## Integrating real Openclaw

Replace the adapter command with your real adapter entrypoint:

```bash
python scripts/run_pipeline.py \
  --qa-run-id qa-pr-123 \
  --changed-path src/gateway/server.py \
  --adapter "python /path/to/your/openclaw_adapter.py" \
  --pr-id 123 \
  --git-sha <head_sha>
```

Adapter contract:

- input: one JSON object via stdin per turn
- output: one JSON object to stdout with keys:
  - `output_text` (string)
  - `trace` (object, optional but recommended)

`trace` recommended shape:

```json
{
  "tags": {"qa_run_id": "...", "case_id": "...", "git_sha": "...", "pr_id": "..."},
  "tools": [{"name": "git_status", "args": {}, "status_code": 200, "latency_ms": 120}],
  "state": {"candidate_list": ["A", "B"]},
  "render_candidates": [{"id": "1", "name": "A"}, {"id": "2", "name": "B"}]
}
```
