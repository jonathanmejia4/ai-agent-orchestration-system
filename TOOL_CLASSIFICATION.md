# Tool Classification

> Generated during Phase 3 of framework fix. Every tool in `tools/` classified by usefulness.

## Classification Legend

- **CORE** — Load-bearing tool referenced by lane agents, commands, or guidelines. Required for framework operation.
- **UTILITY** — Useful standalone CLI tool for end users (security scanners, quality checkers, etc.). Documented in `TOOLS_CATALOG.md`.
- **ADMIN** — For framework maintainers (meta tools, migration scripts, inventory generators).
- **DEAD** — Broken, stub, or one-shot migration that already ran. Removed in Phase 3.7.
- **DUPLICATE** — Overlaps substantially with another tool. Consolidated in Phase 3.6.

---


| Tool | Classification | Purpose | Wire-in / Duplicate-of |
|------|----------------|---------|------------------------|
| ~~a11y_audit.py~~ | REMOVED | Stub implementation — all `_check_rule` calls returned `{"passed": True}`. | Removed in Phase 3.7. Use external tools (axe-core, pa11y). |
| access_control_validator.py | CORE | Validates agent write boundaries, path restrictions, permission hierarchies. | Wire into PM review lane + pre-commit hook for write-boundary enforcement. |
| account_merge_tool.py | UTILITY | Customer support tool to merge duplicate accounts (guest→registered). | Not framework-related; product-specific utility. Document in TOOLS_CATALOG.md as customer-service utility. |
| add_fix_checklist.py | CORE | Converts prose fix requirements into executable bash-step checklists for issue fixers. | Wire into issue-fixers lanes (IF-*) to auto-generate runnable checklists. |
| add_frontmatter.py | CORE | Adds machine-readable YAML frontmatter to issue files for agent parsing. | Wire into issue-hunter lanes as prep step before verification. |
| add_issue_to_catalog.py | CORE | Adds issue entries to Open Issues section of ISSUE_CATALOG.md; used by hunters. | Wire into IH-* lanes as post-issue-creation step. |
| add_issue.py | CORE | Creates new issue file with proper formatting/numbering per lane. | Wire into issue-hunter lanes as canonical issue creation tool. |
| add_pattern_vars.py | CORE | Adds explicit pattern_vars to issue frontmatter for verification. | Wire into issue-hunter/issue-fix pipeline before verification. |
| add_permission_handling_to_lanes.py | ADMIN | Inserts Permission Handling section into IF-Lane-*.md agent specs (one-time migration). | Admin migration script; keep but mark as admin. |
| add_resolution_template.py | CORE | Adds standardized resolution evidence sections to issues. | Wire into IF-* lanes to ensure consistent resolution format. |
| add_verification_commands.py | CORE | Adds copy-paste ready bash verification commands to issue files. | Wire into issue-hunter lanes as standard step after issue creation. |
| agent_health_monitor.py | CORE | Monitors agent health; detects stalled/crashed agents; integrates heartbeat daemon. | Wire into PM monitoring lane / recurring health-check command. |
| agent_session_state.py | CORE | Manages agent session state persistence and recovery across sessions. | Wire into agent framework (agents call save/load on session boundaries). |
| ai-adapter.py | UTILITY | Task-based text processing (summarize, polish, diff-simplify) via prompt templates. | Standalone CLI utility; document in TOOLS_CATALOG.md. |
| alert_manager.py | CORE | Alert management with multi-channel notifications and deduplication. | Wire into monitoring stack; hook up to PM escalation events. |
| alt_branch_stats.py | UTILITY | Counts alternative branch statuses (success/failure/pending) across LogBook. | Small focused utility; document in TOOLS_CATALOG.md. |
| analyze_verification_failures.py | CORE | Categorizes verification failures by type (malformed_cmd, missing file, etc). | Wire into verify-catalog / PM review to surface systemic failure patterns. |
| api_docs_validator.py | CORE | Enforces CONVENTIONS.md:185 — every public API endpoint needs docs/api/<v>/<resource>.md. | Wire into pre-commit / CI quality gates. |
| approve_action.py | CORE | Approves critical actions (delete, modify_tier1, force_push) during validation hooks. | Wire into critical-action-validator hook (already referenced). |
| approve_preview.py | CORE | Approves/rejects Stage -1 spec-to-diff previews for tasks. | Wire into Builder workflow (Stage -1 preview gate). |
| ast_merge_engine.py | CORE | Semantic AST three-way merge for Python/JS/TS/JSON. | Wire into THREE_WAY_MERGE_REGENERATION_POLICY flow for template regen. |
| audit_trail_validator.py | CORE | Validates audit trails for traceability/completeness/integrity across components. | Wire into compliance reporting + PM weekly review. |
| audit.py | CORE | Sphinx documentation quality gates (linkcheck, doctest, metrics vs thresholds). | Wire into docs CI pipeline. |
| auto_resolution.py | CORE | 3-way merge conflict auto-resolver with strategies (keep_local, smart_merge, etc). | Wire into template regeneration / merge policy enforcement. |
| auto_resolve.py | CORE | Detects issues actually fixed but not marked RESOLVED by running verification commands. | Wire into IF-* lanes post-fix to auto-flip status when verified. |
| batch_verify.py | CORE | Runs verification across multiple issues in parallel; produces summary reports. | Wire into verify-catalog command and PM batch reviews. |
| bias_detector.py | CORE | Detects Critic agent bias/severity-drift/rubber-stamping in verdict history. | Wire into Critic self-validation decorator (already referenced by critic_self_validation.py). |
| breaking_change_frequency.py | UTILITY | Analyzes git history for breaking-change frequency per file. | Change-management analytics utility; document in TOOLS_CATALOG.md. |
| build_embeddings.py | CORE | Generates vector embeddings for codebase semantic search. | Wire into search infrastructure (currently scaffolded, needs provider wiring). |
| canonicalize.py | CORE | Canonicalization helpers (sorted keys, stable YAML) for idempotent generation. | Wire into any generator tool per IDEMPOTENT_GENERATION_POLICY. |
| card_expiry_notifier.py | UTILITY | Customer-service tool for proactive card-expiry notifications. | Product utility unrelated to SAF framework. Document in TOOLS_CATALOG.md. |
| causal_mapper.py | CORE | Maps input parameters to output files for spec-to-diff traceability. | Wire into Stage -1 preview generation (SPEC_TO_DIFF_PREVIEWS_POLICY). |
| change_impact_analyzer.py | CORE | Analyzes cross-component impact of proposed changes; assesses risk. | Wire into PM change-review + Builder pre-commit workflow. |
| check_agent_compatibility.py | CORE | SemVer compatibility validation between agent versions. | Wire into work-order validation and coordination protocol. |
| check_canonicalization.py | CORE | CI check: ensures generators use stable ordering (sorted keys, OrderedDict). | Wire into pre-commit hooks per IDEMPOTENT_GENERATION_POLICY. |
| check_cross_references.py | CORE | Validates that file references in docs point to existing files; detects ghost refs. | Wire into IH-* lanes and docs CI. |
| check_dependencies.py | UTILITY | Project dependency checker (outdated, security, conflicts). | Standard devops utility; document in TOOLS_CATALOG.md. |
| check_traceability.py | CORE | Validates generated files contain required provenance headers (template, version). | Wire into TEMPLATE_COMPLIANCE_POLICY gate. |
| checkpoint_runner.py | CORE | Runs two-phase (structural+behavioral) checkpoint tests and logs results. | Wire into Builder lane as gate between structural/behavioral stages. |
| circular_dep_detector.py | CORE | Detects circular dependencies in wiring.yaml task dep graphs. | Wire into CI (prevents merging tasks with cycles). |
| code_quality_analyzer.py | CORE | Cyclomatic complexity, duplication, doc coverage, naming, coupling. | Wire into CI + PM review; or merge with convention_checker.py. |
| collect_evidence.py | CORE | Collects verification evidence via embedded commands; compares to Expected Outputs YAML. | Wire into issue-fixer verification phase. |
| compliance_reporter.py | CORE | Compliance reports tracking policy adherence; identifies violations. | Wire into PM monthly/weekly governance review cadence. |
| comprehensive_verify.py | CORE | Scans all RESOLVED issues, checks affected_paths exist, categorizes failures. | Wire into verify-catalog / PM audit workflow; overlaps somewhat with batch_verify.py. |
| compute_dependencies.py | CORE | Computes inter-issue dependencies via path overlap and references. | Wire into issue-fix orchestrator for correct ordering. |
| conflict_resolver.py | CORE | Detects/resolves work-order, file, state, policy conflicts. | Wire into PM coordination protocol. |
| convention_checker.py | CORE | Validates code against conventions.yaml (SAF conventions). | Wire into pre-commit hooks + CI. |
| coverage_reporter.py | UTILITY | Test coverage reporting with thresholds. | Standard dev utility; document in TOOLS_CATALOG.md. |
| critic_self_validation.py | CORE | `enforce_self_validation` decorator + exception classes for Critic verdicts. | Wire as decorator into Critic verdict functions (already referenced by spec). |
| critical_path_analyzer.py | CORE | DAG critical path + bottleneck analysis for task graphs. | Wire into dag_builder.py output pipeline. |
| ~~cross_reference_validator.py~~ | REMOVED | Duplicate of check_cross_references.py. | Removed in Phase 3.6. Use `check_cross_references.py`. |
| dag_builder.py | CORE | Constructs DAG from task plan YAML; validates acyclicity; topological sort. | Wire into task-plan workflow per DEPENDENCY_GRAPH_POLICY. |
| dag_validator.py | CORE | 7 mechanical checks on DAG (acyclic, connected, orphans, duplicates, etc). | Wire alongside dag_builder.py into task-plan CI. |
| dependency_analyzer.py | CORE | General codebase dependency graph builder (modules/tasks/templates/tools). | Wire into change-impact analysis workflow; overlaps with dependency_graph_generator.py. |
| ~~dependency_graph_generator.py~~ | REMOVED | Duplicate of dependency_analyzer.py. | Removed in Phase 3.6. Use `dependency_analyzer.py`. |
| dependency-boundary-checker.py | CORE | SEC-032 Anti-Corruption Layer enforcement (vendor SDK isolation). | Wire into pre-commit hooks for security enforcement. |
| deprecated_template_scanner.py | CORE | Scans repo for deprecated template usage with early warnings. | Wire into CI per TEMPLATE_VERSIONING_AND_DEPRECATION_POLICY. |
| ~~deprecated_template_usage.py~~ | REMOVED | Duplicate of deprecated_template_scanner.py. | Removed in Phase 3.6. Use `deprecated_template_scanner.py`. |
| detect_missing_manifests.py | CORE | Detects missing package/module manifest files. | Wire into build validation / pre-commit. |
| detect_vendor_type_leakage.py | CORE | Detects vendor-specific types leaking into public APIs (SEC validation). | Wire into pre-commit + Critic review (complements dependency-boundary-checker). |
| doc_coverage.py | CORE | Documentation coverage analysis (docstrings on modules/classes/functions). | Wire into CI alongside coverage_reporter.py. |
| embedded_test_data_checker.py | CORE | Enforces CONVENTIONS.md:509 — no large embedded data in test files. | Wire into pre-commit hooks. |
| enforce_write_boundaries.py | CORE | Enforces PM-only write paths per PM_Operating_Manual.md. | Wire into pre-commit hook (already referenced); overlaps conceptually with access_control_validator. |
| env_config_validator.py | CORE | Validates .env files against templates; detects weak/exposed secrets. | Wire into deployment pipeline + pre-commit. |
| ~~eod_summary.py~~ | REMOVED | Personal habits tool unrelated to the framework. | Removed in Phase 3.7 along with `eod.sh`. |
| escalation_handler.py | CORE | Routes agent escalations, tracks resolution, maintains logs. | Wire into agent-coordination-protocol escalation flow. |
| escape_hatch_validator.py | CORE | Enforces GENERATION_ESCAPE_HATCH_POLICY — manual/patched tasks must log to LogBook/exceptions/generation/. | Wire into CI + PM audit. |
| extension_point_validator.py | CORE | Validates templates properly define/use extension points (hooks, slots, overrides). | Wire into template CI per TEMPLATE_FAMILIES policy. |
| failure_mode_detector.py | CORE | Detects system failure modes with recovery-strategy mapping (FMD-xxx IDs). | Wire into agent_health_monitor or run as recurring PM check. |
| family_validator.py | CORE | Validates template family membership per TEMPLATE_FAMILIES_POLICY. | Wire into template CI. |
| file_integrity_checker.py | CORE | SHA256 checksum baseline/verify for critical files. | Wire into PM integrity-validation lane. |
| final_verify.py | UTILITY | Filters invalid paths (commands, wildcards) during final verification. | Likely one-off helper; document in TOOLS_CATALOG.md. Overlaps with comprehensive_verify.py. |
| find_cycles.py | CORE | Detects/reports all cycles in DAG (dep graph). | Wire into task-plan CI; overlaps with circular_dep_detector.py (both detect cycles in dep graphs). |
| fix_frontmatter.py | CORE | Fixes malformed YAML frontmatter in issue files (cleans affected_paths). | Wire into issue-hunter repair lane. |
| fix_issue_frontmatter.py | CORE | Fixes missing pattern_vars/affected_paths in issue files, filters garbage paths. | Wire into issue-hunter repair lane (complements fix_frontmatter.py — different bugs). |
| fix_pattern_vars.py | CORE | Fixes malformed pattern_vars (BUG-VER-001/002/003 specific bugs). | Wire into issue repair pipeline; complements fix_issue_frontmatter.py. |
| fix_verification_commands.py | CORE | Fixes 7 classes of malformed verification commands (test -f on dirs, wildcards, etc). | Wire into issue-hunter repair lane. |
| fixture_suffix_checker.py | CORE | Enforces CONVENTIONS.md:496 — fixtures must use `_fixture` suffix. | Wire into pre-commit hooks. |
| fixture_validator.py | CORE | Validates test fixtures for correctness/consistency (yaml/json/python). | Wire into CI test-quality gate. |
| fraud_appeal_processor.py | UTILITY | Customer-service AI-assisted fraud appeal review/auto-unblock. | Product utility unrelated to SAF framework. Document in TOOLS_CATALOG.md. |


