#!/usr/bin/env python3
"""
Orchestrator - Core Multi-Agent Coordination System
========================================================
Issues: Z-20 (Core MVP), Z-21 (PlanAuditor), Z-22 (7 Dimension Critics)
Version: 1.1.0

This is the foundation for autonomous agent operation. It coordinates
13 agents via the Anthropic API:
  - 1 Coordinator: PM (Opus)
  - 2 Executors: Builder, Planner (Sonnet)
  - 3 Core Critics: Orchestrator (Opus), FixVerifier, PlanAuditor (Sonnet)
  - 7 Dimension Critics: Dependencies, Effort, ExecutionReady, Verification,
                         ACL (Haiku) + SpecFit, Security (Sonnet)

Usage:
    # Single agent test
    python3 tools/orchestrator.py --agent fix-verifier --task "Verify Lane G"

    # Autonomous loop
    python3 tools/orchestrator.py --cycles 10 --budget 50

    # List agents
    python3 tools/orchestrator.py --list-agents

    # Help
    python3 tools/orchestrator.py --help
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any

# Optional imports with graceful fallback
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    print("Warning: PyYAML not installed. Run: pip3 install pyyaml")

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    print("Warning: anthropic not installed. Run: pip3 install anthropic")

# =============================================================================
# CONFIGURATION
# =============================================================================

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
AGENTS_DIR = PROJECT_ROOT / ".claude" / "agents"
LOGBOOK_DIR = PROJECT_ROOT / "LogBook" / "orchestrator"
STATE_FILE = LOGBOOK_DIR / "ORCHESTRATOR_STATE.yaml"
ENV_FILE = PROJECT_ROOT / ".env"

# Model IDs (optimized per Z-20, Z-22, Z-27 specs)
MODELS = {
    "opus": "claude-opus-4-20250514",
    "sonnet": "claude-sonnet-4-20250514",
    "haiku": "claude-haiku-3-5-20241022",
}

# Default limits
DEFAULT_BUDGET_USD = 10.0
DEFAULT_MAX_CYCLES = 10
MIN_DELAY_SECONDS = 2.0
MAX_TOKENS_PER_REQUEST = 4096

# =============================================================================
# AGENT DEFINITIONS
# =============================================================================

class AgentRole(Enum):
    """Agent role categories"""
    COORDINATOR = "coordinator"
    EXECUTOR = "executor"
    CRITIC = "critic"
    DIMENSION_CRITIC = "dimension-critic"

@dataclass
class AgentDefinition:
    """Definition of an agent"""
    name: str
    system_prompt_file: Path
    model: str
    description: str
    role: AgentRole
    tools: List[str] = field(default_factory=list)
    write_boundaries: List[str] = field(default_factory=list)

# MVP Agent Registry (5 core agents)
AGENT_REGISTRY: Dict[str, AgentDefinition] = {
    # Core Coordinator (Opus for complex decisions)
    "pm": AgentDefinition(
        name="Project-Manager",
        system_prompt_file=Path(".claude/agents/Project-Manager-final.md"),
        model=MODELS["opus"],
        description="Control tower - coordinates agents, approves work, manages priorities",
        role=AgentRole.COORDINATOR,
        tools=["read", "write", "bash"],
        write_boundaries=["LogBook/pm/", "issues/"]
    ),

    # Core Executors (Sonnet for balanced performance)
    "builder": AgentDefinition(
        name="Builder",
        system_prompt_file=Path(".claude/agents/Builder.md"),
        model=MODELS["sonnet"],
        description="Implements ONE task at a time with focused execution",
        role=AgentRole.EXECUTOR,
        tools=["read", "write", "edit", "bash"],
        write_boundaries=["src/", "tools/", "templates/", ".task/"]
    ),
    "planner": AgentDefinition(
        name="Planner",
        system_prompt_file=Path(".claude/agents/Planner.md"),
        model=MODELS["sonnet"],
        description="Decomposes tasks into atomic units",
        role=AgentRole.EXECUTOR,
        tools=["read", "write", "glob", "grep"],
        write_boundaries=["LogBook/progress/plans/", ".task/"]
    ),

    # Critics (Opus for orchestrator, Sonnet for verification)
    "critic": AgentDefinition(
        name="Critic-Orchestrator",
        system_prompt_file=Path(".claude/agents/Critic-Orchestrator.md"),
        model=MODELS["opus"],
        description="Coordinates task evaluation across all dimensions",
        role=AgentRole.CRITIC,
        tools=["read", "glob", "grep", "bash"],
        write_boundaries=["LogBook/critic/"]
    ),
    "fix-verifier": AgentDefinition(
        name="Critic-FixVerifier",
        system_prompt_file=Path(".claude/agents/Critic-FixVerifier.md"),
        model=MODELS["sonnet"],
        description="Verifies RESOLVED issues with 6-level verification protocol",
        role=AgentRole.CRITIC,
        tools=["read", "bash", "glob", "grep"],
        write_boundaries=["LogBook/verification/", "issues/"]
    ),

    # === Z-21: PlanAuditor Agent ===
    "plan-auditor": AgentDefinition(
        name="Critic-PlanAuditor",
        system_prompt_file=Path(".claude/agents/Critic-PlanAuditor.md"),
        model=MODELS["sonnet"],
        description="Reviews action plans before Builder executes - APPROVE/REJECT/REVISE",
        role=AgentRole.CRITIC,
        tools=["read", "glob", "grep"],
        write_boundaries=["LogBook/critic/"]
    ),

    # === Z-22: 7 Dimension Critics ===
    # Haiku for simple validation, Sonnet for complex reasoning

    "critic-dependencies": AgentDefinition(
        name="Critic-Dependencies",
        system_prompt_file=Path(".claude/agents/Critic-Dependencies.md"),
        model=MODELS["haiku"],  # Simple dependency check
        description="Validates all dependencies are satisfied",
        role=AgentRole.DIMENSION_CRITIC,
        tools=["read", "glob"],
        write_boundaries=[]
    ),
    "critic-effort": AgentDefinition(
        name="Critic-Effort",
        system_prompt_file=Path(".claude/agents/Critic-Effort.md"),
        model=MODELS["haiku"],  # Format validation
        description="Validates effort estimates were accurate",
        role=AgentRole.DIMENSION_CRITIC,
        tools=["read"],
        write_boundaries=[]
    ),
    "critic-execution-ready": AgentDefinition(
        name="Critic-ExecutionReady",
        system_prompt_file=Path(".claude/agents/Critic-ExecutionReady.md"),
        model=MODELS["haiku"],  # Field presence check
        description="Validates task is ready to execute",
        role=AgentRole.DIMENSION_CRITIC,
        tools=["read", "bash"],
        write_boundaries=[]
    ),
    "critic-spec-fit": AgentDefinition(
        name="Critic-SpecFit",
        system_prompt_file=Path(".claude/agents/Critic-SpecFit.md"),
        model=MODELS["sonnet"],  # Needs comprehension
        description="Validates task matches specification",
        role=AgentRole.DIMENSION_CRITIC,
        tools=["read", "grep"],
        write_boundaries=[]
    ),
    "critic-verification": AgentDefinition(
        name="Critic-Verification",
        system_prompt_file=Path(".claude/agents/Critic-Verification.md"),
        model=MODELS["haiku"],  # Syntax validation
        description="Validates task can be tested",
        role=AgentRole.DIMENSION_CRITIC,
        tools=["read", "bash"],
        write_boundaries=[]
    ),
    "critic-security": AgentDefinition(
        name="Critic-SecurityPolicy",
        system_prompt_file=Path(".claude/agents/Critic-SecurityPolicy.md"),
        model=MODELS["sonnet"],  # Security needs understanding
        description="Validates task follows security policies",
        role=AgentRole.DIMENSION_CRITIC,
        tools=["read", "grep"],
        write_boundaries=[]
    ),
    "critic-acl": AgentDefinition(
        name="Critic-ACL",
        system_prompt_file=Path(".claude/agents/Critic-ACL.md"),
        model=MODELS["haiku"],  # Boundary checking
        description="Validates task respects write boundaries",
        role=AgentRole.DIMENSION_CRITIC,
        tools=["read", "grep"],
        write_boundaries=[]
    ),
}

# =============================================================================
# SAFETY CONTROLS
# =============================================================================

# Forbidden patterns that should never appear in agent output
FORBIDDEN_PATTERNS = [
    r"rm\s+-rf\s+/",
    r"rm\s+-rf\s+\*",
    r"DROP\s+TABLE",
    r"DROP\s+DATABASE",
    r"DELETE\s+FROM\s+\w+\s*;",
    r">\s*/dev/",
    r"chmod\s+777",
    r"curl.*\|\s*bash",
    r"wget.*\|\s*sh",
    r"ANTHROPIC_API_KEY\s*=",
    r"api_key\s*=\s*['\"]sk-",
]

def check_forbidden_patterns(text: str) -> List[str]:
    """Check text for forbidden patterns, return list of matches"""
    matches = []
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            matches.append(pattern)
    return matches

# =============================================================================
# STATE MANAGEMENT
# =============================================================================

@dataclass
class AgentRun:
    """Record of a single agent run"""
    agent: str
    task: str
    started_at: str
    completed_at: Optional[str] = None
    status: str = "running"
    tokens_used: int = 0
    cost_usd: float = 0.0
    result: Optional[str] = None
    error: Optional[str] = None

@dataclass
class OrchestratorState:
    """Persistent state of the orchestrator"""
    session_id: str
    started_at: str
    last_checkpoint: str
    total_runs: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    budget_limit_usd: float = DEFAULT_BUDGET_USD
    active_agents: Dict[str, Any] = field(default_factory=dict)
    completed_runs: List[Dict] = field(default_factory=list)
    pending_tasks: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "last_checkpoint": self.last_checkpoint,
            "total_runs": self.total_runs,
            "total_tokens": self.total_tokens,
            "total_cost_usd": self.total_cost_usd,
            "budget_limit_usd": self.budget_limit_usd,
            "active_agents": self.active_agents,
            "completed_runs": self.completed_runs,
            "pending_tasks": self.pending_tasks,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OrchestratorState":
        return cls(**data)

def load_state() -> Optional[OrchestratorState]:
    """Load orchestrator state from file"""
    if not YAML_AVAILABLE:
        return None
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            data = yaml.safe_load(f)
            if data:
                return OrchestratorState.from_dict(data)
    return None

def _atomic_write_text(path: Path, content: str) -> None:
    """Atomically write text — temp file + os.replace (POSIX-atomic).

    Per-process temp filename so parallel writers don't collide on the
    intermediate file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f"{path.suffix}.tmp.{os.getpid()}")
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except FileNotFoundError:
                pass
        raise


