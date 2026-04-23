# Traceability by Construction Policy

## Summary

Traceability — the ability to answer "where did this artifact come from, and what downstream things does it affect?" — is a property that must be built into the pipeline from the start, not retrofitted. Traceability by construction means every artifact carries enough metadata to walk its history forward and backward without extra tooling, every dependency is recorded at the moment it is introduced, and every change emits a structured record linking inputs to outputs. Retrofit traceability is expensive and incomplete; construction-time traceability is cheap and exhaustive.

## Why This Matters

- Audit, debugging, and incident response all depend on being able to trace an artifact to its origin; missing traces turn an hour's work into a week.
- Compliance regimes increasingly require verifiable traceability; traces produced after the fact are hard to trust.
- Traceability is the input to impact analysis — "if I change this spec, what artifacts need to be regenerated?" — and impact analysis enables safe rapid change.
- A system with construction-time traceability produces its own documentation; the trace links are the authoritative record of what produced what.
- The cost of adding a trace edge at the moment of creation is trivial; the cost of reconstructing the same edge later is high and often impossible.

## Key Rules

- Every generated artifact MUST carry metadata identifying its source (spec, template, commit) — no unmarked generated files.
- Every change MUST emit a structured record linking the change's inputs to its outputs; logs are not a substitute.
- Trace links MUST be machine-readable and stable across renames and moves; human-readable mentions are not enough.
- Trace data MUST be persisted alongside the artifact it describes; detached metadata is lost metadata.
- Any break in a trace chain (missing parent, unknown source) MUST fail the build that produced it, not show up later as a gap.

## Related Tools

- `tools/check_traceability.py` — validates that all artifacts have complete trace metadata.
- `tools/causal_mapper.py` — builds cause-and-effect maps from trace data.
- `tools/change_impact_analyzer.py` — uses traces to compute impact of a proposed change.
- `tools/collect_evidence.py` — gathers trace-derived evidence for audit.

## Status

ACTIVE
