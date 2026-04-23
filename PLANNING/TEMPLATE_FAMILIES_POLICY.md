# Template Families Policy

## Summary

A template family is a group of related templates that share a common purpose, common shape, and common conventions — differing only in well-defined ways. Grouping templates into families lets authors share validation, documentation, and upgrade paths across the family, and lets consumers reason about "which variant do I need?" rather than "which template should I use?". This policy covers how families are defined, how they evolve, and the rules that keep a family coherent over time.

## Why This Matters

- Without family structure, related templates diverge in small ways that accumulate into a confusing catalog.
- A family contract — what all members share and how members differ — is easier to maintain than a dozen independent template READMEs.
- Family-wide checks catch the class of bugs where one family member regresses on a property that the rest of the family enforces.
- New family members can inherit fixtures, documentation scaffolding, and tests from the family, dramatically lowering the cost of adding a variant.
- Retiring a template is cleaner when the family makes explicit which other members are candidate replacements.

## Key Rules

- Every template MUST declare its family (or declare itself a singleton); untyped templates are not permitted.
- A family MUST have a written contract describing what all members share and what is allowed to vary.
- New family members MUST pass the family's contract checks before they are published.
- Family members MUST share a common version scheme; mixed schemes within a family are a compatibility hazard.
- Cross-family dependencies SHOULD be narrow and documented; a template that silently depends on another family is fragile.

## Related Tools

- `tools/template_family_validator.py` — validates that each template meets its family's contract.
- `tools/template_registry_manager.py` — maintains the family registry.
- `tools/template_lineage.py` — traces family membership and derivation history.

## Status

ACTIVE
