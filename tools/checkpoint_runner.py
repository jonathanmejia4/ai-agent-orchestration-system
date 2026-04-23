"""
Checkpoint Runner

Executes and logs two-phase checkpoint testing:
- Checkpoint 1: Structural/Wiring validation (early)
- Checkpoint 2: Behavioral/Execution validation (final)

Usage:
    python tools/checkpoint_runner.py --run-checkpoint-1
    python tools/checkpoint_runner.py --run-checkpoint-2
    python tools/checkpoint_runner.py --run-both
    python tools/checkpoint_runner.py --verify
"""

import os
import sys
import yaml
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

class CheckpointRunner:
    """Execute and log checkpoint tests."""

    def __init__(self, task_dir: str = '.'):
        """Initialize runner with task directory."""
        self.task_dir = Path(task_dir)
        self.task_path = self.task_dir / '.task'
        self.plan_path = self.task_path / 'checkpoint_plan.yaml'
        self.results_path = self.task_path / 'checkpoint_results.yaml'

    def load_checkpoint_plan(self) -> Dict[str, Any]:
        """Load checkpoint plan from .task/ directory."""
        if not self.plan_path.exists():
            raise FileNotFoundError(
                f"Checkpoint plan not found: {self.plan_path}\n"
                "Planner must create checkpoint_plan.yaml before running tests."
            )

        with open(self.plan_path, 'r') as f:
            plan = yaml.safe_load(f)

        # Validate plan structure
        required = ['task_id', 'task_name', 'checkpoint_1_early', 'checkpoint_2_final']
        missing = [field for field in required if field not in plan]

        if missing:
            raise ValueError(
                f"Checkpoint plan missing required fields: {missing}"
            )

        return plan

    def run_checkpoint_1(self) -> Dict[str, Any]:
        """Execute Checkpoint 1: Structural/Wiring validation."""
        print("=" * 60)
        print("CHECKPOINT 1: Structural/Wiring Validation (Early)")
        print("=" * 60)

        plan = self.load_checkpoint_plan()
        checkpoint_1 = plan['checkpoint_1_early']

        print(f"\nTask: {plan['task_name']}")
        print(f"Description: {checkpoint_1.get('description', 'N/A')}")
        print(f"\nRunning {len(checkpoint_1['tests'])} structural tests...\n")

        results = {
            'checkpoint': 1,
            'name': checkpoint_1.get('name', 'Structural Validation'),
            'type': 'structural',
            'task_id': plan['task_id'],
            'task_name': plan['task_name'],
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'tests': [],
            'status': 'pass',
            'duration_ms': 0,
            'pass_count': 0,
            'fail_count': 0
        }

        start_time = datetime.now()

        for test_def in checkpoint_1['tests']:
            test_result = self._run_test(test_def, checkpoint=1)
            results['tests'].append(test_result)

            if test_result['status'] == 'pass':
                results['pass_count'] += 1
            else:
                results['fail_count'] += 1
                results['status'] = 'fail'

        end_time = datetime.now()
        results['duration_ms'] = int((end_time - start_time).total_seconds() * 1000)

        # Save results
        self._save_checkpoint_results(1, results)

        # Print summary
        self._print_checkpoint_summary(results)

        return results

    def run_checkpoint_2(self, skip_if_checkpoint_1_failed: bool = True) -> Dict[str, Any]:
        """Execute Checkpoint 2: Behavioral/Execution validation."""
        print("=" * 60)
        print("CHECKPOINT 2: Behavioral/Execution Validation (Final)")
        print("=" * 60)

        # Check if Checkpoint 1 passed
        if skip_if_checkpoint_1_failed:
            checkpoint_1_results = self._load_checkpoint_results(1)

            if not checkpoint_1_results:
                raise RuntimeError(
                    "Checkpoint 1 must be run before Checkpoint 2.\n"
                    "Run: python tools/checkpoint_runner.py --run-checkpoint-1"
                )

            if checkpoint_1_results['status'] != 'pass':
                print("\n❌ SKIPPED: Checkpoint 1 did not pass")
                print("   Fix structural issues before running behavioral tests.\n")
                return {
                    'checkpoint': 2,
                    'status': 'skipped',
                    'reason': 'checkpoint_1_failed',
                    'timestamp': datetime.utcnow().isoformat() + 'Z'
                }

        plan = self.load_checkpoint_plan()
        checkpoint_2 = plan['checkpoint_2_final']

        print(f"\nTask: {plan['task_name']}")
        print(f"Description: {checkpoint_2.get('description', 'N/A')}")
        print(f"\nRunning {len(checkpoint_2['tests'])} behavioral tests...\n")

        results = {
            'checkpoint': 2,
            'name': checkpoint_2.get('name', 'Behavioral Validation'),
            'type': 'behavioral',
            'task_id': plan['task_id'],
            'task_name': plan['task_name'],
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'tests': [],
            'status': 'pass',
            'duration_ms': 0,
            'pass_count': 0,
            'fail_count': 0
        }

        start_time = datetime.now()

        for test_def in checkpoint_2['tests']:
            test_result = self._run_test(test_def, checkpoint=2)
            results['tests'].append(test_result)

            if test_result['status'] == 'pass':
                results['pass_count'] += 1
            else:
                results['fail_count'] += 1
                results['status'] = 'fail'

        end_time = datetime.now()
        results['duration_ms'] = int((end_time - start_time).total_seconds() * 1000)

        # Save results
        self._save_checkpoint_results(2, results)

        # Print summary
        self._print_checkpoint_summary(results)

        return results

    def run_both(self) -> Dict[str, Any]:
        """Run both checkpoints sequentially."""
        print("\n🔄 Running Two-Phase Checkpoint Testing\n")

        # Run Checkpoint 1
        checkpoint_1 = self.run_checkpoint_1()

        if checkpoint_1['status'] != 'pass':
            print("\n❌ Checkpoint 1 FAILED - Skipping Checkpoint 2")
            print("   Fix structural issues before running behavioral tests.\n")
            return {
                'checkpoint_1': checkpoint_1,
                'checkpoint_2': {'status': 'skipped', 'reason': 'checkpoint_1_failed'},
                'overall_status': 'fail'
            }

        print("\n✅ Checkpoint 1 PASSED - Proceeding to Checkpoint 2\n")

        # Run Checkpoint 2
        checkpoint_2 = self.run_checkpoint_2(skip_if_checkpoint_1_failed=False)

        overall_status = 'pass' if checkpoint_2['status'] == 'pass' else 'fail'

        results = {
            'checkpoint_1': checkpoint_1,
            'checkpoint_2': checkpoint_2,
            'overall_status': overall_status
        }

        # Print overall summary
        print("\n" + "=" * 60)
        print("OVERALL RESULTS")
        print("=" * 60)
        print(f"Checkpoint 1: {checkpoint_1['status'].upper()}")
        print(f"Checkpoint 2: {checkpoint_2['status'].upper()}")
        print(f"Overall: {overall_status.upper()}")
        print("=" * 60 + "\n")

        return results

    def verify_checkpoints(self) -> Dict[str, Any]:
        """Verify both checkpoints have been run and passed."""
        print("Verifying checkpoint compliance...\n")

        checkpoint_1 = self._load_checkpoint_results(1)
        checkpoint_2 = self._load_checkpoint_results(2)

        results = {
            'checkpoint_1_run': checkpoint_1 is not None,
            'checkpoint_1_passed': checkpoint_1 and checkpoint_1['status'] == 'pass',
            'checkpoint_2_run': checkpoint_2 is not None,
            'checkpoint_2_passed': checkpoint_2 and checkpoint_2['status'] == 'pass',
            'promotion_eligible': False,
            'issues': []
        }

        # Check requirements
        if not results['checkpoint_1_run']:
            results['issues'].append("Checkpoint 1 has not been run")

        if not results['checkpoint_1_passed']:
            results['issues'].append("Checkpoint 1 did not pass")

        if not results['checkpoint_2_run']:
            results['issues'].append("Checkpoint 2 has not been run")

        if not results['checkpoint_2_passed']:
            results['issues'].append("Checkpoint 2 did not pass")

        # Check sequential execution
        if checkpoint_1 and checkpoint_2:
            time_1 = datetime.fromisoformat(checkpoint_1['timestamp'].rstrip('Z'))
            time_2 = datetime.fromisoformat(checkpoint_2['timestamp'].rstrip('Z'))

            if time_2 <= time_1:
                results['issues'].append("Checkpoints not executed sequentially")

        # Determine eligibility
        results['promotion_eligible'] = (
            results['checkpoint_1_passed'] and
            results['checkpoint_2_passed'] and
            len(results['issues']) == 0
        )

        # Print results
        print("Checkpoint Compliance:")
        print(f"  Checkpoint 1 Run: {'✅' if results['checkpoint_1_run'] else '❌'}")
        print(f"  Checkpoint 1 Passed: {'✅' if results['checkpoint_1_passed'] else '❌'}")
        print(f"  Checkpoint 2 Run: {'✅' if results['checkpoint_2_run'] else '❌'}")
        print(f"  Checkpoint 2 Passed: {'✅' if results['checkpoint_2_passed'] else '❌'}")
        print(f"\nPromotion Eligible: {'✅' if results['promotion_eligible'] else '❌'}")

        if results['issues']:
            print(f"\nIssues:")
            for issue in results['issues']:
                print(f"  ❌ {issue}")

        print()

        return results

    def _run_test(self, test_def: Dict[str, Any], checkpoint: int) -> Dict[str, Any]:
        """Execute a single test."""
        test_name = test_def.get('name', 'unnamed_test')
        command = test_def.get('command')
        purpose = test_def.get('purpose', '')

        print(f"Running: {test_name}")
        if purpose:
            print(f"  Purpose: {purpose}")

        result = {
            'name': test_name,
            'purpose': purpose,
            'command': command,
            'status': 'pass',
            'duration_ms': 0,
            'output': '',
            'error': '',
            'issues': []
        }

        if not command:
            result['status'] = 'fail'
            result['error'] = 'No command specified'
            result['issues'].append('Test definition missing command')
            print(f"  ❌ FAIL: No command specified\n")
            return result

        start_time = datetime.now()

        try:
            # Execute command
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            result['output'] = proc.stdout
            result['error'] = proc.stderr

            if proc.returncode == 0:
                result['status'] = 'pass'
                print(f"  ✅ PASS ({proc.returncode})")
            else:
                result['status'] = 'fail'
                result['issues'].append(f'Exit code: {proc.returncode}')
                print(f"  ❌ FAIL (exit code {proc.returncode})")

                if proc.stderr:
                    print(f"  Error: {proc.stderr[:200]}")

        except subprocess.TimeoutExpired:
            result['status'] = 'fail'
            result['error'] = 'Test timeout (300s)'
            result['issues'].append('Test exceeded timeout')
            print(f"  ❌ FAIL: Timeout\n")

        except Exception as e:
            result['status'] = 'fail'
            result['error'] = str(e)
            result['issues'].append(f'Exception: {type(e).__name__}')
            print(f"  ❌ FAIL: {e}\n")

        end_time = datetime.now()
        result['duration_ms'] = int((end_time - start_time).total_seconds() * 1000)

        print(f"  Duration: {result['duration_ms']}ms\n")

        return result

    def _save_checkpoint_results(self, checkpoint: int, results: Dict[str, Any]):
        """Save checkpoint results to .task/ directory."""
        # Ensure .task directory exists
        self.task_path.mkdir(exist_ok=True)

        # Load existing results
        all_results = {}
        if self.results_path.exists():
            with open(self.results_path, 'r') as f:
                all_results = yaml.safe_load(f) or {}

        # Update with new results
        all_results[f'checkpoint_{checkpoint}'] = results

        # Write back
        with open(self.results_path, 'w') as f:
            yaml.dump(all_results, f, default_flow_style=False, sort_keys=False)

        print(f"\n💾 Results saved to: {self.results_path}")

    def _load_checkpoint_results(self, checkpoint: int) -> Optional[Dict[str, Any]]:
        """Load checkpoint results from .task/ directory."""
        if not self.results_path.exists():
            return None

        with open(self.results_path, 'r') as f:
            all_results = yaml.safe_load(f) or {}

        return all_results.get(f'checkpoint_{checkpoint}')

    def _print_checkpoint_summary(self, results: Dict[str, Any]):
        """Print checkpoint summary."""
        print("\n" + "-" * 60)
        print(f"CHECKPOINT {results['checkpoint']} SUMMARY")
        print("-" * 60)
        print(f"Status: {results['status'].upper()}")
        print(f"Tests Passed: {results['pass_count']}")
        print(f"Tests Failed: {results['fail_count']}")
        print(f"Duration: {results['duration_ms']}ms")

        if results['status'] == 'fail':
            print("\nFailed Tests:")
            for test in results['tests']:
                if test['status'] == 'fail':
                    print(f"  ❌ {test['name']}")
                    for issue in test['issues']:
                        print(f"     - {issue}")

        print("-" * 60 + "\n")

