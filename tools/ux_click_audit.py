"""
UX Click Count Audit Tool

Quarterly audit tool to verify all common actions are reachable in 3 or fewer clicks.
Per customer-service-standards.md Section 16.7:
- All common actions should be reachable in 3 clicks or fewer
- Quarterly UX audits
- Results stored in LogBook/ux/click_audits/
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Set
from datetime import datetime
from enum import Enum
import logging
import uuid

logger = logging.getLogger(__name__)

class ClickCompliance(Enum):
    """Compliance status for click count."""
    COMPLIANT = "compliant"          # 3 or fewer clicks
    WARNING = "warning"              # 4 clicks
    NON_COMPLIANT = "non_compliant"  # 5+ clicks

class ActionCategory(Enum):
    """Categories of user actions."""
    NAVIGATION = "navigation"
    ACCOUNT = "account"
    BILLING = "billing"
    SUPPORT = "support"
    SETTINGS = "settings"
    CORE_FEATURE = "core_feature"
    SUBSCRIPTION = "subscription"

@dataclass
class ActionPath:
    """A user action and its click path."""
    action_id: str
    action_name: str
    category: ActionCategory
    starting_point: str
    click_path: List[str]
    click_count: int
    compliance: ClickCompliance
    notes: Optional[str] = None

@dataclass
class ClickAuditResult:
    """Result of a UX click count audit."""
    audit_id: str
    product_name: str
    audited_at: datetime
    auditor: str
    total_actions: int
    compliant_count: int
    warning_count: int
    non_compliant_count: int
    compliance_rate: float
    action_paths: List[ActionPath]
    recommendations: List[str]
    quarter: str  # e.g., "2026-Q1"

@dataclass
class ClickAuditConfig:
    """Configuration for click audits."""
    max_clicks_compliant: int = 3
    max_clicks_warning: int = 4
    common_actions: Dict[ActionCategory, List[str]] = field(default_factory=dict)

    def __post_init__(self):
        if not self.common_actions:
            self.common_actions = {
                ActionCategory.NAVIGATION: [
                    "Access main dashboard",
                    "View recent projects",
                    "Search for content",
                ],
                ActionCategory.ACCOUNT: [
                    "View account settings",
                    "Update profile",
                    "Change password",
                    "View login history",
                ],
                ActionCategory.BILLING: [
                    "View current subscription",
                    "Access billing history",
                    "Update payment method",
                    "Download invoice",
                ],
                ActionCategory.SUPPORT: [
                    "Access help center",
                    "Submit support ticket",
                    "View ticket status",
                    "Access FAQ",
                ],
                ActionCategory.SETTINGS: [
                    "Update preferences",
                    "Manage notifications",
                    "Export data",
                    "Delete account",
                ],
                ActionCategory.SUBSCRIPTION: [
                    "Upgrade plan",
                    "Downgrade plan",
                    "Cancel subscription",
                    "View plan features",
                ],
            }

class ClickAuditor:
    """
    Audits UX click counts for common actions.

    Ensures:
    - All common actions reachable in 3 clicks or fewer
    - Quarterly compliance tracking
    - Recommendations for improvement
    """

    def __init__(self, config: Optional[ClickAuditConfig] = None):
        """
        Initialize the click auditor.

        Args:
            config: Audit configuration
        """
        self.config = config or ClickAuditConfig()
        self._audit_history: List[ClickAuditResult] = []

    def audit_action(
        self,
        action_name: str,
        category: ActionCategory,
        click_path: List[str],
        starting_point: str = "Home"
    ) -> ActionPath:
        """
        Audit a single action's click path.

        Args:
            action_name: Name of the action
            category: Category of the action
            click_path: List of clicks required
            starting_point: Where the user starts

        Returns:
            ActionPath with compliance assessment
        """
        action_id = f"ACT-{uuid.uuid4().hex[:6].upper()}"
        click_count = len(click_path)

        if click_count <= self.config.max_clicks_compliant:
            compliance = ClickCompliance.COMPLIANT
        elif click_count <= self.config.max_clicks_warning:
            compliance = ClickCompliance.WARNING
        else:
            compliance = ClickCompliance.NON_COMPLIANT

        return ActionPath(
            action_id=action_id,
            action_name=action_name,
            category=category,
            starting_point=starting_point,
            click_path=click_path,
            click_count=click_count,
            compliance=compliance
        )

    def run_audit(
        self,
        product_name: str,
        action_paths: List[ActionPath],
        auditor_name: str = "UX Click Auditor"
    ) -> ClickAuditResult:
        """
        Run a full UX click audit.

        Args:
            product_name: Product being audited
            action_paths: List of action paths to audit
            auditor_name: Name of auditor

        Returns:
            ClickAuditResult with findings
        """
        audit_id = f"UXAUDIT-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now()
        quarter = f"{now.year}-Q{(now.month - 1) // 3 + 1}"

        compliant = sum(1 for a in action_paths if a.compliance == ClickCompliance.COMPLIANT)
        warning = sum(1 for a in action_paths if a.compliance == ClickCompliance.WARNING)
        non_compliant = sum(1 for a in action_paths if a.compliance == ClickCompliance.NON_COMPLIANT)
        total = len(action_paths)

        compliance_rate = (compliant / total * 100) if total > 0 else 0

        # Generate recommendations
        recommendations = self._generate_recommendations(action_paths)

        result = ClickAuditResult(
            audit_id=audit_id,
            product_name=product_name,
            audited_at=now,
            auditor=auditor_name,
            total_actions=total,
            compliant_count=compliant,
            warning_count=warning,
            non_compliant_count=non_compliant,
            compliance_rate=compliance_rate,
            action_paths=action_paths,
            recommendations=recommendations,
            quarter=quarter
        )

        self._audit_history.append(result)
        logger.info(
            f"Audit {audit_id} complete: {compliance_rate:.1f}% compliant, "
            f"{non_compliant} non-compliant actions"
        )

        return result

    def _generate_recommendations(self, paths: List[ActionPath]) -> List[str]:
        """Generate improvement recommendations."""
        recommendations = []

        # Find non-compliant paths
        non_compliant = [p for p in paths if p.compliance == ClickCompliance.NON_COMPLIANT]

        for path in non_compliant:
            recommendations.append(
                f"Reduce clicks for '{path.action_name}' from {path.click_count} to 3 or fewer. "
                f"Consider: shortcuts, reorganizing navigation, or adding quick-access links."
            )

        # Category-level recommendations
        category_issues: Dict[ActionCategory, int] = {}
        for path in non_compliant:
            category_issues[path.category] = category_issues.get(path.category, 0) + 1

        for category, count in category_issues.items():
            if count >= 2:
                recommendations.append(
                    f"Multiple {category.value} actions are non-compliant ({count}). "
                    f"Consider a dedicated quick-access panel for {category.value} actions."
                )

        if not recommendations:
            recommendations.append("All actions meet the 3-click standard. No changes needed.")

        return recommendations

    def get_audit_history(self) -> List[ClickAuditResult]:
        """Get history of all audits."""
        return self._audit_history.copy()

    def get_quarterly_report(self, quarter: str) -> Optional[ClickAuditResult]:
        """Get the audit result for a specific quarter."""
        matching = [a for a in self._audit_history if a.quarter == quarter]
        return matching[-1] if matching else None

    def generate_report(self, result: ClickAuditResult) -> str:
        """
        Generate a human-readable click audit report.

        Args:
            result: Audit result to report on

        Returns:
            Formatted report string
        """
        lines = [
            "UX Click Count Audit Report",
            "=" * 50,
            f"Audit ID: {result.audit_id}",
            f"Product: {result.product_name}",
            f"Quarter: {result.quarter}",
            f"Date: {result.audited_at.isoformat()}",
            f"Auditor: {result.auditor}",
            "",
            "Summary",
            "-" * 30,
            f"Total Actions Audited: {result.total_actions}",
            f"Compliant (3 clicks): {result.compliant_count}",
            f"Warning (4 clicks): {result.warning_count}",
            f"Non-Compliant (5+ clicks): {result.non_compliant_count}",
            f"Compliance Rate: {result.compliance_rate:.1f}%",
            "",
        ]

        # Non-compliant actions
        non_compliant = [p for p in result.action_paths if p.compliance == ClickCompliance.NON_COMPLIANT]
        if non_compliant:
            lines.append("Non-Compliant Actions")
            lines.append("-" * 30)
            for action in non_compliant:
                lines.append(f"  - {action.action_name}: {action.click_count} clicks")
                lines.append(f"    Path: {' -> '.join([action.starting_point] + action.click_path)}")
            lines.append("")

        # Recommendations
        lines.append("Recommendations")
        lines.append("-" * 30)
        for i, rec in enumerate(result.recommendations, 1):
            lines.append(f"  {i}. {rec}")

        return "\n".join(lines)

    def export_to_logbook(self, result: ClickAuditResult) -> str:
        """
        Export audit result to LogBook format.

        Returns:
            Path where the report would be saved
        """
        report_path = f"LogBook/ux/click_audits/{result.quarter}_{result.product_name}.md"
        logger.info(f"Exporting audit to {report_path}")
        # In production, would write to filesystem
        return report_path

# Module-level convenience
_auditor: Optional[ClickAuditor] = None

def get_click_auditor() -> ClickAuditor:
    """Get the global click auditor instance."""
    global _auditor
    if _auditor is None:
        _auditor = ClickAuditor()
    return _auditor
