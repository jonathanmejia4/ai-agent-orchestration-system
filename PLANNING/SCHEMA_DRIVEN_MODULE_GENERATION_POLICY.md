# Schema-Driven Module Generation Policy

## Summary

When a module's shape is largely determined by data it operates on, the schema for that data is the natural source of truth — not the module. Rather than hand-maintaining both the schema and the module that consumes it, this policy generates the module from the schema. The schema is authored; the module is a derivative artifact. Changes that would otherwise require coordinated edits across schema, validators, serializers, and client code collapse into one edit to the schema followed by regeneration.

## Why This Matters

- A single source of truth eliminates the drift that otherwise accumulates between schema and consumer over time.
- Generated modules are exactly as current as the schema they were produced from; staleness becomes detectable rather than invisible.
- Hand-written code that duplicates schema structure is expensive to maintain and easy to get subtly wrong.
- When the schema is versioned, every generated artifact inherits a precise provenance: "generated from schema vX.Y.Z at commit C".
- The schema is also more useful as documentation — it is guaranteed to be honest because any drift breaks the build.

## Key Rules

- The schema MUST be the authored artifact; generated modules MUST be marked as generated and MUST NOT be hand-edited.
- Generation MUST be deterministic for a given schema and generator version; two runs of the same inputs produce byte-identical outputs.
- The generator MUST validate the schema before generation; a malformed schema produces a clear error, not a half-written module.
- Generated files MUST declare the schema version and generator version in a header so provenance is visible on inspection.
- If a consumer needs behavior the schema cannot express, the fix is to extend the schema — not to hand-edit the generated file.

## Related Tools

- `tools/schema_validator.py` — validates the authored schema before any generation runs.
- `tools/template_diff_analyzer.py` — shows what changed in the schema and what will change in generated output.
- `tools/template_registry_manager.py` — manages the templates used to generate modules from schemas.

## Status

ACTIVE
