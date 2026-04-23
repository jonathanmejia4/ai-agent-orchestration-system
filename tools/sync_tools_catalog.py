#!/usr/bin/env python3
"""
Sync Tools Catalog Statistics

This script scans ALL executable/actionable items in the the system repository:
1. Tools (tools/*.py, tools/*.sh)
2. Scripts (scripts/*.py, scripts/*.sh)
3. GitHub Workflows (.github/workflows/*.yml)
4. Plugins (plugins/**/*.py)
5. Pre-commit hooks (from .pre-commit-config.yaml)
6. Source code (src/**/*.py)
7. Templates (templates/**/*.j2, *.jinja, *.jinja2)
8. Docker files (Dockerfile*, docker-compose*.yml)
9. Makefiles
10. All shell scripts anywhere in repo

Usage:
    python3 tools/sync_tools_catalog.py           # Update catalog
    python3 tools/sync_tools_catalog.py --check   # Check only, don't update
    python3 tools/sync_tools_catalog.py --verbose # Detailed output
"""

import os
import re
import sys
import subprocess
import py_compile
import yaml
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Base directory
BASE_DIR = Path(__file__).parent.parent
TOOLS_DIR = BASE_DIR / "tools"
SCRIPTS_DIR = BASE_DIR / "scripts"
WORKFLOWS_DIR = BASE_DIR / ".github" / "workflows"
PLUGINS_DIR = BASE_DIR / "plugins"
SRC_DIR = BASE_DIR / "src"
TEMPLATES_DIR = BASE_DIR / "templates"
PRECOMMIT_CONFIG = BASE_DIR / ".pre-commit-config.yaml"
CATALOG_PATH = BASE_DIR / "TOOLS_CATALOG.md"
SAFETY_CONFIG_PATH = TOOLS_DIR / "tool_safety_config.yaml"

# Directories to exclude from scanning
EXCLUDE_DIRS = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', 'env',
                '.task', 'archives', '.mypy_cache', '.pytest_cache', 'dist', 'build'}

# All programming/scripting language extensions (files that "do things")
CODE_EXTENSIONS = {
    # Scripting languages
    '.py': ('Python', 'python'),
    '.sh': ('Shell', 'shell'),
    '.bash': ('Bash', 'shell'),
    '.zsh': ('Zsh', 'shell'),
    '.fish': ('Fish', 'shell'),
    '.ps1': ('PowerShell', 'powershell'),
    '.psm1': ('PowerShell Module', 'powershell'),
    '.bat': ('Batch', 'batch'),
    '.cmd': ('Batch', 'batch'),

    # Web languages
    '.js': ('JavaScript', 'javascript'),
    '.mjs': ('JavaScript (ESM)', 'javascript'),
    '.cjs': ('JavaScript (CJS)', 'javascript'),
    '.jsx': ('React JSX', 'javascript'),
    '.ts': ('TypeScript', 'typescript'),
    '.tsx': ('TypeScript React', 'typescript'),
    '.php': ('PHP', 'php'),

    # Systems languages
    '.c': ('C', 'c'),
    '.h': ('C Header', 'c'),
    '.cpp': ('C++', 'cpp'),
    '.cc': ('C++', 'cpp'),
    '.cxx': ('C++', 'cpp'),
    '.hpp': ('C++ Header', 'cpp'),
    '.rs': ('Rust', 'rust'),
    '.go': ('Go', 'go'),
    '.swift': ('Swift', 'swift'),

    # JVM languages
    '.java': ('Java', 'java'),
    '.kt': ('Kotlin', 'kotlin'),
    '.kts': ('Kotlin Script', 'kotlin'),
    '.scala': ('Scala', 'scala'),
    '.groovy': ('Groovy', 'groovy'),
    '.clj': ('Clojure', 'clojure'),
    '.cljs': ('ClojureScript', 'clojure'),

    # .NET languages
    '.cs': ('C#', 'csharp'),
    '.fs': ('F#', 'fsharp'),
    '.vb': ('VB.NET', 'vbnet'),

    # Functional languages
    '.hs': ('Haskell', 'haskell'),
    '.ml': ('OCaml', 'ocaml'),
    '.erl': ('Erlang', 'erlang'),
    '.ex': ('Elixir', 'elixir'),
    '.exs': ('Elixir Script', 'elixir'),

    # Data/Scientific
    '.r': ('R', 'r'),
    '.R': ('R', 'r'),
    '.jl': ('Julia', 'julia'),
    '.m': ('MATLAB/Octave', 'matlab'),

    # Ruby
    '.rb': ('Ruby', 'ruby'),
    '.rake': ('Rake', 'ruby'),
    '.gemspec': ('Gemspec', 'ruby'),

    # Perl
    '.pl': ('Perl', 'perl'),
    '.pm': ('Perl Module', 'perl'),

    # Lua
    '.lua': ('Lua', 'lua'),

    # Lisp family
    '.lisp': ('Lisp', 'lisp'),
    '.lsp': ('AutoLISP', 'lisp'),
    '.el': ('Emacs Lisp', 'lisp'),
    '.scm': ('Scheme', 'lisp'),
    '.rkt': ('Racket', 'lisp'),

    # Other scripting
    '.awk': ('AWK', 'awk'),
    '.sed': ('Sed', 'sed'),
    '.tcl': ('Tcl', 'tcl'),
    '.vim': ('Vimscript', 'vim'),

    # Query/Data languages that execute
    '.sql': ('SQL', 'sql'),
    '.graphql': ('GraphQL', 'graphql'),
    '.gql': ('GraphQL', 'graphql'),

    # Build/Config that execute
    '.cmake': ('CMake', 'cmake'),
    '.gradle': ('Gradle', 'gradle'),

    # Notebooks (executable)
    '.ipynb': ('Jupyter Notebook', 'jupyter'),
}

