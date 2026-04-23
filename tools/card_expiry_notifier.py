#!/usr/bin/env python3
"""
Card Expiry Notifier Tool

Sends proactive notifications to customers before their payment card expires.

Requirements (per customer-service-standards.md Section 1.3):
- Proactive notification 30 days before expiry
- Reminder at 7 days before expiry
- Easy update flow from notification email
- Graceful handling of expired cards

Usage:
    python card_expiry_notifier.py --check           # Check for expiring cards
    python card_expiry_notifier.py --notify-30      # Send 30-day warnings
    python card_expiry_notifier.py --notify-7       # Send 7-day warnings
    python card_expiry_notifier.py --run            # Full daily check and notify
"""

import argparse
import logging
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from enum import Enum
from typing import Optional, Callable, Iterator
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NotificationType(Enum):
    """Type of expiry notification."""
    THIRTY_DAY = "30_day"
    SEVEN_DAY = "7_day"
    EXPIRED = "expired"

@dataclass
class PaymentCard:
    """A customer's stored payment card."""
    card_id: str
    customer_id: str
    customer_email: str
    last_four: str
    card_type: str  # visa, mastercard, amex, discover
    nickname: Optional[str]
    expiry_month: int
    expiry_year: int
    is_default: bool = False

    @property
    def expiry_date(self) -> date:
        """Get expiration date (last day of expiry month)."""
        if self.expiry_month == 12:
            return date(self.expiry_year + 1, 1, 1) - timedelta(days=1)
        return date(self.expiry_year, self.expiry_month + 1, 1) - timedelta(days=1)

    @property
    def is_expired(self) -> bool:
        """Check if card is expired."""
        return date.today() > self.expiry_date

    @property
    def days_until_expiry(self) -> int:
        """Days until card expires (negative if already expired)."""
        return (self.expiry_date - date.today()).days

    @property
    def display_name(self) -> str:
        """Human-readable card name."""
        name = self.nickname or f"{self.card_type.title()} ending in {self.last_four}"
        return name

@dataclass
class NotificationRecord:
    """Record of a sent notification."""
    card_id: str
    customer_id: str
    notification_type: NotificationType
    sent_at: datetime
    email_sent: bool
    error: Optional[str] = None

