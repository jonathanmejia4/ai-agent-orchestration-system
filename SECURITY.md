# Security & Redaction Statement

This document explains what is intentionally included and excluded from this repository.

## Purpose of This Repository

This is a **public showcase** demonstrating the architecture and orchestration patterns of a production multi-agent system. It is designed to provide technical credibility while protecting proprietary intellectual property.

## What This Repository Contains

| Category | Included | Purpose |
|----------|----------|---------|
| Architecture documentation | Yes | Explain system design |
| Agent coordination patterns | Yes | Demonstrate orchestration flow |
| File-based signaling approach | Yes | Show context reduction technique |
| Sample data structures | Yes | Illustrate schema formats |
| Demo artifacts | Yes | Prove system patterns work |
| Utility tools | Yes | Show tooling approach |

## What Is Intentionally Redacted

| Category | Redacted | Reason |
|----------|----------|--------|
| Full SAF framework | Yes | Proprietary core system |
| Agent prompt library | Yes | Trade secret / competitive advantage |
| Detection patterns | Yes | Issue hunting heuristics |
| Policy documents | Yes | Internal governance |
| Production guidelines | Yes | Operational procedures |
| Scoring weights | Yes | Critic evaluation logic |
| Real issue catalogs | Yes | Customer-specific data |
| Lane naming rationale | Yes | Internal taxonomy |

## Demo Directory

The `/demo` directory contains:

- **demo_issue.md** - Fake issue demonstrating format only
- **demo_work_order.yaml** - Fake work order showing structure
- **demo_verdict.yaml** - Fake verdict showing evaluation format
- **demo_before.txt / demo_after.txt** - Simulated state changes

All demo artifacts are clearly marked as `DEMO / NON-PRODUCTION`.

## Dry-Run Script

The `scripts/demo_dry_run.py` script:

- Makes **NO API calls** (Claude, OpenAI, or any external service)
- Uses **file operations only**
- Simulates the orchestration **pattern**, not intelligence
- Generates artifacts to prove the workflow structure

## What This Proves

1. **Architecture is real** - The coordination patterns are production-tested
2. **Scale is achievable** - 21 parallel agents, 1,352 issues resolved
3. **Efficiency gains are measurable** - 98.9% context reduction documented
4. **System is operational** - Not vaporware; actual execution results shown

## What This Does NOT Prove

1. Proprietary detection logic
2. Internal policy compliance
3. Customer-specific implementations
4. Full agent prompt engineering

## Source of Truth

The complete production system exists in a private repository. This public showcase is a curated subset designed for:

- Technical credibility demonstration
- Architecture pattern sharing
- Interview / portfolio purposes
- Open source community contribution

## Contact

For questions about the full system, architecture decisions, or collaboration opportunities, please open an issue in this repository.

---

*This repository demonstrates architecture + flow only. Real logic exists elsewhere.*
