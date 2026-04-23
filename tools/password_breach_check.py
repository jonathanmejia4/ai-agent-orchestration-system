#!/usr/bin/env python3
"""
Password Breach Check Tool

Checks passwords against HaveIBeenPwned API using k-anonymity.

Requirements (per customer-service-standards.md Section 3.5):
- Integration with HaveIBeenPwned API
- k-anonymity (only first 5 chars of hash sent)
- Check at registration and password change
- Warn but don't block for breached passwords

Usage:
    python password_breach_check.py --check "password"    # Check a specific password
    python password_breach_check.py --interactive        # Interactive mode
    python password_breach_check.py --test               # Run self-test
"""

import argparse
import hashlib
import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class BreachCheckResult:
    """Result of a password breach check."""
    is_breached: bool
    breach_count: int
    checked_at: datetime
    error: Optional[str] = None

    @property
    def severity(self) -> str:
        """Get severity level based on breach count."""
        if not self.is_breached:
            return "safe"
        elif self.breach_count > 100000:
            return "critical"
        elif self.breach_count > 10000:
            return "high"
        elif self.breach_count > 1000:
            return "medium"
        else:
            return "low"

    @property
    def message(self) -> str:
        """Get user-friendly message."""
        if self.error:
            return f"Unable to check password: {self.error}"
        if not self.is_breached:
            return "This password has not been found in any known data breaches."
        if self.breach_count == 1:
            return "This password has been found in 1 data breach. Consider using a different password."
        return f"This password has been found in {self.breach_count:,} data breaches. Please choose a different password."

class HaveIBeenPwnedClient:
    """
    Client for HaveIBeenPwned Passwords API.

    Uses k-anonymity model:
    - Only first 5 characters of SHA-1 hash are sent to API
    - API returns all hashes matching that prefix
    - Local check for exact match
    - Password never leaves your system

    API Documentation: https://haveibeenpwned.com/API/v3#PwnedPasswords
    """

    API_URL = "https://api.pwnedpasswords.com/range/{prefix}"
    TIMEOUT = 10  # seconds

    def __init__(self, http_client=None):
        """
        Initialize HIBP client.

        Args:
            http_client: Optional HTTP client (for testing/mocking)
        """
        self._http_client = http_client

    def _get_sha1_hash(self, password: str) -> str:
        """
        Get SHA-1 hash of password in uppercase hex.

        Args:
            password: Password to hash

        Returns:
            40-character uppercase hex string
        """
        return hashlib.sha1(password.encode('utf-8')).hexdigest().upper()

    def _make_request(self, prefix: str) -> Optional[str]:
        """
        Make request to HIBP API.

        Args:
            prefix: First 5 characters of SHA-1 hash

        Returns:
            Response text or None on error
        """
        if self._http_client:
            return self._http_client.get(prefix)

        try:
            import urllib.request
            url = self.API_URL.format(prefix=prefix)
            request = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'Enter-Robotics-Password-Check/1.0',
                    'Add-Padding': 'true'  # Add padding for consistent response size
                }
            )
            with urllib.request.urlopen(request, timeout=self.TIMEOUT) as response:
                return response.read().decode('utf-8')
        except Exception as e:
            logger.error(f"HIBP API request failed: {e}")
            return None

    def check(self, password: str) -> BreachCheckResult:
        """
        Check if password has been exposed in data breaches.

        Uses k-anonymity: only first 5 chars of SHA-1 hash are sent.
        The password never leaves your system.

        Args:
            password: Password to check (NOT logged or stored)

        Returns:
            BreachCheckResult with breach status and count
        """
        now = datetime.utcnow()

        # Get SHA-1 hash
        sha1_hash = self._get_sha1_hash(password)
        prefix = sha1_hash[:5]
        suffix = sha1_hash[5:]

        # Make API request with prefix only
        response = self._make_request(prefix)
        if response is None:
            return BreachCheckResult(
                is_breached=False,
                breach_count=0,
                checked_at=now,
                error="Unable to connect to breach database"
            )

        # Parse response and check for our suffix
        for line in response.split('\n'):
            line = line.strip()
            if not line or ':' not in line:
                continue

            hash_suffix, count = line.split(':')
            if hash_suffix == suffix:
                breach_count = int(count)
                logger.info(f"Password found in {breach_count} breaches")
                return BreachCheckResult(
                    is_breached=True,
                    breach_count=breach_count,
                    checked_at=now
                )

        # Not found in breaches
        logger.debug("Password not found in breach database")
        return BreachCheckResult(
            is_breached=False,
            breach_count=0,
            checked_at=now
        )

