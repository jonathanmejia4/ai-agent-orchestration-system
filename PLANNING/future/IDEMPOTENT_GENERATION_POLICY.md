# Idempotent Generation Policy

## Summary

Generation is idempotent when running it twice with the same inputs produces byte-identical outputs and makes no state change on the second run. Idempotent generation is the property that makes generation safe to automate, safe to retry, and safe to compose with caching layers. This policy is filed under `future/` because achieving full idempotence across the generation pipeline is an ongoing effort rather than a solved problem — some stages produce output that varies with timestamps, iteration order, or environment — and this document collects the direction we are moving in.

## Why This Matters

- Non-idempotent generation makes caching unsound; every cache hit is a gamble on whether the cached output is still correct.
- Automated retries of a non-idempotent generator can produce divergent outputs, silently corrupting downstream consumers.
- Diffs across runs become unreadable when they are dominated by incidental variation (timestamps, map ordering) rather than real change.
- Idempotence is what lets a CI system confidently skip unchanged work; without it, "unchanged" is an approximation rather than a fact.
- An idempotent generator is one that has eliminated hidden state; that elimination often produces a simpler, better generator.

## Key Rules

- Timestamps, UUIDs, and other time- or entropy-derived values MUST be either pinned to declared inputs or excluded from generated output.
- Iteration over unordered collections (sets, dicts) MUST be sorted by a stable key before producing output.
- External calls during generation SHOULD be eliminated; if unavoidable, they must be cached and replayable.
- A generator MUST be tested by running it twice on the same inputs and diffing the outputs; any diff is a bug.
- Deviations from idempotence MUST be documented in the generator's README with a plan to remove them.

## Related Tools

- `tools/idempotence_checker.py` — runs a generator twice and compares outputs.
- `tools/idempotence_validator.py` — validates declarations about which outputs are expected to be deterministic.
- `tools/test_idempotence.sh` — harness for idempotence checks in CI.

## Status

FUTURE