def main():
    """Run checkpoint tests based on command-line arguments."""
    runner = CheckpointRunner()

    if '--run-checkpoint-1' in sys.argv:
        results = runner.run_checkpoint_1()
        sys.exit(0 if results['status'] == 'pass' else 1)

    elif '--run-checkpoint-2' in sys.argv:
        results = runner.run_checkpoint_2()
        if results['status'] == 'skipped':
            sys.exit(2)
        sys.exit(0 if results['status'] == 'pass' else 1)

    elif '--run-both' in sys.argv:
        results = runner.run_both()
        sys.exit(0 if results['overall_status'] == 'pass' else 1)

    elif '--verify' in sys.argv:
        results = runner.verify_checkpoints()
        sys.exit(0 if results['promotion_eligible'] else 1)

    else:
        print("Checkpoint Runner")
        print("\nUsage:")
        print("  --run-checkpoint-1    Run Checkpoint 1 (Structural)")
        print("  --run-checkpoint-2    Run Checkpoint 2 (Behavioral)")
        print("  --run-both            Run both checkpoints sequentially")
        print("  --verify              Verify checkpoint compliance")
        print("\nExample:")
        print("  python tools/checkpoint_runner.py --run-both")
        sys.exit(1)

if __name__ == '__main__':
    main()
