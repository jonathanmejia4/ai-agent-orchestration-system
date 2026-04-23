# Metrics Feedback Loop Policy

## Summary

A metrics feedback loop closes the gap between the system's declared goals and the system's measured behavior. Metrics are collected continuously, compared against targets, and routed back into the work-prioritization process so that real operational signal — not intuition — drives what gets improved next. The loop is only useful if it actually closes: metrics that are collected but never read, or read but never acted on, are cost with no benefit. A healthy feedback loop has short cycle time between signal and action.

## Why This Matters

- Without metrics, "this is slow" and "this is flaky" are opinions; with metrics, they are ranked facts that can be budgeted.
- Feedback that comes back too late (weekly digests for minute-level problems) fails to influence behavior; cycle time matters as much as the metric itself.
- Metrics surface regressions early enough to be cheap to fix; discovered late, the same regression is expensive.
- A published metrics target is a contract — it shapes what reviewers and contributors optimize for.
- The metrics themselves are a source of requirements: a missing metric is often a missing concept in the system model.

## Key Rules

- Every goal that matters MUST have at least one measurable metric; if it cannot be measured, the goal must be rewritten.
- Metrics MUST be emitted from the running system, not inferred from logs after the fact; derivation is a feature of the pipeline, not of the source.
- Alerts MUST fire when a metric crosses a threshold that represents real user impact, not merely a statistical outlier.
- Dashboards MUST be owned; an orphan dashboard is worse than none because it breeds false confidence.
- Metrics data MUST feed the prioritization process — planning that ignores measured reality is not planning.

## Related Tools

- `tools/metric_aggregator.py` — aggregates raw metric events into time-series form and produces cross-run trends.
- `tools/progress_dashboard.py` — renders metric state for human review.
- `tools/alert_manager.py` — routes threshold crossings to responders.
- `tools/performance_profiler.py` — captures structured performance measurements.

## Status

ACTIVE