def save_state(state: OrchestratorState) -> None:
    """Save orchestrator state to file (atomic: temp + rename)"""
    if not YAML_AVAILABLE:
        print("Warning: Cannot save state - PyYAML not installed")
        return

    LOGBOOK_DIR.mkdir(parents=True, exist_ok=True)
    state.last_checkpoint = datetime.now().isoformat()

    serialized = yaml.dump(state.to_dict(), default_flow_style=False)
    _atomic_write_text(STATE_FILE, serialized)

# =============================================================================
# COST TRACKING
# =============================================================================

# Pricing per 1M tokens (as of late 2024/early 2025)
PRICING = {
    MODELS["opus"]: {"input": 15.0, "output": 75.0},
    MODELS["sonnet"]: {"input": 3.0, "output": 15.0},
    MODELS["haiku"]: {"input": 0.25, "output": 1.25},
}

def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate cost in USD for a request"""
    pricing = PRICING.get(model, PRICING[MODELS["sonnet"]])
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return input_cost + output_cost

# =============================================================================
# ORCHESTRATOR CLASS
# =============================================================================

class Orchestrator:
    """Main orchestrator class for coordinating agents"""

    def __init__(self, budget_limit: float = DEFAULT_BUDGET_USD, verbose: bool = False):
        self.budget_limit = budget_limit
        self.verbose = verbose
        self.client = None
        self.state = None
        self.logger = self._setup_logging()

        # Initialize API client
        if ANTHROPIC_AVAILABLE:
            api_key = self._load_api_key()
            if api_key:
                self.client = anthropic.Anthropic(api_key=api_key)
            else:
                self.logger.warning("No API key found. Set ANTHROPIC_API_KEY in .env")

        # Initialize or load state
        self._init_state()

    def _setup_logging(self) -> logging.Logger:
        """Configure logging"""
        LOGBOOK_DIR.mkdir(parents=True, exist_ok=True)

        logger = logging.getLogger("orchestrator")
        logger.setLevel(logging.DEBUG if self.verbose else logging.INFO)

        # Console handler
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(console)

        # File handler
        log_file = LOGBOOK_DIR / f"ORCH-{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s"
        ))
        logger.addHandler(file_handler)

        return logger

    def _load_api_key(self) -> Optional[str]:
        """Load API key from environment or .env file"""
        # Check environment first
        key = os.environ.get("ANTHROPIC_API_KEY")
        if key:
            return key

        # Try .env file
        if ENV_FILE.exists():
            with open(ENV_FILE) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("ANTHROPIC_API_KEY="):
                        return line.split("=", 1)[1].strip().strip('"\'')

        return None

    def _init_state(self) -> None:
        """Initialize or load state"""
        existing = load_state()
        if existing:
            self.state = existing
            self.state.budget_limit_usd = self.budget_limit
            self.logger.info(f"Resumed session: {self.state.session_id}")
        else:
            session_id = f"ORCH-{datetime.now().strftime('%Y-%m-%d-%H%M%S')}"
            self.state = OrchestratorState(
                session_id=session_id,
                started_at=datetime.now().isoformat(),
                last_checkpoint=datetime.now().isoformat(),
                budget_limit_usd=self.budget_limit
            )
            save_state(self.state)
            self.logger.info(f"Started new session: {session_id}")

    def _load_system_prompt(self, agent_key: str) -> str:
        """Load system prompt from agent's markdown file"""
        agent = AGENT_REGISTRY.get(agent_key)
        if not agent:
            raise ValueError(f"Unknown agent: {agent_key}")

        prompt_file = PROJECT_ROOT / agent.system_prompt_file
        if not prompt_file.exists():
            raise FileNotFoundError(f"Agent prompt not found: {prompt_file}")

        return prompt_file.read_text()

    def check_budget(self) -> bool:
        """Check if we're within budget"""
        return self.state.total_cost_usd < self.budget_limit

    def run_agent(self, agent_key: str, task: str) -> AgentRun:
        """Run a single agent with a task"""

        # Validate agent
        if agent_key not in AGENT_REGISTRY:
            raise ValueError(f"Unknown agent: {agent_key}. Available: {list(AGENT_REGISTRY.keys())}")

        agent = AGENT_REGISTRY[agent_key]

        # Check budget
        if not self.check_budget():
            raise RuntimeError(f"Budget exhausted: ${self.state.total_cost_usd:.2f} / ${self.budget_limit:.2f}")

        # Check API client
        if not self.client:
            raise RuntimeError("Anthropic client not initialized. Check API key.")

        # Create run record
        run = AgentRun(
            agent=agent_key,
            task=task,
            started_at=datetime.now().isoformat()
        )

        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"Running: {agent.name}")
        self.logger.info(f"Model: {agent.model}")
        self.logger.info(f"Task: {task[:100]}...")
        self.logger.info(f"{'='*60}")

        try:
            # Load system prompt
            system_prompt = self._load_system_prompt(agent_key)

            # Make API call
            response = self.client.messages.create(
                model=agent.model,
                max_tokens=MAX_TOKENS_PER_REQUEST,
                system=system_prompt,
                messages=[{"role": "user", "content": task}]
            )

            # Extract response
            result_text = response.content[0].text if response.content else ""

            # Safety check
            forbidden = check_forbidden_patterns(result_text)
            if forbidden:
                self.logger.warning(f"BLOCKED: Forbidden patterns detected: {forbidden}")
                run.status = "blocked"
                run.error = f"Forbidden patterns: {forbidden}"
                run.result = "[BLOCKED - Safety violation]"
            else:
                run.status = "completed"
                run.result = result_text

            # Track usage
            run.tokens_used = response.usage.input_tokens + response.usage.output_tokens
            run.cost_usd = calculate_cost(
                agent.model,
                response.usage.input_tokens,
                response.usage.output_tokens
            )

            # Update state
            self.state.total_runs += 1
            self.state.total_tokens += run.tokens_used
            self.state.total_cost_usd += run.cost_usd

            self.logger.info(f"Tokens: {run.tokens_used:,} | Cost: ${run.cost_usd:.4f}")
            self.logger.info(f"Total: ${self.state.total_cost_usd:.4f} / ${self.budget_limit:.2f}")

        except anthropic.APIError as e:
            run.status = "error"
            run.error = str(e)
            self.logger.error(f"API Error: {e}")
        except Exception as e:
            run.status = "error"
            run.error = str(e)
            self.logger.error(f"Error: {e}")

        # Complete run
        run.completed_at = datetime.now().isoformat()
        self.state.completed_runs.append({
            "agent": run.agent,
            "task": run.task[:200],
            "status": run.status,
            "tokens": run.tokens_used,
            "cost_usd": run.cost_usd,
            "completed_at": run.completed_at
        })

        # Save state
        save_state(self.state)

        # Rate limiting
        time.sleep(MIN_DELAY_SECONDS)

        return run

    def get_dimension_critics(self) -> List[str]:
        """Get all dimension critic agent keys"""
        return [
            key for key, agent in AGENT_REGISTRY.items()
            if agent.role == AgentRole.DIMENSION_CRITIC
        ]

    def evaluate_task_7d(self, task_description: str) -> Dict[str, Dict]:
        """
        Run all 7 dimension critics on a task (Z-22 feature).

        Returns dict mapping dimension name to result:
        {
            "critic-dependencies": {"status": "PASS", "details": "..."},
            "critic-effort": {"status": "WARN", "details": "..."},
            ...
        }
        """
        dimensions = self.get_dimension_critics()
        results = {}

        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"7-DIMENSION TASK EVALUATION")
        self.logger.info(f"{'='*60}")

        for dim in dimensions:
            self.logger.info(f"\nEvaluating dimension: {dim}")

            try:
                run = self.run_agent(dim, f"Evaluate this task:\n\n{task_description}")

                # Parse result for PASS/FAIL/WARN
                result_text = run.result or ""
                if "PASS" in result_text.upper():
                    status = "PASS"
                elif "FAIL" in result_text.upper():
                    status = "FAIL"
                elif "WARN" in result_text.upper():
                    status = "WARN"
                else:
                    status = "UNKNOWN"

                results[dim] = {
                    "status": status,
                    "details": result_text[:500],
                    "cost_usd": run.cost_usd
                }
            except Exception as e:
                results[dim] = {
                    "status": "ERROR",
                    "details": str(e),
                    "cost_usd": 0.0
                }

        # Summary
        pass_count = sum(1 for r in results.values() if r["status"] == "PASS")
        fail_count = sum(1 for r in results.values() if r["status"] == "FAIL")
        total_cost = sum(r["cost_usd"] for r in results.values())

        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"7D EVALUATION COMPLETE: {pass_count} PASS, {fail_count} FAIL")
        self.logger.info(f"Evaluation cost: ${total_cost:.4f}")
        self.logger.info(f"{'='*60}")

        return results

    def run_pm_cycle(self) -> str:
        """Run a PM decision cycle - ask PM what to do next"""
        context = f"""
Current System Status:
- Session: {self.state.session_id}
- Total runs: {self.state.total_runs}
- Budget used: ${self.state.total_cost_usd:.2f} / ${self.budget_limit:.2f}
- Pending tasks: {len(self.state.pending_tasks)}

Available agents: {list(AGENT_REGISTRY.keys())}

What should we work on next? Provide a specific task for one of the agents.
If no more work is needed, respond with "COMPLETE".
"""
        run = self.run_agent("pm", context)
        return run.result or ""

    def run_autonomous_loop(self, max_cycles: int = DEFAULT_MAX_CYCLES) -> None:
        """Run autonomous PM-directed cycles"""
        self.logger.info(f"\nStarting autonomous loop: {max_cycles} cycles, ${self.budget_limit:.2f} budget")

        for cycle in range(max_cycles):
            self.logger.info(f"\n{'#'*60}")
            self.logger.info(f"# CYCLE {cycle + 1} / {max_cycles}")
            self.logger.info(f"{'#'*60}")

            # Check budget
            if not self.check_budget():
                self.logger.warning("Budget exhausted. Stopping.")
                break

            # Ask PM what to do
            pm_response = self.run_pm_cycle()

            if "COMPLETE" in pm_response.upper():
                self.logger.info("PM signaled completion. Stopping.")
                break

            # Log PM decision
            self.logger.info(f"PM Decision: {pm_response[:200]}...")

        self.logger.info(f"\nLoop complete. Total cost: ${self.state.total_cost_usd:.4f}")

