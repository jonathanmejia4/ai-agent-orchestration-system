#!/usr/bin/env python3
"""
the system Orchestrator Recovery Module (Z-26)
=======================================

Recovery and resilience features for autonomous operation:
- Enhanced checkpointing
- Crash recovery
- Exponential backoff retry
- Graceful shutdown
- Health monitoring
"""

import signal
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Any

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# =============================================================================
# CONFIGURATION
# =============================================================================

CHECKPOINT_DIR = Path("LogBook/orchestrator/checkpoints")
HEARTBEAT_FILE = Path("LogBook/orchestrator/HEARTBEAT")
MAX_CHECKPOINTS = 10
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_DELAY = 5

# =============================================================================
# CHECKPOINT MANAGER
# =============================================================================

class CheckpointManager:
    """Manages orchestrator checkpoints for crash recovery"""

    def __init__(self, checkpoint_dir: Path = CHECKPOINT_DIR):
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def save_checkpoint(self, state: dict, label: str = "auto") -> Path:
        """
        Save checkpoint with timestamp and optional label.

        Args:
            state: Orchestrator state dict
            label: Checkpoint label (auto, shutdown, manual)

        Returns:
            Path to saved checkpoint
        """
        if not YAML_AVAILABLE:
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"checkpoint_{timestamp}_{label}.yaml"
        checkpoint_path = self.checkpoint_dir / filename

        with open(checkpoint_path, 'w') as f:
            yaml.dump(state, f, default_flow_style=False)

        # Cleanup old checkpoints
        self._cleanup_old_checkpoints()

        return checkpoint_path

    def load_latest_checkpoint(self) -> Optional[dict]:
        """Load most recent checkpoint"""
        if not YAML_AVAILABLE:
            return None

        checkpoints = sorted(self.checkpoint_dir.glob("checkpoint_*.yaml"))
        if not checkpoints:
            return None

        latest = checkpoints[-1]
        with open(latest) as f:
            return yaml.safe_load(f)

    def list_checkpoints(self) -> list:
        """List all available checkpoints"""
        return sorted(self.checkpoint_dir.glob("checkpoint_*.yaml"))

    def _cleanup_old_checkpoints(self, keep: int = MAX_CHECKPOINTS):
        """Remove old checkpoints, keep most recent"""
        checkpoints = sorted(self.checkpoint_dir.glob("checkpoint_*.yaml"))
        for old in checkpoints[:-keep]:
            old.unlink()

# =============================================================================
# RECOVERY MANAGER
# =============================================================================

@dataclass
class RecoveryResult:
    """Result of crash recovery attempt"""
    recovered: bool
    checkpoint_time: Optional[str] = None
    interrupted_agents: int = 0
    reason: Optional[str] = None

class RecoveryManager:
    """Manages crash recovery for orchestrator"""

    def __init__(self, checkpoint_manager: CheckpointManager):
        self.checkpoint_manager = checkpoint_manager

    def recover_from_crash(self) -> RecoveryResult:
        """
        Attempt to recover from previous crash.

        Returns:
            RecoveryResult with recovery status
        """
        state = self.checkpoint_manager.load_latest_checkpoint()

        if not state:
            return RecoveryResult(
                recovered=False,
                reason="No checkpoint found"
            )

        # Check for interrupted work
        active_agents = state.get("active_agents", {})
        interrupted_count = len(active_agents)

        if interrupted_count > 0:
            # Mark interrupted runs as failed
            completed = state.get("completed_runs", [])
            for agent_name, run_info in active_agents.items():
                completed.append({
                    "agent": agent_name,
                    "status": "interrupted",
                    "error": "Recovered from crash",
                    "completed_at": datetime.now().isoformat()
                })
            state["completed_runs"] = completed
            state["active_agents"] = {}

        return RecoveryResult(
            recovered=True,
            checkpoint_time=state.get("last_checkpoint"),
            interrupted_agents=interrupted_count
        )

# =============================================================================
# RETRY HANDLER
# =============================================================================