# Cache for safety config
_SAFETY_CONFIG = None

# Patterns for auto-classification of new tools (same as safe_tool_tester.py)
SAFE_NAME_PATTERNS = [
    r'^validate_.*\.py$', r'^verify_.*\.py$', r'^check_.*\.py$',
    r'.*_validator\.py$', r'.*_checker\.py$', r'.*_scanner\.py$',
    r'.*_analyzer\.py$', r'.*_reporter\.py$', r'.*_stats\.py$',
]
SANDBOXED_NAME_PATTERNS = [
    r'^add_.*\.py$', r'^fix_.*\.py$', r'^update_.*\.py$',
    r'^generate_.*\.py$', r'^regenerate_.*\.py$',
]
MANUAL_NAME_PATTERNS = [
    r'.*orchestrator.*\.py$', r'.*daemon.*\.py$', r'.*notifier.*\.py$',
    r'.*_runner\.py$', r'.*\.sh$',
]

def load_safety_config():
    """Load safety classifications from tool_safety_config.yaml."""
    global _SAFETY_CONFIG
    if _SAFETY_CONFIG is not None:
        return _SAFETY_CONFIG

    _SAFETY_CONFIG = {"safe": [], "dry_run": {}, "sandboxed": [], "manual": []}

    if SAFETY_CONFIG_PATH.exists():
        try:
            with open(SAFETY_CONFIG_PATH) as f:
                config = yaml.safe_load(f)
                if config:
                    _SAFETY_CONFIG = config
        except Exception:
            pass

    return _SAFETY_CONFIG

def get_safety_level(tool_name: str) -> str:
    """
    Get safety level for a tool.
    Returns: "SAFE", "DRY_RUN", "SANDBOXED", "MANUAL", or "AUTO:*" if auto-classified
    """
    config = load_safety_config()

    # Check explicit config
    if tool_name in config.get("safe", []):
        return "SAFE"
    if tool_name in config.get("dry_run", {}):
        return "DRY_RUN"
    if tool_name in config.get("sandboxed", []):
        return "SANDBOXED"
    if tool_name in config.get("manual", []):
        return "MANUAL"

    # Auto-classify based on name patterns
    for pattern in MANUAL_NAME_PATTERNS:
        if re.match(pattern, tool_name, re.IGNORECASE):
            return "AUTO:MANUAL"
    for pattern in SANDBOXED_NAME_PATTERNS:
        if re.match(pattern, tool_name, re.IGNORECASE):
            return "AUTO:SANDBOX"
    for pattern in the frameworkE_NAME_PATTERNS:
        if re.match(pattern, tool_name, re.IGNORECASE):
            return "AUTO:SAFE"

    # Default for unknown
    return "AUTO:UNKNOWN"

# Tool categories based on naming patterns (for tools/ directory)
TOOL_CATEGORY_PATTERNS = {
    "Task Management": [
        "task_lifecycle", "task_rollback", "task_scanner", "task_status",
        "generate_task", "validate_task"
    ],
    "Checkers & Scanners": [
        "add_fix_checklist", "check_agent", "check_canonicalization", "check_cross",
        "check_dependencies", "check_traceability", "code_quality", "convention_checker",
        "deprecated_template_scanner", "deprecated_template_usage", "detect_missing",
        "embedded_test", "env_config", "failure_mode", "file_integrity", "fixture_suffix",
        "fixture_validator", "lisp_syntax", "naming_pattern", "pii_scanner",
        "retired_template", "spec_compliance", "test_mirror", "variant_symmetry"
    ],
    "Critic System": ["critic_review", "critical_path"],
    "Dependency Analysis": [
        "circular_dep", "compute_dependencies", "dag_builder", "dag_validator",
        "dependency_analyzer", "dependency_graph", "dependency-boundary", "find_cycles",
        "topological_sort", "traceability_mapper"
    ],
    "Generators": [
        "generate.py", "generate_daily", "generate_doc", "generate_expected",
        "generate_preview", "generate_report", "generate_security"
    ],
    "Health & Monitoring": [
        "agent_health", "health_monitor", "heartbeat", "monetization_health",
        "system_health", "time_box"
    ],
    "Issue & Catalog Mgmt": [
        "add_issue", "issue_stats", "restructure_catalog", "sync_catalog_stats",
        "validate_issue", "verify_issue"
    ],
    "LogBook Management": [
        "logbook_access", "logbook_archive", "logbook_auto", "logbook_compliance",
        "logbook_immutability", "logbook_query", "logbook_update", "logbook_validator",
        "validate_logbook"
    ],
    "Merge & Conflict": [
        "account_merge", "ast_merge", "conflict_resolver", "merge_engine",
        "merge_preview", "three_way"
    ],
    "Metrics & Reporting": [
        "agent_session", "alt_branch_stats", "coverage_reporter", "doc_coverage",
        "eod_summary", "metric_aggregator", "metrics_collector", "performance_profiler",
        "progress_dashboard", "progress_reporter", "qa_metrics"
    ],
    "Notifications": [
        "alert_manager", "card_expiry", "escalation_handler", "notification_dispatcher",
        "teams_notifier"
    ],
    "PM & Promotion": [
        "approve_action", "approve_preview", "pm_promote", "preview_approver",
        "preview_generator", "promotion_gate", "stage_promotion"
    ],
    "Policy & Compliance": [
        "compliance_reporter", "enforce_write", "policy_enforcement", "policy_version",
        "escape_hatch"
    ],
    "Protected Regions": [
        "protected_paths", "protected_regions", "region_extractor", "region_hash",
        "region_interface", "region_reinserter", "region_reuse", "region_validator"
    ],
    "Recovery & Rollback": [
        "orchestrator_recovery", "recovery_orchestrator", "snapshot_manager"
    ],
    "SSOT & Wiring": [
        "migrate_to_ssot", "ssot_validator", "update_ssot", "wiring_validator"
    ],
    "Schema Validation": ["schema_validator"],
    "Security": [
        "access_control_validator", "generate_security_tests", "password_breach",
        "security_scanner"
    ],
    "Stage Gate": ["gate_validator", "stage_gate_enforcer"],
    "Template Management": [
        "add_resolution_template", "family_validator", "template_compliance",
        "template_diff", "template_drift", "template_family", "template_lineage",
        "template_metadata", "template_registry", "template_scanner", "template_upgrade",
        "template_usage", "template_version", "validate_template"
    ],
    "Testing": [
        "integration_test_runner", "run_integration", "smoke_test", "test_runner"
    ],
    "Traceability & Audit": [
        "a11y_audit", "audit.py", "audit_trail", "traceability_checker", "ux_click"
    ],
    "Validation": [
        "validate_action", "validate_ci", "validate_composition", "validate_critic",
        "validate_crossrefs", "validate_environment", "validate_equivalence",
        "validate_escalation", "validate_integration", "validate_monitoring",
        "validate_planner", "validate_pm", "validate_rollback", "validate_state",
        "validate_status", "validate_verdict", "validate_wo", "validate_work",
        "validate_write"
    ],
    "Verification": [
        "accurate_verify", "batch_verify", "comprehensive_verify", "final_verify",
        "idempotence_checker", "idempotence_validator", "smart_verify",
        "test_coverage_checker", "verify_all", "verify_dashboard", "verify_execution",
        "verify_frontmatter", "verify_optimization", "verify_patterns", "verify_phase",
        "verify_security", "verify_stats", "version_compatibility", "version_pin"
    ],
}

