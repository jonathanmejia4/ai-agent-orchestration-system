# Customization Guide - Modifying Lanes and Agents

> **Purpose:** How to customize the issue hunting/fixing system for your specific needs.

---

## Everything Is Customizable

**Nothing in this system is set in stone.** The lanes, search patterns, and agent behaviors are all starting points that you should modify to fit YOUR business:

| What | Can You Change It? | How Hard? |
|------|-------------------|-----------|
| What a lane searches for | **YES** | Easy - edit 1 file |
| Lane names/descriptions | **YES** | Easy - edit 2 files |
| Search patterns (grep/glob) | **YES** | Easy - edit agent file |
| Number of lanes | **YES** | Medium - add/remove files |
| Issue severity levels | **YES** | Easy - edit agent files |
| File locations to scan | **YES** | Easy - edit agent files |
| Issue file format | **YES** | Easy - edit templates |

### The Default Lanes Are Just Examples

The 22 lanes (D-Z) were designed for a software development workflow. For a **marketing business**, you might want completely different lanes like:

| Your Lane | What It Could Hunt For |
|-----------|------------------------|
| A | Ad campaign issues (broken links, missing UTMs) |
| B | Brand consistency (logo usage, color codes) |
| C | Content issues (outdated info, broken media) |
| D | Design problems (responsive issues, accessibility) |
| E | Email marketing (broken templates, spam triggers) |
| F | Funnel issues (dead ends, missing CTAs) |
| G | Google Ads problems (disapproved ads, budget issues) |
| S | SEO issues (missing meta tags, broken schema) |
| W | Website bugs (404s, slow pages, form errors) |

**The patterns are yours to define.** Change them to match what YOU need to find.

---

## Important: What Changes Together

When you modify lanes, multiple files need to stay in sync:

| Change | Files to Update |
|--------|-----------------|
| Add a new lane | 5 files |
| Remove a lane | 5 files |
| Modify what a lane looks for | 1-2 files |
| Rename a lane | 6+ files |

---

## Adding a New Lane

Let's say you want to add **Lane A** for "API Issues".

### Step 1: Create the Hunter Agent

Create `.claude/agents/issue-hunters/IH-Lane-A.md`:

```markdown
---
name: IH-Lane-A
description: Issue Hunter for API Issues
model: opus
color: blue
tools: ["Glob", "Grep", "Read", "Bash", "Write"]
---

# Lane A Issue Hunter - API Issues

## Mission
Hunt for API-related issues in the codebase.

## What to Look For

1. **Missing Error Handling**
   - API endpoints without try/catch
   - Missing HTTP status codes
   - No error response schemas

2. **Authentication Gaps**
   - Endpoints without auth middleware
   - Missing token validation
   - Insecure API keys in code

3. **Documentation Issues**
   - Missing OpenAPI/Swagger docs
   - Outdated API docs
   - Missing request/response examples

4. **Rate Limiting**
   - No rate limiting on endpoints
   - Missing throttling configuration

## Search Patterns

```bash
# Find API routes
grep -r "app.get\|app.post\|@route\|@api" src/

# Find missing auth
grep -rL "auth\|authenticate" src/routes/

# Find hardcoded keys
grep -r "api_key\s*=\s*['\"]" --include="*.py" --include="*.js"
```

## Issue File Format

Create issues in `issues/A/A-NN.md` following the standard format.

## Completion

1. Create issue files
2. `git add issues/A/`
3. `git commit -m "Lane A hunting: found N issues"`
4. `touch LogBook/issue-hunting/signals/A.done`
```

### Step 2: Create the Fixer Agent

Create `.claude/agents/issue-fixers/IF-Lane-A.md`:

```markdown
---
name: IF-Lane-A
description: Issue Fixer for API Issues
model: opus
color: green
tools: ["Glob", "Grep", "Read", "Edit", "Write", "Bash"]
---

# Lane A Issue Fixer - API Issues

## Mission
Fix API-related issues in the codebase.

## Complexity Assessment

Before each fix, assess:
- **LOW**: Add missing status code, simple validation
- **MEDIUM**: Add error handling, auth middleware
- **HIGH**: Restructure API routes, add rate limiting
- **EXTREME**: Full API redesign, breaking changes

## Fix Protocol

1. Read the issue file
2. Assess complexity
3. Make the fix (complete, no stubs!)
4. Update issue status to RESOLVED
5. Commit with descriptive message

## Completion

1. Fix up to 5 issues (1 if EXTREME)
2. Mark issues as RESOLVED
3. `git add .`
4. `git commit -m "Lane A fixing: resolved N issues"`
5. `echo "COMPLETE" > LogBook/issue-fixing/signals/A.status`
6. `touch LogBook/issue-fixing/signals/A.done`
```

### Step 3: Create the Issues Directory

```bash
mkdir -p issues/A
touch issues/A/.gitkeep
```

### Step 4: Update the Orchestrators

Edit `.claude/agents/issue-hunters/IH-Orchestrator.md`:
- Add "A" to the `ALL_LANES` list
- Update lane count (22 → 23)

Edit `.claude/agents/issue-fixers/IF-Orchestrator.md`:
- Add "A" to the `ALL_LANES` list
- Update lane count (22 → 23)

### Step 5: Update the Issue Catalog

Edit `ISSUE_CATALOG.md`:

1. Add to **Lane Definitions** table:
```markdown
| A | API Issues | Error handling, auth, documentation |
```

2. Add to **Lane Completion Status** table:
```markdown
| A | 0 | 0 | 0 | 0% |
```

3. Add to **Open Issues by Lane** section:
```markdown
### Lane A - API Issues

| ID | Title | Severity | Type Tags | Status |
|----|-------|----------|-----------|--------|
<!-- LANE_A_ISSUES -->
```

