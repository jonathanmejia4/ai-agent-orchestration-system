"""
Fraud Appeal Processor Tool

AI-assisted fraud review and automatic unblock functionality.
Per customer-service-standards.md Section 8.6:
- Don't block legitimate customers
- Clear communication when blocked
- Easy appeal process
- AI-assisted review (not human queue)
- Automatic unblock after verification
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from enum import Enum
import logging
import uuid

logger = logging.getLogger(__name__)

class FraudStatus(Enum):
    """Status of a fraud flag."""
    FLAGGED = "flagged"
    UNDER_REVIEW = "under_review"
    CONFIRMED_FRAUD = "confirmed_fraud"
    FALSE_POSITIVE = "false_positive"
    APPEALED = "appealed"
    CLEARED = "cleared"

class AppealStatus(Enum):
    """Status of an appeal."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_APPROVED = "auto_approved"

@dataclass
class FraudFlag:
    """A fraud flag on an account."""
    flag_id: str
    account_id: str
    reason: str
    confidence_score: float
    flagged_at: datetime
    status: FraudStatus
    evidence: Dict[str, Any] = field(default_factory=dict)

@dataclass
class FraudAppeal:
    """An appeal against a fraud flag."""
    appeal_id: str
    flag_id: str
    account_id: str
    submitted_at: datetime
    customer_statement: str
    supporting_documents: List[str]
    status: AppealStatus
    reviewed_at: Optional[datetime] = None
    reviewer_notes: Optional[str] = None
    auto_review_score: Optional[float] = None

@dataclass
class VerificationResult:
    """Result of verification during appeal."""
    verified: bool
    confidence: float
    checks_passed: List[str]
    checks_failed: List[str]
    recommendation: AppealStatus