# Workflow categories based on naming patterns
WORKFLOW_CATEGORY_PATTERNS = {
    "CI/CD Core": ["ci.yml", "cd.yml", "deploy", "release", "publish"],
    "Testing": ["test", "smoke", "integration", "e2e", "unit"],
    "Validation": ["validation", "validate", "check", "verify", "lint"],
    "Security": ["security", "codeql", "dependabot", "secret", "vulnerability"],
    "Documentation": ["docs", "documentation", "pages"],
    "Monitoring": ["health", "status", "monitor", "digest", "report"],
    "Task & Template": ["task", "template"],
    "Agent & PM": ["agent", "pm_", "critic", "planner", "builder"],
}

def check_python_syntax(filepath):
    """Check Python syntax using py_compile."""
    try:
        py_compile.compile(str(filepath), doraise=True)
        return True, None
    except py_compile.PyCompileError as e:
        return False, str(e)

def check_shell_syntax(filepath):
    """Check shell script syntax using bash -n."""
    try:
        result = subprocess.run(
            ["bash", "-n", str(filepath)],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return True, None
        return False, result.stderr
    except Exception as e:
        return False, str(e)

def check_yaml_syntax(filepath):
    """Check YAML syntax."""
    try:
        with open(filepath, 'r') as f:
            yaml.safe_load(f)
        return True, None
    except yaml.YAMLError as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)

def check_jinja_syntax(filepath):
    """Check Jinja2 template syntax."""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        # Basic check: matching braces
        open_braces = content.count('{{') + content.count('{%')
        close_braces = content.count('}}') + content.count('%}')
        if open_braces != close_braces:
            return False, f"Unmatched braces: {open_braces} open, {close_braces} close"
        return True, None
    except Exception as e:
        return False, str(e)

def check_dockerfile_syntax(filepath):
    """Check Dockerfile syntax (basic validation)."""
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()

        valid_instructions = {
            'FROM', 'RUN', 'CMD', 'LABEL', 'MAINTAINER', 'EXPOSE', 'ENV',
            'ADD', 'COPY', 'ENTRYPOINT', 'VOLUME', 'USER', 'WORKDIR', 'ARG',
            'ONBUILD', 'STOPSIGNAL', 'HEALTHCHECK', 'SHELL'
        }

        has_from = False
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            instruction = line.split()[0].upper() if line.split() else ''
            if instruction == 'FROM':
                has_from = True
            elif instruction and instruction not in valid_instructions:
                # Could be a continuation line
                if not line.startswith('\\'):
                    pass  # Allow unknown for flexibility

        if not has_from:
            return False, "Missing FROM instruction"
        return True, None
    except Exception as e:
        return False, str(e)

def check_makefile_syntax(filepath):
    """Check Makefile syntax (basic validation)."""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        # Basic check: file is readable and has targets
        if ':' in content:
            return True, None
        return False, "No targets found"
    except Exception as e:
        return False, str(e)

def categorize_tool(tool_name):
    """Categorize a tool based on its name."""
    if tool_name.endswith('.sh'):
        return "Shell Scripts"

    for category, patterns in TOOL_CATEGORY_PATTERNS.items():
        for pattern in patterns:
            if pattern in tool_name:
                return category

    return "Utilities"

