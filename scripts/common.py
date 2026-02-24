#!/usr/bin/env python3
import glob
import json
from pathlib import Path
from typing import Any

import yaml


def read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        # Support multi-document YAML (separated by ---)
        docs = list(yaml.safe_load_all(f))
        if len(docs) == 1:
            return docs[0] or {}
        # For multi-doc YAML, return list of all documents
        return {"_multi_doc": True, "documents": [d or {} for d in docs]}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"JSON must be object: {path}")
    return data


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            if isinstance(item, dict):
                items.append(item)
    return items


def write_jsonl(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def discover_case_files(cases_root: Path) -> list[Path]:
    files = sorted(
        [Path(p) for p in glob.glob(str(cases_root / "**/*.yaml"), recursive=True)]
    )
    return [p for p in files if p.is_file()]

