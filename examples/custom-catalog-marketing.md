# Example: Marketing Business Issue Catalog

> This shows how you might customize ISSUE_CATALOG.md for a marketing business.
> The default lanes are for software development - this example shows marketing-focused lanes.

---

## How to Use This Example

1. Open `ISSUE_CATALOG.md`
2. Replace the Lane Definitions section with something like below
3. Update the Open Issues section headers to match
4. Create matching agent files in `.claude/agents/issue-hunters/` and `.claude/agents/issue-fixers/`

---

## Example Lane Definitions (Marketing)

| Lane | Focus Area | What Hunters Look For |
|------|------------|----------------------|
| A | Ad Campaigns | Missing UTM, broken links, budget gaps |
| B | Brand Assets | Logo misuse, color inconsistency, outdated assets |
| C | Content | Outdated info, broken media, missing SEO |
| D | Design | Responsive issues, accessibility, broken layouts |
| E | Email Marketing | Broken templates, spam triggers, tracking gaps |
| F | Funnels | Dead ends, missing CTAs, conversion drops |
| G | Google Ads | Disapproved ads, budget issues, tracking |
| L | Landing Pages | Slow load, broken forms, missing pixels |
| M | Marketing Automation | Broken workflows, missing triggers |
| P | Privacy & Compliance | GDPR issues, cookie consent, unsubscribe |
| S | SEO | Missing meta tags, broken schema, thin content |
| W | Website | 404 errors, slow pages, broken features |

---

## Example Lane Completion Status

| Lane | Total | Resolved | Open | Progress |
|------|-------|----------|------|----------|
| A | 12 | 8 | 4 | 67% |
| B | 5 | 5 | 0 | 100% |
| C | 8 | 3 | 5 | 38% |
| D | 3 | 1 | 2 | 33% |
| E | 15 | 12 | 3 | 80% |
| F | 7 | 4 | 3 | 57% |
| G | 10 | 6 | 4 | 60% |
| L | 6 | 2 | 4 | 33% |
| M | 4 | 4 | 0 | 100% |
| P | 8 | 8 | 0 | 100% |
| S | 20 | 15 | 5 | 75% |
| W | 11 | 7 | 4 | 64% |

---

## Example Open Issues Section

### Lane A - Ad Campaigns

| ID | Title | Severity | Type Tags | Status |
|----|-------|----------|-----------|--------|
| A-09 | Summer sale ad missing UTM | 6/10 | A-UTM-Missing | OPEN |
| A-10 | Black Friday ad link broken | 8/10 | A-Link-Broken | OPEN |
| A-11 | Product carousel missing alt text | 4/10 | A-Alt-Missing | OPEN |
| A-12 | Retargeting ad no frequency cap | 7/10 | A-Budget-Gap | OPEN |

### Lane C - Content

| ID | Title | Severity | Type Tags | Status |
|----|-------|----------|-----------|--------|
| C-04 | Blog post references 2024 pricing | 5/10 | C-Outdated | OPEN |
| C-05 | About page team photo missing | 3/10 | C-Media-Missing | OPEN |
| C-06 | FAQ page thin content (under 300 words) | 4/10 | C-SEO-Issue | OPEN |
| C-07 | Case study PDF link 404 | 6/10 | C-Link-Broken | OPEN |
| C-08 | Product description missing specs | 5/10 | C-Incomplete | OPEN |

### Lane S - SEO

| ID | Title | Severity | Type Tags | Status |
|----|-------|----------|-----------|--------|
| S-16 | Homepage missing meta description | 7/10 | S-Meta-Missing | OPEN |
| S-17 | Product pages no schema markup | 6/10 | S-Schema-Missing | OPEN |
| S-18 | Blog images missing alt tags | 4/10 | S-Alt-Missing | OPEN |
| S-19 | Sitemap not updated since October | 5/10 | S-Sitemap-Stale | OPEN |
| S-20 | Canonical tags missing on category pages | 6/10 | S-Canonical-Missing | OPEN |

### Lane W - Website

| ID | Title | Severity | Type Tags | Status |
|----|-------|----------|-----------|--------|
| W-08 | Contact form 500 error on submit | 9/10 | W-Form-Broken | OPEN |
| W-09 | Mobile nav menu won't close | 7/10 | W-Mobile-Bug | OPEN |
| W-10 | Pricing page loads in 8 seconds | 6/10 | W-Slow-Page | OPEN |
| W-11 | Footer links to old domain | 5/10 | W-Link-Outdated | OPEN |

---

## Key Differences from Default

| Default (Software) | Marketing Version |
|-------------------|-------------------|
| Lane G: Ghost References | Lane G: Google Ads |
| Lane H: Stubs & Placeholders | (Not needed) |
| Lane P: Security & Policy | Lane P: Privacy & Compliance |
| 22 technical lanes | 12 marketing-focused lanes |

---

## Setting Up for Marketing

### Step 1: Decide Your Lanes
Pick 5-12 areas that matter for YOUR marketing operation. Don't use all 26 letters.

### Step 2: Create Agent Files
For each lane (e.g., Lane A), create:
- `.claude/agents/issue-hunters/IH-Lane-A.md` (see custom-hunter-marketing.md)
- `.claude/agents/issue-fixers/IF-Lane-A.md` (see custom-fixer-marketing.md)

### Step 3: Update Orchestrators
Edit both orchestrator files to list only YOUR lanes:
```markdown
ALL_LANES = ["A", "B", "C", "D", "E", "F", "G", "L", "M", "P", "S", "W"]
```

### Step 4: Update ISSUE_CATALOG.md
Replace the default sections with your marketing-focused lanes.

### Step 5: Test
Run `/find-all lanes A` to test just one lane first.
