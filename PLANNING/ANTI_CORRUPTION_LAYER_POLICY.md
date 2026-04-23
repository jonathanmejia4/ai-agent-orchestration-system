# Anti-Corruption Layer Policy

## Summary

The Anti-Corruption Layer (ACL) pattern isolates this system's internal domain model from external vendor, partner, or upstream system types. Rather than letting vendor-shaped data structures leak into business logic, every external boundary is crossed through a dedicated adapter that translates vendor types into internal types (and back). When an external API changes its schema, only the adapter is modified — domain code remains stable. This pattern is the primary defense against upstream coupling and the silent drift that occurs when third-party types become load-bearing throughout a codebase.

## Why This Matters

- Vendor APIs change on their timeline, not ours — without an ACL, every change becomes a cross-cutting refactor.
- Internal concepts (entities, value objects, events) should be expressed in project-native vocabulary, not in terms inherited from an external provider.
- Testing is dramatically simpler when domain code depends only on internal types that can be constructed in a test without mocking vendor SDKs.
- Security boundaries are clearer: unvalidated vendor data cannot reach business logic without passing through an adapter that can enforce schema and policy checks.
- Migrations between providers (e.g. swapping one payment gateway for another) become localized to the adapter layer.

## Key Rules

- Every external integration MUST have a dedicated adapter module; no direct vendor imports in domain or application layers.
- Adapters MUST return internal domain types, never vendor types, across their public interface.
- Vendor SDK imports MUST be confined to the adapter file; a lint rule or architectural test should enforce this.
- Translation functions MUST be named explicitly (e.g. `to_internal_customer`, `from_internal_order`) and live inside the adapter module.
- Unknown or unexpected vendor fields MUST be handled gracefully — either logged and ignored, or rejected with a clear error — never silently passed through.

## Related Tools

- `tools/dependency-boundary-checker.py` — validates that imports respect layer boundaries.
- `tools/check_cross_references.py` — catches vendor types leaking into internal modules.
- `tools/schema_validator.py` — validates incoming vendor payloads against declared schemas before translation.

## Status

ACTIVE
