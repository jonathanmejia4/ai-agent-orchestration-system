# AI Agent Orchestration System

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)
![Claude Code](https://img.shields.io/badge/Claude_Code-required-orange.svg)

**Production-grade multi-agent framework for automated issue detection and resolution using Claude Code.**

Run 40+ AI agents in parallel — each specialized by domain — coordinated by an orchestrator that uses only 3,000 tokens instead of 265,000.

---

## Security Notice

**Do not run this framework in automated CI/CD with access to production secrets.**

This framework lets AI agents modify code autonomously. Permission requests timeout without user response, which defeats safety gates in unattended environments. Run locally with human oversight.

Before running on any codebase:
- Review all issue files before `/fix-all` (issue files are prompt-injection vectors)
- Run without production credentials (strip `.env` first if running on a real project)
- Use branch protection on main; don't let agents push directly
- Validate issue files with `python3 tools/validate_issue_file.py issues/` before running fixers

See [SECURITY.md](SECURITY.md) for the full threat model.

---

## Requirements

- **Claude Code CLI** installed (this framework uses Claude Code slash commands and Task tool)
- **Claude Sonnet** (orchestrator agents — Haiku cannot use Task tool)
- **Claude Haiku** (lane agents — cost-optimized for parallel execution)
- **Python 3.9+**
- **macOS or Linux** (Windows not supported — shell scripts assume POSIX)
- **Git** (framework uses git hooks and history)

---

## Quick Start

```bash
# Clone and enter the repo
git clone https://github.com/jonathanmejia4/ai-agent-orchestration-system.git
cd ai-agent-orchestration-system

# Install dependencies
pip install pyyaml

# Hunt for issues across all lanes
/find-all

# Fix all discovered issues
/fix-all

# Verify fixes are real
/verify-fixes
```

---

## What This Does

**See it work:** [examples/QUICK_START_WALKTHROUGH.md](examples/QUICK_START_WALKTHROUGH.md) — real terminal output from a live run.

This framework gives you:

- **26 specialized agent lanes** (A-Z) that hunt for issues in parallel
- **26 matching fixer agents** that resolve issues automatically
- **File-signal orchestration** — agents communicate via `.done` files, not transcripts
- **Issue lifecycle tracking** — hunt → catalog → fix → verify
- **240+ tools** for security scanning, code quality, dependency analysis, and more

### The Key Innovation: File-Signal Orchestration

Traditional approach: orchestrator reads each agent's full output transcript.
- **Cost:** ~265,000 tokens for 26 agents = context window blown

This framework's approach: agents write signal files when done.
- **Cost:** ~3,000 tokens to check `ls signals/*.done | wc -l`
- **Result:** 5,000x context reduction, enabling a 200K-window agent to manage 40+ parallel agents

---

## Slash Commands

| Command | What It Does |
|---------|--------------|
| `/find-all` | Hunt for issues across all 26 lanes in parallel |
| `/fix-all` | Fix all open issues across all lanes in parallel |
| `/verify-fixes` | Verify all RESOLVED issues are actually fixed |
| `/verify-catalog` | Systematically re-verify every RESOLVED issue in the catalog |

---

## How It Works

### 1. Lane Specialization

Each lane focuses on one domain so agents don't conflict:

| Lane | Focus | Example Issues |
|------|-------|---------------|
| D | Marketing Infrastructure | Broken UTM links, expired promotions |
| E | External Integrations | API drift, missing error handling |
| G | Ghost References | Dead links, missing files referenced in docs |
| H | Stubs & Placeholders | TODO markers, placeholder implementations |
| P | Security & Policy | Exposed credentials, missing validation |
| X | Documentation | Outdated SOPs, broken internal links |

All 26 lanes are customizable. See [CUSTOMIZATION_GUIDE.md](CUSTOMIZATION_GUIDE.md).

### 2. File-Signal Coordination

```
Orchestrator: Spawns 26 hunter agents in parallel
Each hunter: Scans its lane → files issues → touch signals/X.done
Orchestrator: Polls ls signals/*.done until all 26 complete
Orchestrator: Syncs catalog → reports results
```

No transcript parsing. No context explosion. Just files.

### 3. Issue Lifecycle

```
OPEN → (fixer works) → RESOLVED → (verifier checks) → VERIFIED
                          ↓
                    (if verification fails)
                          ↓
                        OPEN (stays open)
```

Issues live as individual markdown files with YAML frontmatter in `issues/{LANE}/`.

---

## Project Structure

```
ai-agent-orchestration-system/
├── .claude/
│   ├── agents/
│   │   ├── issue-hunters/      # 26 lane hunters + orchestrator
│   │   └── issue-fixers/       # 26 lane fixers + orchestrator
│   ├── commands/               # /find-all, /fix-all, /verify-fixes
│   └── guidelines/             # 30+ operational guidelines
├── issues/                     # A-Z lane directories
├── tools/                      # 240+ Python tools
├── LogBook/
│   ├── issue-hunting/signals/  # Completion signal files
│   └── issue-fixing/signals/   # Completion signal files
├── examples/                   # Customization examples
├── ISSUE_CATALOG.md            # Central issue registry
├── TOOLS_CATALOG.md            # Tool inventory
├── CUSTOMIZATION_GUIDE.md      # How to adapt for your project
└── config.yaml                 # Runtime configuration
```

---

## Customization

The lanes are **not set in stone**. Adapt them to your domain:

| Default Lane | Your Version |
|-------------|--------------|
| Lane D: Marketing Infrastructure | Lane D: Ad Campaigns |
| Lane G: Ghost References | Lane G: Google Ads |
| Lane H: Stubs & Placeholders | Lane H: Website Bugs |
| Lane P: Security & Policy | Lane P: SEO Issues |

**How to customize a lane:**
1. Edit `.claude/agents/issue-hunters/IH-Lane-X.md`
2. Change the search patterns and type tags
3. Edit `.claude/agents/issue-fixers/IF-Lane-X.md`
4. Update `ISSUE_CATALOG.md` with your lane descriptions

See [CUSTOMIZATION_GUIDE.md](CUSTOMIZATION_GUIDE.md) for full details, including a complete marketing agency example.

---

## Tools (240+)

### Issue Management
```bash
python3 tools/add_issue.py D "Broken UTM on homepage" --severity 7
python3 tools/verify_issue.py D-01
python3 tools/issue_stats.py
python3 tools/sync_catalog_stats.py
```

### Security & Quality
```bash
python3 tools/security_scanner.py scan --path src/
python3 tools/pii_scanner.py
python3 tools/code_quality_analyzer.py
python3 tools/dependency_analyzer.py
```

### Monitoring
```bash
python3 tools/orchestrator_dashboard.py
python3 tools/safe_tool_tester.py
python3 tools/sync_tools_catalog.py
```

See [TOOLS_CATALOG.md](TOOLS_CATALOG.md) for the full inventory.

---

## Documentation

| Document | Purpose |
|----------|---------|
| [CUSTOMIZATION_GUIDE.md](CUSTOMIZATION_GUIDE.md) | How to adapt lanes for your project |
| [TUTORIAL_FOR_HUMANS.md](TUTORIAL_FOR_HUMANS.md) | Setup and daily workflow guide |
| [TUTORIAL_FOR_CLAUDE.md](TUTORIAL_FOR_CLAUDE.md) | Context for Claude agents |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design and principles |

---

## Best Practices

- **Max 5 issues per agent per run** — quality over quantity
- **Never use TaskOutput** — poll signal files instead (saves 99% context)
- **Complete fixes only** — no stubs, no placeholders
- **Always verify** — run verification commands before marking RESOLVED

---

## Limitations

- **Claude Code only** — the orchestration uses Task tool + slash commands that are specific to Claude Code. Cannot port to OpenAI, raw Claude API, or other LLMs without major rewrite.
- **Interactive use only** — permission requests timeout in headless environments. Don't run in CI without supervision.
- **Not battle-tested at scale** — designed for parallel execution but large-scale production runs haven't been publicly benchmarked.
- **English only** — all search patterns and agent prompts assume English.

---

## License

MIT License - See [LICENSE](LICENSE).
