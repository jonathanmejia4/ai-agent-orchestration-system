# Conventions

## Summary

This document captures the baseline conventions that apply across the repository: naming, file organization, directory layout, import ordering, style, and the conventions for comments and documentation. Conventions are the lowest-cost form of coordination — they let a reader move between unfamiliar modules without re-learning local dialect every time. Code that follows conventions reads faster, reviews faster, and mutates more safely under automated transformations.

## Why This Matters

- Consistent naming makes cross-module search reliable; inconsistent naming makes grep useless.
- A predictable directory layout lets readers form a mental model of where something lives without opening every file.
- Style and formatting conventions reduce cognitive load during review — reviewers can focus on semantics rather than trivia.
- Conventions are a precondition for most automation (codemods, lints, codegen) — deviation breaks tools.
- Tribal knowledge that exists only in the heads of long-tenured contributors is a liability; conventions move that knowledge into the codebase.

## Key Rules

- File names use `snake_case.py` for Python modules; markdown documents that are policies or references use `SCREAMING_SNAKE_CASE.md`.
- Public identifiers use descriptive, unabbreviated names; avoid single-letter names except for counters and well-known math variables.
- Directory layout groups by feature, not by technical role — keep related code adjacent rather than splitting it across `models/`, `views/`, `controllers/` silos.
- Every public module exposes a minimal, documented surface; internals live under `_private` or module-local names.
- Comments explain *why*, not *what* — the code itself is the source of truth for *what* the code does.

## Related Tools

- `tools/convention_checker.py` — enforces naming and structural conventions.
- `tools/code_quality_analyzer.py` — surfaces style deviations.
- `tools/add_frontmatter.py` — normalizes markdown frontmatter across the docs tree.

## Status

ACTIVE
