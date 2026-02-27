# QAClaw - Two-Step Assertion Testing Framework

> Version: 2.0 | Author: PPClaw | © 2026 PPClaw

## Overview

QAClaw is a self-evolving AI testing platform with **two-step assertion** pattern:
1. **Quick Check**: Use small model (e.g., Qwen3.5-32B) for fast screening
2. **Double Check**: Use large model (e.g., Qwen3.5-Plus) for edge cases

## Directory Structure

```
qaclaws/
├── SKILL.md                    # This file
├── two_step_assert.py          # Core implementation
├── config.yaml                 # Configuration
└── cases/
    ├── quick_pass.yaml        # Test cases for quick pass
    ├── double_check.yaml      # Test cases for double check
    └── batch.yaml             # Batch processing test
```

## Core Configuration

```yaml
# config.yaml
two_step_assertion:
  threshold: 0.8              # Default confidence threshold
  small_model: qwen3.5-32b    # Quick check model
  large_model: qwen3.5-plus   # Double check model
  cache_enabled: true
  batch_size: 10
```

## Implementation

See `two_step_assert.py` for the complete implementation with:
- JSON safe parsing
- Fallback logic
- Cost tracking
- Batch processing
- Input caching

## Test Cases

See `cases/` directory for test cases.

## Usage

```bash
python two_step_assert.py --input test.yaml --config config.yaml
```

---

**© 2026 PPClaw. All Rights Reserved.**
**MIT License**
