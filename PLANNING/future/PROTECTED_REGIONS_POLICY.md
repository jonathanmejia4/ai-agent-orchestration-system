# Protected Regions Policy

## Summary

Protected regions are fenced sections within a generated file that the generator promises not to overwrite on regeneration. A protected region gives authors a place to add hand-maintained code inside an otherwise generated artifact — a useful compromise between "pure generation" (which cannot accommodate legitimate local additions) and "escape hatches for the whole file" (which loses the benefits of generation everywhere else). This policy is filed under `future/` because several design questions remain: how regions are identified, how merges interact with regions, and how protected regions compose with three-way merge regeneration.

## Why This Matters

- Protected regions let a file be part-generated, part-handwritten — which matches the real structure of many modules where most shape is derivable but a few pieces are legitimately author-specific.
- Without protected regions, the only way to add hand-written code to a generated file is to fully escape-hatch the file, losing generator benefits on everything else inside it.
- A sanctioned way to mix generated and hand-written code prevents the growth of hidden, fragile workarounds.
- Protected regions make the scope of hand-written customization visible file by file, so it can be audited.
- Clear region markers interact cleanly with diff tooling, making hand edits inside regions as reviewable as any other change.

## Key Rules

- Protected regions MUST be delimited by explicit, machine-parseable markers; comments that look protective but are not parsed do not count.
- The generator MUST round-trip protected regions unchanged; a regeneration that loses content inside a region is a defect.
- Markers for protected regions MUST NOT be moved by the generator; if the surrounding shape changes, the generator either preserves region contents verbatim or fails with a clear error asking the author to migrate.
- Protected region content MUST be diffable and reviewable like any other source code; regions are not a review bypass.
- The set of files containing protected regions SHOULD be enumerable; opaque proliferation is a smell.

## Related Tools

- `tools/ast_merge_engine.py` — honors protected regions during merge.
- `tools/merge_preview.py` — surfaces changes that would cross protected-region boundaries.
- `tools/template_compliance_checker.py` — treats protected-region content as permitted deviation.

## Status

FUTURE
