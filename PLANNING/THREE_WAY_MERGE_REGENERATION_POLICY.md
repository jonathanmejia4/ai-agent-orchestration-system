# Three-Way Merge Regeneration Policy

## Summary

When a generated artifact has accumulated legitimate hand edits and the template behind it changes, a naive regeneration would overwrite those edits. A three-way merge regeneration computes the new artifact from (1) the previous generator output, (2) the current generator output, and (3) the current file as it lives in the tree — producing a merged file that preserves both the template update and the hand edits wherever they do not conflict. This policy defines when three-way merge regeneration applies, how conflicts are surfaced, and the review discipline that keeps merged output trustworthy.

## Why This Matters

- Hand edits on generated files are sometimes unavoidable (escape hatches, emergency fixes); losing them on every regeneration erodes trust in generation.
- A three-way merge gives authors a predictable, inspectable way to take template updates without discarding local work.
- The conflict set from a three-way merge is exactly the set of decisions a human must make; automation handles the rest.
- Recording the previous generator output as the merge base turns regeneration into a reproducible, auditable operation.
- Without three-way merge, the only alternatives are "never regenerate" (stale templates) or "always clobber" (lost edits) — both bad.

## Key Rules

- The previous generator output for each file MUST be recorded; without it, three-way merge is impossible.
- Conflicts produced by the merge MUST be surfaced prominently; silent resolution in either direction is prohibited.
- A merged file MUST NOT be committed with unresolved conflict markers; all conflicts resolve to a human-reviewed state before landing.
- Merge behavior SHOULD be deterministic for a given triple of inputs; non-deterministic merge is a bug to be fixed.
- The merge step MUST preserve the metadata header (template version, generator version) that identifies the file's provenance.

## Related Tools

- `tools/merge_preview.py` — renders merge outcomes as a preview before apply.
- `tools/ast_merge_engine.py` — runs the merge at the level of the syntax tree rather than plain text.
- `tools/conflict_resolver.py` — assists in resolving the conflicts the merge cannot decide automatically.

## Status

ACTIVE