# =============================================================================
# Z-23: TASK WORKFLOW ENGINE
# =============================================================================

class TaskWorkflowState(Enum):
    """Task workflow state machine states"""
    PENDING = "pending"
    PLANNING = "planning"
    PLAN_REVIEW = "plan_review"
    BUILDING = "building"
    EVALUATING = "evaluating"
    PM_REVIEW = "pm_review"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"

@dataclass
class TaskResult:
    """Result of a task workflow execution"""
    task_id: str
    work_order: str
    status: str
    started_at: str
    completed_at: Optional[str] = None
    plan: Optional[str] = None
    build_output: Optional[str] = None
    evaluation: Optional[Dict] = None
    pm_decision: Optional[str] = None
    total_cost_usd: float = 0.0
    states_traversed: List[str] = field(default_factory=list)
    error: Optional[str] = None

class TaskWorkflowEngine:
    """
    Manages the full task lifecycle (Z-23).

    Workflow:
    1. Planner decomposes work order into task
    2. PlanAuditor reviews the plan (APPROVE/REJECT/REVISE)
    3. Builder implements the task
    4. 7 Dimension Critics evaluate the task
    5. PM promotes or rejects based on evaluation
    """

    def __init__(self, orchestrator: Orchestrator):
        self.orchestrator = orchestrator
        self.logger = orchestrator.logger
        self.current_state = TaskWorkflowState.PENDING

    def _log_state(self, state: TaskWorkflowState, result: TaskResult):
        """Log state transition"""
        self.current_state = state
        result.states_traversed.append(f"{state.value}:{datetime.now().isoformat()}")
        self.logger.info(f"  State: {state.value}")

    def execute_task(self, work_order: str, max_plan_retries: int = 2) -> TaskResult:
        """Execute full task workflow for a work order"""

        task_id = f"TASK-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        result = TaskResult(
            task_id=task_id,
            work_order=work_order,
            status="in_progress",
            started_at=datetime.now().isoformat()
        )

        self.logger.info(f"\n{'#'*60}")
        self.logger.info(f"# TASK WORKFLOW: {task_id}")
        self.logger.info(f"# Work Order: {work_order[:50]}...")
        self.logger.info(f"{'#'*60}")

        try:
            # === Step 1: Planning ===
            self._log_state(TaskWorkflowState.PLANNING, result)
            self.logger.info("\n[1/5] PLANNER: Decomposing work order...")

            plan_run = self.orchestrator.run_agent("planner",
                f"Decompose this work order into a single atomic task:\n\n{work_order}\n\n"
                "Provide: description, acceptance criteria, affected files, and implementation steps."
            )
            result.plan = plan_run.result
            result.total_cost_usd += plan_run.cost_usd

            if not result.plan:
                result.status = "failed"
                result.error = "Planner returned empty plan"
                return self._finalize(result)

            # === Step 2: Plan Review ===
            for attempt in range(max_plan_retries + 1):
                self._log_state(TaskWorkflowState.PLAN_REVIEW, result)
                self.logger.info(f"\n[2/5] PLAN AUDITOR: Reviewing plan (attempt {attempt + 1})...")

                audit_run = self.orchestrator.run_agent("plan-auditor",
                    f"Review this action plan and respond with APPROVE, REJECT, or REVISE:\n\n{result.plan}"
                )
                result.total_cost_usd += audit_run.cost_usd
                audit_result = audit_run.result or ""

                if "APPROVE" in audit_result.upper():
                    self.logger.info("  Plan APPROVED")
                    break
                elif "REJECT" in audit_result.upper():
                    self.logger.warning("  Plan REJECTED")
                    result.status = "rejected"
                    result.error = f"Plan rejected by auditor: {audit_result[:200]}"
                    return self._finalize(result)
                elif "REVISE" in audit_result.upper() and attempt < max_plan_retries:
                    self.logger.info("  Plan needs REVISION, asking planner to revise...")
                    revise_run = self.orchestrator.run_agent("planner",
                        f"Revise this plan based on feedback:\n\nOriginal Plan:\n{result.plan}\n\n"
                        f"Feedback:\n{audit_result}\n\nProvide revised plan."
                    )
                    result.plan = revise_run.result
                    result.total_cost_usd += revise_run.cost_usd
                else:
                    self.logger.warning("  Plan review inconclusive, proceeding anyway")
                    break

            # === Step 3: Building ===
            self._log_state(TaskWorkflowState.BUILDING, result)
            self.logger.info("\n[3/5] BUILDER: Implementing task...")

            build_run = self.orchestrator.run_agent("builder",
                f"Implement this task:\n\n{result.plan}\n\n"
                "Execute the implementation and report what was done."
            )
            result.build_output = build_run.result
            result.total_cost_usd += build_run.cost_usd

            if not result.build_output:
                result.status = "failed"
                result.error = "Builder returned empty output"
                return self._finalize(result)

            # === Step 4: 7D Evaluation ===
            self._log_state(TaskWorkflowState.EVALUATING, result)
            self.logger.info("\n[4/5] CRITICS: Running 7-dimension evaluation...")

            evaluation_input = f"Work Order: {work_order}\n\nPlan:\n{result.plan}\n\nBuild Output:\n{result.build_output}"
            result.evaluation = self.orchestrator.evaluate_task_7d(evaluation_input)

            eval_cost = sum(r.get("cost_usd", 0) for r in result.evaluation.values())
            result.total_cost_usd += eval_cost

            # Count results
            pass_count = sum(1 for r in result.evaluation.values() if r["status"] == "PASS")
            fail_count = sum(1 for r in result.evaluation.values() if r["status"] == "FAIL")

            # === Step 5: PM Review ===
            self._log_state(TaskWorkflowState.PM_REVIEW, result)
            self.logger.info("\n[5/5] PM: Final review and decision...")

            pm_context = f"""
Task Evaluation Summary:
- Task ID: {task_id}
- Work Order: {work_order}
- Dimensions Passed: {pass_count}/7
- Dimensions Failed: {fail_count}/7

Evaluation Details:
{json.dumps(result.evaluation, indent=2, default=str)}

Build Output Summary:
{result.build_output[:1000] if result.build_output else 'N/A'}

Respond with PROMOTE to accept this task, or REJECT with reason.
"""
            pm_run = self.orchestrator.run_agent("pm", pm_context)
            result.pm_decision = pm_run.result
            result.total_cost_usd += pm_run.cost_usd

            pm_result = pm_run.result or ""
            if "PROMOTE" in pm_result.upper():
                self._log_state(TaskWorkflowState.COMPLETED, result)
                result.status = "completed"
                self.logger.info(f"\n  TASK PROMOTED - {task_id}")
            else:
                self._log_state(TaskWorkflowState.REJECTED, result)
                result.status = "rejected"
                result.error = f"PM rejected: {pm_result[:200]}"
                self.logger.warning(f"\n  TASK REJECTED - {task_id}")

        except Exception as e:
            self._log_state(TaskWorkflowState.FAILED, result)
            result.status = "failed"
            result.error = str(e)
            self.logger.error(f"Task workflow failed: {e}")

        return self._finalize(result)

    def _finalize(self, result: TaskResult) -> TaskResult:
        """Finalize and log task result"""
        result.completed_at = datetime.now().isoformat()

        # Save task log
        self._save_task_log(result)

        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"TASK WORKFLOW COMPLETE")
        self.logger.info(f"  ID: {result.task_id}")
        self.logger.info(f"  Status: {result.status}")
        self.logger.info(f"  Cost: ${result.total_cost_usd:.4f}")
        self.logger.info(f"{'='*60}")

        return result

    def _save_task_log(self, result: TaskResult):
        """Save task execution log to LogBook"""
        if not YAML_AVAILABLE:
            return

        tasks_dir = LOGBOOK_DIR / "tasks"
        tasks_dir.mkdir(parents=True, exist_ok=True)

        log_file = tasks_dir / f"{result.task_id}.yaml"
        log_data = {
            "task_id": result.task_id,
            "work_order": result.work_order,
            "status": result.status,
            "started_at": result.started_at,
            "completed_at": result.completed_at,
            "total_cost_usd": result.total_cost_usd,
            "states_traversed": result.states_traversed,
            "error": result.error,
            "evaluation_summary": {
                dim: r["status"] for dim, r in (result.evaluation or {}).items()
            }
        }

        _atomic_write_text(log_file, yaml.dump(log_data, default_flow_style=False))

