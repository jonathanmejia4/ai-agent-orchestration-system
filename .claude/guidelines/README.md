# Agent Guidelines
**Version:** 1.0.0
**Last Updated:** 2025-12-17
**Owner:** PM
**Classification:** MEDIUM - Agent Guidelines

**Purpose:** Operational guidelines for autonomous agents
**Audience:** All agents (Planner, Builder, Critic, PM)
**Status:** Active - Reference these guidelines during all autonomous operations

---

## Overview

This directory contains **authoritative operational guidelines** that all autonomous agents must reference during execution. These guidelines are derived from the the orchestration methodology, PM specifications, and code generation best practices.

**Core Principle:** Autonomous agents must ground their actions in these written guidelines, not assumptions or improvisations.

---

## Available Guidelines

### 1. [Agent Operating Principles](./agent-operating-principles.md)
**Use when:** Starting any work session or making governance decisions

**Core concepts:**
- Repo-as-memory principle
- Write boundaries and ownership
- Micro-task discipline
- Evidence-first decision making
- Fail-safe and escalation rules
- Audit trail requirements

**Key question this answers:** "What are the foundational rules all agents must follow?"

---

### 2. [Code Generation Methodology](./code-generation-methodology.md)
**Use when:** Planning or implementing code (Planner, Builder)

**Core concepts:**
- Task-by-task philosophy
- Task lifecycle (Planned → Built → Reviewed → Archived)
- Decomposition rules and granularity
- Implementation guidelines
- Golden task criteria
- Bad task learning

**Key question this answers:** "How do we transform specs into production code through verified micro-tasks?"

---

### 3. [Agent Coordination Protocol](./agent-coordination-protocol.md)
**Use when:** Coordinating with other agents or handing off work

**Core concepts:**
- Core agent loop communication
- Work order format
- Handoff procedures
- Conflict resolution rules
- State synchronization
- Error handling and recovery

**Key question this answers:** "How do agents communicate and coordinate work without conflicts?"

---

### 4. [Quality Standards & Verification](./quality-standards.md)
**Use when:** Reviewing code, running tests, or evaluating quality (Critic, Builder)

**Core concepts:**
- Five dimensions of quality evaluation
- Code quality and security standards
- Testing requirements (unit, integration, E2E)
- Documentation standards
- CI/CD quality gates
- Quality metrics

**Key question this answers:** "What quality thresholds must code meet before promotion?"

---

### 5. [Conventions](../../PLANNING/CONVENTIONS.md)
**Use when:** Generating code, checking compliance, or enforcing standards (all agents)

**Core concepts:**
- Convention-first automation philosophy
- File/folder layout rules
- Naming conventions (classes, functions, tests)
- API route patterns
- Traceability tag requirements
- Code quality limits
- Testing conventions
- Documentation standards
- Git commit format
- Exception mechanism

**Key question this answers:** "What are the machine-checkable rules that make code generation predictable?"

**Machine-readable schema:** `integration/config/conventions.yaml`
**Enforcement tool:** `tools/convention_checker.py`
**Exception process:** `PLANNING/convention-exceptions/`

---

### 6. [Generation Escape Hatch Policy](../../PLANNING/GENERATION_ESCAPE_HATCH_POLICY.md)
**Use when:** Generator cannot produce required output, manual intervention needed (Planner, PM, Builder)

**Core concepts:**
- Four trigger conditions (template gap, convention conflict, risk spike, one-off economics)
- Three exception types (Manual Build, Template Expansion, Hybrid Patch)
- Exception ticket artifacts
- Type-specific quality gates
- Template debt tracking
- Debt accumulation prevention

**Key question this answers:** "What do we do when the generator hits a wall?"

**Exception tickets:** `LogBook/exceptions/generation/`
**Types:** `type-a-manual/`, `type-b-template/`, `type-c-hybrid/`
**Principle:** Automation is default, exceptions are explicit and tracked—never silent

**Prevents:** "Generated most of it... then hand-edited... now regeneration breaks everything"

---

### 7. [Template Drift Detection Policy](../../PLANNING/TEMPLATE_DRIFT_DETECTION_POLICY.md)
**Use when:** Templates need synchronization with golden tasks, preventing template rot (all agents)

**Core concepts:**
- Three-artifact model (reference implementation, template, equivalence contract)
- Template metadata with `derived_from` and commit tracking
- Equivalence contracts defining "same behavior"
- Regeneration tests that detect drift automatically
- CI drift gate blocking unsynchronized changes
- Drift classification (Intentional/Unintentional/Superset)
- Agent responsibilities for drift management
- Rule: Golden task changes require template update or justification

**Key question this answers:** "How do we prevent templates from rotting quietly?"

**Drift tests:** `tests/drift/`
**Templates:** `archives/golden/templates/`
**Principle:** Drift is observable, responsibility is explicit, regression is blocked early

**Prevents:** "Bugs reappear in generated code because templates weren't updated when golden tasks were fixed"

---

### 8. [Template Variants & Parameter Packs Policy](../../PLANNING/TEMPLATE_VARIANTS_AND_PARAMETER_PACKS_POLICY.md)
**Use when:** Preventing template explosion, supporting controlled variation (all agents)

**Core concepts:**
- Base + variants structure (one task = family of behaviors)
- Parameter packs (named, versioned configurations)
- Composition rules (allowed/forbidden combinations)
- Verification scales (tests scale with variant selections)
- Presets (frequently-used combinations promoted)
- Core rule: "If behavior differs, it must be a parameter—never an undocumented fork"
- Parameter limits (<5 per variant, <10 variants per aspect)
- Fork detection (prevent undocumented template copies)

**Key question this answers:** "How do we support flexibility without template explosion?"

**Structure:** `base/` + `variants/` + `presets/`
**Rules:** `composition.rules.yaml`, `verification.rules.yaml`
**Schemas:** `archives/golden/templates/schemas/`
**Principle:** Controlled variation, not chaos. Exponential behaviors from linear templates.

**Prevents:** "We have 50 nearly-identical templates because requirements vary slightly"

---

### 9. [Traceability by Construction Policy](../../PLANNING/TRACEABILITY_BY_CONSTRUCTION_POLICY.md)
**Use when:** Creating tasks, generating code, ensuring auditability (all agents)

**Core concepts:**
- Traceability embedded during construction, not added later
- Six mandatory questions every artifact must answer
- Task manifest structure (`.task/` directory)
- Enhanced provenance headers (@saf: tags)
- CI enforcement gates
- Ancestry trees for golden tasks
- Core rule: "If an artifact cannot explain its origin, it cannot be promoted"

**Key question this answers:** "How do we ensure every artifact can explain its origin, decisions, and lineage?"

**Manifest structure:** `.task/` → `task.yaml`, `inputs.hash`, `outputs.list`, `verification.json` (planned)
**Headers:** 9+ `@saf:` tags embedded in generated files (implementation in progress)
**Enforcement:** `tools/traceability_checker.py` (not yet implemented) + CI gates (planned)
**Principle:** Traceability SHOULD be structural, not optional—currently enforced through policy and code review

**Prevents:** "Why is this code here? Who approved it? What spec defined it?" becomes archaeology

---

### 10. [Two Test Runs Policy (Early Checkpoints)](../../PLANNING/TWO_TEST_RUNS_POLICY.md)
**Use when:** Planning tasks, implementing code, testing at structural boundaries (all agents)

