# Dependency Graph and Topological Build Order Policy

## Summary

Work items, modules, and generated artifacts are organized as a directed acyclic graph (DAG) of dependencies. Before any build, generation, or validation pass, the graph is constructed and topologically sorted so that dependencies are processed before their dependents. Cycles in the graph are treated as a hard failure — they indicate a modeling problem, not a tooling limitation, and must be resolved by restructuring or splitting the work before proceeding. Topological build order is what makes incremental work safe: when A depends on B, B must be stable before A is touched.

## Why This Matters

- Processing items out of dependency order produces broken intermediate states that waste review cycles and obscure root causes.
- A well-formed DAG is the structure that incremental rebuild, caching, and parallelism all depend on.
- Cycles are almost always a sign that two concerns have been conflated into one node — surfacing them forces cleaner factoring.
- Topological order gives a deterministic schedule for parallel execution: all items at the same topological level are independent and may run concurrently.
- When a dependency is invalidated, topological order determines exactly which downstream items must be rebuilt — no more, no less.

## Key Rules

- Dependencies MUST be declared explicitly; implicit dependencies (e.g. "this file happens to import that file") do not count as declared and must be hoisted into the declaration.
- The dependency graph MUST be acyclic; detection of a cycle halts the build with a report listing the nodes in the cycle.
- Topological sort MUST be deterministic — ties broken by a stable key (typically the node identifier) so builds are reproducible.
- Nodes at the same topological level SHOULD be eligible for parallel execution unless a resource constraint prevents it.
- The graph MUST be re-validated after every edit that could introduce or remove edges; stale graph data is worse than none.

## Related Tools

- `tools/dag_builder.py` — constructs the dependency graph from declarations.
- `tools/dag_validator.py` — checks the graph for cycles and other structural problems.
- `tools/circular_dep_detector.py` — focused cycle detection with human-readable output.
- `tools/dependency_analyzer.py` — emits visualization-ready graph files.
- `tools/compute_dependencies.py` — computes the closure of dependencies for a given node.

## Status

ACTIVE
