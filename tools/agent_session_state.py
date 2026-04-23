#!/usr/bin/env python3
"""
Agent Session State Manager
Version: 1.0.0
Last Updated: 2025-12-25
Owner: PM
Classification: HIGH - State Management Tool

Manages agent session state persistence and recovery.
Enables agents to save/restore state across sessions for continuity.

Usage:
    python tools/agent_session_state.py save --agent pm --state '{"task": "review"}'
    python tools/agent_session_state.py load --agent pm
    python tools/agent_session_state.py list
    python tools/agent_session_state.py clear --agent builder
    python tools/agent_session_state.py history --agent pm --limit 10
"""

import argparse
import json
import os
import sys
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
import yaml
import shutil

@dataclass
class SessionState:
    """Represents an agent's session state."""
    agent_id: str
    session_id: str
    timestamp: str
    state_data: Dict[str, Any]
    checksum: str
    version: str = "1.0.0"
    expires_at: Optional[str] = None
    parent_session: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionState':
        return cls(**data)

class AgentSessionStateManager:
    """Manages agent session state persistence."""

    VALID_AGENTS = ['pm', 'planner', 'builder', 'critic_orchestrator',
                    'critic_plan_auditor', 'critic_dependencies', 'critic_effort',
                    'critic_execution_ready', 'critic_spec_fit', 'critic_verification',
                    'critic_security_policy', 'critic_acl']

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize the session state manager."""
        self.project_root = project_root or Path.cwd()
        self.state_dir = self.project_root / ".agent_state"
        self.history_dir = self.state_dir / "history"
        self.current_dir = self.state_dir / "current"
        self.config_file = self.state_dir / "config.yaml"

        # Ensure directories exist
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.current_dir.mkdir(parents=True, exist_ok=True)

        # Load or create config
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration or create default."""
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                return yaml.safe_load(f) or {}

        default_config = {
            'version': '1.0.0',
            'max_history_per_agent': 100,
            'state_ttl_hours': 168,  # 7 days
            'auto_cleanup': True,
            'compression_enabled': False,
            'encryption_enabled': False
        }

        with open(self.config_file, 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False)

        return default_config

    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
        random_part = hashlib.md5(os.urandom(16)).hexdigest()[:8]
        return f"sess_{timestamp}_{random_part}"

    def _calculate_checksum(self, data: Dict[str, Any]) -> str:
        """Calculate checksum for state data."""
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()[:16]

    def _get_current_state_file(self, agent_id: str) -> Path:
        """Get path to agent's current state file."""
        return self.current_dir / f"{agent_id}.yaml"

    def _get_history_dir(self, agent_id: str) -> Path:
        """Get path to agent's history directory."""
        agent_history = self.history_dir / agent_id
        agent_history.mkdir(parents=True, exist_ok=True)
        return agent_history

    def validate_agent(self, agent_id: str) -> bool:
        """Validate that agent ID is recognized."""
        return agent_id in self.VALID_AGENTS

    def save_state(self, agent_id: str, state_data: Dict[str, Any],
                   ttl_hours: Optional[int] = None,
                   parent_session: Optional[str] = None) -> SessionState:
        """
        Save agent session state.

        Args:
            agent_id: The agent identifier
            state_data: State data to persist
            ttl_hours: Optional TTL in hours (overrides config)
            parent_session: Optional parent session ID for chaining

        Returns:
            SessionState object
        """
        if not self.validate_agent(agent_id):
            raise ValueError(f"Unknown agent: {agent_id}. Valid agents: {self.VALID_AGENTS}")

        # Archive current state to history if exists
        current_file = self._get_current_state_file(agent_id)
        if current_file.exists():
            self._archive_current_state(agent_id)

        # Create new session state
        session_id = self._generate_session_id()
        timestamp = datetime.utcnow().isoformat() + "Z"
        checksum = self._calculate_checksum(state_data)

        ttl = ttl_hours or self.config.get('state_ttl_hours', 168)
        expires_at = (datetime.utcnow() + timedelta(hours=ttl)).isoformat() + "Z"

        session_state = SessionState(
            agent_id=agent_id,
            session_id=session_id,
            timestamp=timestamp,
            state_data=state_data,
            checksum=checksum,
            expires_at=expires_at,
            parent_session=parent_session
        )

        # Save to current state file
        with open(current_file, 'w') as f:
            yaml.dump(session_state.to_dict(), f, default_flow_style=False)

        print(f"Saved state for {agent_id}: session={session_id}")
        return session_state

    def _archive_current_state(self, agent_id: str) -> None:
        """Archive current state to history."""
        current_file = self._get_current_state_file(agent_id)
        if not current_file.exists():
            return

        with open(current_file, 'r') as f:
            state_data = yaml.safe_load(f)

        if not state_data:
            return

        # Save to history with timestamp filename
        history_dir = self._get_history_dir(agent_id)
        timestamp = state_data.get('timestamp', datetime.utcnow().isoformat())
        safe_timestamp = timestamp.replace(':', '-').replace('.', '-')
        history_file = history_dir / f"{safe_timestamp}.yaml"

        with open(history_file, 'w') as f:
            yaml.dump(state_data, f, default_flow_style=False)

        # Cleanup old history if needed
        self._cleanup_history(agent_id)

    def _cleanup_history(self, agent_id: str) -> None:
        """Remove old history entries beyond limit."""
        max_history = self.config.get('max_history_per_agent', 100)
        history_dir = self._get_history_dir(agent_id)

        history_files = sorted(history_dir.glob("*.yaml"), reverse=True)

        if len(history_files) > max_history:
            for old_file in history_files[max_history:]:
                old_file.unlink()

    def load_state(self, agent_id: str) -> Optional[SessionState]:
        """
        Load agent's current session state.

        Args:
            agent_id: The agent identifier

        Returns:
            SessionState object or None if not found
        """
        if not self.validate_agent(agent_id):
            raise ValueError(f"Unknown agent: {agent_id}")

        current_file = self._get_current_state_file(agent_id)

        if not current_file.exists():
            print(f"No state found for {agent_id}")
            return None

        with open(current_file, 'r') as f:
            data = yaml.safe_load(f)

        if not data:
            return None

        # Check if expired
        expires_at = data.get('expires_at')
        if expires_at:
            expiry = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            if datetime.utcnow().replace(tzinfo=expiry.tzinfo) > expiry:
                print(f"State for {agent_id} has expired")
                return None

        # Verify checksum
        stored_checksum = data.get('checksum')
        calculated_checksum = self._calculate_checksum(data.get('state_data', {}))

        if stored_checksum != calculated_checksum:
            print(f"Warning: Checksum mismatch for {agent_id} state")

        return SessionState.from_dict(data)

    def list_agents(self) -> List[Dict[str, Any]]:
        """
        List all agents with current state.

        Returns:
            List of agent state summaries
        """
        agents = []

        for agent_id in self.VALID_AGENTS:
            current_file = self._get_current_state_file(agent_id)
            history_dir = self._get_history_dir(agent_id)

            agent_info = {
                'agent_id': agent_id,
                'has_current_state': current_file.exists(),
                'history_count': len(list(history_dir.glob("*.yaml")))
            }

            if current_file.exists():
                with open(current_file, 'r') as f:
                    data = yaml.safe_load(f)
                if data:
                    agent_info['session_id'] = data.get('session_id')
                    agent_info['timestamp'] = data.get('timestamp')
                    agent_info['expires_at'] = data.get('expires_at')

            agents.append(agent_info)

        return agents

    def clear_state(self, agent_id: str, archive: bool = True) -> bool:
        """
        Clear agent's current state.

        Args:
            agent_id: The agent identifier
            archive: Whether to archive before clearing

        Returns:
            True if state was cleared
        """
        if not self.validate_agent(agent_id):
            raise ValueError(f"Unknown agent: {agent_id}")

        current_file = self._get_current_state_file(agent_id)

        if not current_file.exists():
            print(f"No state to clear for {agent_id}")
            return False

        if archive:
            self._archive_current_state(agent_id)

        current_file.unlink()
        print(f"Cleared state for {agent_id}")
        return True

    def get_history(self, agent_id: str, limit: int = 10) -> List[SessionState]:
        """
        Get agent's state history.

        Args:
            agent_id: The agent identifier
            limit: Maximum number of entries to return

        Returns:
            List of historical SessionState objects
        """
        if not self.validate_agent(agent_id):
            raise ValueError(f"Unknown agent: {agent_id}")

        history_dir = self._get_history_dir(agent_id)
        history_files = sorted(history_dir.glob("*.yaml"), reverse=True)[:limit]

        states = []
        for history_file in history_files:
            with open(history_file, 'r') as f:
                data = yaml.safe_load(f)
            if data:
                states.append(SessionState.from_dict(data))

        return states

    def restore_from_history(self, agent_id: str, session_id: str) -> Optional[SessionState]:
        """
        Restore a historical state as current.

        Args:
            agent_id: The agent identifier
            session_id: Session ID to restore

        Returns:
            Restored SessionState or None if not found
        """
        if not self.validate_agent(agent_id):
            raise ValueError(f"Unknown agent: {agent_id}")

        history_dir = self._get_history_dir(agent_id)

        for history_file in history_dir.glob("*.yaml"):
            with open(history_file, 'r') as f:
                data = yaml.safe_load(f)

            if data and data.get('session_id') == session_id:
                # Archive current and restore this one
                self._archive_current_state(agent_id)

                # Update timestamp and create new session
                return self.save_state(
                    agent_id=agent_id,
                    state_data=data.get('state_data', {}),
                    parent_session=session_id
                )

        print(f"Session {session_id} not found in history for {agent_id}")
        return None

    def cleanup_expired(self) -> Dict[str, int]:
        """
        Remove all expired states.

        Returns:
            Count of removed states per agent
        """
        removed = {}
        now = datetime.utcnow()

        for agent_id in self.VALID_AGENTS:
            count = 0

            # Check current state
            current_file = self._get_current_state_file(agent_id)
            if current_file.exists():
                with open(current_file, 'r') as f:
                    data = yaml.safe_load(f)

                if data and data.get('expires_at'):
                    expiry = datetime.fromisoformat(
                        data['expires_at'].replace('Z', '+00:00')
                    )
                    if now.replace(tzinfo=expiry.tzinfo) > expiry:
                        self._archive_current_state(agent_id)
                        current_file.unlink()
                        count += 1

            # Check history
            history_dir = self._get_history_dir(agent_id)
            for history_file in history_dir.glob("*.yaml"):
                with open(history_file, 'r') as f:
                    data = yaml.safe_load(f)

                if data and data.get('expires_at'):
                    expiry = datetime.fromisoformat(
                        data['expires_at'].replace('Z', '+00:00')
                    )
                    if now.replace(tzinfo=expiry.tzinfo) > expiry:
                        history_file.unlink()
                        count += 1

            if count > 0:
                removed[agent_id] = count

        return removed

    def export_all_states(self, output_file: Path) -> None:
        """Export all current states to a single file."""
        all_states = {}

        for agent_id in self.VALID_AGENTS:
            state = self.load_state(agent_id)
            if state:
                all_states[agent_id] = state.to_dict()

        with open(output_file, 'w') as f:
            yaml.dump(all_states, f, default_flow_style=False)

        print(f"Exported {len(all_states)} states to {output_file}")

    def import_states(self, input_file: Path) -> int:
        """Import states from a file."""
        with open(input_file, 'r') as f:
            all_states = yaml.safe_load(f)

        count = 0
        for agent_id, state_data in all_states.items():
            if self.validate_agent(agent_id):
                self.save_state(agent_id, state_data.get('state_data', {}))
                count += 1

        print(f"Imported {count} states from {input_file}")
        return count

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Agent Session State Manager',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s save --agent pm --state '{"current_task": "review_task", "task_id": "auth"}'
  %(prog)s load --agent pm
  %(prog)s list
  %(prog)s history --agent builder --limit 5
  %(prog)s clear --agent critic_orchestrator
  %(prog)s cleanup
  %(prog)s export --output states_backup.yaml
  %(prog)s import --input states_backup.yaml
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Save command
    save_parser = subparsers.add_parser('save', help='Save agent state')
    save_parser.add_argument('--agent', '-a', required=True, help='Agent ID')
    save_parser.add_argument('--state', '-s', required=True, help='State data as JSON')
    save_parser.add_argument('--ttl', type=int, help='TTL in hours')
    save_parser.add_argument('--parent', help='Parent session ID')

    # Load command
    load_parser = subparsers.add_parser('load', help='Load agent state')
    load_parser.add_argument('--agent', '-a', required=True, help='Agent ID')
    load_parser.add_argument('--format', choices=['yaml', 'json'], default='yaml')

    # List command
    list_parser = subparsers.add_parser('list', help='List all agent states')
    list_parser.add_argument('--format', choices=['table', 'yaml', 'json'], default='table')

    # History command
    history_parser = subparsers.add_parser('history', help='Show agent state history')
    history_parser.add_argument('--agent', '-a', required=True, help='Agent ID')
    history_parser.add_argument('--limit', '-l', type=int, default=10, help='Max entries')

    # Clear command
    clear_parser = subparsers.add_parser('clear', help='Clear agent state')
    clear_parser.add_argument('--agent', '-a', required=True, help='Agent ID')
    clear_parser.add_argument('--no-archive', action='store_true', help='Skip archiving')

    # Restore command
    restore_parser = subparsers.add_parser('restore', help='Restore from history')
    restore_parser.add_argument('--agent', '-a', required=True, help='Agent ID')
    restore_parser.add_argument('--session', '-s', required=True, help='Session ID')

    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Remove expired states')

    # Export command
    export_parser = subparsers.add_parser('export', help='Export all states')
    export_parser.add_argument('--output', '-o', required=True, help='Output file')

    # Import command
    import_parser = subparsers.add_parser('import', help='Import states')
    import_parser.add_argument('--input', '-i', required=True, help='Input file')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    manager = AgentSessionStateManager()

    try:
        if args.command == 'save':
            state_data = json.loads(args.state)
            state = manager.save_state(
                agent_id=args.agent,
                state_data=state_data,
                ttl_hours=args.ttl,
                parent_session=args.parent
            )
            print(yaml.dump(state.to_dict(), default_flow_style=False))

        elif args.command == 'load':
            state = manager.load_state(args.agent)
            if state:
                if args.format == 'json':
                    print(json.dumps(state.to_dict(), indent=2))
                else:
                    print(yaml.dump(state.to_dict(), default_flow_style=False))

        elif args.command == 'list':
            agents = manager.list_agents()
            if args.format == 'table':
                print(f"{'Agent':<25} {'Has State':<12} {'History':<10} {'Session':<30}")
                print("-" * 80)
                for agent in agents:
                    has_state = "Yes" if agent['has_current_state'] else "No"
                    session = agent.get('session_id', '-')[:28] if agent.get('session_id') else '-'
                    print(f"{agent['agent_id']:<25} {has_state:<12} {agent['history_count']:<10} {session:<30}")
            elif args.format == 'json':
                print(json.dumps(agents, indent=2))
            else:
                print(yaml.dump(agents, default_flow_style=False))

        elif args.command == 'history':
            states = manager.get_history(args.agent, args.limit)
            for state in states:
                print(f"Session: {state.session_id}")
                print(f"  Timestamp: {state.timestamp}")
                print(f"  Checksum: {state.checksum}")
                print()

        elif args.command == 'clear':
            manager.clear_state(args.agent, archive=not args.no_archive)

        elif args.command == 'restore':
            state = manager.restore_from_history(args.agent, args.session)
            if state:
                print(f"Restored session {args.session} as new session {state.session_id}")

        elif args.command == 'cleanup':
            removed = manager.cleanup_expired()
            if removed:
                print("Removed expired states:")
                for agent, count in removed.items():
                    print(f"  {agent}: {count}")
            else:
                print("No expired states found")

        elif args.command == 'export':
            manager.export_all_states(Path(args.output))

        elif args.command == 'import':
            manager.import_states(Path(args.input))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
