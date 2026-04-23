# Contributing to AI Agent Orchestration System

Thanks for your interest in contributing. This project is an open-source framework
for multi-agent issue detection and resolution using Claude Code. Contributions
of any size — bug fixes, new lanes, documentation improvements, real-world use
cases — are welcome and appreciated.

## Ways to Contribute

- **Report bugs** using [`.github/ISSUE_TEMPLATE/bug_report.md`](.github/ISSUE_TEMPLATE/bug_report.md)
- **Suggest features** using [`.github/ISSUE_TEMPLATE/feature_request.md`](.github/ISSUE_TEMPLATE/feature_request.md)
- **Submit pull requests** for bug fixes, new lanes, or doc improvements
- **Share use cases** — show how you customized the framework for your domain
- **Improve documentation** — any unclear section is a valid PR target

## Development Setup

```bash
# 1. Fork and clone the repository
git clone https://github.com/YOUR-USERNAME/ai-agent-orchestration-system.git
cd ai-agent-orchestration-system

# 2. (Recommended) create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
pip install pytest

# 4. Verify the install by running the test suite
python3 -m pytest tests/ -v

# 5. Run the validators locally
python3 tools/markdown_link_checker.py .
python3 tools/validate_issue_file.py issues/
```

## Customization Workflow

Most contributions will involve adapting lanes (A–Z) to your own stack or
adding new ones. See [CUSTOMIZATION_GUIDE.md](CUSTOMIZATION_GUIDE.md) for the
full walkthrough, plus any tutorial docs in the repo for a worked example.

## Pull Request Process

1. Fork the repository and create a topic branch:
   `git checkout -b feat/short-description`
2. Make focused changes — prefer one logical change per PR
3. Run the test suite: `python3 -m pytest tests/`
4. Run the link checker and issue validator (see Development Setup)
5. Commit with a clear message that explains the *why*, not just the *what*
6. Push your branch and open a pull request using the PR template
7. Respond to review feedback on the PR thread; keep discussion there so the
   history is preserved

Small, well-scoped PRs land fastest. If your change is large or touches core
orchestration logic, please open an issue first to discuss the direction before
writing code.

## Code Style

- **Python:** PEP 8; include type hints on public functions and module-level APIs
- **Shell:** ShellCheck clean; use `set -euo pipefail` at the top of bash scripts
- **Markdown:** a single H1 per document, consistent heading levels, relative
  links within the repo
- **YAML:** two-space indentation, no tabs, no trailing whitespace

## Security

Security-sensitive contributions should follow [SECURITY.md](SECURITY.md). Please
do **not** open a public issue for vulnerabilities — use the private disclosure
process documented there.

Remember that `tools/validate_issue_file.py` rejects sensitive paths and
dangerous shell patterns in verification commands. Keep verification commands
read-only and narrowly scoped.

## Questions

Open an issue with the `question` label for anything that isn't a bug report or
feature request. For broader discussion about project direction, start a GitHub
Discussion (if enabled) or mention it in an issue.

Thanks again for helping improve this framework.