# =============================================================================
# CLI
# =============================================================================

def list_agents() -> None:
    """Print list of available agents"""
    print("\nAgent Registry")
    print("=" * 80)
    print(f"{'Key':<15} {'Name':<30} {'Model':<10} {'Role'}")
    print("-" * 80)

    for key, agent in AGENT_REGISTRY.items():
        model_name = "opus" if "opus" in agent.model else "sonnet" if "sonnet" in agent.model else "haiku"
        print(f"{key:<15} {agent.name:<30} {model_name:<10} {agent.role.value}")

    print("-" * 80)
    print(f"Total: {len(AGENT_REGISTRY)} agents\n")

def show_status() -> None:
    """Show current orchestrator status"""
    state = load_state()

    if not state:
        print("\nNo active session found.")
        return

    print(f"""
Orchestrator Status
{'=' * 50}
Session:     {state.session_id}
Started:     {state.started_at}
Checkpoint:  {state.last_checkpoint}
{'=' * 50}
Total Runs:  {state.total_runs}
Total Tokens: {state.total_tokens:,}
Total Cost:  ${state.total_cost_usd:.4f}
Budget:      ${state.budget_limit_usd:.2f}
Remaining:   ${state.budget_limit_usd - state.total_cost_usd:.2f}
{'=' * 50}
""")

