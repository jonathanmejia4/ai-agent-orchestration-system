# Generation Escape Hatch Policy

## Summary

Automated generation is powerful but never sufficient on its own. Real systems always include cases where the generator produces code that is almost right but wrong in some specific way, or where a legitimate requirement cannot be expressed in the generator's input language. The Generation Escape Hatch gives authors a sanctioned, traceable way to bypass generation for a specific artifact, region, or invocation — without silently undermining the generation model or losing the ability to regenerate the rest of the system. An escape hatch is a trade: you accept local ownership of a file or region in exchange for flexibility the generator cannot offer.

## Why This Matters

- Every generator encounters edge cases it cannot (or should not) model; without an escape hatch, contributors resort to in-place edits that are silently destroyed on next regeneration.
- Sanctioned opt-out prevents the ecosystem of ad-hoc workarounds that otherwise grows around any rigid codegen system.
- Tracking which artifacts have been opt-ed out makes the scope of hand-maintained code visible — so it can be audited, documented, and eventually closed over.
- An escape hatch with a recorded rationale becomes a prioritized backlog for generator improvements.
- Preserving the ability to regenerate everything else means the escape hatch stays local and does not metastasize.

## Key Rules

- Escape hatches MUST be declared explicitly in a well-known file or marker (e.g. a manifest or a fenced region), never inferred from absent updates.
- Every escape hatch MUST carry a rationale that explains what the generator cannot do; "I wanted it different" is not sufficient.
- Escape-hatched artifacts MUST be regenerable to their starting form at any time; the hatch records the divergence, not a rewrite of history.
- The set of active escape hatches MUST be reported alongside generation output; it is part of the build's public state.
- Escape hatches SHOULD have an expected lifetime and a review cadence; stale hatches accumulate.

## Related Tools

- `tools/deprecated_template_scanner.py` — surfaces drifted generated artifacts and reports usage of legacy templates still covered by hatches.
- `tools/validate_template_metadata.py` — validates escape-hatch markers against the generator manifest.

## Status

ACTIVE
