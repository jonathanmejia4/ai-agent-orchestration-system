# Security Policy Linting as First-Class Gates Policy

## Summary

Security policy is not a separate, later phase applied by a different team — it is a set of machine-checked rules that run alongside every other form of linting on every change. Security checks are promoted to first-class CI gates with the same standing as unit tests and type checks: a failure blocks the change. This policy replaces periodic security review with continuous security enforcement, catching issues at the earliest point in the pipeline where they can be fixed cheaply.

## Why This Matters

- Security issues found in review or in production cost orders of magnitude more than issues caught at the lint stage.
- Making security checks a blocking gate prevents "we'll handle it in the next sprint" drift that leaves known issues in the tree indefinitely.
- Codifying policy as rules makes security expectations explicit rather than tacit; new contributors learn the rules by seeing them enforced.
- A shared set of policy rules creates consistent coverage across every entry point — no carve-outs for "this one is different".
- Machine-checked rules scale; manual review does not.

## Key Rules

- Every security rule MUST have a corresponding check that runs automatically in CI; a rule without enforcement is not a rule.
- Security checks MUST be blocking on default branches; bypasses require explicit, audited approval.
- New vulnerabilities surfaced by dependency scanning MUST fail the build until remediated or explicitly exempted with a time-bounded justification.
- Rules SHOULD produce actionable errors that name the exact file, line, and remediation path, not generic policy language.
- The set of active security rules and their versions MUST be published so downstream auditors can verify coverage.

## Related Tools

- `tools/security_scanner.py` — runs the configured set of security rules against the tree.
- `tools/access_control_validator.py` — verifies access-control declarations match policy.
- `tools/audit_trail_validator.py` — verifies that privileged operations emit audit records.
- `tools/compliance_reporter.py` — emits a compliance snapshot for human auditors.

## Status

ACTIVE
