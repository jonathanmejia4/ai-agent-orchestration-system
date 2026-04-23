# Template Versioning and Deprecation Policy

## Summary

Templates evolve. New parameters are added, old ones are removed, generated output changes shape. Without explicit versioning, consumers have no way to know whether the template they depend on is stable, and template authors have no way to change the template without risking silent breakage across the ecosystem. This policy applies semantic versioning to templates, defines what counts as a breaking change, and establishes a deprecation pathway so that obsolete templates can be retired cleanly rather than abandoned.

## Why This Matters

- Consumers need to know which template versions they can upgrade to without breaking; unversioned templates are ambiguous by default.
- Template authors need to make breaking changes without fearing a hidden chain of broken consumers.
- A deprecation pathway replaces the "just leave it there forever" default that otherwise grows the template catalog without bound.
- Versioning data is input to migration tooling — without it, automated upgrades cannot decide what is safe.
- A shared versioning discipline makes template consumers into peers of library consumers, with the same mental model.

## Key Rules

- Every template MUST be semver-tagged; untagged templates are not published.
- A change that alters generated output in a way a consumer could observe is MAJOR; backward-compatible additions are MINOR; internal cleanups are PATCH.
- Deprecated templates MUST continue to function for a published deprecation window; they MUST also emit a deprecation notice on every use.
- The deprecation notice MUST name a successor template or a documented migration path; "this is deprecated" without direction is not acceptable.
- Removal of a deprecated template MUST be announced in advance, with an enforced cutoff date; silent removal is prohibited.

## Related Tools

- `tools/template_version_checker.py` — validates version tags and consumer compatibility.
- `tools/template_upgrade_assistant.py` — plans and executes migrations from deprecated to successor templates.
- `tools/retired_template_checker.py` — catches remaining references to retired templates.

## Status

ACTIVE