class CardExpiryNotifier:
    """
    Sends proactive notifications for expiring payment cards.

    Features:
    - Check for cards expiring in 30 days and 7 days
    - Send email notifications with update link
    - Track which notifications have been sent (avoid duplicates)
    - Configurable email templates
    """

    def __init__(
        self,
        card_repository=None,
        email_sender: Optional[Callable] = None,
        notification_tracker=None,
        update_card_url: str = "https://app.example.com/account/payment-methods"
    ):
        """
        Initialize card expiry notifier.

        Args:
            card_repository: Repository for fetching cards
            email_sender: Callable for sending emails (email, subject, body)
            notification_tracker: Tracker for sent notifications
            update_card_url: URL for customers to update their card
        """
        self._cards = card_repository or {}
        self._email_sender = email_sender
        self._notifications = notification_tracker or {}
        self._update_url = update_card_url

    def _was_notification_sent(
        self,
        card_id: str,
        notification_type: NotificationType
    ) -> bool:
        """Check if notification was already sent for this card."""
        key = f"{card_id}:{notification_type.value}"
        return key in self._notifications

    def _record_notification(
        self,
        card: PaymentCard,
        notification_type: NotificationType,
        email_sent: bool,
        error: Optional[str] = None
    ) -> NotificationRecord:
        """Record that a notification was sent."""
        record = NotificationRecord(
            card_id=card.card_id,
            customer_id=card.customer_id,
            notification_type=notification_type,
            sent_at=datetime.utcnow(),
            email_sent=email_sent,
            error=error
        )
        key = f"{card.card_id}:{notification_type.value}"
        self._notifications[key] = record
        return record

    def get_expiring_cards(self, days: int) -> Iterator[PaymentCard]:
        """
        Get cards expiring within the specified number of days.

        Args:
            days: Number of days to look ahead

        Yields:
            PaymentCard objects expiring within the timeframe
        """
        target_date = date.today() + timedelta(days=days)

        for card in self._cards.values():
            if isinstance(card, PaymentCard):
                if 0 <= card.days_until_expiry <= days:
                    yield card

    def get_cards_expiring_in_30_days(self) -> Iterator[PaymentCard]:
        """Get cards expiring in approximately 30 days (25-35 day range)."""
        for card in self._cards.values():
            if isinstance(card, PaymentCard):
                days = card.days_until_expiry
                if 25 <= days <= 35:
                    yield card

    def get_cards_expiring_in_7_days(self) -> Iterator[PaymentCard]:
        """Get cards expiring in approximately 7 days (3-10 day range)."""
        for card in self._cards.values():
            if isinstance(card, PaymentCard):
                days = card.days_until_expiry
                if 3 <= days <= 10:
                    yield card

    def _build_email_subject(self, card: PaymentCard, notification_type: NotificationType) -> str:
        """Build email subject line."""
        if notification_type == NotificationType.THIRTY_DAY:
            return f"Your {card.display_name} expires in {card.days_until_expiry} days"
        elif notification_type == NotificationType.SEVEN_DAY:
            return f"Reminder: Your {card.display_name} expires soon"
        else:
            return f"Your {card.display_name} has expired"

    def _build_email_body(self, card: PaymentCard, notification_type: NotificationType) -> str:
        """Build email body."""
        days = card.days_until_expiry
        card_name = card.display_name

        if notification_type == NotificationType.THIRTY_DAY:
            return f"""Hi there,

Your payment method "{card_name}" will expire in {days} days.

To avoid any interruption to your service, please update your payment information before the expiration date.

Update your payment method here:
{self._update_url}

If you've already updated your card or have questions, just reply to this email.

Thanks,
The Enter Robotics Team"""

        elif notification_type == NotificationType.SEVEN_DAY:
            return f"""Hi there,

This is a reminder that your payment method "{card_name}" will expire in {days} days.

Please update your payment information to avoid any service interruption.

Update your payment method here:
{self._update_url}

After your card expires, we'll retry your payment method before suspending service - but it's best to update now to avoid any hassle.

Thanks,
The Enter Robotics Team"""

        else:  # EXPIRED
            return f"""Hi there,

Your payment method "{card_name}" has expired.

Please update your payment information to continue your service without interruption.

Update your payment method here:
{self._update_url}

If you need help or have questions, just reply to this email.

Thanks,
The Enter Robotics Team"""

    def send_notification(
        self,
        card: PaymentCard,
        notification_type: NotificationType
    ) -> NotificationRecord:
        """
        Send an expiry notification for a card.

        Args:
            card: Card to notify about
            notification_type: Type of notification to send

        Returns:
            NotificationRecord with send status
        """
        # Check if already sent
        if self._was_notification_sent(card.card_id, notification_type):
            logger.debug(f"Notification already sent for card {card.card_id}")
            return self._notifications[f"{card.card_id}:{notification_type.value}"]

        subject = self._build_email_subject(card, notification_type)
        body = self._build_email_body(card, notification_type)

        email_sent = False
        error = None

        if self._email_sender:
            try:
                self._email_sender(card.customer_email, subject, body)
                email_sent = True
                logger.info(
                    f"Sent {notification_type.value} notification for card "
                    f"{card.last_four} to {card.customer_email}"
                )
            except Exception as e:
                error = str(e)
                logger.error(f"Failed to send notification: {e}")
        else:
            logger.info(
                f"Would send {notification_type.value} notification for card "
                f"{card.last_four} (no email sender configured)"
            )

        return self._record_notification(card, notification_type, email_sent, error)

    def run_30_day_check(self) -> list[NotificationRecord]:
        """
        Run 30-day expiry check and send notifications.

        Returns:
            List of NotificationRecord for sent notifications
        """
        results = []
        for card in self.get_cards_expiring_in_30_days():
            result = self.send_notification(card, NotificationType.THIRTY_DAY)
            results.append(result)
        return results

    def run_7_day_check(self) -> list[NotificationRecord]:
        """
        Run 7-day expiry check and send notifications.

        Returns:
            List of NotificationRecord for sent notifications
        """
        results = []
        for card in self.get_cards_expiring_in_7_days():
            result = self.send_notification(card, NotificationType.SEVEN_DAY)
            results.append(result)
        return results

    def run_daily_check(self) -> dict[str, list[NotificationRecord]]:
        """
        Run full daily check for all expiry notifications.

        Returns:
            Dict with notification type keys and lists of NotificationRecords
        """
        return {
            "30_day": self.run_30_day_check(),
            "7_day": self.run_7_day_check()
        }

def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Card Expiry Notifier - Send proactive card expiry notifications"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check for expiring cards (no notifications sent)"
    )
    parser.add_argument(
        "--notify-30",
        action="store_true",
        help="Send 30-day expiry notifications"
    )
    parser.add_argument(
        "--notify-7",
        action="store_true",
        help="Send 7-day expiry notifications"
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Run full daily check and notify"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually send emails"
    )

    args = parser.parse_args()

    # Initialize notifier (in production, connect to real data sources)
    notifier = CardExpiryNotifier()

    if args.check:
        print("Checking for expiring cards...")
        print("\n30-day expiry:")
        for card in notifier.get_cards_expiring_in_30_days():
            print(f"  - {card.display_name}: expires in {card.days_until_expiry} days")
        print("\n7-day expiry:")
        for card in notifier.get_cards_expiring_in_7_days():
            print(f"  - {card.display_name}: expires in {card.days_until_expiry} days")

    elif args.notify_30:
        print("Sending 30-day notifications...")
        results = notifier.run_30_day_check()
        print(f"Sent {len(results)} notifications")

    elif args.notify_7:
        print("Sending 7-day notifications...")
        results = notifier.run_7_day_check()
        print(f"Sent {len(results)} notifications")

    elif args.run:
        print("Running daily check...")
        results = notifier.run_daily_check()
        print(f"30-day notifications: {len(results['30_day'])}")
        print(f"7-day notifications: {len(results['7_day'])}")

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