class RetryHandler:
    """Handles retries with exponential backoff"""

    def __init__(self, max_retries: int = DEFAULT_RETRY_ATTEMPTS,
                 base_delay: float = DEFAULT_RETRY_DELAY):
        self.max_retries = max_retries
        self.base_delay = base_delay

    def execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with exponential backoff retry.

        Args:
            func: Function to execute
            *args, **kwargs: Arguments to pass to function

        Returns:
            Function result

        Raises:
            Last exception if all retries fail
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)

            except Exception as e:
                last_error = e
                is_retryable = self._is_retryable(e)

                if not is_retryable or attempt >= self.max_retries - 1:
                    break

                delay = self.base_delay * (2 ** attempt)
                print(f"  Retry {attempt + 1}/{self.max_retries} in {delay}s: {e}")
                time.sleep(delay)

        raise last_error

    def _is_retryable(self, error: Exception) -> bool:
        """Check if error is retryable"""
        if ANTHROPIC_AVAILABLE:
            retryable_types = (
                anthropic.RateLimitError,
                anthropic.APIConnectionError,
                anthropic.InternalServerError,
            )
            return isinstance(error, retryable_types)

        # Fallback: retry on connection errors
        error_str = str(error).lower()
        return any(x in error_str for x in ["rate", "timeout", "connection", "503", "429"])

# =============================================================================
# GRACEFUL SHUTDOWN
# =============================================================================

class GracefulShutdown:
    """Handles graceful shutdown on signals"""

    def __init__(self, on_shutdown: Optional[Callable] = None):
        self.shutdown_requested = False
        self.on_shutdown = on_shutdown

        # Register signal handlers
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum, frame):
        """Handle shutdown signal"""
        print(f"\n[SHUTDOWN] Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_requested = True

        if self.on_shutdown:
            self.on_shutdown()

    def should_continue(self) -> bool:
        """Check if orchestrator should continue running"""
        return not self.shutdown_requested

# =============================================================================
# HEALTH MONITOR
# =============================================================================

class HealthMonitor:
    """Monitors orchestrator health"""

    def __init__(self, heartbeat_file: Path = HEARTBEAT_FILE):
        self.heartbeat_file = heartbeat_file
        self.heartbeat_file.parent.mkdir(parents=True, exist_ok=True)
        self.last_heartbeat = datetime.now()

    def heartbeat(self):
        """Record heartbeat"""
        self.last_heartbeat = datetime.now()
        self.heartbeat_file.write_text(self.last_heartbeat.isoformat())

    def get_last_heartbeat(self) -> Optional[datetime]:
        """Get last heartbeat time"""
        if self.heartbeat_file.exists():
            try:
                return datetime.fromisoformat(self.heartbeat_file.read_text().strip())
            except ValueError:
                return None
        return None

    def check_stuck(self, timeout_minutes: int = 30) -> bool:
        """Check if orchestrator appears stuck"""
        last = self.get_last_heartbeat()
        if not last:
            return False

        elapsed = datetime.now() - last
        return elapsed.total_seconds() > (timeout_minutes * 60)

# =============================================================================
# CLI
# =============================================================================

def main():
    """Test recovery module"""
    print("the system Orchestrator Recovery Module (Z-26)")
    print("=" * 50)

    # Test checkpoint manager
    print("\n1. Testing CheckpointManager...")
    cm = CheckpointManager()
    test_state = {
        "session_id": "TEST-001",
        "total_runs": 5,
        "total_cost_usd": 0.25
    }
    path = cm.save_checkpoint(test_state, "test")
    print(f"   Saved checkpoint: {path}")

    loaded = cm.load_latest_checkpoint()
    print(f"   Loaded checkpoint: {loaded}")

    # Test recovery manager
    print("\n2. Testing RecoveryManager...")
    rm = RecoveryManager(cm)
    result = rm.recover_from_crash()
    print(f"   Recovery result: recovered={result.recovered}")

    # Test health monitor
    print("\n3. Testing HealthMonitor...")
    hm = HealthMonitor()
    hm.heartbeat()
    print(f"   Heartbeat recorded: {hm.last_heartbeat}")
    print(f"   Is stuck: {hm.check_stuck()}")

    # Test retry handler
    print("\n4. Testing RetryHandler...")
    rh = RetryHandler(max_retries=2, base_delay=1)
    try:
        result = rh.execute_with_retry(lambda: "success")
        print(f"   Retry result: {result}")
    except Exception as e:
        print(f"   Retry failed: {e}")

    print("\nRecovery module tests complete.")

if __name__ == "__main__":
    main()