def categorize_workflow(workflow_name):
    """Categorize a workflow based on its name."""
    workflow_lower = workflow_name.lower()

    for category, patterns in WORKFLOW_CATEGORY_PATTERNS.items():
        for pattern in patterns:
            if pattern in workflow_lower:
                return category

    return "Other Workflows"

def scan_tools():
    """Scan tools/ directory."""
    items = []

    # Python tools
    for filepath in TOOLS_DIR.glob("*.py"):
        if filepath.name == "__init__.py":
            continue
        is_valid, error = check_python_syntax(filepath)
        items.append({
            "name": filepath.name,
            "path": str(filepath.relative_to(BASE_DIR)),
            "type": "Python",
            "location": "tools/",
            "valid": is_valid,
            "error": error,
            "category": categorize_tool(filepath.name)
        })

    # Shell tools
    for filepath in TOOLS_DIR.glob("*.sh"):
        is_valid, error = check_shell_syntax(filepath)
        items.append({
            "name": filepath.name,
            "path": str(filepath.relative_to(BASE_DIR)),
            "type": "Shell",
            "location": "tools/",
            "valid": is_valid,
            "error": error,
            "category": "Shell Scripts"
        })

    return items

def scan_scripts():
    """Scan scripts/ directory."""
    items = []

    if not SCRIPTS_DIR.exists():
        return items

    # Python scripts
    for filepath in SCRIPTS_DIR.glob("**/*.py"):
        if filepath.name == "__init__.py":
            continue
        is_valid, error = check_python_syntax(filepath)
        items.append({
            "name": filepath.name,
            "path": str(filepath.relative_to(BASE_DIR)),
            "type": "Python",
            "location": "scripts/",
            "valid": is_valid,
            "error": error,
            "category": "Standalone Scripts"
        })

    # Shell scripts
    for filepath in SCRIPTS_DIR.glob("**/*.sh"):
        is_valid, error = check_shell_syntax(filepath)
        items.append({
            "name": filepath.name,
            "path": str(filepath.relative_to(BASE_DIR)),
            "type": "Shell",
            "location": "scripts/",
            "valid": is_valid,
            "error": error,
            "category": "Standalone Scripts"
        })

    return items

def scan_workflows():
    """Scan .github/workflows/ directory."""
    items = []

    if not WORKFLOWS_DIR.exists():
        return items

    for filepath in WORKFLOWS_DIR.glob("*.yml"):
        is_valid, error = check_yaml_syntax(filepath)
        items.append({
            "name": filepath.name,
            "path": str(filepath.relative_to(BASE_DIR)),
            "type": "Workflow",
            "location": ".github/workflows/",
            "valid": is_valid,
            "error": error,
            "category": categorize_workflow(filepath.name)
        })

    for filepath in WORKFLOWS_DIR.glob("*.yaml"):
        is_valid, error = check_yaml_syntax(filepath)
        items.append({
            "name": filepath.name,
            "path": str(filepath.relative_to(BASE_DIR)),
            "type": "Workflow",
            "location": ".github/workflows/",
            "valid": is_valid,
            "error": error,
            "category": categorize_workflow(filepath.name)
        })

    return items

def scan_plugins():
    """Scan plugins/ directory."""
    items = []

    if not PLUGINS_DIR.exists():
        return items

    for filepath in PLUGINS_DIR.glob("**/*.py"):
        if filepath.name == "__init__.py":
            continue
        is_valid, error = check_python_syntax(filepath)

        # Categorize based on parent directory
        parent = filepath.parent.name
        if parent == "notifiers":
            category = "Plugin: Notifiers"
        elif parent == "validators":
            category = "Plugin: Validators"
        else:
            category = "Plugin: Core"

        items.append({
            "name": filepath.name,
            "path": str(filepath.relative_to(BASE_DIR)),
            "type": "Plugin",
            "location": "plugins/",
            "valid": is_valid,
            "error": error,
            "category": category
        })

    return items

def scan_precommit_hooks():
    """Parse pre-commit config and list hooks."""
    items = []

    if not PRECOMMIT_CONFIG.exists():
        return items

    try:
        with open(PRECOMMIT_CONFIG, 'r') as f:
            config = yaml.safe_load(f)

        if not config or 'repos' not in config:
            return items

        for repo in config.get('repos', []):
            for hook in repo.get('hooks', []):
                hook_id = hook.get('id', 'unknown')
                entry = hook.get('entry', '')

                # Check if hook points to a local file
                is_valid = True
                error = None

                if entry.startswith('python3 tools/') or entry.startswith('python tools/'):
                    tool_path = entry.split()[1] if len(entry.split()) > 1 else ''
                    full_path = BASE_DIR / tool_path
                    if not full_path.exists():
                        is_valid = False
                        error = f"Entry file not found: {tool_path}"
                elif entry.startswith('bash tools/'):
                    tool_path = entry.split()[1] if len(entry.split()) > 1 else ''
                    full_path = BASE_DIR / tool_path
                    if not full_path.exists():
                        is_valid = False
                        error = f"Entry file not found: {tool_path}"

                items.append({
                    "name": hook_id,
                    "path": f".pre-commit-config.yaml#{hook_id}",
                    "type": "Hook",
                    "location": ".pre-commit-config.yaml",
                    "valid": is_valid,
                    "error": error,
                    "category": "Pre-commit Hooks",
                    "entry": entry
                })

    except Exception as e:
        print(f"Warning: Could not parse pre-commit config: {e}")

    return items