| Tool | Classification | Purpose | Wire-in / Duplicate-of |
|------|----------------|---------|------------------------|
| gate_validator.py | CORE | Validates quality gates (pre/during/post implementation) for agent workflows against gate_validation_schema.yaml. | Wire into Builder/Critic gate checks and pre-merge CI. |
| generate_architecture_catalog.py | CORE | Generates repo folder-structure catalog (ARCHITECTURE_CATALOG.md + current_structure.yaml). | Wire into verify-catalog command and PM catalog management. |
| generate_daily_digest.py | UTILITY | Summarizes commits/issues/metrics/deployments into a daily digest report. | Standalone daily CLI; optionally wire into a schedule. |
| generate_dependency_catalog.py | CORE | Generates dual-format dependency catalog (markdown + YAML) with broken-dep detection and impact zones. | Wire into verify-catalog and dep audits; pairs with dependency_analyzer. |
| generate_doc_appendix.py | UTILITY | Emits per-file appendix pages + manifest for the docs site. | Standalone docs-build CLI. |
| generate_expected_outputs.py | CORE | Generates machine-comparable expected-output specs for verification commands in issue files. | Wire into issue-hunter/issue-fixer lanes and verification command generation. |
| generate_preview.py | CORE | Generates spec-to-diff preview for a task before code gen (Stage -1 Preview gate). | Wire into Builder pre-generation gate / SPEC_TO_DIFF policy. |
| generate_report.py | CORE | Generates comprehensive status reports on catalog/progress/agent readiness (console + JSON + markdown). | Wire into PM review cadence and verify-catalog. |
| generate_security_tests.py | UTILITY | Generates security test files from Jinja2 templates per task_id. | Standalone Builder test-scaffold CLI. |
| generate.py | CORE | Master task-template generator used by idempotence workflow to produce task outputs. | Wire into idempotence CI and Builder task generation. |
| get_base_version.py | CORE | Retrieves BASE (originally generated) file version for three-way merge. | Wire into merge_engine / regeneration workflow. |
| graduation_tracker.py | CORE | Detects reused protected regions (3+ uses) that should graduate to real templates. | Wire into PROTECTED_REGIONS_POLICY CI check. |
| health_monitor.py | CORE | Real-time health checks, status dashboards, and alerting for system components. | Wire into operational dashboard / lane-health command. |
| heartbeat_daemon.py | CORE | Background daemon for agent liveness signaling (start/stop/status/check). | Wire into agent runtime supervision. |
| idempotence_checker.py | CORE | Fast Builder-side generate-twice byte-compare for idempotence. | Wire into Builder pre-commit gate. |
| idempotence_validator.py | CORE | Full 6-check idempotence validation for Critic/PM gates. | Wire into Critic pre-approval + PM promotion gates. |
| insert_permission_step.py | ADMIN | One-shot migration that injects "Step 2c½ Permission Check" into all lane fixer specs. | Framework maintenance only; candidate for removal after migration complete. |
| integration_test_runner.py | CORE | Runs and reports integration tests across agent workflows / suites. | Wire into CI integration-test stage. |
| issue_stats.py | CORE | Counts issues per lane, tracks resolved/unresolved, updates catalog header. | Wire into issue-hunter/issue-fixer orchestrators and catalog watcher. |
| issue_tracker.py | CORE | Queries and analyzes ISSUE_CATALOG.md by lane/status/severity/tag. | Wire into issue-hunter/fix-all lanes (SSOT_WIRING_POLICY consumer). |
| lisp_syntax_checker.py | UTILITY | Validates Lisp/S-expression syntax in DSL config files. | Standalone CLI; only wire if Lisp DSL is actively used. |
| log_aggregator.py | CORE | Aggregates/normalizes logs from LogBook, builds, tests, CI with pattern detection. | Wire into PM daily log review and observability. |
| logbook_access_checker.py | CORE | Enforces LogBook single-writer ACL (K002) per agent directory. | Wire into pre-commit hook and agent write paths. |
| logbook_archive.py | CORE | Archives old LogBook entries (K005) per retention policy. | Wire into monthly retention cron. |
| logbook_auto_append.py | CORE | Safe, atomic append of entries to LogBook YAML files with validation + backup. | Wire into agent LogBook append paths (universal). |
| logbook_compliance_report.py | CORE | Generates audit reports from LogBook for compliance reviews (K010). | Wire into monthly governance review. |
| logbook_immutability.py | CORE | Enforces LogBook immutability (K004) via chmod 444 and drift detection. | Wire into post-write hook and CI audit. |
| logbook_query.py | CORE | Structured query interface for LogBook entries (K006) by agent/action/time/task. | Wire into PM + agent LogBook consumption paths. |
| logbook_update.py | UTILITY | Automates LogBook entry creation/updates for task/preview/agent logs. | Standalone CLI; overlaps with logbook_auto_append. |
| logbook_validator.py | CORE | Validates LogBook YAML entries against JSON Schema. | Wire into pre-commit hook and CI gate. |
| markdown_link_checker.py | CORE | Validates internal + external markdown links across docs. | Wire into docs CI and pre-commit hook. |
| merge_engine.py | CORE | Three-way merge algorithm for regeneration workflow (BASE+LOCAL+NEW). | Wire into regeneration pipeline (THREE_WAY_MERGE policy). |
| merge_preview.py | CORE | Simulates three-way merge and shows conflict preview before executing. | Wire into PM pre-merge review step; pairs with merge_engine. |
| metric_aggregator.py | CORE | Aggregates cross-component metrics and tracks performance over time. | Wire into operational reporting. Canonical metrics tool (subsumed former metrics_collector). |
| ~~metrics_collector.py~~ | REMOVED | Duplicate of metric_aggregator.py. | Removed in Phase 3.6. Use `metric_aggregator.py`. |
| monetization_health_check.py | CORE | Daily health check for monetization/licensing flows with Slack/PagerDuty alerts. | Wire into cron + alerting. |



