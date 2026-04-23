# AI Agent Orchestration System

**Production-grade multi-agent framework for automated issue detection and resolution using Claude Code.**

Run 40+ AI agents in parallel — each specialized by domain — coordinated by an orchestrator that uses only 3,000 tokens instead of 265,000.

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

This framework gives you:

- **23 specialized agent lanes** (A-Z) that hunt for issues in parallel
- **23 matching fixer agents** that resolve issues automatically
- **File-signal orchestration** — agents communicate via `.done` files, not transcripts
- **Issue lifecycle tracking** — hunt → catalog → fix → verify
- **100+ tools** for security scanning, code quality, dependency analysis, and more

### The Key Innovation: File-Signal Orchestration

Traditional approach: orchestrator reads each agent's full output transcript.
- **Cost:** ~265,000 tokens for 23 agents = context window blown

This framework's approach: agents write signal files when done.
- **Cost:** ~3,000 tokens to check `ls signals/*.done | wc -l`
- **Result:** 5,000x context reduction, enabling a 200K-window agent to manage 40+ parallel agents

---

## Slash Commands

| Command | What It Does |
|---------|--------------|
| `/find-all` | Hunt for issues across all 23 lanes in parallel |
| `/fix-all` | Fix all open issues across all lanes in parallel |
| `/verify-fixes` | Verify all RESOLVED issues are actually fixed |

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

All 23 lanes are customizable. See [CUSTOMIZATION_GUIDE.md](CUSTOMIZATION_GUIDE.md).

### 2. File-Signal Coordination

```
Orchestrator: Spawns 23 hunter agents in parallel
Each hunter: Scans its lane → files issues → touch signals/X.done
Orchestrator: Polls ls signals/*.done until all 23 complete
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
│   │   ├── issue-hunters/      # 23 lane hunters + orchestrator
│   │   └── issue-fixers/       # 23 lane fixers + orchestrator
│   ├── commands/               # /find-all, /fix-all, /verify-fixes
│   └── guidelines/             # 30+ operational guidelines
├── issues/                     # A-Z lane directories
├── tools/                      # 100+ Python tools
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

## Tools (100+)

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
| [USAGE.md](USAGE.md) | Detailed usage patterns |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design and principles |

---

## Best Practices

- **Max 5 issues per agent per run** — quality over quantity
- **Never use TaskOutput** — poll signal files instead (saves 99% context)
- **Complete fixes only** — no stubs, no placeholders
- **Always verify** — run verification commands before marking RESOLVED

---

## License

MIT License - See [LICENSE](LICENSE).