def scan_src():
    """Scan src/ directory for Python source files."""
    items = []

    if not SRC_DIR.exists():
        return items

    for filepath in SRC_DIR.glob("**/*.py"):
        if filepath.name == "__init__.py":
            continue
        # Skip excluded directories
        if any(excluded in filepath.parts for excluded in EXCLUDE_DIRS):
            continue

        is_valid, error = check_python_syntax(filepath)

        # Categorize based on path
        rel_path = filepath.relative_to(SRC_DIR)
        parts = rel_path.parts
        if len(parts) > 1:
            category = f"Source: {parts[0]}"
        else:
            category = "Source: root"

        items.append({
            "name": filepath.name,
            "path": str(filepath.relative_to(BASE_DIR)),
            "type": "Source",
            "location": "src/",
            "valid": is_valid,
            "error": error,
            "category": category
        })

    return items

def scan_templates():
    """Scan templates/ directory for Jinja templates."""
    items = []

    if not TEMPLATES_DIR.exists():
        return items

    # Scan for Jinja files
    for pattern in ["**/*.j2", "**/*.jinja", "**/*.jinja2"]:
        for filepath in TEMPLATES_DIR.glob(pattern):
            if any(excluded in filepath.parts for excluded in EXCLUDE_DIRS):
                continue

            is_valid, error = check_jinja_syntax(filepath)

            items.append({
                "name": filepath.name,
                "path": str(filepath.relative_to(BASE_DIR)),
                "type": "Template",
                "location": "templates/",
                "valid": is_valid,
                "error": error,
                "category": "Jinja Templates"
            })

    # Also scan for YAML templates in templates/
    for pattern in ["**/*.yaml", "**/*.yml"]:
        for filepath in TEMPLATES_DIR.glob(pattern):
            if any(excluded in filepath.parts for excluded in EXCLUDE_DIRS):
                continue

            is_valid, error = check_yaml_syntax(filepath)

            items.append({
                "name": filepath.name,
                "path": str(filepath.relative_to(BASE_DIR)),
                "type": "Template",
                "location": "templates/",
                "valid": is_valid,
                "error": error,
                "category": "YAML Templates"
            })

    return items

def scan_dockerfiles():
    """Scan for Dockerfiles and docker-compose files."""
    items = []

    # Scan for Dockerfiles in root and subdirs
    for filepath in BASE_DIR.glob("**/Dockerfile*"):
        if any(excluded in filepath.parts for excluded in EXCLUDE_DIRS):
            continue

        is_valid, error = check_dockerfile_syntax(filepath)

        # Determine location
        if filepath.parent == BASE_DIR:
            location = "root"
        else:
            location = str(filepath.parent.relative_to(BASE_DIR)) + "/"

        items.append({
            "name": filepath.name,
            "path": str(filepath.relative_to(BASE_DIR)),
            "type": "Docker",
            "location": location,
            "valid": is_valid,
            "error": error,
            "category": "Dockerfiles"
        })

    # Scan for docker-compose files
    for pattern in ["**/docker-compose*.yml", "**/docker-compose*.yaml"]:
        for filepath in BASE_DIR.glob(pattern):
            if any(excluded in filepath.parts for excluded in EXCLUDE_DIRS):
                continue

            is_valid, error = check_yaml_syntax(filepath)

            if filepath.parent == BASE_DIR:
                location = "root"
            else:
                location = str(filepath.parent.relative_to(BASE_DIR)) + "/"

            items.append({
                "name": filepath.name,
                "path": str(filepath.relative_to(BASE_DIR)),
                "type": "Docker",
                "location": location,
                "valid": is_valid,
                "error": error,
                "category": "Docker Compose"
            })

    return items

def scan_makefiles():
    """Scan for Makefiles."""
    items = []

    for pattern in ["**/Makefile", "**/makefile", "**/*.mk"]:
        for filepath in BASE_DIR.glob(pattern):
            if any(excluded in filepath.parts for excluded in EXCLUDE_DIRS):
                continue

            is_valid, error = check_makefile_syntax(filepath)

            if filepath.parent == BASE_DIR:
                location = "root"
            else:
                location = str(filepath.parent.relative_to(BASE_DIR)) + "/"

            items.append({
                "name": filepath.name,
                "path": str(filepath.relative_to(BASE_DIR)),
                "type": "Makefile",
                "location": location,
                "valid": is_valid,
                "error": error,
                "category": "Build Scripts"
            })

    return items

def scan_all_shell_scripts():
    """Scan for shell scripts anywhere in the repo (not already covered)."""
    items = []
    already_scanned = set()

    # Track what's already scanned by other functions
    for filepath in TOOLS_DIR.glob("*.sh"):
        already_scanned.add(filepath)
    if SCRIPTS_DIR.exists():
        for filepath in SCRIPTS_DIR.glob("**/*.sh"):
            already_scanned.add(filepath)

    # Scan all .sh files not already covered
    for filepath in BASE_DIR.glob("**/*.sh"):
        if filepath in already_scanned:
            continue
        if any(excluded in filepath.parts for excluded in EXCLUDE_DIRS):
            continue

        is_valid, error = check_shell_syntax(filepath)

        if filepath.parent == BASE_DIR:
            location = "root"
        else:
            location = str(filepath.parent.relative_to(BASE_DIR)) + "/"

        items.append({
            "name": filepath.name,
            "path": str(filepath.relative_to(BASE_DIR)),
            "type": "Shell",
            "location": location,
            "valid": is_valid,
            "error": error,
            "category": "Shell Scripts (Other)"
        })

    return items

