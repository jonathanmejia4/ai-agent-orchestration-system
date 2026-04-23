# SSOT Wiring File Policy

## Summary

A Single Source of Truth (SSOT) wiring file is a dedicated, versioned file that declares how modules, services, plugins, or agents are composed into a running system. All other components read their composition from the wiring file rather than from hard-coded imports or scattered configuration. This centralization does three things: it makes the system's structure legible at a glance, it makes composition changes a one-place edit, and it gives every tool that reasons about the system (dependency analysis, diagramming, validation) a single artifact to consume.

## Why This Matters

- Scattered wiring makes system structure invisible; the only way to learn it is to trace imports across dozens of files.
- A central wiring file is the structural contract of the system — changes to it are the changes worth reviewing carefully.
- Tools that visualize, validate, or transform the structure need a reliable input; the SSOT wiring file is that input.
- Wiring by convention hides mistakes (a missing component silently disables a feature); wiring by declaration surfaces them.
- Refactoring becomes safer when composition is separated from implementation — you can rewire without touching every implementation file.

## Key Rules

- Exactly one wiring file MUST be designated as the source of truth; secondary wiring files, if any, derive from it and are marked as generated.
- Components MUST NOT hard-wire their dependencies; dependencies are injected based on the wiring file.
- The wiring file MUST be validated on every build: referenced components must exist, declared interfaces must match, and required wiring must be complete.
- Changes to the wiring file MUST pass the same review bar as code changes — they shape system behavior just as directly.
- Generators and diagram tools MUST read from the wiring file, not re-derive composition from source analysis.

## Related Tools

- `tools/validate_composition.py` — validates the wiring file against declared interfaces.
- `tools/dependency_analyzer.py` — emits a graph derived from the wiring file.
- `tools/check_cross_references.py` — catches references in code that bypass the wiring file.

## Status

ACTIVE