class PasswordBreachChecker:
    """
    High-level password breach checking utility.

    Features:
    - Check passwords against HIBP database
    - Caching to avoid repeated API calls
    - Batch checking capability
    - Severity classification
    """

    def __init__(self, hibp_client: Optional[HaveIBeenPwnedClient] = None):
        """
        Initialize password breach checker.

        Args:
            hibp_client: HIBP client instance
        """
        self._client = hibp_client or HaveIBeenPwnedClient()
        self._cache: dict[str, BreachCheckResult] = {}

    def _get_cache_key(self, password: str) -> str:
        """Get cache key for password (hash, not plaintext)."""
        return hashlib.sha256(password.encode()).hexdigest()

    def check(self, password: str, use_cache: bool = True) -> BreachCheckResult:
        """
        Check if password has been breached.

        Args:
            password: Password to check
            use_cache: Whether to use cached results

        Returns:
            BreachCheckResult
        """
        # Check cache
        if use_cache:
            cache_key = self._get_cache_key(password)
            if cache_key in self._cache:
                logger.debug("Using cached breach check result")
                return self._cache[cache_key]

        # Perform check
        result = self._client.check(password)

        # Cache result
        if use_cache and not result.error:
            cache_key = self._get_cache_key(password)
            self._cache[cache_key] = result

        return result

    def check_at_registration(self, password: str) -> tuple[bool, str]:
        """
        Check password at registration time.

        Returns a recommendation but doesn't block registration.

        Args:
            password: Password being set

        Returns:
            Tuple of (should_warn, message)
        """
        result = self.check(password)

        if result.error:
            # Don't block registration if service is unavailable
            return False, ""

        if result.is_breached:
            if result.severity == "critical":
                return True, (
                    f"Warning: This password has been found in {result.breach_count:,} "
                    "data breaches. We strongly recommend choosing a different password."
                )
            elif result.severity in ("high", "medium"):
                return True, (
                    f"This password has been found in {result.breach_count:,} data breaches. "
                    "Consider using a stronger password."
                )
            else:
                return True, (
                    "This password has been found in a data breach. "
                    "Consider using a different password."
                )

        return False, ""

    def check_at_password_change(self, password: str) -> tuple[bool, str]:
        """
        Check password at password change time.

        Args:
            password: New password being set

        Returns:
            Tuple of (should_warn, message)
        """
        return self.check_at_registration(password)

    def get_password_advice(self, result: BreachCheckResult) -> list[str]:
        """
        Get advice for improving password security.

        Args:
            result: Breach check result

        Returns:
            List of advice strings
        """
        advice = []

        if result.is_breached:
            advice.append("Choose a password that hasn't been used before.")
            advice.append("Use a password manager to generate unique passwords.")

        advice.extend([
            "Use at least 12 characters.",
            "Mix uppercase, lowercase, numbers, and symbols.",
            "Avoid common words or patterns.",
            "Don't reuse passwords across sites.",
            "Enable two-factor authentication for extra security."
        ])

        return advice

def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Password Breach Check - Check passwords against HaveIBeenPwned"
    )
    parser.add_argument(
        "--check",
        metavar="PASSWORD",
        help="Check a specific password"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Interactive mode for checking passwords"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run self-test with known breached passwords"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    checker = PasswordBreachChecker()

    if args.check:
        result = checker.check(args.check)
        print(f"\nResult: {result.message}")
        print(f"Severity: {result.severity}")
        if result.is_breached:
            print("\nAdvice:")
            for advice in checker.get_password_advice(result):
                print(f"  - {advice}")

    elif args.interactive:
        print("Password Breach Checker - Interactive Mode")
        print("Enter passwords to check (Ctrl+C to exit)")
        print("Note: Passwords are NOT stored or logged.\n")

        try:
            while True:
                import getpass
                password = getpass.getpass("Password to check: ")
                if not password:
                    continue

                result = checker.check(password)
                print(f"Result: {result.message}\n")

        except KeyboardInterrupt:
            print("\nGoodbye!")

    elif args.test:
        print("Running self-test with known breached passwords...")

        # These are intentionally weak/common passwords for testing
        test_passwords = [
            ("password", True),      # Should be breached
            ("123456", True),        # Should be breached
            ("qwerty", True),        # Should be breached
        ]

        for password, expected_breach in test_passwords:
            result = checker.check(password)
            status = "PASS" if result.is_breached == expected_breach else "FAIL"
            print(f"  {status}: '{password}' - breached={result.is_breached}, count={result.breach_count}")

        print("\nTest complete.")

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
