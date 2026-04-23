#!/usr/bin/env python3
"""
the system Monetization Health Check
Generated: 2025-12-30
Issue: Z-19 Automated Monetization Flow Verification

Daily health check for monetization flows.
Run via cron or GitHub Actions to catch issues early.

Usage:
    python tools/monetization_health_check.py

Environment Variables:
    API_BASE_URL: Base URL of the API (default: http://localhost:8000)
    HEALTH_CHECK_API_KEY: API key for health check endpoints (optional)
    SLACK_WEBHOOK_URL: Slack webhook for alerts (optional)
    PAGERDUTY_KEY: PagerDuty routing key for alerts (optional)
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

class MonetizationHealthCheck:
    """
    Health check for monetization flows.

    Checks:
    - License validation module imports
    - Trial manager works
    - Fingerprint tracker works
    - API handlers importable
    - License validation logic works
    """

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.failures: List[Tuple[str, str]] = []
        self.passed: List[str] = []

    def log(self, message: str) -> None:
        """Print message if verbose."""
        if self.verbose:
            print(message)

    def run_all_checks(self) -> bool:
        """Run all monetization health checks."""
        checks = [
            ("License Validator Import", self.check_license_validator_import),
            ("Trial Manager Import", self.check_trial_manager_import),
            ("Fingerprint Tracker Import", self.check_fingerprint_tracker_import),
            ("API Handlers Import", self.check_api_handlers_import),
            ("License Validation Logic", self.check_license_validation_logic),
            ("Trial Creation Logic", self.check_trial_creation_logic),
            ("Abuse Detection Logic", self.check_abuse_detection_logic),
            ("Extension Logic", self.check_extension_logic),
            ("Conversion Logic", self.check_conversion_logic),
        ]

        self.log("")
        self.log("=" * 60)
        self.log("the system Monetization Health Check")
        self.log(f"Timestamp: {datetime.now().isoformat()}")
        self.log("=" * 60)
        self.log("")

        for check_name, check_func in checks:
            try:
                check_func()
                self.passed.append(check_name)
                self.log(f"✅ {check_name}")
            except Exception as e:
                self.failures.append((check_name, str(e)))
                self.log(f"❌ {check_name}: {e}")

        self.log("")
        self.log("-" * 60)
        self.log(f"Passed: {len(self.passed)}/{len(checks)}")
        self.log(f"Failed: {len(self.failures)}/{len(checks)}")
        self.log("-" * 60)

        return len(self.failures) == 0

    def check_license_validator_import(self) -> None:
        """Verify license validator module imports."""
        from src.licensing.license_validator import (
            LicenseValidator,
            ValidationResult,
            validate_and_exit_if_invalid,
        )

        assert LicenseValidator is not None
        assert ValidationResult is not None
        assert callable(validate_and_exit_if_invalid)

    def check_trial_manager_import(self) -> None:
        """Verify trial manager module imports."""
        from src.licensing.trial_manager import (
            TrialManager,
            create_trial,
            get_trial,
            check_trial_status,
        )

        assert TrialManager is not None
        assert callable(create_trial)
        assert callable(get_trial)
        assert callable(check_trial_status)

    def check_fingerprint_tracker_import(self) -> None:
        """Verify fingerprint tracker module imports."""
        from src.licensing.fingerprint_tracker import (
            TrialFingerprint,
            DISPOSABLE_EMAIL_DOMAINS,
        )

        assert TrialFingerprint is not None
        assert len(DISPOSABLE_EMAIL_DOMAINS) > 0

    def check_api_handlers_import(self) -> None:
        """Verify API handlers import."""
        from api.trial import (
            create_trial_handler,
            check_trial_handler,
            extend_trial_handler,
            convert_trial_handler,
            cancel_subscription_handler,
        )

        assert callable(create_trial_handler)
        assert callable(check_trial_handler)
        assert callable(extend_trial_handler)
        assert callable(convert_trial_handler)
        assert callable(cancel_subscription_handler)

    def check_license_validation_logic(self) -> None:
        """Verify license validation works correctly."""
        from src.licensing.license_validator import LicenseValidator

        # Test valid dev license
        v = LicenseValidator("ER-SYS-DEV-99991231-healthcheck")
        r = v.validate()
        assert r.is_valid, "DEV license should be valid"

        # Test invalid license
        v = LicenseValidator("INVALID")
        r = v.validate()
        assert not r.is_valid, "Invalid license should fail"

        # Test expired license
        v = LicenseValidator("ER-SYS-MONTHLY-20200101-expired")
        r = v.validate()
        assert not r.is_valid, "Expired license should fail"

    def check_trial_creation_logic(self) -> None:
        """Verify trial creation works."""
        from src.licensing.trial_manager import TrialManager
        from pathlib import Path
        import tempfile

        # Use temp storage
        with tempfile.NamedTemporaryFile(suffix=".json", delete=True) as f:
            manager = TrialManager(storage_path=Path(f.name))

            result = manager.create_trial(
                email=f"healthcheck-{datetime.now().timestamp()}@test.internal",
                ip="127.0.0.1",
            )

            assert result.success or result.show_upgrade_offer, \
                "Trial creation should either succeed or show upgrade offer"

    def check_abuse_detection_logic(self) -> None:
        """Verify abuse detection works."""
        from src.licensing.fingerprint_tracker import TrialFingerprint

        tracker = TrialFingerprint()

        # Test fingerprint generation
        fp = tracker.generate_fingerprint(
            ip="1.2.3.4",
            email="test@example.com",
        )
        assert len(fp) == 64, "Fingerprint should be SHA256 hex"

        # Test disposable email detection
        assert tracker.is_disposable_email("test@mailinator.com"), \
            "Should detect disposable email"
        assert not tracker.is_disposable_email("test@gmail.com"), \
            "Should not flag normal email"

    def check_extension_logic(self) -> None:
        """Verify trial extension logic."""
        from src.licensing.models.trial import Trial, TrialStatus
        from datetime import datetime, timedelta

        trial = Trial(
            id="health-ext",
            email_hash="abc",
            ip_hash="def",
            subnet_hash="ghi",
            fingerprint_hash="jkl",
            license_key="ER-SYS-TRIAL-20301231-health",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(days=14),
        )

        # First extension should work
        result = trial.extend("Testing")
        assert result.success, "First extension should succeed"

        # Second extension should fail
        result2 = trial.extend("Testing again")
        assert not result2.success, "Second extension should fail"

    def check_conversion_logic(self) -> None:
        """Verify trial conversion logic."""
        from src.licensing.models.trial import Trial, TrialStatus
        from datetime import datetime, timedelta

        trial = Trial(
            id="health-conv",
            email_hash="abc",
            ip_hash="def",
            subnet_hash="ghi",
            fingerprint_hash="jkl",
            license_key="ER-SYS-TRIAL-20301231-health",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(days=14),
        )

        # Conversion should work
        assert trial.convert("monthly"), "Conversion to monthly should work"
        assert trial.status == TrialStatus.CONVERTED
        assert trial.converted_to_plan == "monthly"

    def alert_on_failure(self) -> bool:
        """Send alert if any checks failed."""
        if not self.failures:
            return True

        alert_message = f"🚨 the system Monetization Health Check Failed!\n\n"
        alert_message += f"Timestamp: {datetime.now().isoformat()}\n"
        alert_message += f"Failed: {len(self.failures)} checks\n\n"

        for check_name, error in self.failures:
            alert_message += f"❌ {check_name}: {error}\n"

        # Send to Slack if configured
        slack_webhook = os.environ.get("SLACK_WEBHOOK_URL")
        if slack_webhook:
            self._send_slack_alert(slack_webhook, alert_message)

        # Send to PagerDuty if configured
        pagerduty_key = os.environ.get("PAGERDUTY_KEY")
        if pagerduty_key:
            self._send_pagerduty_alert(pagerduty_key, alert_message)

        return False

    def _send_slack_alert(self, webhook_url: str, message: str) -> None:
        """Send alert to Slack."""
        try:
            import requests
            requests.post(
                webhook_url,
                json={"text": message},
                timeout=10,
            )
        except Exception as e:
            self.log(f"Failed to send Slack alert: {e}")

    def _send_pagerduty_alert(self, routing_key: str, message: str) -> None:
        """Send alert to PagerDuty."""
        try:
            import requests
            requests.post(
                "https://events.pagerduty.com/v2/enqueue",
                json={
                    "routing_key": routing_key,
                    "event_action": "trigger",
                    "payload": {
                        "summary": "the system Monetization Health Check Failed",
                        "severity": "critical",
                        "source": "monetization_health_check.py",
                        "custom_details": {"message": message},
                    },
                },
                timeout=10,
            )
        except Exception as e:
            self.log(f"Failed to send PagerDuty alert: {e}")

def main() -> int:
    """Run health check and return exit code."""
    checker = MonetizationHealthCheck(verbose=True)

    success = checker.run_all_checks()
    checker.alert_on_failure()

    if success:
        print("\n✅ All monetization health checks passed!")
        return 0
    else:
        print(f"\n❌ {len(checker.failures)} health check(s) failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