| Tool | Classification | Purpose | Wire-in / Duplicate-of |
|------|----------------|---------|------------------------|
| naming_pattern_checker.py | UTILITY | Enforces CONVENTIONS.md naming patterns (PascalCase/snake_case/UPPER_SNAKE) via AST | Wire into pre-commit/CI lint stage |
| notification_dispatcher.py | CORE | Multi-channel notification dispatcher (email/Slack/Teams/webhook) for system events | Wire into orchestrator event hooks and PM escalation paths |
| orchestrator.py | CORE | Core multi-agent coordination system (PM+Builder+Planner+7 critics) via Anthropic API | Already central; verify import graph coverage |
| orchestrator_dashboard.py | ADMIN | Visual/live dashboard for orchestrator status (reads STATE.yaml + heartbeat) | Wire into operator CLI/monitoring |
| orchestrator_permission_handler.py | CORE | Polls permission request files and drives user-interaction approval flow | Wire into orchestrator loop + permission_request.py |
| orchestrator_recovery.py | CORE | Checkpoint/crash-recovery/backoff/health-monitor module for orchestrator | Wire into orchestrator.py startup/shutdown |
| orchestrator_safety.py | CORE | Forbidden-pattern detection, write boundaries, output validation, safety audit | Wire into orchestrator output pipeline (pre-write gate) |
| parallel_work_estimator.py | UTILITY | DAG parallel vs sequential time estimator + Builder fan-out recommender | Wire into Planner when graph.yaml produced |
| password_breach_check.py | UTILITY | HaveIBeenPwned k-anonymity password breach check for registration/password-change | Wire into auth pipeline (registration + password change) |
| performance_profiler.py | ADMIN | Profiles tool execution times, workflow bottlenecks, agent metrics | Wire into ops/monitoring CLI |
| permission_guardrails.py | CORE | Classifies operations as SAFE/CONDITIONAL/UNSAFE with tier+decision logic | Wire into permission_request.py + orchestrator_permission_handler.py |
| permission_request.py | CORE | Helper library for agents to create permission requests and wait for approval | Wire into all fixer/builder agents needing approval |
| pii_scanner.py | UTILITY | Detects PII (email/phone/SSN/CC/name/address) in files/logs/DB | Wire into LogBook support-conversation scanner + CI |
| plugin_compatibility_checker.py | UTILITY | Validates plugin manifests against interface contracts and version requirements | Wire into Stage-2 gate and plugin install flow |
| plugin_validator.py | UTILITY | Validates plugin structure/entry-points/exports for correctness | Wire into plugin registration alongside plugin_compatibility_checker.py |
| pm_monitor.sh | CORE | Bash poller watching brick status.yaml → invokes critic_orchestrator.py on READY | Wire as systemd/cron or long-running process next to PM |
| pm_promote.py | CORE | Promotes approved template-upgrade tasks after Critic verification | Wire into PM post-approval workflow |
| policy_enforcement_engine.py | CORE | Real-time policy compliance checker; validates actions before execution | Wire into orchestrator pre-action gate + all fixer agents |
| policy_version_checker.py | UTILITY | Validates policy documents are current/properly versioned; flags outdated | Wire into weekly governance review / CI |
| policy_version_control.py | UTILITY | Tracks policy versions, detects unauthorized changes via git history | Wire into pre-commit hook and governance audit job |
| pre_implementation_gate.py | CORE | Validates pre-implementation gates per builder-scope-enforcement (WO+task+reqs+deps) | Wire into Builder start-of-task flow |
| preview_approver.py | CORE | PM-facing approval gate for diff previews before Builder writes files | Wire into preview_generator.py → PM approval loop |
| preview_generator.py | CORE | Generates unified diffs from task plan (dry-run) for PM approval | Wire into Builder pre-write workflow |
| progress_dashboard.py | ADMIN | Real-time PM monitoring dashboard for task/agent/system health | Wire into operator CLI |
| progress_reporter.py | UTILITY | Generates progress reports/dashboards for tasks/action plans (has dup TaskProgress class - minor bug) | Wire into PM daily report; fix dup dataclass when touched |
| promotion_gate.py | CORE | Validates promotion gates (tests/coverage/security/approval) before deploy | Wire into CI/CD promotion stage |
| protected_paths_checker.py | CORE | Enforces PM-exclusive path restrictions and agent path boundaries | Wire into pre-commit hook and orchestrator write-validation |
| protected_regions_validator.py | UTILITY | Validates protected regions are properly defined/intact/hash-matched | Overlaps with protected_regions.py (validate subcmd) — consolidate |
| protected_regions.py | CORE | Unified protected-region tool: extract/validate/reinsert/hash/check-limits/full-check | Canonical tool; consolidates region_* family |
| qa_metrics_collector.py | ADMIN | Collects/aggregates QA metrics (tests/coverage/defects) across SAF | Wire into weekly QA dashboard |
| reconstruct_pm_state.py | CORE | Rebuilds PM STATE.md from LogBook+git+tasks for amnesia recovery | Wire into PM recovery runbook (agent-coordination-protocol) |
| recovery_orchestrator.py | CORE | Orchestrates checkpoint/rollback/restore recovery procedures for SAF failures | Wire into failure-handling protocol |
| regenerate_verification_commands.py | UTILITY | Regenerates embedded verification command blocks in issue files from frontmatter | Run on-demand when pattern_vars change; could be one-shot |
| ~~region_extractor.py~~ | REMOVED | Duplicate of `protected_regions.py extract`. | Removed in Phase 3.6. Use `protected_regions.py extract`. |
| ~~region_hash.py~~ | REMOVED | Duplicate of `protected_regions.py hash`. | Removed in Phase 3.6. Use `protected_regions.py hash`. |
| region_interface_checker.py | UTILITY | Validates region interface contracts (function/class/variable/import signatures) | Distinct from protected_regions.py; wire into Stage-2 gate |
| ~~region_reinserter.py~~ | REMOVED | Duplicate of `protected_regions.py reinsert`. | Removed in Phase 3.6. Use `protected_regions.py reinsert`. |
| region_reuse_detector.py | UTILITY | Detects duplicate/similar protected regions across templates for consolidation | Wire into template-optimization audit; distinct from protected_regions.py |
| ~~region_validator.py~~ | REMOVED | Duplicate of `protected_regions.py validate` / `protected_regions_validator.py`. | Removed in Phase 3.6. |
| ~~remove_proactive_steps.py~~ | REMOVED | One-shot migration that already ran. | Removed in Phase 3.7. |
| restructure_catalog.py | UTILITY | Extracts issues from monolithic ISSUE_CATALOG.md into per-lane files | One-shot catalog migration; keep for re-runs on catalog regrowth |
| retired_template_checker.py | CORE | CI blocker scanning wiring.yaml for retired template usage | Wire into CI pre-merge gate |
| retry.sh | UTILITY | Bash wrapper with exponential backoff for transient-failure retries | Wire into git/API-call sites per agent-coordination-protocol:461 |
| run_integration_tests.py | CORE | Discovers and runs integration tests per task-id with multi-format reports | Wire into CI + Builder post-implementation verification |


