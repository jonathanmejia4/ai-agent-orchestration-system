# Changelog

All notable changes to this project will be documented here.

Format: Keep a Changelog. Versioning: Semantic Versioning.

## [0.1.0] - 2026-04-23

### Added
- Initial public release
- 26 specialized hunter + fixer lanes (A-Z)
- File-signal orchestration pattern (~99% token reduction vs transcript parsing)
- Issue lifecycle (hunt → catalog → fix → verify)
- 241 tools across issue management, security scanning, code quality, catalog operations
- Slash commands: /find-all, /fix-all, /verify-fixes, /verify-catalog
- 22 policy documentation files in PLANNING/
- End-to-end walkthrough at examples/QUICK_START_WALKTHROUGH.md
- Issue file security validator (tools/validate_issue_file.py)
- Per-issue locks for fixer safety (tools/issue_lock.py)
- Atomic writes for concurrent-safe state updates

### Security
- Threat model documented in SECURITY.md
- Issue file validator rejects sensitive paths and dangerous commands
- Prominent CI/CD warning in README

### Documentation
- TOOL_CLASSIFICATION.md (per-tool purpose + status)
- CUSTOMIZATION_GUIDE.md (adapt lanes to your domain)
- TUTORIAL_FOR_HUMANS.md + TUTORIAL_FOR_CLAUDE.md
- CONTRIBUTING.md, SECURITY.md
- GitHub issue/PR templates + CI workflow
