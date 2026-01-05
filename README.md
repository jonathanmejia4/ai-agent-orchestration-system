# AI Agent Orchestration System

**Production-grade multi-agent system for automated issue resolution**

## Overview

This repository demonstrates a scalable AI agent architecture that resolves issues in parallel using specialized agents coordinated by orchestrators. Built with Claude AI and modern agentic workflows.

### Key Results
- **1,030 issues resolved** across 21 specialized domains
- **77.4% completion rate** (verified, not claimed)
- **41.5x productivity multiplier** vs manual resolution
- **46 autonomous agents** (23 hunters + 22 fixers + orchestrators)

## Architecture

### Core Concept: Lane-Based Specialization

The system divides problems into 21 "lanes" (A-Z), each with domain-specific expertise:
- **Lane E**: Customer services & data protection
- **Lane G**: Reference integrity & missing artifacts
- **Lane H**: Code stubs & placeholders
- **Lane M**: Schema validation & drift detection
- ...and 17 more specialized domains

### Two-Phase Agent System

**Phase 1: Issue Hunters**
- 23 specialized hunter agents scan codebase for issues
- Each hunter focuses on specific problem patterns
- Parallel execution with separate context windows
- Results cataloged in central issue registry

**Phase 2: Issue Fixers**
- 22 specialized fixer agents resolve issues
- Oldest-first priority (FIFO queue)
- 5-issue batches per agent
- Autonomous commit & verification

### Orchestration Pattern: File-Based Signaling

Traditional approach: Return full agent transcripts (265k tokens)
Our approach: File-based `.done` signals (3k tokens - 98.9% reduction)

```yaml
# Orchestrator spawns 21 agents in parallel
workflow:
  - spawn agents with Task tool
  - agents work independently
  - agents write .done files when complete
  - orchestrator polls for completion signals
  - orchestrator syncs results
```

**Benefits:**
- Massive context window savings (98.9% reduction)
- True parallel execution
- No transcript parsing overhead
- Simple state management

## Technical Stack

- **AI Framework**: Claude AI (Anthropic)
- **Languages**: Python, Markdown, YAML
- **Orchestration**: Custom file-based signaling
- **State Management**: YAML orchestrator states
- **Verification**: Automated validation tools

## Code Quality Tools

### Convention Checker
- Auto-fix trailing whitespace, newlines
- API documentation verification
- Escape hatch tracking
- 494+ lines of quality enforcement

### Schema Validator
- Circular dependency detection (DFS algorithm)
- Path validation for security
- Configurable coverage thresholds
- 744+ lines of validation logic

### Catalog Sync
- Parses 1,330 issue files automatically
- Updates statistics in real-time
- Maintains "Open Issues by Lane" registry
- Single source of truth for orchestrators

## Sample Agent: Issue Hunter (Lane E)

```
**Lane:** E - Customer Services & Data Protection
**Quota:** Up to 5 issues per run
**Model:** Haiku (fast, cost-efficient)

**Search Strategy:**
1. Check for forbidden patterns (things that shouldn't exist)
2. Check for missing required patterns (things that should exist)
3. Cross-reference guidelines vs implementation
4. Create issue files with verification commands
```

## Data Models

### Orchestrator State

Orchestrators track agent execution without storing full transcripts:

```yaml
lanes:
  E:
    status: completed
    issues: 15
    committed: true
```

See [orchestrator-state-example.yaml](examples/orchestrator-state-example.yaml) for complete structure.

### Verification Evidence

Each issue fix generates verification evidence:

```json
{
  "issue_id": "E-01",
  "all_passed": true,
  "confidence_score": 100,
  "checks": [...]
}
```

See [verification-evidence.json](examples/verification-evidence.json) for complete structure.

**Key insight:** File-based state + verification evidence = complete audit trail without context overhead.

## Results

### Issue Resolution Statistics

| Metric | Value |
|--------|-------|
| Total issues | 1,330 |
| Resolved | 1,030 (77.4%) |
| Open | 299 |
| Lanes complete | 3 (100% resolution) |
| Average completion | 77.4% |

### Productivity Impact

- **Traditional (1 developer)**: 299 issues x 30 min = 149.5 hours
- **With orchestrators**: 299 issues / 21 lanes x 5/batch x 15 min = 3.6 hours
- **Multiplier**: 41.5x faster

## Use Cases

This architecture applies to:

- Automated code quality enforcement
- Large-scale refactoring projects
- Issue triage and resolution
- Documentation gap analysis
- Compliance checking
- Technical debt reduction

## Key Learnings

1. **Specialization > Generalization** - 21 focused agents outperform 1 general agent
2. **File signals > Transcript returns** - 98.9% context reduction
3. **Parallel > Sequential** - 21 simultaneous context windows
4. **Verification built-in** - Each issue has automated verification
5. **State as files** - YAML states easier than database

## Author

Built by a mechanical engineering student exploring AI-assisted automation and agentic workflows.

## License

MIT License - Feel free to study, adapt, or build upon this architecture.
