# Template Variants and Parameter Packs Policy

## Summary

Templates rarely have exactly one correct shape — different use cases call for different combinations of features, defaults, and tuning parameters. A variant is a named instantiation of a template with a predefined parameter pack; a parameter pack is a bundle of parameter values that belong together semantically. Rather than forcing every consumer to rediscover the right parameter values for common cases, the template publishes a small set of well-tested variants and allows consumers to start from one. This reduces configuration error and makes template evolution clearer: changes to shared parameter packs affect every variant that uses them.

## Why This Matters

- Hand-picking parameters for each use case is a known source of defects; packaged variants eliminate the class.
- Named variants carry intent ("compact" vs "full") that bare parameter sets cannot communicate.
- Consumers benefit from the testing that variant authors performed; each consumer no longer needs to rediscover what works.
- Parameter packs decouple the "what" from the "where" — a single pack can be applied to multiple templates consistently.
- Retiring a variant is a clearer signal than changing parameters one at a time; consumers migrate as a group.

## Key Rules

- Every published variant MUST be tested against a representative consumer; unverified variants are not published.
- Parameter packs MUST be named, versioned, and documented; ad-hoc parameter bundles are not parameter packs.
- Consumers SHOULD start from a published variant; overriding parameters is allowed but discouraged for values that belong to a shared pack.
- A parameter pack MUST declare which templates it is valid for; applying a pack to an incompatible template fails at generation time.
- Introducing or retiring a variant MUST follow the same deprecation discipline as any other public interface.

## Related Tools

- `tools/template_compatibility_checker.py` — validates that parameter packs match template expectations.
- `tools/template_upgrade_candidates.py` — surfaces consumers that should migrate between variants.
- `tools/template_upgrade_assistant.py` — plans and executes variant migrations.

## Status

ACTIVE
