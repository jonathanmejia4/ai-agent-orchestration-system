# Template Compliance Policy

## Summary

Templates exist to produce artifacts that meet a defined standard; template compliance is the machine-verified fact that a given artifact matches the template it was produced from. Compliance checking runs continuously, catches silent drift, and refuses to let generated artifacts diverge from their source without an explicit, recorded escape hatch. The policy covers what "compliant" means, how deviations are reported, and the remediation path for non-compliant artifacts.

## Why This Matters

- Without a compliance check, generated artifacts slowly drift from their templates as ad-hoc edits accumulate, and the benefits of the template are lost.
- A compliance report identifies precisely which artifacts diverge and on which lines, turning a vague "things are out of sync" into a concrete work list.
- Compliance as a first-class check makes template-based generation safe to adopt: contributors know that accidental manual edits will be caught, not silently propagated.
- The same machinery that verifies compliance can be used to regenerate from template, producing a clean fix for non-compliant artifacts.
- Compliance data over time shows where templates are failing to serve their consumers — repeated deviations point to a template that needs a new parameter.

## Key Rules

- Every artifact produced by a template MUST be traceable back to its template and template version.
- Compliance checks MUST run on every build; they are not an occasional audit.
- Non-compliant artifacts MUST either be regenerated, reclassified as hand-maintained under an escape hatch, or have the template updated to reflect the new truth.
- A deviation report MUST name the artifact, the template, and the specific lines that differ.
- Compliance MUST be binary per artifact: either it matches or it does not; "mostly compliant" is not a state the system tracks.

## Related Tools

- `tools/template_compliance_checker.py` — runs the compliance check across the tree.
- `tools/template_diff_analyzer.py` — produces line-level deviation reports.
- `tools/template_drift_detector.py` — surfaces historical drift trends.

## Status

ACTIVE
