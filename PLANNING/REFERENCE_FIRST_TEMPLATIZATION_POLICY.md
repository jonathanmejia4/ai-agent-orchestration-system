# Reference-First Templatization Policy

## Summary

Before extracting a template, build at least one complete, working reference implementation of the thing the template is meant to produce. Only once a real instance exists — exercised, reviewed, and running in a representative environment — should its shape be abstracted into a template. Templates written before the reference they claim to generalize tend to encode speculative structure that no real use case needs and miss structure that every real use case does need. Reference-first templatization grounds the abstraction in observed reality.

## Why This Matters

- A template extracted from one concrete example is honest about what varies and what is constant; a template extracted from zero examples is a guess.
- Working reference code provides the empirical test that the template is supposed to reproduce — with no reference, "does the template work?" has no answer.
- Early templatization freezes decisions that the reference would have revealed as wrong; the template then becomes a barrier to learning.
- A reference implementation doubles as usage documentation for the template.
- With a real reference in hand, the next one or two instances confirm which parts of the reference are parameters and which are constants — the template almost writes itself.

## Key Rules

- Templates MUST NOT be introduced before at least one working reference exists; speculative templates are rejected at review.
- The reference implementation MUST be retained in the repository even after the template is extracted; it is the canonical regression target.
- Parameters in the template MUST correspond to points that demonstrably varied between the reference and the second instance.
- Structure present in the reference but constant across all known instances MUST stay constant in the template until a new use case forces the parameter.
- Templates MUST be regenerated against the reference in CI to catch drift between them.

## Related Tools

- `tools/template_scanner.py` — inventories existing templates and their reference links.
- `tools/template_lineage.py` — traces the reference from which each template was derived.
- `tools/template_diff_analyzer.py` — compares generated output against the reference.

## Status

ACTIVE
