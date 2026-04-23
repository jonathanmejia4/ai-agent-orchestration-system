# Two Test Runs Policy

## Summary

Every test suite that gates a change is run twice in succession. The second run is not a retry-on-failure, and its result is not discarded. The second run is the idempotence check: a suite that passes the first time and fails the second has demonstrated a state leak between runs, and that leak is a bug regardless of whether it surfaces in the original test's assertion. Running tests twice is a cheap, unambiguous way to catch the class of issues where tests mutate shared state, rely on ordering, or accumulate side effects across runs.

## Why This Matters

- A test that passes once but fails on the second run is not reliable — it is passing by accident of ordering or residual state.
- Intermittent CI failures are frequently caused by accumulated state that happens to clear out before the next run; two runs back-to-back catch this where single runs do not.
- Idempotent tests are a precondition for parallel execution; two-run testing enforces that precondition.
- A second run almost doubles the confidence gained from a single run at a small fraction of the engineering cost of other reliability investments.
- Two-run discipline teaches authors to write self-contained tests by surfacing violations immediately.

## Key Rules

- Every gating test suite MUST run twice; a single green run is not sufficient.
- Both runs MUST be evaluated identically; the second run's failures block the change just as the first run's failures do.
- No test may mark itself as "run once per suite"; if a test cannot be run twice, it is not a gating test.
- Tests MUST clean up resources they create; a test that leaks a file, a port, or a database row fails the second run and rightly blocks the change.
- Setup and teardown MUST be symmetric: anything setup introduces, teardown removes.

## Related Tools

- `tools/idempotence_validator.py` — flags test suites that behave differently across repeated runs.
- `tools/idempotence_checker.py` — repeat-run checker for individual operations.
- `tools/batch_verify.py` — runs verification batches with repeat counts.
- `tools/checkpoint_runner.py` — supports ordered re-execution of pipeline stages.

## Status

ACTIVE
