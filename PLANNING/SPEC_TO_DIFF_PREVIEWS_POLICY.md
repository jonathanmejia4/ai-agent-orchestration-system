# Spec-to-Diff Previews Policy

## Summary

Before a spec is applied — before any file is changed in the repository — the spec is rendered as a diff preview that shows exactly what will change, where, and why. The preview is the artifact that humans review; the apply step only commits what the preview already showed. Previews turn spec application into a two-step process (see, then approve) and eliminate the class of mistakes where a spec was approved in the abstract but produced unexpected changes in the concrete.

## Why This Matters

- Humans are far better at reviewing concrete diffs than at simulating abstract specs in their heads; the preview moves review to where humans are strong.
- A preview surfaces the full blast radius of a spec; scope creep and unintended edits become visible before they land.
- Rejecting a preview is a low-cost operation; rejecting a landed change is expensive.
- Previews make spec review teachable: a reviewer can point at specific diff lines to explain why a spec needs revision.
- When a spec is rerun, byte-identical previews confirm determinism; drift in the preview flags generator or input changes.

## Key Rules

- Every spec application MUST produce a preview before any file is modified; previews are a precondition, not an option.
- The preview MUST represent the complete change set; partial previews that hide edits are prohibited.
- Apply MUST be mechanically identical to the preview; if the result differs, the apply is aborted and the divergence is reported.
- Previews MUST be reproducible from the spec alone; re-running the preview with the same spec produces the same diff.
- A preview that has not been approved MUST NOT be applied; approval is a distinct, recorded action.

## Related Tools

- `tools/preview_generator.py` — renders specs as diff previews.
- `tools/generate_preview.py` — alternative preview-rendering entry point.
- `tools/approve_preview.py` — records explicit approval of a preview.
- `tools/preview_approver.py` — gates apply on approval state.

## Status

ACTIVE
