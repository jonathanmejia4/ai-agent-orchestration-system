# Examples Directory

This directory contains examples to help you understand and customize the issue hunting/fixing system.

---

## Available Examples

### 1. Issue Template (Default)
**File:** `issue-template.md`

The blank template used for creating new issues. Shows all required sections but with placeholder values.

**Use this when:** Creating a new issue manually

---

### 2. Filled Issue Example
**File:** `filled-issue-example.md`

A complete, filled-in example of what a real issue looks like - including the resolution section after it was fixed.

**Use this when:** You want to see what a properly documented issue looks like

**Key sections demonstrated:**
- Clear problem description with file:line references
- Evidence with runnable bash commands
- Impact analysis explaining why it matters
- Multiple fix options
- Verification commands that confirm the fix
- Resolution section showing what was done

---

### 3. Example Guidelines
**File:** `example-guidelines.md`

A template for project standards that hunters use to find violations.

**Use this when:** Setting up `.claude/guidelines/` for your project

**Copy to:** `.claude/guidelines/your-project-standards.md`

**Includes examples of:**
- Code style rules (Python, JavaScript)
- API standards
- Security requirements
- Testing standards
- Documentation requirements
- Git workflow

---

### 4. Custom Hunter - Marketing
**File:** `custom-hunter-marketing.md`

An example of a customized hunter agent for a marketing business (not software).

**Use this when:** You want to hunt for marketing-related issues instead of code issues

**Shows how to customize:**
- What patterns to search for (UTM, pixels, budget)
- Type tags for marketing issues
- Severity guide for marketing context
- File locations for marketing assets

---

### 5. Custom Fixer - Marketing
**File:** `custom-fixer-marketing.md`

The matching fixer agent for the marketing hunter above.

**Use this when:** You need to fix marketing issues found by the custom hunter

**Shows how to customize:**
- Common fix patterns (adding UTM, pixels, alt text)
- Complexity assessment for marketing work
- Marketing-specific error handling
- What files to touch

---

### 6. Custom Catalog - Marketing
**File:** `custom-catalog-marketing.md`

Example of how to set up ISSUE_CATALOG.md for a marketing business.

**Use this when:** Setting up lanes for a non-software project

**Shows:**
- Marketing-focused lane definitions
- Example open issues for marketing
- How to adapt from software to marketing context

---

## Quick Start: Customization

### For a Software Project
1. Copy `example-guidelines.md` to `.claude/guidelines/`
2. Edit to match your coding standards
3. Run `/find-all` to hunt for violations

### For a Marketing Project
1. Read `custom-catalog-marketing.md` for lane ideas
2. Copy `custom-hunter-marketing.md` to `.claude/agents/issue-hunters/IH-Lane-A.md`
3. Copy `custom-fixer-marketing.md` to `.claude/agents/issue-fixers/IF-Lane-A.md`
4. Update `ISSUE_CATALOG.md` with your marketing lanes
5. Run `/find-all lanes A` to test

### For Any Project
1. Decide what "issues" means for your domain
2. Define 5-12 lanes (specialized focus areas)
3. Create hunter + fixer agents for each lane
4. Add your standards to `.claude/guidelines/`
5. Start hunting!

---

## File Reference

| Example | Purpose | Copy To |
|---------|---------|---------|
| issue-template.md | Blank issue structure | issues/{LANE}/{LANE}-NN.md |
| filled-issue-example.md | Learning reference | (don't copy - just read) |
| example-guidelines.md | Project standards | .claude/guidelines/*.md |
| custom-hunter-marketing.md | Marketing hunter | .claude/agents/issue-hunters/IH-Lane-*.md |
| custom-fixer-marketing.md | Marketing fixer | .claude/agents/issue-fixers/IF-Lane-*.md |
| custom-catalog-marketing.md | Catalog structure | ISSUE_CATALOG.md (sections) |
