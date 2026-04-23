#!/usr/bin/env python3
"""
the system Heartbeat Daemon
Version: 1.0.0
Last Updated: 2025-12-25
Owner: PM
Classification: HIGH - Agent Liveness Tool

Background daemon for agent liveness signaling.
Enables detection of stalled or crashed agents.

Usage:
    python tools/heartbeat_daemon.py start --agent pm --interval 30
    python tools/heartbeat_daemon.py stop --agent pm
    python tools/heartbeat_daemon.py status
    python tools/heartbeat_daemon.py check --agent builder
"""

import argparse
import json
import os
import signal
import sys
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

class HeartbeatDaemon:
    """Manages agent heartbeat signals."""

    VALID_AGENTS = ['pm', 'planner', 'builder', 'critic_orchestrator',
                    'critic_plan_auditor', 'critic_dependencies', 'critic_effort',
                    'critic_execution_ready', 'critic_spec_fit', 'critic_verification',
                    'critic_security_policy', 'critic_acl']

    DEFAULT_INTERVAL = 30  # seconds
    STALE_THRESHOLD_MULTIPLIER = 3  # heartbeat is stale after 3 intervals

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize the heartbeat daemon."""
        self.project_root = project_root or Path.cwd()
        self.heartbeat_dir = self.project_root / ".heartbeats"
        self.config_file = self.heartbeat_dir / "config.yaml"
        self.pid_dir = self.heartbeat_dir / "pids"

        # Ensure directories exist
        self.heartbeat_dir.mkdir(parents=True, exist_ok=True)
        self.pid_dir.mkdir(parents=True, exist_ok=True)

        # Load config
        self.config = self._load_config()

        # Daemon state
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration."""
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                return yaml.safe_load(f) or {}

        default_config = {
            'version': '1.0.0',
            'default_interval': self.DEFAULT_INTERVAL,
            'stale_threshold_multiplier': self.STALE_THRESHOLD_MULTIPLIER,
            'auto_cleanup_hours': 24,
            'log_heartbeats': True,
            'agents': {}
        }

        self._save_config(default_config)
        return default_config

    def _save_config(self, config: Dict[str, Any]) -> None:
        """Save configuration."""
        with open(self.config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)

    def _get_heartbeat_file(self, agent_id: str) -> Path:
        """Get path to agent's heartbeat file."""
        return self.heartbeat_dir / f"{agent_id}.heartbeat"

    def _get_pid_file(self, agent_id: str) -> Path:
        """Get path to agent's daemon PID file."""
        return self.pid_dir / f"{agent_id}.pid"

    def _get_history_file(self, agent_id: str) -> Path:
        """Get path to agent's heartbeat history file."""
        return self.heartbeat_dir / f"{agent_id}.history.yaml"

    def send_heartbeat(self, agent_id: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Send a heartbeat signal for an agent.

        Args:
            agent_id: Agent identifier
            metadata: Optional metadata to include

        Returns:
            Heartbeat data
        """
        if agent_id not in self.VALID_AGENTS:
            raise ValueError(f"Unknown agent: {agent_id}")

        timestamp = datetime.utcnow()

        heartbeat = {
            'agent_id': agent_id,
            'timestamp': timestamp.isoformat() + "Z",
            'sequence': self._get_next_sequence(agent_id),
            'pid': os.getpid(),
            'metadata': metadata or {}
        }

        # Write heartbeat file
        heartbeat_file = self._get_heartbeat_file(agent_id)
        with open(heartbeat_file, 'w') as f:
            yaml.dump(heartbeat, f, default_flow_style=False)

        # Log to history if enabled
        if self.config.get('log_heartbeats', True):
            self._log_heartbeat(agent_id, heartbeat)

        return heartbeat

    def _get_next_sequence(self, agent_id: str) -> int:
        """Get next sequence number for agent."""
        heartbeat_file = self._get_heartbeat_file(agent_id)

        if heartbeat_file.exists():
            with open(heartbeat_file, 'r') as f:
                data = yaml.safe_load(f)
            return (data.get('sequence', 0) + 1) if data else 1

        return 1

    def _log_heartbeat(self, agent_id: str, heartbeat: Dict[str, Any]) -> None:
        """Log heartbeat to history."""
        history_file = self._get_history_file(agent_id)

        history = []
        if history_file.exists():
            with open(history_file, 'r') as f:
                history = yaml.safe_load(f) or []

        # Add new heartbeat
        history.append({
            'timestamp': heartbeat['timestamp'],
            'sequence': heartbeat['sequence']
        })

        # Keep last 1000 entries
        history = history[-1000:]

        with open(history_file, 'w') as f:
            yaml.dump(history, f, default_flow_style=False)

    def get_heartbeat(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the latest heartbeat for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            Heartbeat data or None
        """
        heartbeat_file = self._get_heartbeat_file(agent_id)

        if not heartbeat_file.exists():
            return None

        with open(heartbeat_file, 'r') as f:
            return yaml.safe_load(f)

    def is_alive(self, agent_id: str, interval: Optional[int] = None) -> bool:
        """
        Check if an agent is alive based on heartbeat.

        Args:
            agent_id: Agent identifier
            interval: Expected heartbeat interval in seconds

        Returns:
            True if agent is alive (heartbeat is fresh)
        """
        heartbeat = self.get_heartbeat(agent_id)

        if not heartbeat:
            return False

        interval = interval or self.config.get('default_interval', self.DEFAULT_INTERVAL)
        threshold = interval * self.config.get('stale_threshold_multiplier', self.STALE_THRESHOLD_MULTIPLIER)

        timestamp = datetime.fromisoformat(heartbeat['timestamp'].replace('Z', '+00:00'))
        age = (datetime.utcnow().replace(tzinfo=timestamp.tzinfo) - timestamp).total_seconds()

        return age < threshold

    def get_status(self, agent_id: str) -> Dict[str, Any]:
        """
        Get detailed status for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            Status dictionary
        """
        heartbeat = self.get_heartbeat(agent_id)

        if not heartbeat:
            return {
                'agent_id': agent_id,
                'status': 'unknown',
                'alive': False,
                'last_heartbeat': None,
                'message': 'No heartbeat found'
            }

        interval = self.config.get('agents', {}).get(agent_id, {}).get(
            'interval', self.config.get('default_interval', self.DEFAULT_INTERVAL)
        )
        alive = self.is_alive(agent_id, interval)

        timestamp = datetime.fromisoformat(heartbeat['timestamp'].replace('Z', '+00:00'))
        age = (datetime.utcnow().replace(tzinfo=timestamp.tzinfo) - timestamp).total_seconds()

        return {
            'agent_id': agent_id,
            'status': 'alive' if alive else 'stale',
            'alive': alive,
            'last_heartbeat': heartbeat['timestamp'],
            'age_seconds': int(age),
            'sequence': heartbeat.get('sequence', 0),
            'pid': heartbeat.get('pid'),
            'interval': interval,
            'metadata': heartbeat.get('metadata', {})
        }

    def get_all_status(self) -> List[Dict[str, Any]]:
        """Get status for all known agents."""
        statuses = []

        for agent_id in self.VALID_AGENTS:
            statuses.append(self.get_status(agent_id))

        return statuses

    def start_daemon(self, agent_id: str, interval: int = 30,
                     metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Start heartbeat daemon for an agent.

        Args:
            agent_id: Agent identifier
            interval: Heartbeat interval in seconds
            metadata: Metadata to include in heartbeats

        Returns:
            True if started successfully
        """
        if agent_id not in self.VALID_AGENTS:
            raise ValueError(f"Unknown agent: {agent_id}")

        # Check if already running
        pid_file = self._get_pid_file(agent_id)
        if pid_file.exists():
            with open(pid_file, 'r') as f:
                old_pid = int(f.read().strip())

            # Check if process is still running
            try:
                os.kill(old_pid, 0)
                print(f"Daemon for {agent_id} already running (PID: {old_pid})")
                return False
            except OSError:
                # Process not running, remove stale PID file
                pid_file.unlink()

        # Update config
        if 'agents' not in self.config:
            self.config['agents'] = {}

        self.config['agents'][agent_id] = {
            'interval': interval,
            'started_at': datetime.utcnow().isoformat() + "Z"
        }
        self._save_config(self.config)

        # Write PID file
        with open(pid_file, 'w') as f:
            f.write(str(os.getpid()))

        # Start heartbeat loop
        self._running = True

        def heartbeat_loop():
            while self._running:
                try:
                    self.send_heartbeat(agent_id, metadata)
                except Exception as e:
                    print(f"Heartbeat error: {e}", file=sys.stderr)
                time.sleep(interval)

        self._thread = threading.Thread(target=heartbeat_loop, daemon=True)
        self._thread.start()

        print(f"Started heartbeat daemon for {agent_id} (interval: {interval}s)")
        return True

    def stop_daemon(self, agent_id: str) -> bool:
        """
        Stop heartbeat daemon for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            True if stopped successfully
        """
        pid_file = self._get_pid_file(agent_id)

        if not pid_file.exists():
            print(f"No daemon running for {agent_id}")
            return False

        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())

        # Try to kill the process
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"Sent SIGTERM to PID {pid}")
        except OSError as e:
            print(f"Process {pid} not running: {e}")

        # Remove PID file
        pid_file.unlink()

        # Update config
        if agent_id in self.config.get('agents', {}):
            del self.config['agents'][agent_id]
            self._save_config(self.config)

        print(f"Stopped daemon for {agent_id}")
        return True

    def cleanup_stale(self) -> Dict[str, int]:
        """
        Clean up stale heartbeat files.

        Returns:
            Count of cleaned files per agent
        """
        cleanup_hours = self.config.get('auto_cleanup_hours', 24)
        threshold = datetime.utcnow() - timedelta(hours=cleanup_hours)

        cleaned = {}

        for heartbeat_file in self.heartbeat_dir.glob("*.heartbeat"):
            agent_id = heartbeat_file.stem

            with open(heartbeat_file, 'r') as f:
                data = yaml.safe_load(f)

            if data:
                timestamp = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
                if timestamp.replace(tzinfo=None) < threshold:
                    heartbeat_file.unlink()
                    cleaned[agent_id] = 1

        return cleaned

    def get_history(self, agent_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get heartbeat history for an agent."""
        history_file = self._get_history_file(agent_id)

        if not history_file.exists():
            return []

        with open(history_file, 'r') as f:
            history = yaml.safe_load(f) or []

        return history[-limit:]

    def calculate_uptime(self, agent_id: str) -> Dict[str, Any]:
        """Calculate uptime statistics for an agent."""
        history = self.get_history(agent_id, limit=1000)

        if len(history) < 2:
            return {
                'agent_id': agent_id,
                'uptime_percent': 0,
                'total_heartbeats': len(history),
                'gaps': 0
            }

        interval = self.config.get('agents', {}).get(agent_id, {}).get(
            'interval', self.config.get('default_interval', self.DEFAULT_INTERVAL)
        )
        threshold = interval * 2  # Allow some jitter

        gaps = 0
        for i in range(1, len(history)):
            prev = datetime.fromisoformat(history[i-1]['timestamp'].replace('Z', '+00:00'))
            curr = datetime.fromisoformat(history[i]['timestamp'].replace('Z', '+00:00'))
            gap = (curr - prev).total_seconds()
            if gap > threshold:
                gaps += 1

        # Calculate uptime percentage
        first = datetime.fromisoformat(history[0]['timestamp'].replace('Z', '+00:00'))
        last = datetime.fromisoformat(history[-1]['timestamp'].replace('Z', '+00:00'))
        total_time = (last - first).total_seconds()

        expected_heartbeats = total_time / interval if interval > 0 else 0
        actual_heartbeats = len(history)

        uptime = min(100, (actual_heartbeats / expected_heartbeats * 100) if expected_heartbeats > 0 else 0)

        return {
            'agent_id': agent_id,
            'uptime_percent': round(uptime, 2),
            'total_heartbeats': actual_heartbeats,
            'expected_heartbeats': int(expected_heartbeats),
            'gaps': gaps,
            'first_heartbeat': history[0]['timestamp'],
            'last_heartbeat': history[-1]['timestamp']
        }

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='the system Heartbeat Daemon',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Start command
    start_parser = subparsers.add_parser('start', help='Start heartbeat daemon')
    start_parser.add_argument('--agent', '-a', required=True, help='Agent ID')
    start_parser.add_argument('--interval', '-i', type=int, default=30, help='Interval in seconds')
    start_parser.add_argument('--foreground', '-f', action='store_true', help='Run in foreground')

    # Stop command
    stop_parser = subparsers.add_parser('stop', help='Stop heartbeat daemon')
    stop_parser.add_argument('--agent', '-a', required=True, help='Agent ID')

    # Status command
    status_parser = subparsers.add_parser('status', help='Show status')
    status_parser.add_argument('--format', choices=['table', 'yaml', 'json'], default='table')

    # Check command
    check_parser = subparsers.add_parser('check', help='Check agent liveness')
    check_parser.add_argument('--agent', '-a', required=True, help='Agent ID')

    # Beat command (send single heartbeat)
    beat_parser = subparsers.add_parser('beat', help='Send single heartbeat')
    beat_parser.add_argument('--agent', '-a', required=True, help='Agent ID')
    beat_parser.add_argument('--metadata', '-m', help='Metadata as JSON')

    # History command
    history_parser = subparsers.add_parser('history', help='Show heartbeat history')
    history_parser.add_argument('--agent', '-a', required=True, help='Agent ID')
    history_parser.add_argument('--limit', '-l', type=int, default=20, help='Limit entries')

    # Uptime command
    uptime_parser = subparsers.add_parser('uptime', help='Calculate uptime')
    uptime_parser.add_argument('--agent', '-a', required=True, help='Agent ID')

    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Clean stale heartbeats')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    daemon = HeartbeatDaemon()

    try:
        if args.command == 'start':
            daemon.start_daemon(args.agent, args.interval)

            if args.foreground:
                print("Running in foreground (Ctrl+C to stop)...")
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    print("\nStopping...")
                    daemon._running = False

        elif args.command == 'stop':
            daemon.stop_daemon(args.agent)

        elif args.command == 'status':
            statuses = daemon.get_all_status()

            if args.format == 'table':
                print(f"\n{'Agent':<25} {'Status':<10} {'Age':<10} {'Sequence':<10}")
                print("-" * 60)
                for s in statuses:
                    status = s['status'].upper()
                    age = f"{s.get('age_seconds', '-')}s" if s.get('age_seconds') else '-'
                    seq = str(s.get('sequence', '-'))
                    print(f"{s['agent_id']:<25} {status:<10} {age:<10} {seq:<10}")
            elif args.format == 'json':
                print(json.dumps(statuses, indent=2))
            else:
                print(yaml.dump(statuses, default_flow_style=False))

        elif args.command == 'check':
            status = daemon.get_status(args.agent)
            alive = status['alive']
            print(f"Agent {args.agent}: {'ALIVE' if alive else 'NOT ALIVE'}")
            print(f"  Last heartbeat: {status.get('last_heartbeat', 'Never')}")
            print(f"  Age: {status.get('age_seconds', '-')} seconds")
            sys.exit(0 if alive else 1)

        elif args.command == 'beat':
            metadata = json.loads(args.metadata) if args.metadata else None
            heartbeat = daemon.send_heartbeat(args.agent, metadata)
            print(f"Heartbeat sent: sequence={heartbeat['sequence']}")

        elif args.command == 'history':
            history = daemon.get_history(args.agent, args.limit)
            for entry in history:
                print(f"  {entry['timestamp']} (seq: {entry['sequence']})")

        elif args.command == 'uptime':
            uptime = daemon.calculate_uptime(args.agent)
            print(f"Agent: {uptime['agent_id']}")
            print(f"Uptime: {uptime['uptime_percent']}%")
            print(f"Total heartbeats: {uptime['total_heartbeats']}")
            print(f"Gaps detected: {uptime['gaps']}")

        elif args.command == 'cleanup':
            cleaned = daemon.cleanup_stale()
            if cleaned:
                print("Cleaned stale heartbeats:")
                for agent, count in cleaned.items():
                    print(f"  {agent}: {count}")
            else:
                print("No stale heartbeats found")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
