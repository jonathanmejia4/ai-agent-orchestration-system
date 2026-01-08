# AI Agent Orchestration System

**Showcase demonstrating file-signal orchestration for multi-agent coordination**

## What This Is

A public excerpt demonstrating a production-tested pattern for coordinating multiple AI agents. This repo shows **how** the orchestration works without exposing proprietary detection logic, policies, or internal tooling.

**Key pattern:** File-based signaling instead of transcript parsing.

## Real-World Validation

This repository is a **sanitized showcase subset** of a larger internal system that has been actively used in real development workflows.

The full system has been exercised with:
- **Dozens of coordinated autonomous agents** running in parallel
- **Multiple specialized work lanes** (D, E, G-Z)
- **Hundreds+ tracked and resolved issues** across a production codebase
- **Sustained daily usage** over extended development cycles

Exact metrics, agent rulebooks, and governance policies are intentionally abstracted to avoid exposing proprietary architecture. This repository demonstrates **how the system works**, not the full extent of its internals.

> **Note:** This demo includes only lanes E and M. The full system spans many more lanes and agents.

## The Problem It Solves

Traditional multi-agent orchestration returns full transcripts from each agent, which:
- Consumes massive context windows (100k+ tokens per agent)
- Requires complex transcript parsing
- Doesn't scale beyond a few agents

**Our solution:** Agents write small signal files (`.status`, `.done`). The orchestrator polls for these files instead of parsing transcripts. Result: ~3k tokens vs 100k+ tokens per coordination cycle.

## Quick Start

```bash
# Clone the repository
git clone https://github.com/jonathanmejia4/ai-agent-orchestration-system.git
cd ai-agent-orchestration-system

# Set up Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run the file-signal demo
python3 scripts/run_demo_file_signals.py
```

**Expected output:**
```
============================================================
            FILE-SIGNAL ORCHESTRATION DEMO
============================================================

[Step 1] Cleaning old signals...
  ✓ Signal directory cleaned
[Step 2] Reading issue catalog...
  → Lane E: 3 open issues
  → Lane M: 2 open issues
[Step 3] Spawning lane workers in PARALLEL...
  → In production: dozens of parallel agents via Task tool
  → In demo: Threaded simulation with same signal behavior
  → Starting Lane E worker...
  → Starting Lane M worker...
[Step 4] Polling for completion signals...
  Polling: E:✓ | M:✓ (2/2 done)
  ✓ All lanes completed!
[Step 5] Generating report...
  ✓ Report: examples/output/sample_run_report.md

============================================================
                      DEMO COMPLETE
============================================================

  Lanes:        2
  Issues fixed: 5
  Signals:      LogBook/issue-fixing/signals/
  Report:       examples/output/sample_run_report.md
```

**Output files created:**
- `LogBook/issue-fixing/signals/E.status` - Progress updates
- `LogBook/issue-fixing/signals/E.done` - Completion signal
- `LogBook/issue-fixing/signals/M.status` - Progress updates
- `LogBook/issue-fixing/signals/M.done` - Completion signal
- `examples/output/sample_run_report.md` - Run summary

## Architecture

### File-Signal Pattern

```
┌─────────────────┐         ┌─────────────────┐
│  Orchestrator   │         │  Lane Worker E  │
│                 │         │                 │
│  1. Spawn       │────────▶│  Process issues │
│     workers     │         │  Write .status  │
│                 │         │  Write .done    │
│  2. Poll for    │◀────────│                 │
│     .done files │         └─────────────────┘
│                 │
│  3. Sync        │         ┌─────────────────┐
│     results     │         │  Lane Worker M  │
│                 │         │                 │
└─────────────────┘◀────────│  Same pattern   │
                            └─────────────────┘
```

### Why This Works

| Traditional | File-Signal |
|-------------|-------------|
| Return full transcript | Write small .done file |
| Parse 100k+ tokens | Check file existence |
| Sequential context load | Parallel file polling |
| Complex error handling | Simple file checks |

### Lane-Based Specialization

Each "lane" handles a specific domain:
- **Lane E**: Customer services, data protection
- **Lane M**: Schema validation, configuration

In production, this scales to multiple lanes running in parallel.

## Repository Structure

```
ai-agent-orchestration-system/
├── .claude/agents/              # Agent specifications
│   ├── issue-fixers/
│   │   ├── IF-Orchestrator.md   # Orchestrator spec
│   │   ├── IF-Lane-E.md         # Lane E worker spec
│   │   └── IF-Lane-M.md         # Lane M worker spec
│   └── issue-hunters/           # Hunter agent specs
├── examples/
│   ├── minimal_demo/            # Self-contained demo
│   │   ├── SAF_ISSUE_CATALOG.md # Sample issue catalog
│   │   ├── issues/              # Sample issue files
│   │   └── config/              # Demo config files
│   └── output/                  # Demo output artifacts
├── scripts/
│   ├── run_demo_file_signals.py # Main demo script
│   └── demo_dry_run.py          # Alternative demo
├── tools/                       # Utility scripts
├── LogBook/                     # Runtime state
│   └── issue-fixing/signals/    # Signal files go here
├── README.md
├── LICENSE
└── requirements.txt
```

## What's Included vs Omitted

This repo demonstrates **orchestration patterns and governance architecture** without exposing proprietary system internals.

### Included (safe to share)

| Item | Purpose |
|------|---------|
| File-signal pattern | Core orchestration technique |
| Agent specs | Show lane-based structure |
| Demo harness | Prove the pattern works |
| Sample issues | Demonstrate format |

### Intentionally Omitted

| Item | Reason |
|------|--------|
| Full agent prompt library | Proprietary |
| Detection heuristics | Competitive advantage |
| Policy engine | Organization-specific |
| Production integrations | Customer data |
| Guardrails / safety filters | Internal governance |

**Note:** The demo requires no API keys, external services, or secrets. It runs entirely locally using pure Python stdlib.

## Alternative Demo

There's also a dry-run demo showing work order + verdict patterns:

```bash
python3 scripts/demo_dry_run.py
```

This demonstrates a different aspect of the system (PM dispatch → fix → critic verdict). It performs **no file modifications** - just prints what would happen.

**Sample output from a real run:** `demo/sample_run_output.txt`

## Technical Stack

- **Orchestration**: File-based signaling (no database required)
- **State**: YAML files for configuration and status
- **Agents**: Claude AI (in production)
- **Demo**: Pure Python, no AI calls needed

## Key Takeaways

1. **File signals beat transcript returns** - Dramatic context savings
2. **Lane specialization scales** - Each agent has focused scope
3. **Polling is simple** - Just check for file existence
4. **Idempotent by design** - Clean signals, re-run safely

## License

MIT License - See [LICENSE](LICENSE)

---

*This is a public showcase. The full production system includes additional tooling and policies not shown here.*