class FraudAppealProcessor:
    """
    Processes fraud appeals with AI-assisted review.

    Key Features:
    - Automatic verification checks
    - AI-assisted evidence analysis
    - Quick appeal processing (target: < 24 hours)
    - Automatic unblock for verified false positives
    """

    # Threshold for automatic approval
    AUTO_APPROVE_THRESHOLD = 0.85
    # Threshold for automatic rejection
    AUTO_REJECT_THRESHOLD = 0.15
    # Maximum review time before escalation
    MAX_REVIEW_HOURS = 24

    def __init__(self):
        """Initialize the fraud appeal processor."""
        self._appeals: Dict[str, FraudAppeal] = {}
        self._flags: Dict[str, FraudFlag] = {}

    def submit_appeal(
        self,
        flag_id: str,
        account_id: str,
        customer_statement: str,
        supporting_documents: Optional[List[str]] = None
    ) -> FraudAppeal:
        """
        Submit a new fraud appeal.

        Args:
            flag_id: ID of the fraud flag being appealed
            account_id: Customer account ID
            customer_statement: Customer's explanation
            supporting_documents: Optional list of document references

        Returns:
            The created FraudAppeal
        """
        appeal_id = f"APPEAL-{uuid.uuid4().hex[:8].upper()}"

        appeal = FraudAppeal(
            appeal_id=appeal_id,
            flag_id=flag_id,
            account_id=account_id,
            submitted_at=datetime.now(),
            customer_statement=customer_statement,
            supporting_documents=supporting_documents or [],
            status=AppealStatus.PENDING
        )

        self._appeals[appeal_id] = appeal
        logger.info(f"Appeal submitted: {appeal_id} for flag {flag_id}")

        # Immediately start AI review
        self._start_ai_review(appeal)

        return appeal

    def _start_ai_review(self, appeal: FraudAppeal) -> None:
        """Start AI-assisted review of an appeal."""
        appeal.status = AppealStatus.IN_PROGRESS
        logger.info(f"Starting AI review for appeal {appeal.appeal_id}")

        # Run verification checks
        result = self._run_verification(appeal)
        appeal.auto_review_score = result.confidence

        # Auto-approve if high confidence
        if result.confidence >= self.AUTO_APPROVE_THRESHOLD and result.verified:
            appeal.status = AppealStatus.AUTO_APPROVED
            appeal.reviewed_at = datetime.now()
            appeal.reviewer_notes = (
                f"Auto-approved: Verification score {result.confidence:.2f}. "
                f"Checks passed: {', '.join(result.checks_passed)}"
            )
            self._unblock_account(appeal.account_id)
            logger.info(f"Appeal {appeal.appeal_id} auto-approved")

        # Auto-reject if very low confidence and clear fraud indicators
        elif result.confidence <= self.AUTO_REJECT_THRESHOLD and not result.verified:
            appeal.status = AppealStatus.REJECTED
            appeal.reviewed_at = datetime.now()
            appeal.reviewer_notes = (
                f"Auto-rejected: Verification score {result.confidence:.2f}. "
                f"Checks failed: {', '.join(result.checks_failed)}"
            )
            logger.info(f"Appeal {appeal.appeal_id} auto-rejected")

    def _run_verification(self, appeal: FraudAppeal) -> VerificationResult:
        """
        Run AI-assisted verification checks.

        Returns:
            VerificationResult with checks and recommendation
        """
        checks_passed = []
        checks_failed = []
        score = 0.5  # Start neutral

        # Check 1: Account history
        if self._check_account_history(appeal.account_id):
            checks_passed.append("account_history_clean")
            score += 0.15
        else:
            checks_failed.append("account_history_suspicious")
            score -= 0.15

        # Check 2: Payment verification
        if self._check_payment_verification(appeal.account_id):
            checks_passed.append("payment_verified")
            score += 0.15
        else:
            checks_failed.append("payment_unverified")
            score -= 0.1

        # Check 3: Supporting documents
        if appeal.supporting_documents:
            checks_passed.append("documents_provided")
            score += 0.1
        else:
            checks_failed.append("no_documents")

        # Check 4: Statement analysis
        if len(appeal.customer_statement) > 50:
            checks_passed.append("detailed_statement")
            score += 0.1
        else:
            checks_failed.append("brief_statement")

        # Clamp score
        score = max(0.0, min(1.0, score))

        verified = score >= 0.5
        recommendation = (
            AppealStatus.APPROVED if score >= self.AUTO_APPROVE_THRESHOLD
            else AppealStatus.REJECTED if score <= self.AUTO_REJECT_THRESHOLD
            else AppealStatus.PENDING
        )

        return VerificationResult(
            verified=verified,
            confidence=score,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            recommendation=recommendation
        )

    def _check_account_history(self, account_id: str) -> bool:
        """Check if account has clean history."""
        # In production, this would query account history
        return True

    def _check_payment_verification(self, account_id: str) -> bool:
        """Check if payment methods are verified."""
        # In production, this would check payment verification status
        return True

    def _unblock_account(self, account_id: str) -> bool:
        """
        Automatically unblock an account after successful appeal.

        Args:
            account_id: Account to unblock

        Returns:
            True if unblock successful
        """
        logger.info(f"Unblocking account {account_id}")
        # In production, this would interact with the account service
        return True

    def get_appeal(self, appeal_id: str) -> Optional[FraudAppeal]:
        """Get an appeal by ID."""
        return self._appeals.get(appeal_id)

    def get_appeals_for_account(self, account_id: str) -> List[FraudAppeal]:
        """Get all appeals for an account."""
        return [a for a in self._appeals.values() if a.account_id == account_id]

    def get_pending_appeals(self) -> List[FraudAppeal]:
        """Get all pending appeals."""
        return [
            a for a in self._appeals.values()
            if a.status in (AppealStatus.PENDING, AppealStatus.IN_PROGRESS)
        ]

# Module-level convenience function
_processor: Optional[FraudAppealProcessor] = None

def get_fraud_appeal_processor() -> FraudAppealProcessor:
    """Get the global fraud appeal processor instance."""
    global _processor
    if _processor is None:
        _processor = FraudAppealProcessor()
    return _processor