| Tool | Classification | Purpose | Wire-in / Duplicate-of |
|------|----------------|---------|------------------------|
| safe_tool_tester.py | UTILITY | Functionally tests tools at varying safety levels (SAFE/DRY_RUN/SANDBOXED) via tool_safety_config.yaml | Dev/CI tool-testing harness |
| scan_timestamps.py | CORE | Detects forbidden timestamp patterns breaking idempotence in generated code | Wire into pre-commit + CI idempotence gate |
| schema_validator.py | CORE | Validates schema completeness, correspondence, coverage per Schema-Driven Module Generation Policy | Wire into generation pipeline / stage gates |
| security_scanner.py | CORE | Scans codebase for hardcoded secrets, SQL/command injection, insecure configs | Wire into CI security gate |
| smart_verify.py | UTILITY | Identifies primary fix target for RESOLVED issues from affected_paths metadata | Support for verify_issue workflows |
| smoke_test.py | CORE | Runs quick post-deployment smoke tests on critical paths | Wire into post-deploy CI/CD gate |
| snapshot_manager.py | ADMIN | Creates/restores full-system, task, or LogBook state snapshots | Admin / point-in-time recovery |
| spec_compliance_checker.py | CORE | Validates task implementation matches declared templates (Dimension 6 SpecFit) | Referenced in .github/workflows/saf-gates.yml:374-375 |
| stage_gate_enforcer.py | CORE | Enforces stage gates by blocking operations that don't meet requirements | Wire into workflow stage transitions |
| stage_promotion.py | CORE | Promotes tasks through Stage0-Stage4-Golden with auto LogBook entries | Wire into Builder stage workflow |
| state_manager.py | CORE | Atomic state file persistence with backups/checksums per state-persistence-protocol.md | Wire into agent state workflows |
| sync_catalog_stats.py | UTILITY | Scans issue files and updates ISSUE_CATALOG.md statistics | Pre-commit / maintenance task |
| sync_tools_catalog.py | UTILITY | Scans all executable items and updates TOOLS_CATALOG.md | Maintenance task |
| system_health_check.py | UTILITY | Comprehensive system health check for SAF infrastructure | Ops monitoring tool |
| teams_notifier.py | UTILITY | Sends notifications to Microsoft Teams channels via webhooks | Notification infra |
| template_compatibility_checker.py | CORE | Checks template compatibility constraints before regeneration | Wire into three-way merge regeneration workflow |
| template_compliance_checker.py | CORE | Validates templates for required files/structure/metadata per TEMPLATE_COMPLIANCE_POLICY | Referenced in TEMPLATE_COMPLIANCE_POLICY.md |
| template_diff_analyzer.py | UTILITY | Analyzes template changes to determine semver bump (MAJOR/MINOR/PATCH) | Referenced in TEMPLATE_VERSIONING_AND_DEPRECATION_POLICY.md |
| template_drift_detector.py | CORE | Detects template version drift across tasks vs registry | Wire into regeneration safety gate |
| template_family_validator.py | UTILITY | Validates template family membership + symmetry per README.md:808-809 | Template governance |
| template_lineage.py | UTILITY | Reverse-lookup template origin for generated files | Referenced in TEMPLATE_VERSIONING_AND_DEPRECATION_POLICY.md |
| template_metadata_generator.py | UTILITY | Generates/updates template.yaml metadata files automatically | Referenced in TEMPLATE_VERSIONING_AND_DEPRECATION_POLICY.md |
| template_registry_manager.py | CORE | Manages template registry (registration, validation, versioning, usage tracking) | Template infrastructure |
| template_scanner.py | UTILITY | Scans Jinja2 templates extracting variables/blocks/includes | Template analysis |
| template_upgrade_assistant.py | CORE | Interactive template upgrade wizard analyzing breaking changes | Referenced in TEMPLATE_VERSIONING_AND_DEPRECATION_POLICY.md:584 |
| template_upgrade_candidates.py | UTILITY | Identifies tasks using outdated template versions | Template maintenance |
| ~~template_upgrade_planner.py~~ | REMOVED | Back-compat wrapper around template_upgrade_assistant.py. | Removed in Phase 3.6. Use `template_upgrade_assistant.py`. |
| template_usage.py | UTILITY | Scans repo for template usage across tasks; reports version distribution | Capacity planning |
| template_version_checker.py | CORE | Validates template versions for compatibility + deprecation (stage gate validator) | Wire into integration/config/stage-gates.yaml |
| test_coverage_checker.py | CORE | Validates test coverage (Dimension 7 Verification) | Referenced in .github/workflows/saf-gates.yml:380-381 |
| test_mirror_checker.py | CORE | Enforces CONVENTIONS.md:166 — src/*/module.py requires tests/*/test_module.py | Wire into pre-commit / CI |
| test_runner.py | CORE | Unified test runner with reporting/coverage | Wire into CI pipeline |
| three_way_merge.py | CORE | Line-based three-way merge (BASE+LOCAL+NEW) for regeneration | Referenced in THREE_WAY_MERGE_REGENERATION_POLICY.md:1190 |
| time_box_monitor.py | CORE | Tracks/enforces work order time limits; triggers escalations | Referenced in .claude/agents/Builder.md:434-466 |
| topological_sort.py | CORE | DAG topological ordering + critical path via Kahn's algorithm | Referenced in DEPENDENCY_GRAPH_AND_TOPOLOGICAL_BUILD_ORDER_POLICY.md |
| traceability_checker.py | CORE | Enforces traceability by construction (headers, manifests, specs, lineage) | Wire into CI traceability gate |
| traceability_mapper.py | UTILITY | Maps traceability relationships across SAF artifacts (WO→Tasks→Files) | Analysis tool |
| update_base_version.py | CORE | Stores BASE versions for future three-way merge operations | Referenced in THREE_WAY_MERGE_REGENERATION_POLICY.md:445-470 |
| update_dashboard.py | UTILITY | Generates LogBook/verification/DASHBOARD.md | Dashboard maintenance |
| update_future_index.py | UTILITY | Updates PLANNING/future/INDEX.md with current directory contents | Doc maintenance |
| update_spec_section_9.py | UTILITY | Syncs dependency graph into wiring.yaml Section 9 | Referenced in DEPENDENCY_GRAPH_AND_TOPOLOGICAL_BUILD_ORDER_POLICY.md |
| ~~update_step_references.py~~ | REMOVED | One-off migration that already ran. | Removed in Phase 3.7. |
| ux_click_audit.py | UTILITY | Quarterly UX audit — verifies actions reachable in ≤3 clicks | Referenced in customer-service-standards.md Section 16.7 |
| validate_action_plan.py | CORE | Validates action plan files against action_plan_schema.yaml | Wire into Planner gate |
| validate_ci_references.py | CORE | Validates workflow refs in PLANNING docs match .github/workflows/ | Referenced in CI_WORKFLOW_TRIGGER_PROTOCOL.md |
| validate_composition.py | CORE | Validates variant combinations against composition rules | Referenced in TEMPLATE_VARIANTS_AND_PARAMETER_PACKS_POLICY.md Task 4 |
| validate_conflict_declaration.py | CORE | Validates Critic conflict declarations per critic-self-validation.md:610-661 | Wire into Critic verdict workflow |
| validate_crossrefs.py | CORE | Validates issue cross-references (depends_on/blocks/related, no cycles) | Wire into pre-commit |
| validate_environment.py | UTILITY | Validates dev env (Python version, packages, dirs, hooks) | Setup/diagnostic tool |
| validate_equivalence_contracts.py | CORE | Validates templates have equivalence contracts for drift detection | Referenced in TEMPLATE_DRIFT_DETECTION_POLICY.md |
| validate_escalation.py | CORE | Validates escalation event files against escalation_event_schema.yaml | Wire into escalation workflow |
| validate_integration_test.py | CORE | Validates integration test defs against integration_test_schema.yaml | Wire into CI |
| validate_issue_frontmatter.py | CORE | Pre-commit validator for issue frontmatter pattern_vars (catches BUG-VER-001/002/003) | Wire into pre-commit |
| validate_logbook.py | CORE | Validates LogBook YAML files for schema compliance/integrity | Referenced in FAILURE_MODES.md:344,761 |
| validate_monitoring.py | CORE | Validates monitoring event files against monitoring_event_schema.yaml | Wire into observability workflow |
| validate_planner_output.py | CORE | Validates planner output files against planner_output_schema.yaml | Wire into Planner gate |
| validate_pm_state.py | CORE | Validates LogBook/pm/STATE.md against pm_state_schema.yaml (prevents PM amnesia) | Referenced in agent-coordination-protocol.md:1471 |
| validate_review_verdict.py | CORE | Validates critic verdicts against critic_verdict_schema.yaml | Referenced in critic_verdict_schema.yaml:392 |
| validate_rollback.py | CORE | Validates rollback event files against rollback_event_schema.yaml | Wire into rollback workflow |
| validate_state.py | CORE | Validates agent STATE.md / state YAML for schema compliance | Referenced in integration-test.yml:367 |
| validate_status.py | CORE | Validates LogBook status.yaml against state machine transitions | Referenced in STATE_TRANSITION_VALIDATION.md |
| validate_task_spec.py | CORE | Validates task specs against task_spec_schema.yaml | Referenced in PLANNING/specs/tasks/README.md:60 |
| validate_template_metadata.py | CORE | Validates template metadata files for completeness | Wire into template gate |
| ~~validate_verdict.py~~ | REMOVED | Older variant of validate_review_verdict.py. | Removed in Phase 3.6. Use `validate_review_verdict.py`. |
| validate_verification_commands.py | CORE | Pre-save validator catching malformed verification commands in issue files | Wire into pre-commit |
| validate_wo_queue.py | CORE | Validates work order queue YAML for schema compliance / ordering / duplicates | Referenced in integration-test.yml:367 |
| validate_work_order.py | CORE | Validates work orders against work_order_schema.yaml | Referenced in Builder.md:61,78 |
| validate_write_boundaries.py | CORE | Validates agent write operations comply with defined boundaries | Referenced in pm-write-boundaries.md |
| variant_symmetry_checker.py | UTILITY | Verifies Code/Test families have symmetric variants (thin wrapper over template_family_validator) | Partial overlap with template_family_validator.py |
| variant_validator.py | CORE | Validates template variants for consistency + compatibility (stage gate) | Wire into stage-gates.yaml |
| verify_all_resolved.py | UTILITY | Bulk verifies all RESOLVED issues using Level 3 verification with checkpointing | Verification workflow |
| verify_all_tools.py | UTILITY | Verifies all catalog tools are working; checks required tools exist | Ops/CI tool-health check |
| verify_dashboard.py | UTILITY | Verifies dashboard generation works + stats match issue_stats.py | Dashboard ops |
| verify_execution_order.py | CORE | Verifies tasks were executed in topological dependency order via logbook timestamps | Referenced in DEPENDENCY_GRAPH_AND_TOPOLOGICAL_BUILD_ORDER_POLICY.md:1362 |
| verify_frontmatter.py | CORE | Verifies YAML frontmatter present/valid in all issue files | Wire into pre-commit |
| verify_issue.py | CORE | Main issue verification tool — reads frontmatter, runs pattern checks, updates status | Core verification workflow |
| verify_optimization.py | UTILITY | Verifies Phase 1 optimizations applied (Verification Commands, Expected Outputs, Dependencies) | One-time phase audit |
| verify_patterns.py | UTILITY | Verifies verification_patterns.yaml is valid and complete | Pattern library health check |
| verify_phase2.py | UTILITY | Verifies Phase 2 optimizations applied (Fix Checklists, Pattern Vars) | One-time phase audit |
| verify_phase3.py | UTILITY | Verifies Phase 3 optimizations applied (batch verif, resolution templates, etc.) | One-time phase audit |
| verify_security_test_coverage.py | CORE | Verifies security-sensitive code has corresponding security tests | Wire into security CI gate |
| verify_stats.py | CORE | Validates issue stats consistency (Resolved+Open=Total, severity counts) | Wire into pre-commit |
| version_compatibility_checker.py | CORE | Checks version compatibility across SAF components (tasks/templates/schemas/tools) | Wire into integration validation |
| version_pin_checker.py | CORE | Enforces CONVENTIONS.md:793 — CI tools must be pinned to specific versions | Wire into pre-commit / CI |
| wiring_validator.py | CORE | Validates wiring between SAF components (refs/deps/integrations) | Wire into integration gate |
| ~~work_order_validator.py~~ | REMOVED | Duplicate of validate_work_order.py. | Removed in Phase 3.6. Use `validate_work_order.py`. |
| workflow_state_manager.py | CORE | Manages workflow state transitions + validation + history | Wire into workflow orchestration |
| tool_safety_config.yaml | CORE | Classifies tools by safety level for automated testing | Config for safe_tool_tester.py |
| verification_patterns.yaml | CORE | Defines reusable verification patterns referenced in issue frontmatter | Config for verify_issue.py |
| send_notification.sh | UTILITY | Sends notifications to Teams webhook with exponential backoff retry | Referenced in edge-cases-and-recovery.md Section 3 |
| setup_saf.sh | ADMIN | Initializes SAF dev environment (dirs, deps, prerequisites) | Referenced in PLANNING/future/enforcement_roadmap.md:320 |
| test_idempotence.sh | CORE | Tests brick generation idempotence (twice → identical output) | Referenced in TEMPLATE_COMPLIANCE_POLICY.md:174,248 |
| validate_tool.sh | CORE | Pre-flight validator — tool exists + is executable | Referenced in edge-cases-and-recovery.md:309 |
| check_builder_scope.sh | CORE | Pre-commit hook enforcing Builder brick scope compliance | Referenced in builder-scope-enforcement.md:316-318 |
| ~~eod.sh~~ | REMOVED | Collateral removal — wrapped the removed eod_summary.py. | Removed in Phase 3.7. |
| health_check.sh | UTILITY | SAF system health check (LogBook, config, workflows) | Referenced in docs/DEPLOYMENT.md |
| logbook_append.sh | CORE | Atomic append to LogBook JSON/text with retry + file locking | Referenced in agent-coordination-protocol.md:766,804,886 |
| logbook_rollup.sh | ADMIN | Monthly LogBook rollup — aggregates + archives | Referenced in quality-standards.md Section 11.3 |
| pm_monitor.sh | UTILITY | PM polling daemon — detects brick COMPLETE_READY_FOR_REVIEW | PM orchestration |
| retry.sh | UTILITY | Wraps commands with exponential backoff retry logic | Infrastructure utility |
| hooks/check_circular_deps.sh | CORE | Pre-commit hook running circular dep detector on DAG/wiring files | Pre-commit hook |
| hooks/enforce_pm_boundaries.sh | CORE | Prevents PM from committing to implementation dirs | Pre-commit hook |
| hooks/generate_logbook_entries.sh | UTILITY | Auto-generates LogBook entries for significant changes (disabled by default) | Optional pre-commit hook |
| hooks/install_hooks.sh | ADMIN | Installs SAF git hooks (pre-commit/commit-msg/pre-push) | Setup / admin task |
| hooks/pm_boundary_check.sh | CORE | Validates agents respect PM-exclusive write boundaries | Pre-commit hook |
| hooks/validate_naming_conventions.sh | CORE | Enforces file/ID naming patterns on staged files | Pre-commit hook |
| hooks/validate_policy_versions.sh | CORE | Ensures PLANNING/*_POLICY.md files have version headers + changelogs | Pre-commit hook |
| hooks/validate_state.sh | CORE | Validates LogBook/pm/STATE.md against schema (prevents PM amnesia) | Pre-commit hook |
| hooks/validate_yaml_schemas.sh | CORE | Validates staged YAML files against corresponding schemas | Pre-commit hook |

## Summary (post-Phase 3.6/3.7)

Original tool count: 257 (246 .py + 11 .sh)
Removed duplicates: 8 (cross_reference_validator, dependency_graph_generator, deprecated_template_usage, metrics_collector, template_upgrade_planner, validate_verdict, work_order_validator) + 4 region_* tools subsumed by protected_regions.py
Removed dead: 4 (a11y_audit, eod_summary, remove_proactive_steps, update_step_references) + 1 collateral (eod.sh — wrapped the removed eod_summary.py)
Final tool count: 241 (231 .py + 10 .sh, excluding hooks/)