def check_code_file(filepath, lang_type):
    """Basic validation for code files - check if readable and non-empty."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        if not content.strip():
            return False, "Empty file"
        return True, None
    except Exception as e:
        return False, str(e)

def scan_all_code_files():
    """Scan for ALL programming language files in the repo."""
    items = []
    already_scanned_paths = set()

    # Collect paths already scanned by other functions
    # Python in tools/, scripts/, plugins/, src/
    for filepath in TOOLS_DIR.glob("**/*.py"):
        already_scanned_paths.add(filepath)
    if SCRIPTS_DIR.exists():
        for filepath in SCRIPTS_DIR.glob("**/*.py"):
            already_scanned_paths.add(filepath)
    if PLUGINS_DIR.exists():
        for filepath in PLUGINS_DIR.glob("**/*.py"):
            already_scanned_paths.add(filepath)
    if SRC_DIR.exists():
        for filepath in SRC_DIR.glob("**/*.py"):
            already_scanned_paths.add(filepath)

    # Shell scripts
    for filepath in BASE_DIR.glob("**/*.sh"):
        already_scanned_paths.add(filepath)

    # Workflows
    if WORKFLOWS_DIR.exists():
        for filepath in WORKFLOWS_DIR.glob("**/*.yml"):
            already_scanned_paths.add(filepath)
        for filepath in WORKFLOWS_DIR.glob("**/*.yaml"):
            already_scanned_paths.add(filepath)

    # Templates
    if TEMPLATES_DIR.exists():
        for pattern in ["**/*.j2", "**/*.jinja", "**/*.jinja2", "**/*.yaml", "**/*.yml"]:
            for filepath in TEMPLATES_DIR.glob(pattern):
                already_scanned_paths.add(filepath)

    # Now scan for ALL code extensions not already covered
    for ext, (lang_name, lang_type) in CODE_EXTENSIONS.items():
        # Skip extensions already handled by other scanners
        if ext in ['.py', '.sh']:
            continue

        for filepath in BASE_DIR.glob(f"**/*{ext}"):
            if filepath in already_scanned_paths:
                continue
            if any(excluded in filepath.parts for excluded in EXCLUDE_DIRS):
                continue
            if filepath.name == "__init__.py":
                continue

            # Use appropriate validator
            if lang_type == 'python':
                is_valid, error = check_python_syntax(filepath)
            elif lang_type == 'shell':
                is_valid, error = check_shell_syntax(filepath)
            elif lang_type == 'lisp':
                is_valid, error = check_lisp_syntax(filepath)
            elif lang_type == 'javascript':
                is_valid, error = check_javascript_syntax(filepath)
            else:
                is_valid, error = check_code_file(filepath, lang_type)

            if filepath.parent == BASE_DIR:
                location = "root"
            else:
                location = str(filepath.parent.relative_to(BASE_DIR)) + "/"

            items.append({
                "name": filepath.name,
                "path": str(filepath.relative_to(BASE_DIR)),
                "type": lang_name,
                "location": location,
                "valid": is_valid,
                "error": error,
                "category": f"Code: {lang_name}"
            })

    return items

def check_lisp_syntax(filepath):
    """Check Lisp/AutoLISP syntax - balanced parentheses."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Remove comments (lines starting with ;)
        lines = [l for l in content.split('\n') if not l.strip().startswith(';')]
        code = '\n'.join(lines)

        # Check balanced parentheses
        open_count = code.count('(')
        close_count = code.count(')')
        if open_count != close_count:
            return False, f"Unbalanced parens: {open_count} open, {close_count} close"

        return True, None
    except Exception as e:
        return False, str(e)