**Core concepts:**
- Test at structural boundaries, not just at finish line
- Test Run #1: Structural/Wiring check (before full behavior)
- Test Run #2: Behavioral/Execution check (after implementation)
- Checkpoint-driven development (structure → Test #1 → behavior → Test #2)
- Planner declares both checkpoints in advance
- Critic evaluates both independently
- Core rule: "A task that cannot define an early checkpoint is not yet understood"

**Key question this answers:** "How do we catch failures early and localize issues to wiring vs behavior?"

**Checkpoints:** Early (schema validates, routes resolve, config parses, files compile) + Final (behavior correct, tests pass, spec met)
**Tool:** `tools/checkpoint_runner.py` (--run-checkpoint-1, --run-checkpoint-2, --run-both, --verify)
**Enforcement:** PM blocks promotion if either checkpoint missing or failed
**Principle:** Fail fast at structural boundaries before sunk cost accumulates

**Prevents:** "Something is wrong" debugging marathons, wiring bugs hidden until integration, iterative thrashing

---

### 11. [Plugin Architecture Policy](../../PLANNING/PLUGIN_ARCHITECTURE_POLICY.md)
**Use when:** Implementing cross-cutting concerns, composing features from capabilities (all agents)

**Core concepts:**
- Plugins are orthogonal functionality (logging, auth, validation, rate-limit, caching, metrics)
- Base task = core behavior only; plugins = attached capabilities
- Plugins attached via declaration (`.task/plugins.yaml`), never code modification
- Extension points (before_execution, after_execution, on_error, on_success)
- Plugins independently verifiable, versioned, testable
- Plugins + Variants = named capability bundles
- Core rule: "If functionality can be expressed as a plugin, it must not be baked into base task"

**Key question this answers:** "How do we compose features from reusable capabilities without baking everything into monolithic tasks?"

**Structure:** `plugins/<category>/<plugin-name>/` with plugin.yaml, apply.ts, tests/, compatibility.yaml
**Examples:** auth, rate-limit, audit-log, validation, caching, metrics, retry
**Critic rules:** 5 rules verify plugin doesn't modify base, declares extension points, has tests, respects compatibility
**Principle:** Assemble features from plugins, don't build monoliths

**Prevents:** Cross-cutting concerns duplicated across tasks, template explosion from slight variations, monolithic untestable code

---

### 12. [Schema-Driven Module Generation Policy](../../PLANNING/SCHEMA_DRIVEN_MODULE_GENERATION_POLICY.md)
**Use when:** Defining data structures, generating code from specifications (all agents)

**Core concepts:**
- Schema as executable intent, not documentation
- Three schema types (Structural, Behavioral, Integration)
- Schema-first workflow (schema → validate → generate → test)
- Task-by-task schema flow (define schema → skeleton → plugins → behavior → promote)
- Schema completeness rules (all fields typed, constraints explicit, relationships defined)
- Core rule: "No task may generate behavior that is not representable in a schema or explicitly declared as exception"

**Key question this answers:** "How do we ensure generated code is derived from authoritative specifications, not invented?"

**Schema types:** Structural (data shape), Behavioral (validation/rules), Integration (API contracts/routes)
**Tool:** `tools/schema_validator.py` (validate, check-correspondence, measure-coverage, score-completeness, verify-task)
**Integration:** Works with Two Test Runs (Test #1 = schema validation), Plugin Architecture (schemas define extension points), Traceability (schema versioned/tracked)
**Principle:** Single source of truth → fail fast on incomplete specs → consistent code across variants

**Prevents:** Schema drift from implementation, incomplete specifications causing late failures, undocumented behavior in generated code

---

### 13. [Reference-First Templatization Policy](../../PLANNING/REFERENCE_FIRST_TEMPLATIZATION_POLICY.md)
**Use when:** Creating templates, extracting patterns from proven code (all agents)

**Core concepts:**
- "Prove it once by hand, then automate the proof"
- You never template ideas, you template proven reality
- Task Type A (Reference Implementation): manually-built, battle-tested, production-ready code
- Task Type B (Templatization): extract templates from verified references
- Battle-tested verification required (production exposure or equivalent)
- Structural parameterization only (names, types, paths) - creative parameterization forbidden
- LLMs as compression tools (extract patterns), not decision-makers (don't invent abstractions)
- Core rule: "No template may exist without a reference implementation"

**Key question this answers:** "How do we ensure templates generate correct code without debugging loops?"

**Task types:** Type A (Reference) manually built + battle-tested → Type B (Templatization) extracts template
**Battle-tested:** ≥2 weeks production (zero incidents) OR ≥1,000 test executions (100% pass) OR security audit
**Directory:** Reference + template co-located (drift obvious)
**Integration:** Works with Drift Detection (reference is drift comparison target), Escape Hatch (Type B creates templates), Two Test Runs (reference must pass both)
**Principle:** Templates are derived artifacts, never primary → generators don't rot → generated code is bug-free

**Prevents:** Template-first design failures, LLM-invented abstractions, premature templatization, creative parameterization bugs, generator rot

---

### 14. [Stage-Gated Generation Pipeline Policy](../../PLANNING/STAGE_GATED_GENERATION_PIPELINE_POLICY.md)
**Use when:** Executing any generation workflow, enforcing sequential validation (all agents)

**Core concepts:**
- "Nothing advances unless the previous stage proved itself"
- Break generation into explicit stages, require proof at each boundary
- 5 canonical stages: (0) Specification & Schema → (1) Structural Skeleton → (2) Capability Composition → (3) Behavioral Generation → (4) Integration & Promotion
- 5 mandatory gates (one per stage, all must pass before proceeding)
- Stages are tasks with required predecessors (explicit ordering)
- Failure behaviors: Stop (block until fixed), Rollback (revert to prior stage), Escalate (human intervention)
- Core rule: "A stage cannot be skipped, repeated out of order, or merged with another stage"

**Key question this answers:** "How do we catch failures early, localize issues, and prevent cascading errors?"

**5 stages:** Stage 0 (schema validates) → Stage 1 (Test Run #1, structure compiles) → Stage 2 (plugins compatible) → Stage 3 (Test Run #2, tests pass) → Stage 4 (CI green, promoted)
**Gates:** Stage 0 (schema validation), Stage 1 (structural validation), Stage 2 (compatibility validation), Stage 3 (behavioral validation), Stage 4 (system integration validation)
**Integration:** Test Run #1 = Stage 1 gate, Test Run #2 = Stage 3 gate, plugins attach at Stage 2, traceability injected at Stage 1, schema consumed by all stages after Stage 0
**Principle:** Stages are physics (not suggestions) → agents are interchangeable → development is controlled pipeline, not creative gamble

**Prevents:** "Generate everything and test at the end" failures, cascading errors, mystery bugs, late-stage debugging marathons, unlocalized failures

---

### 15. [SSOT Wiring File Policy](../../PLANNING/SSOT_WIRING_FILE_POLICY.md)
**Use when:** Creating tasks, declaring assembly/wiring, verifying completeness (all agents)

**Core concepts:**
- "If it's not in SSOT, it doesn't exist"
- Single authoritative file declares how feature/module is assembled and connected
- Everything else (code, tests, docs, CI gates) derived from or verified against SSOT
- SSOT is executable intent, not documentation
- 5 core sections: Identity, Interfaces, Composition, Wiring, Verification Contract
- Core rule: "If code does something not declared in SSOT, Critic flags it as drift/escape hatch"

**Key question this answers:** "What is the authoritative source of truth for how this module is assembled, connected, and verified?"

**5 sections:** Identity & Traceability (task ID, spec refs, lineage) + Interfaces (API endpoints, events, commands) + Composition (plugins attached) + Wiring (file paths, data flow, connections) + Verification Contract (gates, required tests, coverage)
**File:** `.task/wiring.yaml` (consolidates task.yaml + plugins.yaml + adds interfaces/wiring/verification)
**Enforcement:** `tools/schema_validator.py` validates structure, file correspondence, interface registration, composition compliance, verification contract
**Integration:** SSOT created at Stage 0, updated at Stages 1-2, verified at all gates, frozen after Stage 2, promoted at Stage 4
**Principle:** Single source of truth → mechanical review (not subjective) → enforceable governance → regeneration safe

**Prevents:** Documentation drift, phantom endpoints, missing tests, dependency mystery, regeneration fear, integration archaeology, competing sources of truth

---

### 16. [Template Families Policy](../../PLANNING/TEMPLATE_FAMILIES_POLICY.md)
**Use when:** Creating templates, selecting templates, verifying template compliance (all agents)

**Core concepts:**
- "Group templates by what they produce (artifact type), not where they're used (domain)"
- 5 canonical families: Code, Test, Doc, Config, Schema
- Each family has contracts: Input (required/optional/forbidden params) + Output (file types, paths, headers) + Verification (early/late checks)
- Family per stage mapping: Stage 0 (Schema), Stage 1 (Code + Config), Stage 2 (Config), Stage 3 (Code + Test), Stage 4 (Doc + Config)
- Variant symmetry: Code variants → Test variants (must match)
- Core rule: "A template may only generate ONE class of artifact and must declare which family it belongs to"

**Key question this answers:** "How do we prevent template sprawl, copy-paste divergence, and 'almost the same but slightly different' chaos?"

**5 families:** Code (services, controllers, libraries) + Test (unit, integration, E2E) + Doc (README, API docs, guides) + Config (SSOT wiring, env configs, plugin bindings) + Schema (JSON Schema, OpenAPI, domain schemas)
**Contracts:** Input (required/optional/forbidden params), Output (file types, paths, headers), Verification (early/late checks)
**Stage alignment:** Specific families per stage (Code @ Stage 1/3, Test @ Stage 3, Doc @ Stage 4, Schema @ Stage 0, Config @ all stages)
**Integration:** Families enforce Reference-First (family-scoped derivation), Variants (family-scoped, symmetric), Stage-Gated (family per stage), SSOT (declares families used)
**Principle:** Organized by artifact type → shared verification → local evolution → contained failures → predictable generation

**Prevents:** Template sprawl (O(domains × types) → O(types)), copy-paste divergence, unknown blast radius, entangled verification, cross-contamination (docs driving behavior)

---

### 17. [Idempotent Generation Policy](../../PLANNING/future/IDEMPOTENT_GENERATION_POLICY.md)
**Use when:** Creating generators, running templates, verifying generation determinism (all agents)

**Core concepts:**
- "Generate twice, get identical output"
- All generators must be idempotent: generate(inputs) ∘ generate(inputs) = generate(inputs)
- Running same generator with same inputs MUST produce byte-identical output every time
- 5 causes of non-idempotence: timestamps, unstable ordering, formatting drift, reading back generated files, randomness/AI creativity
- Idempotence contract required for all templates (deterministic: true, causes addressed, test procedure)
- No timestamps in generated code (only in .task/ metadata files)
- Canonical ordering (sorted keys, stable iteration)
- Rule: "If it's not byte-identical, it's not idempotent"

**Key question this answers:** "How do we ensure generators produce consistent, predictable output for drift detection and traceability?"

**5 causes addressed:** Timestamps (no @saf:generated-at in code) + Unstable ordering (sorted keys, stable iteration) + Formatting drift (locked formatter versions) + File reads (inputs from SSOT only, never read generated files) + Randomness (Jinja2 templates only, no LLM creativity with temperature > 0)
**Idempotence contract:** All templates declare deterministic: true, list causes addressed, define test procedure (run twice, assert no diffs)
**Test gate:** CI job runs generator twice, asserts byte-identical output, blocks merge if test fails
**Canonicalization utilities:** sortedKeys, canonical_yaml_dump, normalize_line_endings, stableJsonStringify
**Integration:** Enables drift detection (regenerate + compare), supports two-test-run pattern, powers traceability (input hash → output fingerprint), verified at Stage 1 and Stage 3 gates
**Principle:** Deterministic generation → drift detection works → traceability reliable → regeneration safe

**Prevents:** "Regeneration roulette" (unpredictable output changes), drift detection failures, traceability breaks, test flakiness, template debugging loops

---

### 18. [Protected Regions Policy](../../PLANNING/future/PROTECTED_REGIONS_POLICY.md)
**Use when:** Handling one-off customizations in generated code, preserving manual edits during regeneration (all agents)

**Core concepts:**
- "Small customizations stay local and regeneration-safe"
- Protected regions are marked blocks in generated files that generators preserve verbatim during regeneration
- Region markers: `@saf:region begin name=<name> hash=<hash>` ... `@saf:region end name=<name>`
- Everything outside regions is regenerated, everything inside regions is preserved
- Extract → Regenerate → Reinsert workflow
- Hash guards for integrity protection (detect corruption)
- Regions reduce escape hatch usage (fewer Type C Hybrid Patches)
- Rule: "If it's important enough to reuse, it must graduate from a protected region into a template/plugin/variant"

**Key question this answers:** "How do we allow controlled manual customizations in generated code without breaking regeneration?"

**Allowlist:** 6 approved region names (custom_validation, custom_logic, custom_ui, custom_error_mapping, custom_logging, custom_metrics) - new names require PM approval
**Limits:** Max 2 regions per file, max 80 lines per region (larger → escape hatch ticket)
**Forbidden alterations:** Regions CANNOT alter function signatures, exported types, route contracts, database schemas (interface stability protected)
**SSOT declaration:** All regions declared in `.task/wiring.yaml` Section 6 with rationale, hash, lines, graduation tracking
**Graduation path:** Pattern used 3+ times → MUST graduate to template/plugin/variant (regions are for one-offs, not reusables)
**Integration:** Works with Idempotent Generation (region content excluded from idempotence hash), Template Drift Detection (regions preserved during drift tests), Stage-Gated Pipeline (regions created Stage 1, modified Stage 3), SSOT Wiring (regions declared in SSOT), Escape Hatch (reduces Type C Hybrid Patch usage)
**Principle:** Controlled flexibility (not chaos) → regeneration safe with customization → manual edits tracked and audited → one-offs stay local, reusables graduate

**Prevents:** "Hand-edit breaks regeneration" failure mode, template explosion from slight variations, Type C Hybrid Patch sprawl, undocumented manual edits, interface instability from customizations

---

### 19. [Three-Way Merge Regeneration Policy](../../PLANNING/THREE_WAY_MERGE_REGENERATION_POLICY.md)
**Use when:** Regenerating code with manual edits, reconciling BASE/LOCAL/NEW versions, handling merge conflicts (all agents)

**Core concepts:**
- "Regeneration is a merge, not an overwrite"
- Three inputs: BASE (last generated version), LOCAL (current file with edits), NEW (freshly generated version)
- Three merge rules: (1) NEW differs from BASE, LOCAL unchanged → accept NEW, (2) LOCAL differs from BASE, NEW unchanged → keep LOCAL, (3) Both changed → CONFLICT (block regeneration)
- Conflict detection and resolution workflow (human-in-loop required)
- BASE version storage (`.saf/generated/<task-id>/base/`) with metadata (when generated, from which inputs)
- Merge engine (3 levels: line-based, AST-aware, auto-resolution)
- Rule: "Regeneration without BASE is overwrite, not merge—you're playing Russian roulette with developer edits"

**Key question this answers:** "How do we reconcile manual edits with regeneration without overwriting developer work?"

**Three merge rules:**
1. NEW differs from BASE, LOCAL unchanged → accept NEW (generator improved, developer didn't touch this part)
2. LOCAL differs from BASE, NEW unchanged → keep LOCAL (developer changed, generator didn't update this part)
3. Both changed → CONFLICT (both modified same section, human decision required)

**BASE version storage:** `.saf/generated/<task-id>/base/` directory with files and `metadata.yaml` (generated_at, template info, inputs_hash, file hashes)
**Conflict policy:** 5 types (generated core, plugin output, protected region, documentation, test) - each has resolution strategy
**SSOT Section 7:** Merge conflicts declared in `.task/wiring.yaml` with status (pending/resolved/blocked), conflict details, resolution strategy
**Merge engine:** Level 1 (line-based merge), Level 2 (AST-aware merge), Level 3 (auto-resolution with heuristics) - incremental maturity
**Integration:** Works with Protected Regions (regions = "guaranteed keep zones", everything else = "merge zones"), Idempotent Generation (BASE version updated after idempotent generation), Drift Detection (drift = unexpected LOCAL changes), Stage-Gated Pipeline (merge validation at Stage 3 gate), SSOT Wiring (conflict declaration in Section 7)
**Principle:** Merge not overwrite → developer edits respected → routine regeneration safe → "regeneration fear" eliminated → generators survive past month 6

**Prevents:** "Regeneration = overwrite = fear" failure mode, developer edits lost during regeneration, "never regenerate again" syndrome, generator rot from disuse, manual drift accumulation

---

### 20. [Template Versioning & Deprecation Policy](../../PLANNING/TEMPLATE_VERSIONING_AND_DEPRECATION_POLICY.md)
**Use when:** Managing template versions, upgrading templates, deprecating old versions, planning template lifecycle (all agents)

**Core concepts:**
- "Templates are products. Products have versions. Upgrades are migrations, not accidents."
- SemVer rules: MAJOR.MINOR.PATCH with explicit bumping criteria
- Template lineage: Every generated artifact declares template@version
- Lifecycle states: active → maintenance → deprecated → retired
- Template Upgrade Tasks: Controlled upgrade workflow (not silent updates)
- Compatibility matrix: Declare which template versions work together
- Version pinning: SSOT locks template versions until explicit migration
- Rule: "Regeneration with a different template version is a migration, not a bug fix—requires PM approval"

**Key question this answers:** "How do we evolve templates safely without breaking existing code or causing 'template updated → everything changed' surprises?"

**SemVer bumping:**
- PATCH: Bug fix, no behavior/interface change (2.3.0 → 2.3.1)
- MINOR: Backward-compatible addition (2.3.1 → 2.4.0)
- MAJOR: Breaking change (2.9.0 → 3.0.0, requires migration guide)

**Lifecycle states:** active (recommended) → maintenance (6 months, PATCH only) → deprecated (3 months, critical fixes only) → retired (forbidden)
**Version pinning:** SSOT `.task/wiring.yaml` Section 8 declares template versions, pinned until Template Upgrade Task
**Template Upgrade Task:** Type U task migrates module from old template version to new (retrieve BASE → regenerate → merge → test → update SSOT)
**Compatibility matrix:** Templates declare compatible versions (e.g., `api-crud@2.3.0` requires `api-crud-tests@==2.3.*`)
**Deprecation enforcement:** CI blocks retired templates, Critic blocks promotion if retired template used, PM tracks migration deadlines
**Integration:** Works with Traceability (template version in headers), Three-Way Merge (template upgrades use merge), Template Drift (detects version drift), SSOT Wiring (Section 8 template versions), Template Families (family version symmetry)
**Principle:** Versioned products → controlled evolution → predictable upgrades → migration not surprise → templates survive long-term

**Prevents:** "Template updated → everything changed" nightmare, "which version created this?" archaeology, "can I upgrade safely?" gamble, "this template is broken" but can't retire it, generator rot from fear of upgrades

---

### 21. [Template Compliance Policy](../../PLANNING/TEMPLATE_COMPLIANCE_POLICY.md)
**Use when:** Creating new templates, updating templates, promoting templates, verifying template quality (all agents)

**Core concepts:**
- "Templates are products that need tests, CI, and promotion gates before they can generate production code."
- Universal compliance checks: renders deterministically, produces traceability metadata, matches SSOT schema, no unresolved placeholders
- Family-specific checks: Code (compiles, lints clean, smoke test), Test (executes, sanity check), Doc (markdown valid, links resolve, no invented endpoints), Config (YAML valid, schema valid, no secrets), Schema (valid, no TODOs, all fields typed)
- Template test harness: Sandbox environment with fixtures (minimal/typical/edge)
- Stage 0.5 gate: Templates tested BEFORE production use
- CI enforcement: Automated compliance on template changes
- Rule: "A template is not golden because it looks good. It's golden because it passes compliance in a sandbox."

**Key question this answers:** "How do we verify templates can generate valid output BEFORE they infect production tasks?"

**Compliance workflow:**
1. Extract template from golden task
2. Create 3 fixtures (minimal/typical/edge)
3. Run compliance suite (generate → compile → test → lint)
4. Fix failures → re-run → PASS
5. Promote to golden templates

**Compliance contracts:**
- Code family: output compiles, lints clean, passes smoke test
- Test family: tests execute, negative test fails when code broken (sanity check)
- Doc family: markdown valid, links resolve, no invented behavior
- Config family: YAML valid, schema valid, no secrets
- Schema family: schema valid, no TODOs, all fields typed

**Stage 0.5 gate:** Templates cannot be used in Stage 1+ unless compliance PASS (100% requirement)
**CI enforcement:** `.github/workflows/template_compliance.yml` runs on template changes, PR cannot merge if compliance fails
**Integration:** Works with Template Versioning (compliance re-run on version bump), Template Families (family-specific checks), Idempotent Generation (idempotence check is universal), Reference First (template output matches reference), Drift Detection (compliance verifies template still valid)
**Principle:** Test templates in sandbox → catch broken templates early → production tasks stay clean → developers trust templates

**Prevents:** Broken templates generating broken code, "template looks good but doesn't compile" failures, "template passed but production failed" fixture gaps, template updates without verification, family-specific broken output

---

### 22. [Dependency Graph & Topological Build Order Policy](../../PLANNING/DEPENDENCY_GRAPH_AND_TOPOLOGICAL_BUILD_ORDER_POLICY.md)
**Use when:** Planning task execution, computing build order, identifying parallel work, validating dependencies (PM, Planner, Builder, Critic)

**Core concepts:**
- "If your tasks have dependencies, you don't output a list—you output a DAG with a topologically sorted build order."
- Graph.yaml files: Formal DAG structure (nodes + edges) in `.task/graph.yaml`
- Topological sort: Kahn's algorithm computes safe build order
- Parallel work sets: Group tasks into waves for concurrent execution
- DAG validation: 7 mechanical checks (acyclic, connected, no orphans, no duplicates, no self-loops, node-edge correspondence, stage consistency)
- Critical path: Longest path from root to leaf (identifies bottleneck tasks)
- SSOT Section 9: Stores topological order, parallel sets, critical path
- Rule: "Planner outputs DAG, PM computes topological sort, Builder executes in safe order"

**Key question this answers:** "How do we compute safe task execution order and identify parallel work opportunities?"

**DAG workflow:**
1. Planner outputs graph.yaml (nodes + edges)
2. Run `tools/dag_validator.py` (7 checks)
3. Run `tools/topological_sort.py` (compute order + parallel sets)
4. PM assigns work in waves (Wave N tasks can run in parallel)
5. Builder executes in topological order
6. Critic verifies execution order respected

**7 validation checks:**
- Acyclic: No cycles (run topological sort, verify all nodes processed)
- Connected: All nodes reachable from roots
- No orphans: All nodes have edges (except single-node graphs)
- No duplicates: No duplicate edges (same from → to)
- No self-loops: No edges where from == to
- Node-edge correspondence: All edge endpoints reference existing nodes
- Stage consistency: Dependencies respect stage ordering

**Topological sort output:**
```
Topological order: [B1, B2, B3, B4, B5, B6]
Parallel sets:
  - Wave 0: [B1] (2.0 hours)
  - Wave 1: [B2, B3, B4] (4.0 hours max) ← Parallel!
  - Wave 2: [B5] (1.0 hours)
  - Wave 3: [B6] (2.0 hours)
Critical path: B1 → B4 → B5 → B6 (9.0 hours)
```

**Integration:** Works with Stage-Gated Pipeline (stage consistency validation), SSOT Wiring (Section 9 for dependency_graph), Plugin Architecture (plugin tasks depend on base tasks), Template Versioning (Template Upgrade Tasks depend on original tasks), Three-Way Merge (regeneration tasks depend on BASE tasks)

**Principle:** Plan dependencies as DAG → compute topological order → execute safely → identify parallel work → optimize critical path

**Prevents:** Sequential execution when parallelism possible, tasks starting before predecessors complete, circular dependencies discovered late, PM guessing execution order, "Why is Builder blocked when work could run in parallel?"

---

### 23. [Security & Policy Linting as First-Class Gates Policy](../../PLANNING/SECURITY_POLICY_LINTING_AS_FIRST_CLASS_GATES_POLICY.md)
**Use when:** Implementing security checks, enforcing policy compliance, reviewing code security (all agents)

**Core concepts:**
- "Security is not optional review—it's a mandatory gate with deterministic enforcement."
- 3-layer security architecture: Static policy rules + SSOT-driven contracts + Security tests
- Stage 1 Security Gate: SSOT validation, secret scan, SAST, dependency scan
- Stage 3 Security Gate: Auth tests, validation tests, audit logging tests
- Critic Dimension 6: Security & Policy Compliance (binary: Pass or Blocked)
- Policy registry: `PLANNING/policy/security_policies.yaml` with 13 policies (11 blocking, 2 warning)
- Rule: "If policy checks fail, task cannot be promoted—no exceptions"

**Key question this answers:** "How do we enforce security and policy compliance as mandatory gates, not optional reviews?"

**13 Security Policies:**
- SEC-001: No Hard-Coded Secrets (Stage 1, block)
- SEC-010: Endpoints Must Declare Auth Policy (Stage 1, block)
- SEC-020: Auth Policy Must Be Tested (Stage 3, block)
- SEC-021: Validation Policy Must Be Tested (Stage 3, block)
- SEC-022: Audit Logging Must Be Tested (Stage 3, block)
- SEC-030: No SQL Injection Vectors (Stage 1, block)
- SEC-031: No Command Injection Vectors (Stage 1, block)
- SEC-032: No Vendor SDKs Outside Adapters (Stage 1, block)
- SEC-033: Dependency Vulnerability Scan (Stage 1, block)
- SEC-040: No Sensitive Data in Logs (Stage 3, block)
- SEC-041: Rate Limiting Must Be Tested (Stage 3, warn)
- SEC-050: Database Tables Must Declare PII and Encryption (Stage 1, block)
- SEC-051: External Integrations Must Declare Security Boundary (Stage 1, block)

**Tools:** `check_ssot_security.py`, `generate_security_tests.py`, `verify_security_test_coverage.py`, `detect_vendor_type_leakage.py`

**Integration:** Works with Stage-Gated Pipeline (security gates at Stage 1 and 3), SSOT Wiring (security schema extensions), Anti-Corruption Layer (SEC-032, SEC-051 enforce adapter isolation)

**Principle:** Security as physics (not suggestions) → deterministic enforcement → mechanical review → no "looks secure" vibes

**Prevents:** Hard-coded secrets, missing auth tests, SQL injection, vendor coupling, PII leakage, silent security failures

---

### 24. [Anti-Corruption Layer (ACL) Policy](../../PLANNING/ANTI_CORRUPTION_LAYER_POLICY.md)
**Use when:** Integrating external APIs/SDKs, isolating vendor dependencies, preventing vendor coupling (all agents)

**Core concepts:**
- "Core code → Ports (interfaces) → Adapters (ACL) → External API"
- Ports-and-Adapters architecture (Hexagonal Architecture)
- Vendor SDK isolation: All vendor imports MUST be in `/adapters/` directory
- Port interfaces use internal types only (no vendor types leak to core code)
- Adapters implement ports + translate vendor ↔ internal types
- Mappers centralize type conversions (vendor ↔ internal)
- Internal error taxonomy (vendor errors → internal error types)
- Contract test harness (golden compliance tests)
- SSOT Section 7: Adapter Wiring (port, implementation, vendor SDK, version, plugins)
- Rule: "If vendor type leaks into core code, the adapter doesn't exist—you have vendor coupling"

**Key question this answers:** "How do we prevent vendor lock-in and isolate external dependencies?"

**Directory structure:**
```
/domain/          # Core business logic (vendor-free)
/ports/           # Port interfaces (internal types only)
/adapters/        # Adapters (vendor SDK isolation)
  /stripe/        # StripePaymentProvider implements PaymentProvider
  /twilio/        # TwilioNotificationProvider implements NotificationProvider
/tests/contract/  # Contract tests (golden compliance)
```

**Contract test example:**
- Golden compliance test: Record vendor responses, replay in tests
- Verify adapter behavior matches golden responses
- Detect vendor API changes early

**Integration:** Works with SEC-032 (No Vendor SDKs Outside Adapters), SEC-051 (External Integrations Must Declare Security Boundary), Plugin Architecture (adapters are plugins), SSOT Wiring (adapter declarations in Section 7)

**Principle:** Vendor isolation → internal types everywhere → contract tests prevent drift → vendor changes don't break core

**Prevents:** Vendor lock-in, vendor types leaking into core code, "Stripe changed their API and broke everything", undeclared external dependencies

---

### 25. [Metrics Feedback Loop Policy](../../PLANNING/METRICS_FEEDBACK_LOOP_POLICY.md)
**Use when:** Tracking template quality, making investment decisions, continuous improvement (PM, all agents)

**Core concepts:**
- "Every task run produces measurable signals. PM uses signals to decide what to standardize, refactor, retire, templatize next."
- 5 key metrics: generation success rate, time saved (estimated vs actual), defect rate, drift frequency, reuse frequency
- Per-task specification: `LogBook/progress/tasks/<task-id>.json` (machine-readable)
- Rollups: daily/weekly/monthly summaries (human-readable)
- ROI decision rules (deterministic criteria):
  - Templatize: Pattern ≥3 times AND ≥2 hours each AND low defect rate
  - Harden: First-pass success <85% OR drift >20% OR conflicts >10%
  - Retire: Reuse <3 AND high maintenance AND alternatives exist
  - Promote to Golden: Reused ≥10 times AND defect <5% AND success >85%
- 6-step feedback loop: Run tasks → Collect metrics → PM reviews weekly → Choose investment → Update templates → Repeat
- Rule: "If you're not measuring it, you're not improving it"

**Key question this answers:** "How do we use data to decide which templates to invest in, harden, or retire?"

**5 Key Metrics:**
1. **Generation success rate:** % tasks passing Stage 1+3 gates on first attempt (target: ≥85%)
2. **Time saved:** Estimated hours vs actual hours (estimation accuracy trend)
3. **Defect rate:** Defects per task (target: <5%)
4. **Drift frequency:** Template regeneration + diff (target: <20% drift)
5. **Reuse frequency:** Times template reused (ROI indicator)

**Per-task specification schema:**
```json
{
  "task_id": "task_2025-01-15_add-user-registration_a7f3b2",
  "template_id": "crud-api",
  "template_version": "2.1.0",
  "timestamps": { "started_at": "...", "completed_at": "...", "duration": "PT5H15M" },
  "estimates": { "planner_estimated": "PT3H", "builder_actual": "PT5H", "rework": "PT2H" },
  "gates": { "stage_0_passed": true, "stage_1_passed": true, "stage_3_passed": false, "first_pass_success": false },
  "critic": { "iterations": 2, "dimensions_failed": ["Dimension 3: Execution Readiness"] },
  "defects": [{ "type": "missing_validation", "stage": "stage_3", "severity": "medium" }]
}
```

**ROI Decision Rules:**
- **Templatize Next:** Pattern ≥3 times AND ≥2 hours each AND low defect rate
- **Harden:** First-pass success <85% OR drift >20% OR conflicts >10%
- **Retire:** Reuse <3 AND high maintenance AND alternatives exist
- **Promote to Golden:** Reused ≥10 times AND defect <5% AND success >85%

**Tools:** `collect_task_metrics.py`, `rollup_template_metrics.py`, `roi_decision_engine.py`, `generate_pipeline_health.py`

**Integration:** Works with Protected Regions (graduation tracking), Template Versioning (template lifecycle decisions), Quality Standards (defect tracking), Idempotent Generation (drift detection), Template Compliance (template quality metrics)

**Principle:** Measure → Analyze → Decide → Act → Repeat → Continuous improvement via data

**Prevents:** "Gut feel" template decisions, silent template rot, over-investment in low-ROI templates, under-investment in high-value patterns, "we don't know which templates work"

---

### 26. [Spec-to-diff Previews Policy](../../PLANNING/SPEC_TO_DIFF_PREVIEWS_POLICY.md)
**Use when:** Generating code from SSOT changes, regenerating code, assessing generation risk (all agents)

**Core concepts:**
- "No apply without preview—plan before apply"
- Stage -1: Preview Generation (new first stage before Stage 0)
- Preview artifact bundle: `preview.diff`, `preview.json`, `preview.md`, `risk_report.md`
- Four preview questions: (1) What files will change? (2) How will they change? (3) Why will they change? (4) What are the risks?
- Causal mapping: Input change → output change traceability (SSOT line → files affected)
- Risk scoring: 0-10 scale (LOW/MEDIUM/HIGH/CRITICAL)
- Three-way merge simulation: Detect conflicts BEFORE applying
- PM approval gate: Preview approved before proceeding to Stage 0
- Rule: "No apply without preview—if generator can't preview, it doesn't understand the change"

**Key question this answers:** "How do we see the plan before execution and approve changes before generation?"

**Workflow transformation:**
```
❌ Old: SSOT change → Generate → Review → Fix (too late)
✅ New: SSOT change → Preview → Approve → Generate → Verify
        └─ Stage -1 ─┘└─ Stage 0 ─┘└─ Stages 1-3 ─┘
```

**Preview artifact bundle:**
- **preview.diff:** Unified diff of all planned changes
- **preview.json:** Machine-readable execution plan (inputs, planned_changes, gates, risks)
- **preview.md:** Human-readable "why" summary (causal mapping, risk assessment)
- **risk_report.md:** Risk categorization (blast radius, conflict probability, approval decision support)

**Causal mapping example:**
```yaml
causal_chain:
  - input:
      file: PLANNING/ssot.yaml
      line: 42
      change: "Added security.rate_limiting: 100 requests/min"
    output:
      - file: src/api/users/auth.py
        lines: 18-19
        change: "Added is_rate_limited() check"
        why: "SSOT rate_limiting config triggered rate-limiter plugin"
```

**Risk scoring:**
- **0.0-2.0:** LOW (auto-approve optional)
- **2.1-5.0:** MEDIUM (PM review required)
- **5.1-8.0:** HIGH (PM + Critic review required)
- **8.1-10.0:** CRITICAL (manual review, possible SSOT revision)

**Tools:** `preview_generator.py`, `causal_mapper.py`, `preview_approver.py`, CI preview gate

**Integration:** Works with Three-Way Merge Regeneration (merge preview simulation), Traceability (preview traceability metadata), SSOT Wiring (causal mapping uses SSOT), Stage-Gated Pipeline (Stage -1 added before Stage 0), Idempotent Generation (preview uses dry-run mode)

**Principle:** Preview → Approve → Generate → Verify → No surprises → Risk-aware generation

**Prevents:** Surprise diffs, unknown blast radius, late-discovered conflicts, unreviewed generation, "What just happened to my repo?" syndrome

---

## How to Use These Guidelines

### For Project Manager (PM)

**Read at session start:**
1. [Agent Operating Principles](./agent-operating-principles.md) - Review governance rules
2. [Agent Coordination Protocol](./agent-coordination-protocol.md) - Check handoff procedures
3. [Generation Escape Hatch Policy](../../PLANNING/GENERATION_ESCAPE_HATCH_POLICY.md) - Review exception handling
4. [Template Drift Detection Policy](../../PLANNING/TEMPLATE_DRIFT_DETECTION_POLICY.md) - Review drift management
5. [Template Variants & Parameter Packs Policy](../../PLANNING/TEMPLATE_VARIANTS_AND_PARAMETER_PACKS_POLICY.md) - Review variant system
6. [Traceability by Construction Policy](../../PLANNING/TRACEABILITY_BY_CONSTRUCTION_POLICY.md) - Review traceability requirements
7. [Two Test Runs Policy](../../PLANNING/TWO_TEST_RUNS_POLICY.md) - Review checkpoint requirements
8. [Plugin Architecture Policy](../../PLANNING/PLUGIN_ARCHITECTURE_POLICY.md) - Review plugin system
9. [Schema-Driven Module Generation Policy](../../PLANNING/SCHEMA_DRIVEN_MODULE_GENERATION_POLICY.md) - Review schema-driven generation
10. [Reference-First Templatization Policy](../../PLANNING/REFERENCE_FIRST_TEMPLATIZATION_POLICY.md) - Review reference-first template creation
11. [Stage-Gated Generation Pipeline Policy](../../PLANNING/STAGE_GATED_GENERATION_PIPELINE_POLICY.md) - Review 5-stage pipeline and gate enforcement
12. [SSOT Wiring File Policy](../../PLANNING/SSOT_WIRING_FILE_POLICY.md) - Review SSOT requirements and validation
13. [Template Families Policy](../../PLANNING/TEMPLATE_FAMILIES_POLICY.md) - Review 5 canonical families and family contracts
14. [Idempotent Generation Policy](../../PLANNING/future/IDEMPOTENT_GENERATION_POLICY.md) - Review idempotence contract and deterministic generation requirements
15. [Protected Regions Policy](../../PLANNING/future/PROTECTED_REGIONS_POLICY.md) - Review protected region system and graduation path
16. [Three-Way Merge Regeneration Policy](../../PLANNING/THREE_WAY_MERGE_REGENERATION_POLICY.md) - Review three-way merge workflow and conflict resolution
17. [Template Versioning & Deprecation Policy](../../PLANNING/TEMPLATE_VERSIONING_AND_DEPRECATION_POLICY.md) - Review SemVer rules, template lifecycle, and upgrade workflow
18. [Template Compliance Policy](../../PLANNING/TEMPLATE_COMPLIANCE_POLICY.md) - Review template compliance contracts, Stage 0.5 gate, and CI enforcement
19. [Dependency Graph & Topological Build Order Policy](../../PLANNING/DEPENDENCY_GRAPH_AND_TOPOLOGICAL_BUILD_ORDER_POLICY.md) - Review DAG-based planning, topological sort, and parallel work identification
20. [Security & Policy Linting as First-Class Gates Policy](../../PLANNING/SECURITY_POLICY_LINTING_AS_FIRST_CLASS_GATES_POLICY.md) - Review 13 security policies, Stage 1 & 3 security gates, and Critic Dimension 6
21. [Anti-Corruption Layer Policy](../../PLANNING/ANTI_CORRUPTION_LAYER_POLICY.md) - Review Ports-and-Adapters architecture, vendor SDK isolation, and adapter wiring
22. [Metrics Feedback Loop Policy](../../PLANNING/METRICS_FEEDBACK_LOOP_POLICY.md) - Review 5 key metrics, ROI decision rules, and template investment criteria
23. [Spec-to-diff Previews Policy](../../PLANNING/SPEC_TO_DIFF_PREVIEWS_POLICY.md) - Review Stage -1 preview generation, causal mapping, and risk scoring

**Reference during:**
- Issuing work orders → Use work order template
- Resolving conflicts → Apply priority order
- Escalating issues → Follow escalation rules
- Exception requests → Classify type, track template debt
- Golden task changes → Schedule drift check, enforce rule
- Drift detection → Classify drift type, track resolution
- Template explosion → Check for undocumented forks, enforce "parameter not fork" rule
- Preset promotion → Track combinations used 3+ times
- Promotion gates → Verify manifests complete, verify both checkpoints passed, enforce "no origin = no promotion" rule
- Traceability checks → Ensure six questions answerable for all artifacts
- Checkpoint verification → Ensure both Test Run #1 and #2 executed, passed, with evidence
- Plugin compliance → Verify plugins declared, not baked into base task, enforce "if can be plugin, must not be baked" rule
- Plugin promotion → Approve golden plugins for reuse across tasks
- Schema governance → Approve schema exceptions (non-representable behavior), track schema exception debt
- Schema quality → Review schema quality metrics quarterly (coverage, exception rate, completeness, drift)
- Reference implementation promotion → Verify reference implementation battle-tested before golden promotion, set templatizable.eligible when criteria met
- Templatization approval → Verify reference implementation exists and is golden before assigning Task Type B (Templatization), enforce "no template without reference" rule
- Template ROI tracking → Track template creation cost vs usage savings, ensure ROI ≥3×
- Stage governance → Enforce "no skipping stages" rule (rule: stage cannot be skipped, repeated out of order, or merged)
- Gate enforcement → Review gate results before approving progression, response to "can we skip ahead?" is "Which gate did you pass that proves that? No proof → No jump"
- Stage metrics → Track gate pass rates (first attempt), debugging time per task, stage skip attempts (target: 0), rollback frequency, escalation rate
- SSOT completeness → Verify all 5 sections populated (identity, interfaces, composition, wiring, verification), block promotion if SSOT incomplete
- SSOT hash validation → Check SSOT hash unchanged after gates passed (no retroactive edits), block if SSOT modified after tests
- SSOT reference validation → Verify template refs point to golden templates, schema refs point to valid schemas, spec refs point to approved specs
- SSOT compliance → Run `tools/schema_validator.py --verify-task` before promotion, block if validator fails
- SSOT metrics → Track % tasks with complete SSOT (target: 100%), % SSOT violations (target: 0%), phantom file/endpoint detection rate, time to fix SSOT violations
- Template family governance → Approve new template families (if needed beyond 5 canonical), enforce "template may only generate one class of artifact" rule
- Family membership verification → Verify template has family field before promotion, verify family contract complete, verify stage alignment declared, block templates without family membership
- Variant symmetry enforcement → Verify Code and Test families have symmetric variants (Code auth:role-based → Test auth:role-based must match), block if asymmetric
- Family compliance metrics → Track % templates with family membership (target: 100%), % templates violating family rules (target: 0%), variant symmetry compliance (target: 100%), template count per family
- Idempotence gate enforcement → Verify idempotence test passed before promoting tasks to golden, block promotion if test fails
- CI idempotence job → Ensure CI pipeline has idempotence job (run generator twice, assert no diffs)
- Metadata timestamp audit → Verify timestamps ONLY in .task/ metadata files (wiring.yaml, gate_results.yaml, logbook.yaml), NOT in src/ or tests/
- Idempotence contract review → Verify all templates have idempotence contract in metadata, verify all 5 causes addressed
- Promotion checklist → Add idempotence checks to promotion criteria (contract declared, test passed, CI green, no timestamps in code)
- Idempotence metrics → Track % templates idempotent (target: 100%), idempotence test pass rate, timestamp violations (target: 0), idempotence test runtime
- Protected region limit enforcement → Verify ≤2 regions per file, ≤80 lines per region before promotion, block if limits exceeded
- Protected region SSOT declaration → Verify all regions declared in `.task/wiring.yaml` Section 6 with rationale, hash, lines, graduation tracking
- Protected region graduation tracking → Run quarterly review with `tools/region_reuse_detector.py`, detect patterns used 3+ times, file graduation tickets in `LogBook/exceptions/protected-regions/`
- Region allowlist governance → Approve new region names (if pattern not suitable for template/plugin/variant), enforce "6 approved names only" rule
- Protected region promotion checklist → Add region checks to promotion criteria (8 mechanical checks pass, within limits, no interface alterations, graduation check passed, region quality adequate)
- Protected region metrics → Track % tasks with regions (target <30%), region size distribution (average <20 lines, max <80 lines), graduation rate (target 100%), region violation rate (target 0%)
- BASE version archival → Ensure BASE version stored in `.saf/generated/<task-id>/base/` after successful generation, verify metadata.yaml complete (generated_at, template info, inputs_hash, file hashes)
- Merge conflict escalation → Review merge conflicts declared in `.task/wiring.yaml` Section 7, escalate to human arbiter when conflict resolution strategy unclear or conflict recurring
- Merge policy enforcement → Enforce three-way merge policy (BASE + LOCAL + NEW), block regeneration if BASE version missing (no BASE = no merge = overwrite), require conflict resolution before promotion
- CI merge test gate → Ensure CI pipeline has merge test gate (simulate regeneration with manual edits, verify no conflicts or conflicts detected correctly), block if merge test fails
- Merge metrics → Track % tasks with BASE versions (target: 100%), merge conflict rate (target: <10%), auto-merge success rate (Level 1: 60%, Level 2: 80%, Level 3: 95%), conflict resolution time (average)
- Template lifecycle management → Approve MAJOR version releases (breaking changes), manage deprecation schedule (active → maintenance → deprecated → retired), enforce retirement dates (block tasks using retired templates), track template upgrade progress
- Template version governance → Review template version bump proposals (PATCH/MINOR/MAJOR), approve breaking change documentation, verify migration guides complete before MAJOR release, escalate when Template Upgrade Task fails
- SemVer enforcement → Ensure PATCH = no behavior change, MINOR = backward compatible, MAJOR = breaking change + migration guide + PM approval required
- Template deprecation workflow → Announce deprecation (LogBook + Teams), set retirement deadlines (maintenance: 6 months, deprecated: 3 months), scan for affected tasks, file migration tickets, verify all tasks migrated before retirement
- Retired template blocking → Block promotion if task uses retired template, verify CI rejects retired templates, approve emergency exceptions (with aggressive re-retirement date)
- Template Upgrade Task approval → Review Template Upgrade Task plans, verify compatibility matrix satisfied, approve coordinated upgrades (multiple templates with dependencies), track upgrade velocity (target: 10+ upgrades/month)
- Template version metrics → Track template version distribution (target: 80%+ on active), deprecated template usage (target: 0), breaking change frequency (target: ≤2 MAJOR/year), template lifecycle health (active 12+ months, maintenance 6 months, deprecated 3 months)
- Template compliance governance → Approve compliance contracts per family (code/test/doc/config/schema), verify compliance suite runs on template changes, block template promotion if compliance fails, track compliance pass rate (target: 100%)
- Stage 0.5 gate enforcement → Templates cannot advance past Stage 0.5 unless compliance PASS, verify compliance results logged in template metadata, block template usage if compliance results missing or stale (>3 months)
- Fixture management → Approve test fixtures (minimal/typical/edge), verify fixtures cover realistic scenarios, add fixtures when compliance passes but production usage fails (fixture gap)
- CI compliance enforcement → Verify `.github/workflows/template_compliance.yml` enabled, monitor CI compliance results, escalate compliance failures to template maintainers
- Template compliance metrics → Track compliance pass rate (target: 100%), compliance failures by family, fixture coverage (target: 100% with 3 fixtures), time to fix compliance failures (target: ≤4 hours), production failures after compliance (target: 0%)
- DAG validation enforcement → Run `tools/dag_validator.py` on all task plans, block promotion if validation fails (7 checks: acyclic, connected, no orphans, no duplicates, no self-loops, node-edge correspondence, stage consistency)
- Topological order computation → Run `tools/topological_sort.py`, store topological order in SSOT Section 9, verify all tasks have computed build order before work starts
- Parallel work assignment → Identify parallel sets from DAG, assign tasks to multiple Builder agents concurrently, execute tasks in waves (Wave N tasks can run in parallel)
- Critical path monitoring → Track progress on critical path (longest path from root to leaf), escalate if bottleneck tasks delayed, prioritize critical path tasks
- Cycle detection escalation → If cycle detected by `tools/find_cycles.py`, escalate to human arbiter with cycle details, block task plan until cycle broken
- Build order enforcement → Ensure tasks executed in topological order, verify predecessor tasks completed before successor tasks start, block execution if dependencies violated
- Wave-based execution → Execute tasks in waves, wait for all Wave N tasks to complete before starting Wave N+1, log wave completion times
- Concurrency metrics tracking → Track actual vs estimated speedup from parallel execution, log max parallel workers used, compare critical path time vs sequential time
- DAG promotion checklist → Verify graph.yaml exists, validation passed (7 checks), topological order computed, parallel sets identified, critical path computed before approving task plan
- Quarterly reviews → Check exception metrics, drift debt, template freshness, fork violations, traceability debt, checkpoint compliance rates, plugin reuse rates, schema coverage, schema exception rate, reference-first compliance, template ROI, stage gate pass rates, SSOT compliance rate, SSOT violation rate, template family compliance, idempotence test pass rate, protected region usage rate, graduation rate, BASE version coverage, merge conflict rate, auto-merge success rate, template version distribution, deprecated template usage, template upgrade velocity, template compliance pass rate, DAG validation pass rate, parallel execution speedup, critical path optimization rate

---

### For Planner

**Read at session start:**
1. [Code Generation Methodology](./code-generation-methodology.md) - Review decomposition rules
2. [Agent Operating Principles](./agent-operating-principles.md) - Check micro-task discipline
3. [Generation Escape Hatch Policy](../../PLANNING/GENERATION_ESCAPE_HATCH_POLICY.md) - Know when to trigger escape hatch
4. [Template Drift Detection Policy](../../PLANNING/TEMPLATE_DRIFT_DETECTION_POLICY.md) - Know drift detection workflow
5. [Template Variants & Parameter Packs Policy](../../PLANNING/TEMPLATE_VARIANTS_AND_PARAMETER_PACKS_POLICY.md) - Know variant selection
6. [Traceability by Construction Policy](../../PLANNING/TRACEABILITY_BY_CONSTRUCTION_POLICY.md) - Know traceability requirements
7. [Two Test Runs Policy](../../PLANNING/TWO_TEST_RUNS_POLICY.md) - Know checkpoint definition requirements
8. [Plugin Architecture Policy](../../PLANNING/PLUGIN_ARCHITECTURE_POLICY.md) - Know plugin system and orthogonal functionality
9. [Schema-Driven Module Generation Policy](../../PLANNING/SCHEMA_DRIVEN_MODULE_GENERATION_POLICY.md) - Know schema types and schema-first workflow
10. [Reference-First Templatization Policy](../../PLANNING/REFERENCE_FIRST_TEMPLATIZATION_POLICY.md) - Know Task Type A/B distinction and battle-tested criteria
11. [Stage-Gated Generation Pipeline Policy](../../PLANNING/STAGE_GATED_GENERATION_PIPELINE_POLICY.md) - Know 5-stage pipeline and gate criteria
12. [SSOT Wiring File Policy](../../PLANNING/SSOT_WIRING_FILE_POLICY.md) - Know SSOT structure and creation requirements
13. [Template Families Policy](../../PLANNING/TEMPLATE_FAMILIES_POLICY.md) - Know 5 canonical families and family-per-stage mapping
14. [Idempotent Generation Policy](../../PLANNING/future/IDEMPOTENT_GENERATION_POLICY.md) - Know idempotence contract requirements and 5 causes of non-idempotence
15. [Protected Regions Policy](../../PLANNING/future/PROTECTED_REGIONS_POLICY.md) - Know region vs plugin decision criteria and graduation path
16. [Three-Way Merge Regeneration Policy](../../PLANNING/THREE_WAY_MERGE_REGENERATION_POLICY.md) - Know three-way merge workflow, three merge rules, and conflict types
17. [Template Versioning & Deprecation Policy](../../PLANNING/TEMPLATE_VERSIONING_AND_DEPRECATION_POLICY.md) - Know SemVer rules, template lifecycle states, and Template Upgrade Task workflow
18. [Template Compliance Policy](../../PLANNING/TEMPLATE_COMPLIANCE_POLICY.md) - Know compliance requirements for template selection, fixture planning, and Stage 0.5 gate
19. [Dependency Graph & Topological Build Order Policy](../../PLANNING/DEPENDENCY_GRAPH_AND_TOPOLOGICAL_BUILD_ORDER_POLICY.md) - Know DAG output requirements, topological sort, and parallel work planning
20. [Security & Policy Linting as First-Class Gates Policy](../../PLANNING/SECURITY_POLICY_LINTING_AS_FIRST_CLASS_GATES_POLICY.md) - Know 13 security policies, SSOT security schema extensions, and security test requirements
21. [Anti-Corruption Layer Policy](../../PLANNING/ANTI_CORRUPTION_LAYER_POLICY.md) - Know Ports-and-Adapters architecture, vendor SDK isolation rules, and adapter creation workflow
22. [Metrics Feedback Loop Policy](../../PLANNING/METRICS_FEEDBACK_LOOP_POLICY.md) - Know per-task specification schema, ROI decision rules, and when to templatize/harden/retire
23. [Spec-to-diff Previews Policy](../../PLANNING/SPEC_TO_DIFF_PREVIEWS_POLICY.md) - Know preview generation workflow, causal mapping requirements, and preview approval criteria

**Reference during:**
- Breaking down specs → Apply task size constraints (≤4 hours)
- Identifying dependencies → Ensure explicit ordering
- Estimating effort → Use Golden Task patterns
- Template gaps → Assess trigger conditions, recommend exception type
- Golden task changes → Flag tasks, schedule drift check task
- Variant selection → Identify required variants, check composition rules
- Similar requirements → Use variants instead of creating new templates
- Creating task plans → Generate task IDs (UUIDs), reference specs, list expected outputs
- Template selection → Select templates with versions for traceability
- Defining checkpoints → Declare Test Run #1 (structural) and Test Run #2 (behavioral) for every task
- Structural boundary identification → Define "what validates wiring is correct" before behavior
- Task understanding check → If cannot define early checkpoint, task not yet understood (decompose or clarify)
- Cross-cutting concerns → Identify orthogonal functionality (logging, auth, validation), specify as plugins not base task code
- Plugin selection → Declare which plugins attach to task (validation, auth, rate-limit, audit-log, etc.)
- Base task scope → Define core behavior only, exclude cross-cutting concerns from base
- Schema type identification → Determine which schema types needed (Structural / Behavioral / Integration)
- Schema completeness criteria → Define what makes schema complete before generation can begin
- Schema definition tasks → Create tasks for schema definition (separate from generation tasks)
- Schema selection → Choose appropriate schema format (JSON Schema, OpenAPI, custom)
- Schema exceptions → Determine when behavior is non-representable in schema, file exception tickets
- Reference implementation identification → Identify patterns that will repeat (reuse probability >30%), recommend Task Type A (Reference Implementation) when new pattern needed
- Templatization planning → Identify templatization opportunities (golden tasks not yet templated), recommend Task Type B (Templatization) when reference battle-tested and pattern used ≥2 times
- Template selection → Search archives/golden/*/template/ for matching patterns, specify template + parameters in task plan, estimate effort savings vs manual implementation
- Battle-tested criteria → Define verification requirements for reference implementation (production exposure, high-confidence testing, or security audit)
- Stage planning → Break work into 5 stage tasks (Stage 0: Specification & Schema, Stage 1: Structural Skeleton, Stage 2: Capability Composition, Stage 3: Behavioral Generation, Stage 4: Integration & Promotion)
- Stage dependencies → Define dependencies (each stage task depends on prior stage), set explicit ordering (0 → 1 → 2 → 3 → 4)
- Gate criteria definition → Specify what each gate must verify, list acceptance criteria per stage, identify tests to run at each gate boundary
- SSOT creation (Stage 0) → Create minimal SSOT with 5 sections: identity (task ID, spec ref, schema ref), interfaces (API endpoints, events), composition (empty), wiring (empty), verification (gate criteria, required tests)
- SSOT interface declaration → Declare all API endpoints (method, path, request, response, auth), all events (published, subscribed), all commands (CLI, queue messages)
- SSOT verification contract → Define all 5 stage gates (criteria + tests), list required test files, specify coverage threshold
- SSOT validation → Use `examples/ssot/minimal-wiring.yaml` as template, validate SSOT with `tools/schema_validator.py --validate` before committing
- Template family selection (per stage) → Stage 0: Schema family, Stage 1: Code + Config families, Stage 2: Config family, Stage 3: Code + Test families, Stage 4: Doc + Config families
- Family membership declaration → Declare template family for each template in task plan, ensure no forbidden families used at each stage (Test family forbidden at Stage 1, Code family forbidden at Stage 4)
- Variant symmetry planning → If Code family uses variants (auth: role-based, validation: strict), Test family MUST use matching variants, declare variant symmetry in task plan
- Family-specific parameters → Provide required parameters from family input contract, do NOT provide forbidden parameters (Code family forbids test_framework, Test family forbids service_logic)
- Template organization → Select templates from family-based structure (archives/golden/templates/code/, /test/, /doc/, /config/, /schema/), NOT domain-based (auth/, payment/)
- Template selection (idempotent templates only) → Only select templates with idempotence contract in metadata, reject templates without deterministic: true
- SSOT idempotence metadata → Include idempotence contract in .task/wiring.yaml verification section, declare idempotence test as gate criterion
- Variant symmetry planning → If Code family uses variants, Test family MUST use matching variants (enables idempotent test generation)
- Idempotence test planning → Declare idempotence test as gate criterion for Stage 1 and Stage 3, specify test command (npm run test:idempotence)
- Region vs Plugin decision → If orthogonal functionality (logging, auth, validation) → plugin, if one-off customization (domain-specific quirk) → protected region
- Template selection (with region placeholders) → Choose templates with region placeholders for files needing customization, verify templates have region markers in appropriate locations
- SSOT region declaration → Declare region placeholders in `.task/wiring.yaml` Section 6 with `hash=PLACEHOLDER`, rationale (why needed), graduation tracking (eligible: false, usage_count: 0)
- Graduation planning → When pattern used 3+ times, recommend Task Type B (Templatization/Plugin Creation) instead of protected region, file graduation ticket
- BASE version planning → Plan for BASE version storage in `.saf/generated/<task-id>/base/` after Stage 1 completion (skeleton) and after Stage 3 completion (behavioral)
- Merge-aware task planning → For regeneration tasks (updating existing generated code), declare BASE version dependency, plan three-way merge workflow, specify conflict detection criteria
- SSOT merge conflict declaration → Declare merge conflict section (Section 7) in `.task/wiring.yaml` with status: pending initially, plan for resolution strategy (manual_merge, accept_local, accept_new, rebase)
- Conflict type identification → Identify potential conflict types (generated core, plugin output, protected region, documentation, test) based on expected manual edits vs generator changes
- Template version selection → Select template version for new tasks (default: latest active), justify if using non-active version (maintenance/deprecated), document reason in task plan
- Template version declaration → Declare template@version in task plan (e.g., api-crud@2.3.0), specify parameter pack version, verify template status not retired
- SSOT Section 8 creation → Populate `.task/wiring.yaml` Section 8 (template_versions) with template name, version, family, parameter_pack, pinned: true, files_generated
- Template compatibility verification → Verify template compatibility constraints satisfied (e.g., api-crud@2.3.0 requires api-crud-tests@==2.3.*), check compatibility matrix before template selection
- Template Upgrade Task planning → When migration needed, create Template Upgrade Task (Type U), specify source template version, target template version, migration steps (retrieve BASE → regenerate → merge → test → update SSOT)
- Coordinated upgrade planning → When multiple templates have dependencies, plan coordinated upgrade (upgrade auth-plugin first → then api-crud), estimate total effort, sequence upgrades to avoid conflicts
- Deprecated template exception filing → If upgrade blocked, file exception ticket in LogBook/exceptions/template-upgrades/, document blocking reason, propose workaround, set extension deadline
- Template upgrade effort estimation → Estimate upgrade effort based on change type (PATCH=5min, MINOR=15min, MAJOR=45min), factor in dependency upgrades, provide total effort in task plan
- Template selection (compliance-verified only) → Only select templates with compliance badge in metadata, reject templates without compliance results, verify compliance results not stale (>3 months), flag templates with warnings (lint issues, deprecated APIs)
- Fixture planning → When creating new template, plan 3 fixtures (minimal/typical/edge), estimate effort (minimal: 15min, typical: 30min, edge: 45min), include fixture creation in task plan
- Compliance planning for new templates → Plan compliance suite run BEFORE template promotion, include compliance run in task effort estimate (≤1 hour), plan compliance re-run for template version bumps
- DAG output requirement → Output graph.yaml (DAG structure) for all task plans with 2+ tasks, include nodes (tasks with effort_hours, stage) and edges (dependencies with reason)
- Dependency declaration → Declare all task dependencies as edges in graph.yaml with reason field explaining why dependency exists, avoid implicit dependencies
- Effort estimation for DAG → Estimate effort_hours for each task node (used for critical path calculation), provide realistic estimates for accurate parallel work planning
- Stage assignment → Assign stage (0-4) to each task, ensure dependencies respect stage ordering (Stage N task cannot depend on Stage N+1 task)
- Parallel work identification → Structure task plan to maximize parallel work opportunities, minimize unnecessary sequential dependencies, identify independent work streams
- Cycle avoidance → Design task plans without circular dependencies, verify no task depends on itself transitively, check dependency graph for cycles
- Root task identification → Identify root tasks (no dependencies) as Wave 0, ensure at least one root task exists for DAG to be valid
- Leaf task identification → Identify leaf tasks (no successors) as final integration/verification tasks, typical examples: integration tests, doc generation, deployment
- SSOT Section 9 planning → Plan dependency_graph section in `.task/wiring.yaml` with topological_order, parallel_sets, critical_path (populated by PM after topological sort)

---

### For Builder

**Read at session start:**
1. [Code Generation Methodology](./code-generation-methodology.md) - Review implementation rules
2. [Quality Standards & Verification](./quality-standards.md) - Check quality requirements
3. [Template Drift Detection Policy](../../PLANNING/TEMPLATE_DRIFT_DETECTION_POLICY.md) - Know template update responsibilities
4. [Template Variants & Parameter Packs Policy](../../PLANNING/TEMPLATE_VARIANTS_AND_PARAMETER_PACKS_POLICY.md) - Know variant implementation
5. [Traceability by Construction Policy](../../PLANNING/TRACEABILITY_BY_CONSTRUCTION_POLICY.md) - Know manifest structure and provenance headers
6. [Two Test Runs Policy](../../PLANNING/TWO_TEST_RUNS_POLICY.md) - Know checkpoint-driven development workflow
7. [Plugin Architecture Policy](../../PLANNING/PLUGIN_ARCHITECTURE_POLICY.md) - Know plugin attachment and extension points
8. [Schema-Driven Module Generation Policy](../../PLANNING/SCHEMA_DRIVEN_MODULE_GENERATION_POLICY.md) - Know schema implementation and validation workflow
9. [Reference-First Templatization Policy](../../PLANNING/REFERENCE_FIRST_TEMPLATIZATION_POLICY.md) - Know reference implementation requirements and template extraction workflow
10. [Stage-Gated Generation Pipeline Policy](../../PLANNING/STAGE_GATED_GENERATION_PIPELINE_POLICY.md) - Know 5-stage pipeline and gate execution requirements
11. [SSOT Wiring File Policy](../../PLANNING/SSOT_WIRING_FILE_POLICY.md) - Know SSOT update workflow and validation
12. [Template Families Policy](../../PLANNING/TEMPLATE_FAMILIES_POLICY.md) - Know family contracts and stage alignment
13. [Idempotent Generation Policy](../../PLANNING/future/IDEMPOTENT_GENERATION_POLICY.md) - Know idempotent generation workflow and canonicalization utilities
14. [Protected Regions Policy](../../PLANNING/future/PROTECTED_REGIONS_POLICY.md) - Know extract → regenerate → reinsert workflow and region limits
15. [Three-Way Merge Regeneration Policy](../../PLANNING/THREE_WAY_MERGE_REGENERATION_POLICY.md) - Know BASE version storage, three-way merge execution, and conflict detection workflow
16. [Template Versioning & Deprecation Policy](../../PLANNING/TEMPLATE_VERSIONING_AND_DEPRECATION_POLICY.md) - Know template version enforcement, Template Upgrade Task execution, and compatibility checking
17. [Template Compliance Policy](../../PLANNING/TEMPLATE_COMPLIANCE_POLICY.md) - Know compliance suite usage, fixture creation, and compliance failure resolution
18. [Dependency Graph & Topological Build Order Policy](../../PLANNING/DEPENDENCY_GRAPH_AND_TOPOLOGICAL_BUILD_ORDER_POLICY.md) - Know topological order execution, wave-based execution, and predecessor verification
19. [Security & Policy Linting as First-Class Gates Policy](../../PLANNING/SECURITY_POLICY_LINTING_AS_FIRST_CLASS_GATES_POLICY.md) - Know security policy enforcement, SSOT security validation, and security test generation
20. [Anti-Corruption Layer Policy](../../PLANNING/ANTI_CORRUPTION_LAYER_POLICY.md) - Know adapter implementation workflow, port interface creation, and vendor type translation
21. [Metrics Feedback Loop Policy](../../PLANNING/METRICS_FEEDBACK_LOOP_POLICY.md) - Know per-task metrics collection, LogBook manifest creation, and metrics reporting
22. [Spec-to-diff Previews Policy](../../PLANNING/SPEC_TO_DIFF_PREVIEWS_POLICY.md) - Know preview generation (dry-run mode), preview artifact creation, and "no apply without preview" rule

**Reference during:**
- Starting implementation → Check Golden Task archive for patterns
- Writing tests → Apply testing standards
- Submitting for review → Use review request template
- Updating golden tasks → Never update template in same commit
- Updating templates → Update metadata (commit hash, sync date)
- Adding variants → Implement in base + variants structure, not forks
- Creating presets → Ensure combination is used 3+ times first
- Generating files → Embed provenance headers (9+ tags required)
- Completing task → Create complete manifest in `.task/` directory
- Before commit → Run `tools/traceability_checker.py` to verify compliance
- Implementation workflow → Follow checkpoint-driven development: implement structure → Test Run #1 → implement behavior → Test Run #2
- After structure → Run `tools/checkpoint_runner.py --run-checkpoint-1` (MUST PASS before continuing)
- After behavior → Run `tools/checkpoint_runner.py --run-checkpoint-2` (MUST PASS for promotion eligibility)
- Base task implementation → Core behavior ONLY, no cross-cutting concerns (logging, auth, validation)
- Plugin attachment → Read `.task/plugins.yaml`, load plugins, execute at extension points
- Extension points → Implement before_execution, after_execution, on_error, on_success hooks
- Plugin declaration → Create `.task/plugins.yaml` with plugin names, versions, configs
- Schema implementation → Write schemas following completeness rules (all fields typed, constraints explicit, relationships defined)
- Schema validation → Run `tools/schema_validator.py --validate` before generation (Test #1 checkpoint)
- Schema-driven generation → Run generator with schema as input, embed `@saf:schema-source` in generated artifacts
- Schema traceability → Add schema references to task specification (schemas section with path, version, type, hash)
- Schema versioning → Version schemas using semantic versioning, update metadata (version, last_updated)
- Schema-first workflow → Implement structure from schema → Test #1 → attach plugins based on schema extension points → generate behavior from behavioral schema → Test #2
- Non-representable behavior → Do NOT write behavior not defined in schema unless exception filed and marked with `@saf:exception=schema-non-representable`
- Reference implementation (Type A) → Build manually (or minimal generation), follow full quality standards, create comprehensive test suite, deploy to production or equivalent, create reference metadata, document battle-tested verification
- Templatization (Type B) → Extract template from reference (LLM-assisted if approved), ONLY structural parameterization (names, types, paths, optional blocks), create parameter schema, generate code from template with default params, verify equivalence (generated == reference), create equivalence tests, write usage docs + examples, update reference metadata (templated = true)
- Template usage → Generate code from template with specified parameters, embed provenance (@saf:template, @saf:derived-from-reference), run equivalence tests if template provides them, do NOT manually edit generated code (use parameters instead)
- Structural parameterization only → Parameterize names, types, paths, optional blocks, do NOT parameterize algorithms, logic, business rules (creative parameterization forbidden)
- Stage execution → Execute stages sequentially (0 → 1 → 2 → 3 → 4), do NOT skip stages, repeat out of order, or merge stages
- Gate testing → Run gate tests after completing each stage (Stage 0: schema validates, Stage 1: Test Run #1, Stage 2: compatibility validation, Stage 3: Test Run #2, Stage 4: CI green)
- Gate results logging → Log gate results in `.task/gate_results.yaml` with timestamp, verdict, criteria, test results
- Failure handling → Stop if gate fails (block until fixed), fix root cause, re-run gate, proceed only after pass
- Gate failure escalation → Escalate to PM if gate fails 3+ times, provide failure analysis, request guidance
- No shortcuts → Do NOT skip stages ("we'll test later"), do NOT merge stages ("structural + behavioral together"), do NOT repeat out of order ("go back to Stage 1 after Stage 3")
- Stage traceability → Track which stage task is executing, update task status when stage completes, link gate results to task specification
- SSOT update (Stage 1) → Update `wiring:` section with file paths (controller, service, repository, tests), update `data_flow:`, update `config_sources:`, update `dependencies:`, update `identity: builder_commit:`
- SSOT update (Stage 2) → Update `composition: plugins:` with plugin declarations (name, version, config, extension_points), verify plugin compatibility
- SSOT validation → Run `tools/schema_validator.py --verify-task .task/` after updating SSOT, fix violations before proceeding
- SSOT frozen after Stage 2 → Do NOT modify SSOT in Stages 3-4 (only code), if structure changes needed → rollback to Stage 1
- Family-aware template usage → Only use templates from allowed families for current stage (Stage 1: Code+Config, Stage 3: Code+Test, Stage 4: Doc+Config), block if forbidden family attempted
- Family input contract adherence → Provide required parameters from family contract, do NOT provide forbidden parameters (Code forbids test_framework, Test forbids service_logic, Doc forbids code_logic)
- Family output contract compliance → Embed required headers in generated files (@saf:template-family: code), place files in expected paths (Code → src/, Test → tests/, Doc → docs/), update SSOT with family membership
- Variant symmetry execution → If Code family template uses variants (auth: role-based), Test family template MUST use matching variants, block if asymmetric
- Family-specific verification → Run family verification rules (Code: compiles + types_valid, Test: tests_executable + tests_pass, Doc: markdown_valid + links_resolve)
- Idempotent generation → Run generators with stable inputs (from SSOT, NOT from disk), use canonicalization utilities (sorted keys, stable ordering)
- No file reads → Never read generated files as inputs to generation, inputs ONLY from specs, schemas, SSOT
- No timestamps in code → Remove @saf:generated-at and similar timestamps from generated code (only in metadata)
- Formatter locking → Lock formatter version in template metadata, run formatter ONCE after generation
- Gate testing → Run idempotence test after Stage 1 and Stage 3 (generate twice, assert no diffs), log results in .task/gate_results.yaml
- Canonicalization usage → Use sortedKeys, canonical_yaml_dump, normalize_line_endings for stable output
- Idempotence test execution → Run `npm run test:idempotence` after completing Stage 1 and Stage 3, verify byte-identical output, block progression if test fails
- Protected region preservation → Extract regions before regeneration using `tools/protected_regions.py extract`, reinsert after regeneration using `tools/protected_regions.py reinsert`
- Region hash updates → Calculate new hashes when region content changes using `tools/protected_regions.py hash`, update SSOT `.task/wiring.yaml` Section 6 with new hash, lines count, modified_at timestamp
- Region limit enforcement → Ensure ≤2 regions per file, ≤80 lines per region, block if exceeded (file escape hatch ticket instead)
- No interface alterations in regions → Do NOT modify function signatures, exported types, route contracts, database schemas in protected regions (interface stability required)
- Region LogBook entries → Log region creation, modification events in `.task/logbook.yaml` with old_hash, new_hash, lines_changed
- Template usage with region placeholders → Use templates with region placeholders, fill placeholders with `hash=PLACEHOLDER` initially (Stage 1), allow developer to fill regions (Stage 3)
- BASE version storage → After successful generation (Stage 1 and Stage 3), copy generated files to `.saf/generated/<task-id>/base/`, create `metadata.yaml` with generated_at, template info, inputs_hash, file hashes
- Three-way merge execution → For regeneration, retrieve BASE version using `tools/get_base_version.py`, run `tools/three_way_merge.py` with BASE/LOCAL/NEW, apply merge rules (Rule 1: NEW wins if LOCAL unchanged, Rule 2: LOCAL wins if NEW unchanged, Rule 3: CONFLICT if both changed)
- Conflict detection → Detect merge conflicts (both BASE→LOCAL and BASE→NEW changed same lines), block regeneration if conflicts found, log conflicts in `.task/wiring.yaml` Section 7 with conflict type, base/local/new content, line numbers
- Conflict resolution workflow → If conflicts detected, escalate to PM/human arbiter, await resolution strategy (manual_merge, accept_local, accept_new, rebase), execute resolution, update SSOT Section 7 with resolved_at timestamp and resolution_strategy
- BASE version updates → After conflict-free merge or successful resolution, update BASE version with merged result, update metadata.yaml with new generated_at timestamp and inputs_hash
- Merge LogBook entries → Log merge operations in `.task/logbook.yaml` with merge_type (auto_merge, manual_merge, conflict_detected), files_merged, conflicts_count, resolution_strategy
- Template version enforcement → Use exact template version declared in SSOT Section 8 (no silent upgrades), block regeneration if template version mismatch between SSOT and requested version
- Template compatibility checking → Run `tools/template_compatibility_checker.py` before regeneration, verify all compatibility constraints satisfied (e.g., api-crud@2.3.0 requires api-crud-tests@==2.3.*), block if constraints violated
- Template version headers → Embed template version in file headers (@saf:template-version=2.3.0, @saf:parameter-pack-version=1.0.0), ensure headers match SSOT declarations
- Template Upgrade Task execution → For Template Upgrade Tasks (Type U), execute workflow: retrieve BASE version → regenerate with new template version → three-way merge → run Test #1 and #2 → update SSOT Section 8 → update BASE version
- SSOT Section 8 updates → After successful Template Upgrade Task, update template_versions with new version, set upgraded_from and upgraded_at, add entry to template_upgrade_history
- Template version LogBook entries → Log template version changes in `.task/logbook.yaml` with old_version, new_version, change_type (patch/minor/major), breaking_changes list, upgrade_task_id
- Compliance suite execution → Run compliance suite locally before committing template changes using `./templates/compliance/harness/run_checks.sh`, fix compliance failures before pushing, log compliance results in template metadata
- Fixture creation → Create 3 fixtures per template (minimal/typical/edge): minimal (simplest valid inputs), typical (realistic module with common patterns), edge (annoying edge cases: nullable, enums, max length)
- Compliance failure resolution → If compliance fails, investigate failure reason (common: non-idempotent rendering, missing traceability headers, compile errors, lint violations, sanity check failures), fix template, re-run compliance, commit only after PASS
- Template metadata updates → Update `template_metadata.yaml` with compliance results (last_compliance_run, compliance_status, compliance_results_file), LogBook entry: "Ran compliance suite for <template>, status: <pass|fail>"
- Topological order execution → Execute tasks in topological order from SSOT Section 9, never start task until all predecessors completed, verify predecessor status before execution
- Wave-based execution → Execute all tasks in current wave, wait for all Wave N tasks to complete before advancing to Wave N+1, log wave start/end times
- Predecessor verification → Before starting task, verify all predecessors in completed state, block execution if any predecessor failed or incomplete
- DAG status updates → Update task status in graph.yaml (pending → in_progress → completed), update execution timestamps, log actual effort vs estimated effort
- Blocked task handling → If predecessor task fails, mark dependent tasks as blocked, escalate to PM with failure details and blocked task list
- LogBook entries for DAG → Log task execution order, wave completion times, actual vs estimated parallel speedup, predecessor verification results
- No out-of-order execution → NEVER execute task before its predecessors (even if tempting to "get ahead"), strict topological order enforcement

---

### For Critic

**Read at session start:**
1. [Quality Standards & Verification](./quality-standards.md) - Review evaluation criteria
2. [Agent Coordination Protocol](./agent-coordination-protocol.md) - Check verdict format
3. [Template Drift Detection Policy](../../PLANNING/TEMPLATE_DRIFT_DETECTION_POLICY.md) - Know drift classification
4. [Template Variants & Parameter Packs Policy](../../PLANNING/TEMPLATE_VARIANTS_AND_PARAMETER_PACKS_POLICY.md) - Know composition validation
5. [Traceability by Construction Policy](../../PLANNING/TRACEABILITY_BY_CONSTRUCTION_POLICY.md) - Know traceability verification checklist
6. [Two Test Runs Policy](../../PLANNING/TWO_TEST_RUNS_POLICY.md) - Know two-checkpoint evaluation requirements
7. [Plugin Architecture Policy](../../PLANNING/PLUGIN_ARCHITECTURE_POLICY.md) - Know 5 plugin verification rules
8. [Schema-Driven Module Generation Policy](../../PLANNING/SCHEMA_DRIVEN_MODULE_GENERATION_POLICY.md) - Know schema validation rules and exception verification
9. [Reference-First Templatization Policy](../../PLANNING/REFERENCE_FIRST_TEMPLATIZATION_POLICY.md) - Know battle-tested criteria and equivalence verification requirements
10. [Stage-Gated Generation Pipeline Policy](../../PLANNING/STAGE_GATED_GENERATION_PIPELINE_POLICY.md) - Know gate evaluation criteria and blocking rules
11. [SSOT Wiring File Policy](../../PLANNING/SSOT_WIRING_FILE_POLICY.md) - Know SSOT verification checklist and mechanical checks
12. [Template Families Policy](../../PLANNING/TEMPLATE_FAMILIES_POLICY.md) - Know 6 family verification checks and blocking rules
13. [Idempotent Generation Policy](../../PLANNING/future/IDEMPOTENT_GENERATION_POLICY.md) - Know 6 idempotence verification checks and blocking rules
14. [Protected Regions Policy](../../PLANNING/future/PROTECTED_REGIONS_POLICY.md) - Know 8 protected region verification checks and graduation criteria
15. [Three-Way Merge Regeneration Policy](../../PLANNING/THREE_WAY_MERGE_REGENERATION_POLICY.md) - Know merge conflict verification checks and resolution strategy review
16. [Template Versioning & Deprecation Policy](../../PLANNING/TEMPLATE_VERSIONING_AND_DEPRECATION_POLICY.md) - Know template version verification checks, lifecycle state validation, and upgrade verification
17. [Template Compliance Policy](../../PLANNING/TEMPLATE_COMPLIANCE_POLICY.md) - Know compliance verification checks, blocking rules, and compliance verdict requirements
18. [Dependency Graph & Topological Build Order Policy](../../PLANNING/DEPENDENCY_GRAPH_AND_TOPOLOGICAL_BUILD_ORDER_POLICY.md) - Know DAG mechanical checks, execution order verification, and blocking rules
19. [Security & Policy Linting as First-Class Gates Policy](../../PLANNING/SECURITY_POLICY_LINTING_AS_FIRST_CLASS_GATES_POLICY.md) - Know 13 security policy checks, security gate verification, and Critic Dimension 6 enforcement
20. [Anti-Corruption Layer Policy](../../PLANNING/ANTI_CORRUPTION_LAYER_POLICY.md) - Know vendor type leakage detection, adapter contract verification, and port interface compliance
21. [Metrics Feedback Loop Policy](../../PLANNING/METRICS_FEEDBACK_LOOP_POLICY.md) - Know per-task metrics validation, ROI calculation verification, and metrics completeness checks
22. [Spec-to-diff Previews Policy](../../PLANNING/SPEC_TO_DIFF_PREVIEWS_POLICY.md) - Know preview artifact verification, causal mapping completeness, and Stage -1 gate enforcement

**Reference during:**
- Evaluating code → Apply 5-dimension framework
- Writing verdicts → Use verdict template
- Identifying issues → Reference security/quality standards
- Drift detection → Classify drift type (Intentional/Unintentional/Superset)
- Template review → Verify metadata complete, equivalence contract exists
- Variant validation → Check composition rules respected, verify required tests
- Fork detection → Flag templates >80% similar without documented variants
- Traceability check → Verify headers present, headers match manifest, spec references valid
- Manifest validation → Verify all outputs declared, all six questions answerable
- Writing verdict → Include traceability check results in `verification.json`
- Checkpoint evaluation → Evaluate both Test Run #1 (structural) and Test Run #2 (behavioral) independently
- Blocking rules → Block if early checkpoint failed, block if final checkpoint failed, passing only one is insufficient
- Evidence verification → Verify checkpoint results logged with evidence, timestamps show sequential execution
- Plugin verification → Apply 5 rules: (1) plugin doesn't modify base logic, (2) declares extension points, (3) tests exist, (4) compatibility passes, (5) declared in manifest
- Plugin isolation check → Verify base task contains core behavior only, cross-cutting concerns in plugins
- Plugin conflicts → Check no conflicting plugins attached (caching + real-time, etc.)
- Schema validation → Run `tools/schema_validator.py --verify-task` before approval
- Schema completeness → Verify all fields typed, constraints explicit, relationships defined, metadata complete, versioning correct
- Schema-artifact correspondence → Verify every generated artifact traces to schema via `@saf:schema-source` header
- Schema exceptions → Verify exceptions documented in `LogBook/exceptions/schema-driven/`, code marked with `@saf:exception=schema-non-representable`
- Schema coverage → Verify ≥95% of code traces to schema (measured by `tools/schema_validator.py --measure-coverage`)
- Blocking rules → Block if schema incomplete, block if generated code doesn't match schema, block if undocumented exceptions exist, block if schema version invalid
- Reference implementation review (Type A) → Apply full quality rubric, verify Test Run #1 + #2 passed, verify security review if security-critical, verify production exposure documented (≥2 weeks OR ≥1,000 test executions OR security audit), approve only if battle-tested
- Templatization review (Type B) → Verify reference implementation exists and is golden, verify ONLY structural parameterization (no creative: algorithms, logic, business rules), verify equivalence tests pass (generated == reference with defaults), verify parameter schema complete, verify template metadata links to reference, block if creative parameterization detected, block if equivalence tests fail
- Template usage review → Verify generated code traces to template (@saf:template, @saf:derived-from-reference), verify parameters within allowed ranges, verify equivalence properties maintained, flag if manual edits made to generated code
- Gate evaluation → Review gate results in `.task/gate_results.yaml`, verify all criteria passed, verify test evidence included
- Quality rubric application → Apply full quality rubric at Stage 3 gate (behavioral validation) and Stage 4 gate (system integration)
- Traceability verification → Verify traceability at all gates (Stage 1+: provenance headers, Stage 3+: manifest complete, Stage 4: ancestry tree)
- Gate blocking decisions → Block progression if gate fails (Stage 0: schema invalid, Stage 1: Test #1 failed, Stage 2: plugin conflicts, Stage 3: Test #2 failed, Stage 4: CI failed or Critic verdict negative)
- Stage sequence verification → Verify stages executed in order (0 → 1 → 2 → 3 → 4), flag if stage skipped, flag if stages merged, flag if repeated out of order
- Gate evidence verification → Verify gate results have timestamps, verify sequential execution, verify test outputs included, verify failure analysis provided if failed
- Stage-specific criteria → Stage 0 (schema validates, no TODOs), Stage 1 (code compiles, routes resolve, types check), Stage 2 (plugins compatible, no conflicts), Stage 3 (tests pass, spec met, coverage ≥80%), Stage 4 (CI green, Critic approved, PM decision logged)
- SSOT mechanical checks → Run `tools/schema_validator.py --verify-task .task/` for automated verification (6 checks: structure, file correspondence, interface registration, composition compliance, verification contract, traceability)
- SSOT structure validation → Verify all 5 sections present (identity, interfaces, composition, wiring, verification), verify required fields populated, verify valid values (UUIDs, versions, paths)
- File correspondence check → Verify files in `wiring:` exist on disk, flag phantom files (exist but not in SSOT), flag missing files (in SSOT but not on disk)
- Interface registration check → Verify routes in `interfaces: api:` registered in code, verify events in `interfaces: events:` published/subscribed, flag phantom endpoints (code has, SSOT doesn't)
- Composition compliance check → Verify plugins in `composition: plugins:` attached in code, flag undeclared plugins (code uses, SSOT doesn't declare)
- Verification contract check → Verify all tests in `verification:` exist, verify all gates passed, verify coverage meets threshold
- SSOT blocking rules → Block if ANY check fails, block if SSOT invalid, block if phantom files/endpoints detected, block if tests missing, block if verification contract incomplete
- SSOT verdict → Verdict is deterministic based on SSOT checks (no more "looks right" → "SSOT says so"), include SSOT check results in `verification.json`
- Template family mechanical checks → Run 6 automated checks: (1) family membership declared, (2) input contract satisfied, (3) output contract satisfied, (4) verification rules pass, (5) stage alignment respected, (6) variant symmetry (Code ↔ Test)
- Family membership check → Verify template has `template_family` field in metadata, verify family is one of 5 canonical (code, test, doc, config, schema), block if missing or invalid
- Input contract check → Verify required parameters provided (Code: entity_name, module_type, spec_ref, schema_ref), verify forbidden parameters NOT provided (Code forbids test_framework), block if violated
- Output contract check → Verify file types allowed (Code: .ts/.py, Test: .spec.ts/.test.py, Doc: .md), verify files in expected paths (Code: src/, Test: tests/, Doc: docs/), verify required headers present (@saf:template-family), block if violated
- Verification rules check → Verify family early checks pass (Code: compiles + types_valid, Test: tests_executable, Doc: markdown_valid), verify family late checks pass (Code: tests_pass, Test: tests_fail_when_code_broken, Doc: interfaces_match_SSOT), block if failed
- Stage alignment check → Verify template family allowed at current stage (Code @ Stage 1/3, Test @ Stage 3, Doc @ Stage 4), flag if forbidden family used (Test @ Stage 1 = BLOCKED), block if violated
- Variant symmetry check → If Code family uses variants (auth: role-based, validation: strict), verify Test family uses matching variants, block if asymmetric
- Family verdict → Verdict deterministic based on 6 family checks (no "looks right" → "family contract says so"), include family compliance in `verification.json`
- Idempotence mechanical checks → Run `tools/idempotence_validator.py` for automated verification (6 checks: contract declared, no timestamps in code, canonicalization used, no file reads, test passes, formatter locked)
- Idempotence test verification → Verify generator run twice with byte-identical output, block if diffs found
- Timestamp violation blocking → Scan src/ and tests/ for timestamps, block if @saf:generated-at found in code
- File read violation → Scan generator code for reads of generated files (read_file('src/', fs.readFileSync('tests/), block if found
- Canonicalization verification → Check if generator uses sortedKeys, sorted(), OrderedDict, stableJsonStringify (soft requirement, warn if missing)
- Formatter lock verification → Check if template metadata locks formatter version and config (soft requirement, warn if missing)
- Idempotence verdict → Verdict deterministic based on 6 idempotence checks (no "looks right" → "idempotence contract says so"), include idempotence check results in `verification.json`
- Protected region mechanical checks → Run `tools/protected_regions_validator.py` for automated verification (8 checks: markers valid, allowlist compliance, limits enforced, SSOT correspondence, hash integrity, no interface alterations, rationale documented, graduation tracked)
- Region marker validation → Verify region markers well-formed (matching begin/end pairs, valid syntax, hash present)
- Region allowlist enforcement → Verify region names from allowlist (custom_validation, custom_logic, custom_ui, custom_error_mapping, custom_logging, custom_metrics), block if not in allowlist
- Region limit enforcement → Verify ≤2 regions per file, ≤80 lines per region, block if exceeded
- Region SSOT correspondence → Verify regions in SSOT match regions in code (no phantom regions, no undeclared regions)
- Region hash integrity → Verify region hashes match content (unless PLACEHOLDER), calculate actual hash and compare to stored hash
- Region interface alteration check → Verify regions don't alter function signatures, exported types, route contracts, database schemas (static analysis), block if interface alterations detected
- Region quality review → Apply quality rubric to region content (code quality, security, tests), verify region content meets standards
- Region graduation eligibility → Flag if region pattern hash used 3+ times without graduation ticket, recommend graduation to template/plugin/variant
- Protected region verdict → Verdict deterministic based on 8 region checks (no "looks right" → "all checks passed"), include region compliance in `verification.json`
- Merge conflict verification → Verify merge conflicts properly detected and logged in `.task/wiring.yaml` Section 7, verify all conflicts have conflict_type, base/local/new content, line numbers, detected_at timestamp
- BASE version verification → Verify BASE version exists in `.saf/generated/<task-id>/base/` for all regeneration tasks, verify metadata.yaml complete (generated_at, template info, inputs_hash, file hashes), block if BASE version missing
- Resolution strategy review → Review conflict resolution strategy declared in SSOT Section 7 (manual_merge, accept_local, accept_new, rebase), verify strategy appropriate for conflict type (generated core → manual_merge, documentation → accept_local, test → regenerate)
- Merge result validation → Verify merged code compiles, tests pass, no syntax errors introduced by merge, verify merge didn't violate interface contracts or protected region boundaries
- Merge verdict → Verdict deterministic based on merge checks (BASE exists, conflicts detected correctly, resolution strategy appropriate, merged result valid), include merge compliance in `verification.json`, block if unresolved conflicts or BASE missing
- Template version validation → Verify file header `@saf:template-version` matches SSOT Section 8 `template_versions:` declared version, flag version drift (file says 2.3.0, SSOT says 2.4.0), verify parameter pack version matches
- Template status verification → Verify template status is not `retired` (check `templates/<name>/template_metadata.yaml`), block if retired template used, verify status is `active` or `maintenance` for new tasks, flag if `deprecated` (warn developer)
- Compatibility matrix checking → Verify template `requires:` constraints satisfied (check `template_metadata.yaml`), verify dependency versions compatible (api-crud@2.3.0 requires api-crud-tests@==2.3.*, verify Test task uses 2.3.x), block if incompatible versions detected
- Template Upgrade Task verification → Verify Template Upgrade Task (Type U) followed workflow: (1) BASE retrieved, (2) regeneration with new version, (3) three-way merge executed, (4) Test #1 passed, (5) Test #2 passed, (6) SSOT Section 8 updated, (7) BASE version updated, verify upgrade LogBook entry exists
- Lifecycle state validation → Verify template lifecycle dates valid (`active_until`, `maintenance_until`, `deprecated_until`, `retired_after`), verify current date within allowed lifecycle state, block if template past `retired_after` date
- Breaking change documentation verification → For MAJOR version bumps (1.x.x → 2.0.0), verify migration guide exists in `template_metadata.yaml`, verify breaking_changes section documents category (file_layout, interface, behavior), verify migration steps provided (automated flag, step-by-step instructions), block if MAJOR bump missing migration guide
- Template version verdict → Verdict deterministic based on template version checks (header matches SSOT, status not retired, compatibility satisfied, upgrade workflow valid, lifecycle dates valid, MAJOR bump has migration guide), include template version compliance in `verification.json`, block if retired template or incompatible versions
- Template compliance verification → Run `tools/template_compliance_checker.py <template>` to verify compliance results exist in template metadata, verify compliance status is "pass", verify compliance results not stale (>3 months old), verify all fixtures passed (minimal/typical/edge), verify all blocking checks passed, verify CI compliance check passed
- Template promotion review → For template promotion, verify compliance suite passed, verify all fixtures passed, verify compliance results logged, verify CI check passed, verify universal checks passed (idempotence, traceability, SSOT, placeholders), verify family-specific checks passed (compile, lint, smoke test, etc.)
- Compliance blocking rules → Block if compliance results missing, block if compliance status "fail", block if compliance results stale (>3 months), block if any blocking check failed, block if CI compliance check failed
- Compliance verdict → Verdict deterministic based on compliance checks (no "looks right" → "compliance contract says so"), include compliance status in `verification.json`, block template promotion if compliance fails
- DAG mechanical checks → Run `tools/dag_validator.py .task/graph.yaml` for automated verification (7 checks: acyclic, connected, no orphans, no duplicates, no self-loops, node-edge correspondence, stage consistency), verify validation status "valid", block if any check fails
- Topological order verification → Verify topological order computed and stored in SSOT Section 9 (`dependency_graph: topological_order:`), verify all tasks appear in topological order, verify no task appears before its predecessors
- Parallel sets verification → Verify parallel sets correctly identify independent tasks, verify all tasks in Wave N have no dependencies on tasks in Wave N+1 or later, verify wave numbers sequential (0, 1, 2, ...), verify can_start_after lists accurate
- Critical path verification → Verify critical path computed and identifies longest path from root to leaf, verify bottleneck task identified (task with longest effort on critical path), verify critical path effort sum correct
- Execution order verification → Verify tasks executed in topological order (check LogBook timestamps), verify no task started before predecessors completed, verify wave-based execution respected (all Wave N tasks completed before Wave N+1 started), flag out-of-order execution
- Wave completion verification → Verify all tasks in Wave N completed before Wave N+1 started, verify wave completion times logged in LogBook, verify actual wave effort ≤ max task effort in wave
- Blocking rules → Block if DAG validation fails, block if topological order missing, block if topological order invalid, block if execution order violated, block if cycle detected, block if no graph.yaml exists
- Stage consistency check → Verify dependencies respect stage ordering (Stage N task cannot depend on Stage N+1 task), flag if stage-skipping dependencies exist (Stage 0 → Stage 2), review if unusual dependencies justified
- DAG verdict → Verdict deterministic based on DAG checks (graph.yaml exists, validation passed, topological order computed, execution order respected), include DAG compliance in `verification.json`, block if DAG validation failed or execution order violated

---

## Update Policy

### When to Update Guidelines

Guidelines should be updated when:
- New patterns emerge from Golden Task archive
- Repeated issues identified in Bad Task archive
- Quality metrics indicate systemic problems
- the orchestration methodology evolves
- Human arbiter mandates policy changes

### Who Can Update

**PM only** may update guidelines, following this procedure:
1. Document proposed change in `/PLANNING/`
2. Provide rationale and evidence
3. Update guideline file
4. Log change in `/LogBook/pm/`
5. Notify all agents of update

**Rule:** No silent guideline changes. All updates must be logged and announced.

---

## Relationship to Other Documentation

```
Documentation Hierarchy:

┌────────────────────────────────────────┐
│ Project_Manager_Spec.md            │ ← Authoritative spec
└─────────────────┬──────────────────────┘
                  │
       ┌──────────┴──────────┐
       ▼                     ▼
┌─────────────┐      ┌──────────────────┐
│ PM_Decision │      │ PM_Operating     │ ← How PM operates
│ _Matrix.md  │      │ _Manual.md       │
└─────────────┘      └──────────────────┘
       │                     │
       └──────────┬──────────┘
                  ▼
       ┌────────────────────┐
       │ .claude/guidelines/│ ← How all agents operate
       │                    │
       │ • Operating Principles
       │ • Code Generation
       │ • Coordination
       │ • Quality Standards
       └────────────────────┘
                  │
       ┌──────────┴──────────┐
       ▼                     ▼
┌─────────────┐      ┌──────────────────┐
│ archives/   │      │ LogBook/         │
│ golden/     │      │                  │ ← Evidence & audit trail
│ bad/        │      │                  │
└─────────────┘      └──────────────────┘
```

**Guidelines are operational derivatives of the authoritative spec.**
They translate high-level governance rules into actionable procedures.

---

## Quick Reference Checklist

Before starting any autonomous work:

- [ ] Read relevant guideline(s) for my role
- [ ] Verify I understand write boundaries
- [ ] Check LogBook for active work orders / tasks
- [ ] Confirm repo state is up-to-date
- [ ] Review Golden Task archive for relevant patterns
- [ ] Understand escalation triggers for my task

After completing work:

- [ ] Verified work against quality standards
- [ ] Written complete LogBook entry
- [ ] Submitted handoff using proper template
- [ ] No silent assumptions or improvised procedures
- [ ] Evidence artifacts created and linked
- [ ] Next agent clearly identified

---

## Anti-Patterns (Common Mistakes)

❌ **"I read these once"**
   → Guidelines must be referenced during execution, not just once

❌ **"These are suggestions"**
   → Guidelines are mandatory operational rules

❌ **"I'll improvise when guidelines are unclear"**
   → Unclear guidelines = escalate to PM

❌ **"I don't need templates, I'll write freeform"**
   → Templates ensure consistency and completeness

❌ **"This guideline doesn't apply to me"**
   → All guidelines apply unless role-specific section says otherwise

---

## Success Indicators

**Guidelines are working when:**
- Agent actions are consistent across sessions
- Handoffs occur without information loss
- Quality verdicts are predictable and fair
- Escalations include clear rationale
- LogBook entries follow standard format
- No "silent" decisions or improvised protocols

**Guidelines need revision when:**
- Same mistakes repeated across multiple tasks
- Frequent escalations due to ambiguity
- Agent conflict rate increasing
- Quality metrics degrading despite adherence

---

## Support & Questions

**If guidelines are:**
- **Unclear:** Escalate to PM with specific question
- **Conflicting:** PM applies conflict resolution priority order
- **Silent on a topic:** Escalate to PM (do not improvise)
- **Outdated:** PM updates following update policy

**Contact:** PM coordinates all guideline updates and interpretations

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-12-17 | PM | Initial document creation |

---

**End of Guidelines README**
