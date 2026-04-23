# Stage-Gated Generation Pipeline Policy

## Summary

Generation proceeds through explicit, ordered stages, and each stage has a gate: a set of checks that must pass before the pipeline advances. Failure at a gate halts the pipeline, reports exactly what failed, and prevents downstream stages from running on inputs that are known to be bad. Stage gating converts "the build crashed somewhere" into "stage four failed this specific check" — and that specificity is what makes generation pipelines diagnosable at scale.

## Why This Matters

- Without gates, failures in an early stage manifest as confusing errors many stages later, far from the actual cause.
- Gates make it cheap to add new validation: a new check joins the gate for the stage where the relevant information exists, instead of being wedged into a late catch-all.
- A failing gate produces a targeted remediation; a failing generic build produces a bug report.
- Stage gates are a natural place to attach incremental caching — if stage three's inputs are unchanged, its output can be reused.
- Clear stages make the pipeline teachable; contributors can reason about what each stage does and where to make changes.

## Key Rules

- Stages MUST be ordered and declared; ad-hoc ordering ("it runs when I run it") produces non-reproducible builds.
- Each stage MUST have explicit entry and exit gates; entry gates guard the stage's assumptions, exit gates guard its outputs.
- A gate failure MUST halt the pipeline and produce a structured report naming the stage, the check, and the offending inputs.
- Stages MUST be idempotent on their inputs; re-running a stage with unchanged inputs produces the same outputs.
- Skipping or bypassing a gate requires an explicit, audited override — it is never the default path.

## Related Tools

- `tools/checkpoint_runner.py` — advances the pipeline one checkpoint at a time, honoring gates.
- `tools/dag_builder.py` — computes the stage graph from declarations.
- `tools/validate_status.py` — reports which stages have passed and which are blocked.

## Status

ACTIVE
