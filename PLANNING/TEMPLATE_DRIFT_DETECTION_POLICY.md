# Template Drift Detection Policy

## Summary

Template drift is the gradual divergence between a template and the artifacts generated from it — driven by ad-hoc edits, schema changes not reflected in the template, or template updates not propagated to consumers. Drift detection runs continuously, identifies exactly where templates and artifacts have diverged, and produces the work items needed to re-converge them. Undetected drift quietly undoes the benefits of templating; detected drift is a tractable engineering backlog.

## Why This Matters

- Drift is silent by nature; no one notices a small divergence until it accumulates into a major incompatibility.
- Detecting drift early turns a year of compounding fixes into a week of targeted remediations.
- Drift reports make template health visible — a template with chronic drift is telling you that its shape no longer matches the problem.
- Downstream consumers can trust generated output only if drift is actively managed.
- Drift data over time identifies templates that should be consolidated, split, or retired.

## Key Rules

- Every generated artifact MUST carry metadata naming the template and template version it was produced from.
- Drift detection MUST run on a cadence short enough that drift is caught while context is still fresh; weekly at minimum, per-build where feasible.
- A drift report MUST name the artifact, the template, and the nature of the divergence (hand edit, schema change, template update).
- Drift above a declared threshold MUST fail the build, not merely warn; warnings accumulate and are ignored.
- Remediation MUST record whether the artifact was regenerated, the template was updated, or an escape hatch was opened — the disposition is itself data.

## Related Tools

- `tools/template_drift_detector.py` — detects drift between templates and artifacts.
- `tools/template_compliance_checker.py` — the strict-mode counterpart that fails on drift.
- `tools/template_diff_analyzer.py` — produces line-level drift reports.

## Status

ACTIVE
