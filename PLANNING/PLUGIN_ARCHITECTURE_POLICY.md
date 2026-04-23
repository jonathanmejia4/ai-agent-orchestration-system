# Plugin Architecture Policy

## Summary

A plugin architecture defines a stable core with well-specified extension points, and allows behavior to be added, replaced, or removed by installing plugins without modifying the core. The value of the pattern depends entirely on the quality of the extension-point contract: narrow, well-documented extension points produce reliable plugins; wide, under-specified ones produce brittle ones. This policy covers when to use plugins, how to design extension points, and the compatibility discipline that keeps the plugin ecosystem stable across core releases.

## Why This Matters

- Plugins let third parties (and internal teams) extend behavior without the core having to anticipate every use case.
- A plugin surface is effectively a published API; it deserves the same versioning rigor as any other public interface.
- Core stability improves: risky customization is pushed out of the core and into plugins where it can fail in isolation.
- Plugins become the natural unit for feature-flagged or experimental behavior.
- A clear plugin surface clarifies what the core is and is not responsible for — it sharpens the core's identity.

## Key Rules

- Extension points MUST be defined by explicit interfaces; "pass a callable that does the right thing" is not an extension point.
- Plugins MUST declare the core version range they support; incompatible combinations fail loudly at load time, not with subtle misbehavior at runtime.
- The core MUST NOT depend on any specific plugin being present; missing plugins degrade gracefully to a documented baseline.
- Plugin authors MUST be able to test plugins against a stable fixture of the core, without bringing up the full system.
- Breaking changes to extension points MUST follow the same deprecation path as any other public API: announce, deprecate, remove.

## Related Tools

- `tools/check_agent_compatibility.py` — validates plugin/core compatibility declarations.
- `tools/dependency_boundary_checker.py` — enforces that the core does not import plugin-private modules.
- `tools/validate_composition.py` — checks composed plugin configurations for conflicts.

## Status

ACTIVE