### Step 6: Update State Files

Edit `LogBook/issue-hunting/orchestrator-state.yaml`:
```yaml
lanes:
  A: { status: pending, issues: 0, issue_ids: [], committed: false }
  D: ...
```

Edit `LogBook/issue-fixing/orchestrator-state.yaml`:
```yaml
lanes:
  A: { status: pending, issues_fixed: 0, issue_ids: [] }
  D: ...
```

---

## Removing a Lane

To remove Lane X:

### Step 1: Delete Agent Files
```bash
rm .claude/agents/issue-hunters/IH-Lane-X.md
rm .claude/agents/issue-fixers/IF-Lane-X.md
```

### Step 2: Delete Issues Directory
```bash
rm -rf issues/X/
```

### Step 3: Update Orchestrators
- Remove "X" from `ALL_LANES` list in both orchestrators
- Update lane count

### Step 4: Update Issue Catalog
- Remove from Lane Definitions table
- Remove from Lane Completion Status table
- Remove from Open Issues by Lane section

### Step 5: Update State Files
- Remove lane entry from both state files

---

## Modifying What a Lane Looks For

This is the simplest change - only edit the hunter agent file.

### Example: Change Lane H to look for different patterns

Edit `.claude/agents/issue-hunters/IH-Lane-H.md`:

```markdown
## What to Look For

1. **Old Pattern (remove)**
   - ~~TODOs in code~~

2. **New Pattern (add)**
   - Deprecated function calls
   - Legacy API usage
   - Outdated dependencies
```

Update the search patterns:

```bash
# Old (remove)
grep -r "TODO\|FIXME" src/

# New (add)
grep -r "@deprecated\|legacy\|obsolete" src/
```

### What Else to Update?

| Change | Update Catalog? | Update Orchestrator? |
|--------|-----------------|----------------------|
| Search patterns | No | No |
| Lane description | Yes (Lane Definitions) | No |
| Lane specialization | Yes | No |

---

## Renaming a Lane

This is complex - rename everywhere.

### Example: Rename Lane D from "Marketing" to "Growth"

1. Rename agent files:
```bash
mv .claude/agents/issue-hunters/IH-Lane-D.md .claude/agents/issue-hunters/IH-Lane-D.md
# (keep filename, just update content)
```

2. Update agent content:
```markdown
# Lane D Issue Hunter - Growth Infrastructure
```

3. Rename issues directory (optional):
```bash
# Usually keep same letter, just change description
```

4. Update ISSUE_CATALOG.md:
```markdown
| D | Growth Infrastructure | Lead gen, campaigns, funnels |
```

5. Update README in issue-hunters folder

---

## Creating Your Own Guidelines

The system works best with guidelines that tell agents your standards.

### Step 1: Create Guidelines Directory

```bash
mkdir -p .claude/guidelines/
```

### Step 2: Add Your Standards

Create `.claude/guidelines/your-standards.md`:

```markdown
# Your Project Standards

## Code Style
- Use 2-space indentation
- Always use TypeScript
- Prefer async/await over callbacks

## API Design
- Use REST naming conventions
- Always return JSON
- Include error details in responses

## Testing
- Unit tests for all functions
- Integration tests for API routes
- Minimum 80% coverage

## Documentation
- JSDoc for all public functions
- README in each module
- Changelog for each release
```

### Step 3: Reference in Agents

Update hunter/fixer agents to read guidelines:

```markdown
## Before Hunting

1. Read `.claude/guidelines/your-standards.md`
2. Use these standards to identify violations
```

---

## Customizing Issue Templates

### Default Issue Format

Issues follow this format in `issues/{LANE}/{LANE}-NN.md`:

```markdown
# {LANE}-NN: Title

## Status
OPEN | RESOLVED

## Severity
LOW | MEDIUM | HIGH | CRITICAL

## Description
What is the problem?

## Location
- `path/to/file.py:line`

## Evidence
```code
The problematic code
```

## Suggested Fix
How to resolve it.

## Type Tags
- tag1
- tag2
```

### Adding Custom Fields

Add fields relevant to your project:

```markdown
## Priority
P0 | P1 | P2 | P3

## Assignee
@username

## Sprint
2024-Q1

## Related Issues
- D-05
- E-12
```

### Updating sync_catalog_stats.py

If you add fields, update the sync script to parse them:

```python
# In tools/sync_catalog_stats.py
# Add parsing for new fields if needed for catalog display
```

---

## Best Practices

### 1. Start Small
Don't add 10 lanes at once. Add one, test it, then add more.

### 2. Keep Lanes Focused
Each lane should have ONE clear specialization. Overlap = conflicts.

### 3. Test Search Patterns
Run your grep/glob patterns manually first to see what they find.

### 4. Document Everything
Future you (and Claude) need to understand what each lane does.

### 5. Sync After Changes
After modifying files, run:
```bash
python3 tools/sync_catalog_stats.py --verbose
```

---

## Files Reference

| Purpose | File |
|---------|------|
| Hunter agent | `.claude/agents/issue-hunters/IH-Lane-{X}.md` |
| Fixer agent | `.claude/agents/issue-fixers/IF-Lane-{X}.md` |
| Hunter orchestrator | `.claude/agents/issue-hunters/IH-Orchestrator.md` |
| Fixer orchestrator | `.claude/agents/issue-fixers/IF-Orchestrator.md` |
| Issue catalog | `ISSUE_CATALOG.md` |
| Issues folder | `issues/{X}/` |
| Hunting state | `LogBook/issue-hunting/orchestrator-state.yaml` |
| Fixing state | `LogBook/issue-fixing/orchestrator-state.yaml` |
| Lane definitions | `.claude/agents/issue-hunters/README.md` |