def check_javascript_syntax(filepath):
    """Basic JavaScript syntax check."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Check balanced braces
        open_braces = content.count('{')
        close_braces = content.count('}')
        if open_braces != close_braces:
            return False, f"Unbalanced braces: {open_braces} open, {close_braces} close"

        # Check balanced brackets
        open_brackets = content.count('[')
        close_brackets = content.count(']')
        if open_brackets != close_brackets:
            return False, f"Unbalanced brackets: {open_brackets} open, {close_brackets} close"

        return True, None
    except Exception as e:
        return False, str(e)

def scan_all():
    """Scan all locations."""
    all_items = {
        "tools": scan_tools(),
        "scripts": scan_scripts(),
        "workflows": scan_workflows(),
        "plugins": scan_plugins(),
        "hooks": scan_precommit_hooks(),
        "src": scan_src(),
        "templates": scan_templates(),
        "docker": scan_dockerfiles(),
        "makefiles": scan_makefiles(),
        "other_shell": scan_all_shell_scripts(),
        "all_code": scan_all_code_files(),  # All other programming languages
    }
    return all_items

def calculate_stats(all_items):
    """Calculate statistics from all scanned items."""
    stats = {
        "total": 0,
        "working": 0,
        "broken": 0,
        "by_location": defaultdict(lambda: {"total": 0, "working": 0, "broken": 0}),
        "by_type": defaultdict(int),
        "categories": defaultdict(lambda: {"total": 0, "working": 0, "broken": 0}),
        "broken_items": []
    }

    for location, items in all_items.items():
        for item in items:
            stats["total"] += 1
            stats["by_type"][item["type"]] += 1
            stats["by_location"][item["location"]]["total"] += 1
            stats["categories"][item["category"]]["total"] += 1

            if item["valid"]:
                stats["working"] += 1
                stats["by_location"][item["location"]]["working"] += 1
                stats["categories"][item["category"]]["working"] += 1
            else:
                stats["broken"] += 1
                stats["by_location"][item["location"]]["broken"] += 1
                stats["categories"][item["category"]]["broken"] += 1
                stats["broken_items"].append({
                    "name": item["name"],
                    "path": item["path"],
                    "location": item["location"],
                    "category": item["category"],
                    "error": item["error"]
                })

    return stats

def generate_progress_bar(percentage, width=20):
    """Generate ASCII progress bar."""
    filled = int(width * percentage / 100)
    empty = width - filled
    return f"[{'█' * filled}{'░' * empty}]"

def update_catalog(stats, all_items, check_only=False, verbose=False):
    """Update the TOOLS_CATALOG.md file."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Calculate percentage
    if stats["total"] > 0:
        percentage = (stats["working"] / stats["total"]) * 100
    else:
        percentage = 0

    progress_bar = generate_progress_bar(percentage)

    # Generate stats section
    stats_section = f"""<!-- STATS_START -->
## Catalog Statistics

> **Last Updated:** {now}

| Total | Working | Broken | Progress |
|-------|---------|--------|----------|
| {stats['total']} | {stats['working']} | {stats['broken']} | {progress_bar} {percentage:.1f}% |

### By Location

| Location | Total | Working | Broken | % |
|----------|-------|---------|--------|---|
"""
    for loc in sorted(stats["by_location"].keys()):
        data = stats["by_location"][loc]
        loc_pct = (data["working"] / data["total"] * 100) if data["total"] > 0 else 0
        status = "✅" if data["broken"] == 0 else "🔴"
        stats_section += f"| {status} `{loc}` | {data['total']} | {data['working']} | {data['broken']} | {loc_pct:.0f}% |\n"

    stats_section += """
### By Type

| Type | Count |
|------|-------|
"""
    for typ in sorted(stats["by_type"].keys()):
        stats_section += f"| {typ} | {stats['by_type'][typ]} |\n"

    stats_section += """
<details>
<summary>By Category (click to expand)</summary>

| Category | Total | Working | Broken | % |
|----------|-------|---------|--------|---|
"""

    for cat_name in sorted(stats["categories"].keys()):
        cat = stats["categories"][cat_name]
        cat_pct = (cat["working"] / cat["total"] * 100) if cat["total"] > 0 else 0
        status = "✅" if cat["broken"] == 0 else "🔴"
        stats_section += f"| {status} {cat_name} | {cat['total']} | {cat['working']} | {cat['broken']} | {cat_pct:.0f}% |\n"

    # Category health status
    healthy = [cat for cat, data in stats["categories"].items() if data["broken"] == 0]
    needs_attention = [cat for cat, data in stats["categories"].items() if data["broken"] > 0]

    stats_section += """
### Category Health Status

"""
    if healthy:
        stats_section += f"**Healthy (100%):** {len(healthy)} categories\n\n"

    if needs_attention:
        stats_section += "**Needs Attention:**\n| Category | Progress | Broken |\n|----------|----------|--------|\n"
        for cat in sorted(needs_attention, key=lambda x: stats["categories"][x]["broken"], reverse=True):
            data = stats["categories"][cat]
            pct = (data["working"] / data["total"] * 100) if data["total"] > 0 else 0
            stats_section += f"| {cat} | {pct:.0f}% | {data['broken']} |\n"
    else:
        stats_section += "**Needs Attention:** None\n"

    stats_section += """
</details>

<!-- STATS_END -->"""

    # Generate broken items section
    broken_section = """<!-- BROKEN_ITEMS_START -->
## Broken Items

> **Purpose:** Quick reference for items that need fixing
> **Usage:** If an item appears here, it has syntax errors or failed validation

| Item | Location | Category | Error | Last Checked |
|------|----------|----------|-------|--------------|
"""

    if stats["broken_items"]:
        for item in stats["broken_items"]:
            error_short = item["error"][:40] + "..." if item["error"] and len(item["error"]) > 40 else (item["error"] or "Unknown")
            broken_section += f"| `{item['name']}` | {item['location']} | {item['category']} | {error_short} | {now[:10]} |\n"
    else:
        broken_section += "| *None* | - | - | - | - |\n"

    broken_section += "\n<!-- BROKEN_ITEMS_END -->"

    # Generate full listing section
    listing_section = """<!-- FULL_LISTING_START -->
## Full Inventory

> All actionable items in the repository: tools, scripts, workflows, source code, templates, Docker, and more

### Safety Levels (for Python/Shell tools)

| Level | Test Method | Description |
|-------|-------------|-------------|
| SAFE | `--help` | Read-only tools, validators, checkers |
| DRY_RUN | `--dry-run` | Has safe execution flag |
| SANDBOXED | temp dir | File-modifying tools (run in isolation) |
| MANUAL | skip | Dangerous (orchestrators, daemons, external) |
| *Italics* | auto | Not in config, auto-classified by patterns |

"""

    # Group items by type for display
    items_by_type = defaultdict(list)

    for location, items in all_items.items():
        for item in items:
            items_by_type[item["type"]].append(item)

    # Define display order and labels for types
    type_display = [
        ("Python", "Python Tools & Scripts"),
        ("Shell", "Shell Scripts"),
        ("Workflow", "GitHub Workflows"),
        ("Source", "Source Code (src/)"),
        ("Template", "Templates"),
        ("Plugin", "Plugins"),
        ("Docker", "Docker Files"),
        ("Makefile", "Makefiles"),
        ("Hook", "Pre-commit Hooks"),
    ]

    for type_key, type_label in type_display:
        if items_by_type[type_key]:
            count = len(items_by_type[type_key])

            # Only show Safety Level for Python and Shell (testable tools)
            if type_key in ["Python", "Shell"]:
                listing_section += f"""<details>
<summary>{type_label} ({count} items)</summary>

| Name | Location | Category | Safety | Status |
|------|----------|----------|--------|--------|
"""
                for item in sorted(items_by_type[type_key], key=lambda x: x["name"]):
                    status = "✅" if item["valid"] else "❌"
                    safety = get_safety_level(item["name"])
                    # Shorten for display
                    if safety.startswith("AUTO:"):
                        safety_display = f"*{safety[5:]}*"  # Italics for auto
                    else:
                        safety_display = safety
                    listing_section += f"| `{item['name']}` | {item['location']} | {item['category']} | {safety_display} | {status} |\n"
            else:
                listing_section += f"""<details>
<summary>{type_label} ({count} items)</summary>

| Name | Location | Category | Status |
|------|----------|----------|--------|
"""
                for item in sorted(items_by_type[type_key], key=lambda x: x["name"]):
                    status = "✅" if item["valid"] else "❌"
                    listing_section += f"| `{item['name']}` | {item['location']} | {item['category']} | {status} |\n"
            listing_section += "\n</details>\n\n"

    listing_section += "<!-- FULL_LISTING_END -->"

    # Generate tool status section
    status_section = f"""<!-- TOOL_STATUS_START -->
<details>
<summary>Sync Status (click to expand)</summary>

| Metric | Value |
|--------|-------|
| Last Run | {now} |
| Items Scanned | {stats['total']} |
| Passed Validation | {stats['working']} |
| Failed Validation | {stats['broken']} |
| Locations | {len(stats['by_location'])} |
| Categories | {len(stats['categories'])} |

**Validation Methods:**
- Python: `py_compile`
- Shell: `bash -n`
- YAML/Workflows: `yaml.safe_load`
- Jinja: Brace matching
- Dockerfile: Instruction validation
- Makefile: Target detection
- Hooks: Entry file existence

</details>
<!-- TOOL_STATUS_END -->"""

    if verbose:
        print(f"\n{'='*60}")
        print(f"TOOLS CATALOG SCAN RESULTS")
        print(f"{'='*60}")
        print(f"\nTotal Items: {stats['total']}")
        print(f"Working: {stats['working']}")
        print(f"Broken: {stats['broken']}")
        print(f"Pass Rate: {percentage:.1f}%")
        print(f"\nBy Location:")
        for loc, data in sorted(stats["by_location"].items()):
            status = "✅" if data["broken"] == 0 else "❌"
            print(f"  {status} {loc}: {data['working']}/{data['total']}")
        print(f"\nBy Type:")
        for typ, count in sorted(stats["by_type"].items()):
            print(f"  {typ}: {count}")
        print(f"\nCategories: {len(stats['categories'])}")

        if stats["broken_items"]:
            print(f"\n❌ Broken Items ({len(stats['broken_items'])}):")
            for item in stats["broken_items"]:
                print(f"  - {item['path']}: {item['error']}")

    if check_only:
        print(f"\n✅ Check complete: {stats['working']}/{stats['total']} items passing ({percentage:.1f}%)")
        if stats["broken_items"]:
            print(f"❌ {len(stats['broken_items'])} broken item(s)")
            for item in stats["broken_items"]:
                print(f"   - {item['path']}")
        return stats["broken"] == 0

    # Read existing catalog
    if CATALOG_PATH.exists():
        content = CATALOG_PATH.read_text()

        # Replace stats section
        content = re.sub(
            r'<!-- STATS_START -->.*?<!-- STATS_END -->',
            stats_section,
            content,
            flags=re.DOTALL
        )

        # Replace broken items section
        content = re.sub(
            r'<!-- BROKEN_ITEMS_START -->.*?<!-- BROKEN_ITEMS_END -->',
            broken_section,
            content,
            flags=re.DOTALL
        )

        # Also handle old marker name for backwards compatibility
        content = re.sub(
            r'<!-- BROKEN_TOOLS_START -->.*?<!-- BROKEN_TOOLS_END -->',
            broken_section.replace("BROKEN_ITEMS", "BROKEN_TOOLS"),
            content,
            flags=re.DOTALL
        )

        # Replace tool status section
        content = re.sub(
            r'<!-- TOOL_STATUS_START -->.*?<!-- TOOL_STATUS_END -->',
            status_section,
            content,
            flags=re.DOTALL
        )

        # Replace or add full listing section
        if '<!-- FULL_LISTING_START -->' in content:
            content = re.sub(
                r'<!-- FULL_LISTING_START -->.*?<!-- FULL_LISTING_END -->',
                listing_section,
                content,
                flags=re.DOTALL
            )
        else:
            # Add before TOOL_STATUS if not present
            content = content.replace(
                '<!-- TOOL_STATUS_START -->',
                listing_section + '\n\n<!-- TOOL_STATUS_START -->'
            )

        CATALOG_PATH.write_text(content)
        print(f"✅ Updated TOOLS_CATALOG.md: {stats['working']}/{stats['total']} items passing ({percentage:.1f}%)")
    else:
        print(f"❌ TOOLS_CATALOG.md not found at {CATALOG_PATH}")
        return False

    return stats["broken"] == 0

def main():
    """Main entry point."""
    check_only = "--check" in sys.argv
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    if verbose:
        print(f"Scanning all executable items in {BASE_DIR}...")
        print(f"  - tools/")
        print(f"  - scripts/")
        print(f"  - .github/workflows/")
        print(f"  - plugins/")
        print(f"  - .pre-commit-config.yaml")

    all_items = scan_all()
    stats = calculate_stats(all_items)
    success = update_catalog(stats, all_items, check_only=check_only, verbose=verbose)

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