def main():
    parser = argparse.ArgumentParser(
        description="Orchestrator - Multi-Agent Coordination System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List available agents
  python3 tools/orchestrator.py --list-agents

  # Show current status
  python3 tools/orchestrator.py --status

  # Run single agent
  python3 tools/orchestrator.py --agent fix-verifier --task "Verify issue G-15"

  # Run autonomous loop
  python3 tools/orchestrator.py --cycles 10 --budget 50

  # Run task workflow (Z-23)
  python3 tools/orchestrator.py --workflow task --work-order "Fix issue G-15"

  # Verbose mode
  python3 tools/orchestrator.py --agent pm --task "Status report" --verbose
"""
    )

    parser.add_argument("--agent", "-a", help="Agent to run (pm, builder, planner, critic, fix-verifier, etc.)")
    parser.add_argument("--task", "-t", help="Task for the agent")
    parser.add_argument("--workflow", "-w", choices=["task"], help="Run workflow: task (full task lifecycle)")
    parser.add_argument("--work-order", help="Work order for task workflow")
    parser.add_argument("--cycles", "-c", type=int, default=DEFAULT_MAX_CYCLES, help=f"Max autonomous cycles (default: {DEFAULT_MAX_CYCLES})")
    parser.add_argument("--budget", "-b", type=float, default=DEFAULT_BUDGET_USD, help=f"Budget limit in USD (default: {DEFAULT_BUDGET_USD})")
    parser.add_argument("--list-agents", "-l", action="store_true", help="List available agents")
    parser.add_argument("--status", "-s", action="store_true", help="Show orchestrator status")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Handle info commands
    if args.list_agents:
        list_agents()
        return 0

    if args.status:
        show_status()
        return 0

    # Check dependencies
    if not YAML_AVAILABLE:
        print("Error: PyYAML required. Run: pip3 install pyyaml")
        return 1

    if not ANTHROPIC_AVAILABLE:
        print("Error: anthropic library required. Run: pip3 install anthropic")
        return 1

    # Initialize orchestrator
    try:
        orch = Orchestrator(budget_limit=args.budget, verbose=args.verbose)
    except Exception as e:
        print(f"Error initializing orchestrator: {e}")
        return 1

    # Run single agent
    if args.agent:
        if not args.task:
            print("Error: --task required when using --agent")
            return 1

        try:
            run = orch.run_agent(args.agent, args.task)
            print(f"\n{'='*60}")
            print(f"Result ({run.status}):")
            print(f"{'='*60}")
            print(run.result or run.error or "No output")
            return 0 if run.status == "completed" else 1
        except Exception as e:
            print(f"Error: {e}")
            return 1

    # Run task workflow (Z-23)
    if args.workflow == "task":
        if not args.work_order:
            print("Error: --work-order required when using --workflow task")
            return 1

        try:
            engine = TaskWorkflowEngine(orch)
            result = engine.execute_task(args.work_order)
            print(f"\n{'='*60}")
            print(f"Task Workflow Result:")
            print(f"{'='*60}")
            print(f"  Task ID: {result.task_id}")
            print(f"  Status: {result.status}")
            print(f"  Cost: ${result.total_cost_usd:.4f}")
            if result.error:
                print(f"  Error: {result.error}")
            print(f"  Log: LogBook/orchestrator/tasks/{result.task_id}.yaml")
            return 0 if result.status == "completed" else 1
        except Exception as e:
            print(f"Error: {e}")
            return 1

    # Run autonomous loop
    if args.cycles > 0 and not args.agent:
        try:
            orch.run_autonomous_loop(max_cycles=args.cycles)
            return 0
        except KeyboardInterrupt:
            print("\nInterrupted. Saving state...")
            save_state(orch.state)
            return 0
        except Exception as e:
            print(f"Error: {e}")
            return 1

    # No action specified
    parser.print_help()
    return 0

if __name__ == "__main__":
    sys.exit(main())
