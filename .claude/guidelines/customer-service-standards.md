# Customer Service Standards & Infrastructure Requirements

> **Version:** 2.2.0
> **Last Updated:** 2026-01-02
> **Owner:** PM / Human
> **Classification:** Tier 2 - Operational Guidelines
> **Related Lane:** Lane E (Customer Services & Data Protection)

---

## Purpose

This guideline defines the comprehensive standards for customer-facing systems, payment processing, support infrastructure, and data protection for Enter Robotics - a solo-founder AI-powered B2B SaaS portfolio company.

**Business Context:**
- Solo founder, one-man operation (for now)
- Multiple B2B SaaS products under "Enter Robotics" brand
- Service-based (software automation, starting with HVAC)
- Support constraint: < 2 hours/week per product - MUST automate everything
- Target customers: Small B2B firms (1-10 people), technical users who can self-serve
- Pricing: $30-40/month, 60-70% cheaper than competitors

---

## 1. Payment & Billing Infrastructure

### 1.1 Multiple Payment Methods

| Method | Priority | Implementation |
|--------|----------|----------------|
| Credit/Debit Cards | Required | Visa, Mastercard, Amex, Discover |
| PayPal | Required | Standard integration |
| Apple Pay | Recommended | Mobile + web |
| Google Pay | Recommended | Mobile + web |
| Bank Transfer / ACH | Optional | For annual plans |
| Square | Optional | Card payments (POS-ready) |
| Klarna | Optional | BNPL - Pay Later, Pay in 4, Financing |

**Files to Check:**
- `src/payments/providers/*.py` (stripe, paypal, apple_pay, google_pay, square, klarna)
- `checkout/payment_methods.py`
- `templates/adapters/payment-adapter.jinja2`

#### 1.1.1 Buy Now Pay Later (BNPL) - Klarna

**Klarna Payment Options:**

| Option | Amount Range | Description |
|--------|-------------|-------------|
| Pay Now | Any | Immediate payment via card/bank |
| Pay in 30 Days | $35-$1,000 | Single payment in 30 days, interest-free |
| Pay in 4 | $35-$1,500 | 4 bi-weekly payments, interest-free |
| Monthly Financing | $200-$10,000 | 6-36 month terms, APR may apply |

**Eligibility:**
- Available for annual plans, lifetime purchases, enterprise tiers
- US customers only (initially)
- Customer must pass Klarna's soft credit check
- Not available for monthly subscriptions

**Handling BNPL:**
- Display available Klarna options based on cart amount
- Use Klarna.js widget for seamless checkout experience
- Acknowledge orders within 24 hours of authorization
- Capture payment when order ships/activates

**Handling BNPL Failures:**
- If Klarna declines, offer alternative payment methods
- Do not store or display decline reasons (privacy)
- Suggest card payment as fallback
- No embarrassing messaging

**Files to Check:**
- `src/payments/providers/klarna.py`
- `src/payments/bnpl/eligibility.py`
- `src/payments/bnpl/installment_tracker.py`
- `src/checkout/klarna_widget.py`

#### 1.1.2 Square Integration

**Square Features:**
- Card payments via Square Payments API
- Card on File for returning customers
- Multi-location support (future retail/POS)
- Webhook-driven payment confirmations

**Files to Check:**
- `src/payments/providers/square.py`
- `src/payments/webhooks/square_webhooks.py`
- `src/checkout/square_widget.py`

### 1.2 Saved Payment Methods

**Requirements:**
- Securely tokenize cards (never store raw card numbers)
- PCI-DSS compliant storage
- Allow customers to add/remove/set default
- Card nickname support ("Work Visa", "Personal Amex")

**Files to Check:**
- `src/accounts/payment_methods.py`
- `src/payments/saved_methods.py`

### 1.3 Card Expiry Handling

**Requirements:**
- Proactive notification 30 days before expiry
- Reminder at 7 days before expiry
- Graceful handling of expired card during transaction
- Easy update flow from notification email

**Files to Check:**
- `tools/card_expiry_notifier.py`- `templates/emails/card_expiring.jinja2`
### 1.4 Card Decline Handling

**UX Requirements:**
- Handle gracefully - no embarrassment
- Clear, friendly error message
- Immediate retry option
- Alternative payment method suggestion

**Messaging Example:**
- ❌ "Your card was declined"
- ✅ "We couldn't process this card. Want to try another payment method?"

### 1.5 Subscription Payment Failures (Grace Period)

**Grace Period: Exactly 1 WEEK (7 days)**

| Day | Action |
|-----|--------|
| Day 0 | Payment fails - auto-retry |
| Day 1 | Email: "Payment failed - please update" |
| Day 3 | Email: "Reminder - update payment to keep access" |
| Day 6 | Email: "Final notice - access suspended tomorrow" |
| Day 7 | Access suspended (not deleted) |

**Requirements:**
- Never accidentally discontinue service
- Clear messaging about timeline
- Easy link to update payment method
- Access suspended, not account deleted (can restore)

**Files to Check:**
- `src/subscriptions/grace_period.py`
- `src/payments/retry.py`
- `templates/emails/payment_grace_day1.jinja2`- `templates/emails/payment_grace_day3.jinja2`- `templates/emails/payment_grace_day6.jinja2`- `templates/emails/payment_final_notice.jinja2`
### 1.6 Fraud Block Recovery

**When legitimate customer flagged as fraud:**
- Clear communication: "Your account was flagged for review"
- Easy appeal process
- Fast resolution (AI-assisted review)
- Automatic unblock after verification

### 1.7 Prevent Accidental Discontinuation

**Safeguards:**
- Grace period before any suspension
- Multiple notification attempts
- Suspension is reversible
- Data preserved during suspension

### 1.8 Invoice & Receipt Access

**Requirements:**
- All past invoices/receipts accessible in account
- PDF download option
- Email re-send option
- Search/filter by date, amount, status
- Business customers: VAT invoice support

**Files to Check:**
- `src/billing/invoices.py`
- `src/accounts/receipts.py`

### 1.9 Subscription Management

**Subscription Features:**
| Feature | Description |
|---------|-------------|
| Pause | Temporarily suspend without canceling |
| Skip | Skip next billing cycle |
| Upgrade/Downgrade | Change plan mid-cycle |
| Proration | Fair billing on plan changes |
| Cancel | With retention offers |

**Files to Check:**
- `src/subscriptions/pause.py`
- `src/subscriptions/skip.py`
- `src/billing/proration.py`

### 1.10 Refund Policy

**Core Principle:** Fair refunds for unused time. No questions asked, but abuse is tracked.

#### 1.10.1 Monthly Subscriptions

| Scenario | Refund Amount |
|----------|---------------|
| Request during current billing month | Full refund for current month |
| Previous months already used | No refund (value already extracted) |

**Example:** Customer subscribed Jan 1, requests refund on Jan 20
- Refund: January payment (current month)
- No refund for any prior months

#### 1.10.2 Annual Subscriptions

| Scenario | Refund Amount |
|----------|---------------|
| Unused months remaining | Pro-rata refund for unused portion |
| Current month | Included in refund |
| Previous months used | No refund |

**Calculation:** `Refund = (Remaining months + Current month) × Monthly equivalent rate`

**Example:** Customer on annual plan ($300/year = $25/mo equivalent)
- Subscribed: January 1
- Refund requested: September 15 (9 months into subscription)
- Months used: Jan-Aug (8 months)
- Current month: September (refundable)
- Remaining months: Oct, Nov, Dec (3 months)
- **Refund: 4 months × $25 = $100** (current month + 3 remaining)

#### 1.10.3 Refund Process

**Customer Experience:**
1. Self-service refund request in account settings
2. No questions asked - refund processed automatically
3. Confirmation email with refund amount and timeline
4. Refund to original payment method (3-5 business days)

**No Interrogation:**
- Do NOT require reason for refund
- Do NOT guilt-trip or add friction
- Do NOT require phone call or human approval
- Simply process and move on

#### 1.10.4 Abuse Prevention

**Pattern Tracking:**
- Log all refund requests per account
- Track by: Customer account ID + IP address + Payment method fingerprint

**Abuse Threshold:** 3 refund requests

| Refund Count | Action |
|--------------|--------|
| 1st refund | Process normally, log |
| 2nd refund | Process normally, flag for monitoring |
| 3rd refund | Process normally, add to abuse watch list |
| 4th+ attempt | Block subscription, show message |

**Block Message:**
> "We're unable to process a new subscription for this account. If you believe this is an error, please contact support."

**Tracking Identifiers:**
- Customer account ID (primary)
- IP address (secondary - catches new accounts)
- Payment card fingerprint (catches card reuse)
- Email domain pattern (optional - for disposable emails)

**Circumvention Prevention:**
- If new account matches blocked IP → flag for review
- If new account uses same payment card → auto-block
- If new account uses known disposable email domain → require verification

**Files to Check:**
- `src/billing/refunds.py`
- `src/billing/refund_calculator.py`
- `src/billing/abuse_tracker.py`
- `src/accounts/subscription_blocks.py`

### 1.11 Chargeback & Dispute Handling

**Core Principle:** Prevent chargebacks through easy refunds. When they happen, respond systematically.

#### 1.11.1 Chargeback Prevention

**Best Prevention = Easy Refunds**
- If customer can self-service refund in 2 clicks, they won't call their bank
- Chargebacks cost $15-25 in fees PLUS the refund amount
- Much cheaper to just refund proactively

**Billing Descriptor Clarity:**
- Use recognizable descriptor: "ENTERROBOTICS" or "ENTERROB*PRODUCTNAME"
- NOT cryptic codes that confuse customers
- Include support URL in descriptor if possible

**Pre-Charge Communication:**
- Send receipt immediately after charge
- Send renewal reminder 7 days before recurring charge
- Clear subject line: "Your [Product] subscription renewed - $X charged"

#### 1.11.2 Chargeback Types

| Type | Description | Response |
|------|-------------|----------|
| True Fraud | Card stolen, unauthorized use | Accept, refund, assist customer |
| Friendly Fraud | Customer got service but disputes | Fight with evidence |
| Confusion | Didn't recognize charge on statement | Provide clarity, often withdraws |
| Subscription Forgot | Forgot they subscribed | Show signup evidence, offer refund |

#### 1.11.3 Response Process

**When Chargeback Received:**

| Step | Action | Timeline |
|------|--------|----------|
| 1 | Alert received from payment processor | Day 0 |
| 2 | Auto-gather evidence from logs | Day 0 (automated) |
| 3 | Assess chargeback type | Day 1 |
| 4 | Decide: Fight or Accept | Day 1 |
| 5 | Submit response OR accept | Day 2-5 |
| 6 | Await decision | 30-90 days |

**Response Deadline:** Most processors require response within 7-14 days. Submit within 5 days.

#### 1.11.4 Evidence to Collect (Automated)

**For Every Transaction, Log:**
- Customer IP address at signup
- Device fingerprint
- Signup timestamp
- Email confirmation sent/opened
- Terms of Service acceptance timestamp
- Login history after purchase
- Feature usage logs (proves service was used)
- Any support conversations

**Evidence Package for Disputes:**
| Evidence Type | Purpose |
|---------------|---------|
| Signup confirmation email | Proves customer initiated |
| ToS acceptance log | Customer agreed to terms |
| IP + Device match | Same device used service |
| Usage logs | Service was accessed/used |
| Support transcripts | Any prior communication |
| Refund policy link | Customer had easy refund option |

#### 1.11.5 Fight vs. Accept Decision

**Auto-Accept (Don't Fight):**
| Scenario | Reason |
|----------|--------|
| Amount < $25 | Cost of fighting exceeds recovery |
| No usage logs | Hard to prove value delivered |
| Customer claims true fraud | Legitimate victim, accept gracefully |
| First-time customer, first charge | Little evidence, not worth fighting |

**Fight These:**
| Scenario | Reason |
|----------|--------|
| Clear usage logs showing service used | Strong evidence |
| Customer contacted support before dispute | Shows awareness |
| Multiple chargebacks from same customer | Pattern of abuse |
| High-value transaction with evidence | Worth the effort |

#### 1.11.6 Chargeback Ratio Monitoring

**Critical Threshold:** Keep chargeback ratio below 1%

| Ratio | Status | Action |
|-------|--------|--------|
| < 0.5% | Healthy | Monitor normally |
| 0.5% - 0.75% | Caution | Review prevention measures |
| 0.75% - 1.0% | Warning | Immediate action required |
| > 1.0% | Critical | Risk of processor termination |

**Calculation:** `Chargeback Ratio = Chargebacks / Total Transactions (rolling 30 days)`

**If Ratio Climbs:**
- Review refund process friction
- Check billing descriptor clarity
- Audit renewal notification timing
- Consider adding pre-dunning reminders

#### 1.11.7 Friendly Fraud Repeat Offenders

**Track customers who file chargebacks after using service:**

| Chargeback Count | Action |
|------------------|--------|
| 1st chargeback | Log, monitor |
| 2nd chargeback | Block from future subscriptions |
| Pattern detected | Add to industry blacklist (if available) |

**Blocking Identifiers:**
- Customer email
- Payment card fingerprint
- IP address range
- Device fingerprint

#### 1.11.8 Post-Chargeback Communication

**If We Accept:**
> "We've processed a refund for your recent charge. Your account has been closed. We're sorry [Product] wasn't the right fit."

**If We Fight and Win:**
- Account remains suspended until resolved
- If we win: Account stays closed (customer showed bad faith)
- Do NOT re-engage customer

**If We Fight and Lose:**
- Accept the loss
- Block customer from future signups
- Log for pattern analysis

**Files to Check:**
- `src/billing/chargebacks.py`
- `src/billing/dispute_responder.py`
- `src/billing/evidence_collector.py`
- `src/billing/chargeback_monitor.py`
- `LogBook/billing/chargebacks/`

### 1.12 Cancellation Flow & Retention

**Core Principle:** Make cancellation easy but offer genuine value to stay. No dark patterns.

#### 1.12.1 Cancellation Philosophy

**What We DO:**
- Clear, findable cancel button (≤ 3 clicks from dashboard)
- Self-service cancellation (no phone call required)
- Offer genuine alternatives before final cancel
- Respect their decision if they proceed

**What We DON'T Do:**
- Hide cancel in deep menus
- Require phone call to cancel (illegal in some places)
- Guilt-trip or manipulate
- Make them confirm 5 times
- Send aggressive "win-back" emails after cancellation

#### 1.12.2 Cancellation Flow Steps

```
Dashboard → Account → Subscription → Cancel
                         ↓
              "Before you go..." (retention offers)
                         ↓
              [Accept Offer] or [Continue to Cancel]
                         ↓
              Quick feedback (optional, skippable)
                         ↓
              Confirmation: "Your subscription will end on [date]"
                         ↓
              Access continues until billing period ends
```

**Total Clicks to Cancel:** 4-5 (including confirmation)

#### 1.12.3 Retention Offers

**Offer Based on Cancel Reason:**

| Reason Selected | Retention Offer |
|-----------------|-----------------|
| Too expensive | Offer discount (see 1.12.4) |
| Not using it enough | Offer pause (1-3 months) |
| Missing features | Log request, offer pause until feature ships |
| Switching to competitor | Offer discount + ask what competitor has |
| Temporary situation | Offer pause |
| Just trying it out | Offer extended trial or downgrade |
| Other / No reason | Offer pause or discount |

#### 1.12.4 Discount Retention Offers

**Discount Strategy:**

| Customer Type | Discount Offer | Duration |
|---------------|----------------|----------|
| First 3 months | 25% off next 2 months | One-time |
| 3-6 months tenure | 30% off next 3 months | One-time |
| 6-12 months tenure | 40% off next 3 months | One-time |
| 12+ months tenure | 50% off next 3 months | One-time |

**Rules:**
- Only ONE discount retention offer per customer per year
- If they cancel again within 6 months: No discount offer (just pause)
- Track discount acceptance in customer record

**Display:**
> "We'd hate to see you go! How about 30% off your next 3 months? That's [amount] saved."
> [Accept & Stay] [No thanks, continue canceling]

#### 1.12.5 Pause vs Cancel

**Pause Option (Preferred):**

| Feature | Pause | Cancel |
|---------|-------|--------|
| Account access | Suspended | Ends at period end |
| Data retained | Yes (indefinitely) | Yes (90 days then deleted) |
| Billing | Stops immediately | Stops at period end |
| Resume | One-click | Re-subscribe |
| Settings preserved | Yes | No (starts fresh) |

**Pause Durations:**
- 1 month
- 2 months
- 3 months (max)

**After Max Pause:** Auto-converts to cancelled if not resumed

**Pause Messaging:**
> "Need a break? Pause your subscription for up to 3 months. Your data and settings will be waiting when you return."

#### 1.12.6 Downgrade Path

**If on higher tier, offer downgrade before cancel:**

| Current Plan | Offer |
|--------------|-------|
| Enterprise | Downgrade to Pro |
| Pro | Downgrade to Basic |
| Basic | Offer pause or discount |

**Downgrade Messaging:**
> "Would a smaller plan work better? Switch to [Lower Plan] at $X/month and keep access to [key features]."

#### 1.12.7 Exit Feedback (Optional)

**Quick Survey - MUST be skippable:**

```
Why are you canceling? (Select one)
○ Too expensive
○ Not using it enough
○ Missing features I need
○ Found a better alternative
○ Temporary - I'll be back
○ Other

[Skip] [Submit & Cancel]
```

**Rules:**
- Single question only
- Skip button prominent
- No guilt-tripping copy
- Thank them regardless

#### 1.12.8 Post-Cancellation

**Immediate:**
- Confirmation email with end date
- Reminder: "Access continues until [date]"
- Data export reminder: "Download your data before [date]"

**At Period End:**
- Account access suspended (not deleted)
- Data retained for 90 days
- One "We miss you" email allowed (optional)

**Data Deletion:**
- 90 days after cancellation: Data deletion scheduled
- Email warning at 80 days: "Your data will be deleted in 10 days"
- Option to re-subscribe and retain data

#### 1.12.9 Win-Back (Light Touch Only)

**What's Allowed:**
| Timing | Action |
|--------|--------|
| At cancellation | Retention offers (above) |
| 30 days after | ONE "We miss you" email (optional) |
| 90 days (before deletion) | Data deletion warning |

**What's NOT Allowed:**
- Weekly win-back emails
- SMS/push after cancellation
- Aggressive discounting via email
- "Last chance" pressure tactics

**Win-Back Email Tone:**
> "Hi [Name], just checking in. If things have changed and you'd like to come back, your account is ready. No pressure either way. [Resubscribe button]"

#### 1.12.10 Metrics to Track

| Metric | Purpose |
|--------|---------|
| Cancellation rate | Overall health |
| Reason distribution | Product improvements |
| Retention offer acceptance | Offer effectiveness |
| Pause vs cancel ratio | Pause feature usage |
| Win-back rate | Re-subscription success |
| Time to cancel (clicks) | UX friction check |

**Files to Check:**
- `src/subscriptions/cancellation.py`
- `src/subscriptions/retention.py`
- `src/subscriptions/pause.py`
- `src/subscriptions/downgrade.py`
- `src/feedback/exit_survey.py`
- `templates/emails/cancellation_confirm.jinja2`
- `templates/emails/winback.jinja2`

### Payment Type Tags
`PaymentMethodGap`, `SavedPaymentGap`, `CardExpiryGap`, `CardDeclineUXGap`, `GracePeriodGap`, `FraudRecoveryGap`, `AccidentalDiscontinuationRisk`, `InvoiceAccessGap`, `SubscriptionPauseGap`, `ProrationGap`, `RefundPolicyGap`, `RefundAbuseGap`, `ChargebackGap`, `DisputeHandlingGap`, `FriendlyFraudGap`, `CancellationFlowGap`, `RetentionOfferGap`, `WinBackGap`

---

## 2. AI-First Support Infrastructure

### 2.1 Support Philosophy

**Core Principle:** AI handles ALL customer interactions. No human intervention required at any stage.

| Stage | Support Model |
|-------|---------------|
| 0-100 customers | AI chatbot + docs + FAQ |
| 100-500 customers | AI chatbot + community helpers |
| 500-1000 customers | AI + community forums |
| 1000+ customers | Consider hiring support manager |

**Core Requirement:** AI handles ALL customer interactions. No human intervention required at any stage.

### 2.2 AI Chatbot (Primary Support)

**Requirements:**
- Handles most common questions without human intervention
- Per-product knowledge bases (different products = different contexts)
- Trained on product documentation, FAQ, common issues
- Graceful handoff messaging when it can't help
- Available 24/7

**Files to Check:**
- `src/support/ai_chatbot.py`
- `src/support/product_knowledge/`
- `integration/config/chatbot_training/`

### 2.3 AI Voice Bot (Optional Channel)

**Requirements:**
- For customers who prefer voice interaction
- Same knowledge base as chatbot
- Must work without human intervention
- Context windows are finite - sessions end gracefully

**Files to Check:**
- `src/support/ai_voicebot.py`

### 2.4 Suspicious Request Handling

**When request seems "fishy":**
1. AI responds: "Let me check with my team on that"
2. Actually: AI runs security checks
3. Checks: Would this leak customer data? System data?
4. If safe: Proceed with response
5. If unsafe: Decline gracefully with explanation

**This is NOT human escalation - it's automated security review.**

**Files to Check:**
- `src/support/security_check.py`
- `src/security/request_validator.py`

### 2.5 Community Forums (500+ Customers)

**Requirements:**
- Users help other users
- Reduces support burden
- Power users become community helpers
- Founder monitors but doesn't respond to everything

### 2.6 Self-Service Documentation

**Priority Order:**
1. Comprehensive FAQ (answers 80% of questions)
2. Knowledge base articles
3. Video tutorials (skippable)
4. In-app tooltips and guidance
5. AI chatbot (for remaining questions)

**Principle:** Customer should find answer before needing to ask.

### 2.7 Conversation Logging (Pseudo-Infrastructure)

**Status:** LOGGING ACTIVE, ANALYSIS DEFERRED

**Purpose:** Capture all AI support conversations for future analysis.

**Current State:**
| Component | Status |
|-----------|--------|
| Conversation logging | ACTIVE - all chats/voice saved |
| Log storage | ACTIVE - retained indefinitely |
| Edge case analysis | DEFERRED - future agent |
| Bad info detection | DEFERRED - future agent |

**Future Use (When Infrastructure Ready):**
- Agent analyzes if original AI gave bad/incorrect info
- Identifies edge cases AI couldn't handle
- Improves AI training data
- Flags patterns requiring product changes

**What's Logged:**
- Full conversation transcript
- Customer ID (anonymized for analysis)
- Product context
- Timestamp
- Resolution status (solved/unsolved)
- Customer satisfaction signal (if provided)

**Files (Stubs):**
- `src/support/conversation_logger.py` - ACTIVE (logs everything)
- `src/support/log_storage.py` - ACTIVE (stores logs)
- `src/support/log_analyzer.py` - STUB (future agent)
- `src/support/bad_info_detector.py` - STUB (future agent)
- `LogBook/support/conversations/` - Log storage location

**Type Tags:** `ConversationLoggingActive`, `LogAnalysisDeferred`, `EdgeCaseDetectionDeferred`

### 2.8 Communication Preferences

**Preferences:**
| Setting | Options |
|---------|---------|
| Channel | Email, Push, In-App, None |
| Frequency | Real-time, Daily digest, Weekly |
| Types | Marketing, Transactional, Security |
| Time | Respect quiet hours |

**Files to Check:**
- `src/notifications/preferences.py`
- `src/accounts/communication_settings.py`

### 2.9 Language & Timezone

**Requirements:**
- UI language preference persisted
- All notifications respect timezone
- No marketing emails at 3am local time
- Date/time format localization

**Files to Check:**
- `src/accounts/locale.py`
- `src/notifications/timezone.py`

### Support Type Tags
`AIFirstSupportGap`, `ChatbotGap`, `VoiceBotGap`, `CommunityForumGap`, `SelfServeDocsGap`, `CommPrefsGap`, `LanguagePrefsGap`, `TimezoneGap`

---

## 3. Account Security & Access

### 3.1 Session Management

**Requirements:**
- View all active sessions
- Device name/type visible
- Location (city/country) visible
- Last activity timestamp
- "Log out all other devices" button
- Individual session revocation

**Files to Check:**
- `src/accounts/sessions.py`
- `src/security/session_manager.py`

### 3.2 Login History

**Requirements:**
- Last 50+ login attempts visible
- Timestamp, IP, location, device
- Success/failure status
- Suspicious activity flagging
- Downloadable for security review

**Files to Check:**
- `src/security/login_history.py`
- `LogBook/security/login_audit/`

### 3.3 Security Alerts

**Automatic Alerts For:**
| Event | Notification |
|-------|--------------|
| New device login | Email + push |
| New location login | Email + push |
| Password changed | Email |
| Email changed | Email (to old AND new) |
| 2FA disabled | Email |
| Multiple failed logins | Email |

**Files to Check:**
- `src/security/alerts.py`
- `templates/emails/new_login_alert.jinja2`- `templates/emails/security_alert.jinja2`
### 3.4 Multi-Factor Authentication Options

| Method | Security Level | Ease of Use |
|--------|----------------|-------------|
| TOTP App | High | Medium |
| Email OTP | Medium | High |
| Hardware Key (FIDO2) | Highest | Low |
| Backup Codes | High | Emergency only |
| Biometric | High | Highest |

**Requirements:**
- At least 3 MFA options
- Backup codes always available
- Trusted device option
- Recovery without phone access

**Files to Check:**
- `src/auth/mfa/*.py`
- `src/auth/backup_codes.py`

### 3.5 Password Security

**Requirements:**
- Secure hashing (bcrypt/argon2)
- Email confirmation on change
- Old password required to change
- Password strength meter
- Breach database check (HaveIBeenPwned)
- No password hints stored

**Files to Check:**
- `src/auth/password.py`
- `tools/password_breach_check.py`
### 3.6 Social Login Management

**Requirements:**
- Link multiple providers (Google, Apple, etc.)
- Unlink without losing account access
- Clear which providers are linked
- Primary email management

**Files to Check:**
- `src/auth/social_links.py`
- `src/auth/oauth_providers/*.py`

### 3.7 Account Recovery Options

**Recovery Methods (minimum 3):**
- Email verification
- Backup codes
- Security questions
- Identity verification (ID upload)

**Files to Check:**
- `src/accounts/recovery/multi_method.py`
- `src/auth/recovery_options.py`

### 3.8 Hacked Account Response

**Requirements:**
- Clear incident response process
- Immediate account lockdown option
- Session termination across all devices
- Password reset enforcement
- Review of recent account activity
- Notification to customer

**Files to Check:**
- `src/accounts/recovery/hack_response.py`
- `PLANNING/policies/hacked_account.md`

### 3.9 Duplicate Account Merge

**Use Cases:**
- Guest checkout → registered account
- Duplicate accounts (same person)
- Same email, different auth methods

**Requirements:**
- Subscription history combined
- Single sign-on after merge
- Usage data preserved

**Files to Check:**
- `src/accounts/merge.py`
- `tools/account_merge_tool.py`
### 3.10 Email Lookup by Alternative Identifiers

**When customer forgot email:**
- Lookup by phone number
- Lookup by billing address
- Lookup by last 4 of payment card
- Verification required before revealing

**Files to Check:**
- `src/accounts/recovery/email_lookup.py`

### Security Type Tags
`SessionMgmtGap`, `LoginHistoryGap`, `SecurityAlertGap`, `2FAOptionsGap`, `PasswordSecurityGap`, `SocialLoginGap`, `RecoveryOptionsGap`, `HackedAccountGap`, `AccountMergeGap`, `EmailLookupGap`

---

## 4. Onboarding & Tutorial System

### 4.1 Welcome Sequence

**Requirements:**
- Triggered for NEW customers only
- Teaches how to use purchased product
- Skippable at any point
- Per-product (different tutorial per product type)
- Does NOT pop up for returning customers

**Implementation:**
- Track: Has user completed/skipped onboarding?
- If completed/skipped: Never show again
- If new: Show welcome sequence

**Files to Check:**
- `src/onboarding/tutorial_tracker.py`
- `src/onboarding/welcome_sequence.py`
- `src/onboarding/product_tutorials/`

### 4.2 Tutorial Accessibility

**Requirements:**
- Tutorials accessible later in FAQ/Help section
- User can re-watch anytime
- Searchable by topic

### 4.3 In-App Guidance

**Requirements:**
- Tooltips on first use of features
- Wizards for complex workflows
- Pre-built templates with common configurations
- Strong defaults (works out of box)

### Onboarding Type Tags
`OnboardingGap`, `TutorialGap`, `WelcomeSequenceGap`, `InAppGuidanceGap`

---

## 5. Proactive Notifications

### 5.1 Transactional Notifications

| Event | Timing | Channels |
|-------|--------|----------|
| Subscription Started | Immediate (< 30 sec) | Email |
| Payment Confirmed | Immediate | Email |
| Payment Failed | On event + retry schedule | Email |
| Subscription Renewed | On event | Email |
| Subscription Cancelled | On event | Email |

### 5.2 Security Notifications

| Event | Timing | Channels |
|-------|--------|----------|
| New Login | Immediate | Email + Push |
| Password Changed | Immediate | Email |
| 2FA Changed | Immediate | Email |
| Account Locked | Immediate | Email |

### 5.3 Product Update Notifications

| Event | Timing | Channels |
|-------|--------|----------|
| New Feature Announcement | When released | Email (optable) |
| Maintenance Window | 24hr+ advance | Email + In-App |
| Outage Detected | On event | In-App |
| Outage Resolved | On event | Email |

**Files to Check:**
- `src/notifications/triggers/*.py`
- `src/notifications/channels/*.py`
- `templates/emails/*.jinja2`

### Notification Type Tags
`NotificationGap`, `RenewalWarningGap`, `SecurityNotificationGap`, `MaintenanceNoticeGap`, `OutageNotificationGap`

---

## 6. Trust & Transparency

### 6.1 Pricing Transparency

**Requirements:**
- Clear pricing on website (no "contact for quote")
- Sign up online immediately (no sales calls)
- All fees visible before checkout
- No hidden costs

**Display:**
- Monthly price
- Annual price (with savings highlighted)
- What's included at each tier
- Comparison with competitors (we're 60-70% cheaper)

### 6.2 Free Trial / Freemium

**Requirements:**
- Free tier to reduce friction
- Limited features (e.g., X uses per month)
- Upgrade path clear
- No credit card required for trial

### 6.3 Policy Visibility

**Visible Policies:**
| Policy | Location |
|--------|----------|
| Privacy Policy | Footer, signup, checkout |
| Terms of Service | Footer, signup |
| Refund Policy | Footer, pricing page |
| Contact Information | Header/footer, not buried |

### 6.4 Trust Signals

**Elements:**
- Secure checkout indicators
- Real customer testimonials (when available)
- Uptime statistics (when reliable)

**Files to Check:**
- `templates/checkout/trust_signals.jinja2`

### Trust Type Tags
`HiddenFeeRisk`, `PolicyClarityGap`, `ContactVisibilityGap`, `TrustSignalGap`, `PriceTransparencyGap`, `FreeTierGap`

---

## 7. Security & Trust Communication

### 7.1 Core Security Messaging

**Primary Message:** "Security is our main priority"

**Trust Promises:**
- We don't steal your data
- We don't sell your data
- Fair use of your work
- Your designs/data won't be leaked

### 7.2 AI Training Data Opt-In

**Model:** Opt-IN (not opt-out)
**Default:** NOT sharing

**Requirements:**
- Customer explicitly chooses to share data
- Clear explanation of what sharing means
- Easy opt-out at any time
- Purpose: "Help improve the service you love"

**Product-Specific Example (HVAC):**
- Share: Design layouts for AI training
- Benefit: AI handles more complex scenarios
- Protection: Data anonymized before training

**Files to Check:**
- `src/consent/ai_training_optin.py`
- `src/data/anonymization.py`
- `templates/consent/ai_training_explainer.jinja2`

### 7.3 Product-Specific Reassurance

**When customer expresses concern:**
- Proactive reassurance messaging
- Product-specific privacy explanations
- Example: HVAC customers worried about design leaks → reassure them

**Files to Check:**
- `src/trust/security_reassurance.py`
- `templates/trust/product_specific_reassurance/`

### Security Trust Type Tags
`SecurityReassuranceGap`, `DataOptInGap`, `AITrainingConsentGap`, `FairUseGap`

---

## 8. Edge Cases & Special Handling

### 8.1 Deceased Customer Handling

**Requirements:**
- Documented process for family/estate
- Required documentation (death certificate)
- Account closure or transfer options
- Sensitive communication templates
- Subscription cancellation with refund

**Files to Check:**
- `src/accounts/special_cases/deceased.py`
- `PLANNING/policies/deceased_customer.md`

### 8.2 Minor Account Handling

**COPPA Compliance:**
- Age verification at signup
- Parental consent for under-13
- Parental controls available
- Limited data collection for minors
- Easy parental account management

**Files to Check:**
- `src/accounts/special_cases/minor.py`
- `src/auth/age_verification.py`

### 8.3 Business vs Personal Accounts

**Differences:**
| Feature | Personal | Business |
|---------|----------|----------|
| VAT/Tax ID | No | Yes |
| Invoicing | Basic | Detailed |
| Multi-user | No | Yes |
| Volume discounts | No | Yes |

**Note:** Volume discounts are for seat quantity, not tenure. This is separate from the deferred loyalty program.

| Discount Type | Status | Description |
|---------------|--------|-------------|
| Volume (seats) | BUILD NOW | Buy 5+ seats = discount per seat |
| Tenure (loyalty) | DEFERRED | 6mo/1yr = % off (requires profitability) |

**Files to Check:**
- `src/accounts/account_types.py`
- `src/billing/business_invoicing.py`
- `src/billing/volume_discounts.py`

### 8.4 Multi-User & Team Accounts

**Features:**
- Primary account holder
- Add/remove team members
- Role-based access
- Individual vs shared billing
- Activity visibility settings

**Files to Check:**
- `src/accounts/multi_user.py`
- `src/accounts/teams.py`

### 8.5 Power of Attorney / Authorized Users

**Requirements:**
- Legal documentation upload
- Verification process
- Scoped access (view only, full access)
- Audit trail of authorized actions
- Revocation process

**Files to Check:**
- `src/accounts/special_cases/authorized_user.py`
- `PLANNING/policies/power_of_attorney.md`

### 8.6 Fraud vs False Positive Handling

**Requirements:**
- Don't block legitimate customers
- Clear communication when blocked
- Easy appeal process
- AI-assisted review (not human queue)
- Automatic unblock after verification

**Files to Check:**
- `src/security/fraud_review.py`
- `src/support/fraud_appeals.py`

### Edge Case Type Tags
`DeceasedHandlingGap`, `MinorAccountGap`, `BusinessAccountGap`, `MultiUserAccessGap`, `AuthorizedUserGap`, `FraudFalsePositiveRisk`

---

## 9. Exit Experience

### 9.1 Account Closure

**Self-service requirements:**
- Customer can close account without calling
- Clear process (not buried)
- Confirmation before deletion
- Grace period for recovery

### 9.2 Exit Survey (Optional)

**Requirements:**
- Show when customer leaves
- MUST be omittable (not forced)
- Customer should NOT feel pressured
- Simple: "Mind telling us why?" with skip option

**Tone:**
- Respectful of their decision
- No guilt-tripping
- Thank them for being a customer

### 9.3 Data Export Before Leaving

**Requirements:**
- Customer can download all their data
- Available before account closure
- Standard formats (JSON, CSV)

**Files to Check:**
- `src/accounts/exit_survey.py`
- `src/accounts/data_export.py`
- `templates/exit/survey_optional.jinja2`

### Exit Type Tags
`ExitSurveyGap`, `GracefulExitGap`, `DataExportGap`

---

## 10. Loyalty Program (Deferred - Pseudo-Infrastructure Only)

### Status: NOT IMPLEMENTED

**Activation Requirements:**
1. Business must be profitable
2. Founder explicit green light required
3. Margin verification before enabling

### Planned Tiers (When Enabled)

| Tenure | Discount |
|--------|----------|
| 6 months | 10% off future orders |
| 1+ year | 15% off |
| Continuing | Increases to cap |
| Maximum | 30% cap |

### Current State

| Component | Status |
|-----------|--------|
| Tenure tracking | ACTIVE (silent background) |
| Discount calculation | DISABLED (returns 0%) |
| UI messaging | DISABLED |
| "Why you got this discount" | DISABLED |

### Implementation Notes

- `src/loyalty/loyalty_config.yaml` has `enabled: false`
- Tenure is tracked from day 1 (ready when needed)
- When enabled: Discounts apply automatically based on tracked tenure
- Message template: "We noticed you've been with us for X - that's why you get this discount"

**Files (Stubs):**
- `src/loyalty/tenure_tracker.py` - Tracks tenure (runs silently)
- `src/loyalty/discount_calculator.py` - Returns 0% until enabled
- `src/loyalty/loyalty_config.yaml` - `enabled: false`

### Loyalty Type Tags
`LoyaltyDeferred`, `PseudoInfrastructure`, `FounderApprovalRequired`, `TenureTrackingGap`

---

## 11. Multi-Product Infrastructure

### 11.1 Product Partitioning

**Context:** Enter Robotics operates multiple B2B SaaS products. Customer service must be partitioned by product.

**Per-Product Separation:**
| Component | Partitioned? |
|-----------|--------------|
| AI chatbot knowledge | YES - different context per product |
| Onboarding tutorials | YES - product-specific |
| FAQ/Knowledge base | YES - product-specific |
| Support routing | YES - route to correct product context |
| Customer accounts | SHARED - single account across products |
| Billing | SHARED - unified billing |

### 11.2 Cross-Product Experience

**Requirements:**
- Single sign-on across products
- Unified billing dashboard
- Product-specific support contexts
- Cross-sell opportunities (suggest related products)

**Files to Check:**
- `src/products/registry.py`
- `src/support/product_router.py`
- `src/onboarding/product_specific/`

### Multi-Product Type Tags
`MultiProductGap`, `ProductPartitionGap`, `CrossProductGap`

---

## 12. Infrastructure Resilience

### 12.1 Cloud Provider Infrastructure

**Strategy:** Build infrastructure for all 3 major providers. Switch when founder decides.

| Provider | Status | Purpose |
|----------|--------|---------|
| AWS | Infrastructure ready | Option A |
| GCP | Infrastructure ready | Option B |
| Azure | Infrastructure ready | Option C |

**Current Primary:** TBD (founder decision pending)

**Failover Capability:**
- Can switch between any provider
- Infrastructure pre-built for all 3
- Decision on primary made when scaling

**Files to Check:**
- `infrastructure/providers/aws/`
- `infrastructure/providers/gcp/`
- `infrastructure/providers/azure/`
- `infrastructure/failover/provider_switch.py`

### 12.2 Outage Communication

**When outage occurs:**
- Proactive notification: "We know and are working on it"
- Status page updates
- Estimated resolution time (if known)
- Post-mortem after resolution

### 12.3 Update Scheduling

**Requirements:**
- Schedule updates during low-traffic periods
- Advance warning: "Updates happening at X time"
- Maintenance window announcements
- Minimize customer impact

**Files to Check:**
- `infrastructure/failover/cloud_switch.py`
- `infrastructure/monitoring/outage_detector.py`
- `templates/notifications/outage_notice.jinja2`
- `templates/notifications/update_warning.jinja2`

### Infrastructure Type Tags
`CloudFailoverGap`, `OutageCommunicationGap`, `UpdateTimingGap`

---

## 13. Accessibility (A11y)

### 13.1 Screen Reader Support

**Requirements:**
- Semantic HTML structure
- ARIA labels on interactive elements
- Alt text on all images
- Form labels properly associated
- Error messages announced

### 13.2 Keyboard Navigation

**Requirements:**
- All functions accessible via keyboard
- Logical tab order
- Visible focus indicators
- Skip navigation links
- No keyboard traps

### 13.3 Visual Accessibility

**Requirements:**
- Color contrast ratio (WCAG 2.1 AA)
- High contrast mode option
- Scalable text (up to 200%)
- No information conveyed by color alone
- Reduced motion option

### 13.4 Media Accessibility

**Requirements:**
- Video closed captions
- Video transcripts
- Audio descriptions
- Adjustable playback speed

**Files to Check:**
- `src/accessibility/preferences.py`
- External a11y tooling (axe-core or pa11y — not bundled)

### Accessibility Type Tags
`A11yScreenReaderGap`, `A11yKeyboardGap`, `A11yContrastGap`, `A11yFontScaleGap`, `A11yAltTextGap`, `A11yCaptionGap`

---

## 14. Recommended File Structure

```
src/
├── checkout/
│   └── one_click.py            # One-click purchasing
├── support/
│   ├── ai_chatbot.py           # Primary AI support
│   ├── ai_voicebot.py          # Voice-based AI (optional)
│   ├── product_knowledge/       # Per-product knowledge bases
│   ├── security_check.py       # "Checking with associates" handler
│   ├── product_router.py       # Route to correct product context
│   ├── conversation_logger.py  # ACTIVE - logs all chats
│   ├── log_storage.py          # ACTIVE - stores logs
│   ├── log_analyzer.py         # STUB - future edge case detection
│   └── bad_info_detector.py    # STUB - future QA agent
│
├── feedback/
│   └── feature_requests.py     # Power user request logging
│
├── onboarding/
│   ├── tutorial_tracker.py     # Track who's seen tutorial
│   ├── welcome_sequence.py     # Orchestrate welcome flow
│   └── product_tutorials/      # Per-product tutorial content
│
├── loyalty/
│   ├── tenure_tracker.py       # STUB - tracks tenure (active)
│   ├── discount_calculator.py  # STUB - returns 0% until enabled
│   └── loyalty_config.yaml     # enabled: false
│
├── subscriptions/
│   ├── grace_period.py         # 1-week grace period logic
│   ├── suspension.py           # Suspend (not delete) on non-payment
│   ├── pause.py                # Subscription pause
│   ├── skip.py                 # Skip billing cycle
│   └── retention.py            # Cancel flow with retention
│
├── consent/
│   ├── ai_training_optin.py    # Opt-in for data sharing
│   └── preferences.py          # Communication preferences
│
├── trust/
│   ├── security_reassurance.py # Reassurance messaging
│   └── product_specific_reassurance/
│
├── products/
│   └── registry.py             # Multi-product registry
│
├── accounts/
│   ├── sessions.py             # Active session management
│   ├── exit_survey.py          # Optional exit survey
│   ├── data_export.py          # Customer data export
│   ├── merge.py                # Duplicate account merge
│   ├── multi_user.py           # Team accounts
│   ├── teams.py                # Team management
│   ├── account_types.py        # Personal vs business
│   ├── power_user_tracker.py   # Track power user metrics
│   ├── recovery/
│   │   ├── lockout_flow.py
│   │   ├── hack_response.py
│   │   ├── email_lookup.py     # Lookup by alt identifiers
│   │   └── multi_method.py     # Multiple recovery paths
│   └── special_cases/
│       ├── deceased.py
│       ├── minor.py
│       └── authorized_user.py
│
├── payments/
│   ├── providers/              # Payment gateway integrations
│   │   ├── stripe.py
│   │   ├── paypal.py
│   │   └── apple_pay.py
│   ├── saved_methods.py        # Stored payment methods
│   └── retry.py                # Failed payment retry logic
│
├── billing/
│   ├── invoices.py             # Invoice generation
│   ├── proration.py            # Plan change billing
│   └── business_invoicing.py   # B2B invoicing
│
├── security/
│   ├── alerts.py               # Security notifications
│   ├── login_history.py        # Login audit
│   ├── fraud_review.py         # Fraud handling
│   ├── session_manager.py      # Session control
│   └── request_validator.py    # Suspicious request checks
│
├── notifications/
│   ├── preferences.py          # Communication preferences
│   ├── timezone.py             # Timezone-aware sending
│   ├── channels/               # Email, push, in-app
│   └── triggers/               # Subscription, security events
│
└── accessibility/
    ├── preferences.py          # User A11y settings
    └── audit.py                # A11y compliance checking

infrastructure/
├── providers/
│   ├── aws/                    # AWS infrastructure
│   ├── gcp/                    # GCP infrastructure
│   └── azure/                  # Azure infrastructure
├── failover/
│   └── provider_switch.py      # Switch between clouds
├── monitoring/
│   └── outage_detector.py
└── updates/
    └── low_traffic_scheduler.py

LogBook/
├── support/
│   └── conversations/          # All AI conversation logs
├── ux/
│   └── click_audits/           # Periodic UX audits
└── feedback/
    └── feature_requests/       # Power user request notebook

tools/
├── card_expiry_notifier.py
├── account_merge_tool.py
├── ux_click_audit.py           # Click count auditor
├── fraud_appeal_processor.py
└── password_breach_check.py

templates/
├── emails/
│   ├── payment_grace_day1.jinja2
│   ├── payment_grace_day3.jinja2
│   ├── payment_grace_day6.jinja2
│   ├── payment_final_notice.jinja2
│   ├── card_expiring.jinja2
│   ├── new_login_alert.jinja2
│   ├── security_alert.jinja2
│   └── subscription_renewal.jinja2
├── notifications/
│   ├── outage_notice.jinja2
│   └── update_warning.jinja2
├── consent/
│   └── ai_training_explainer.jinja2
├── trust/
│   └── product_specific_reassurance/
│       └── hvac.jinja2
└── exit/
    └── survey_optional.jinja2

PLANNING/policies/
├── hacked_account.md
├── deceased_customer.md
├── power_of_attorney.md
└── minor_account_policy.md
```

---

## 15. Power User Feature Requests (Logged Only)

### 15.1 System Overview

**Status:** REQUEST LOGGING ONLY - No commitment to implement

**Philosophy:** Power users (frequent/effective users) can request features. Requests are logged for founder review. Logging ≠ commitment.

### 15.2 Eligibility (Power Users)

**Tracked by:**
- Usage frequency (sessions per week)
- Feature utilization depth
- Account tenure
- Engagement metrics

**Threshold:** TBD by founder based on product data

### 15.3 Request Flow

```
Power user submits request
    ↓
Request logged to notebook
    ↓
(NO automatic response promising implementation)
    ↓
Founder reviews periodically
    ↓
If useful → Add to roadmap
If not useful → Stays in log (may make sense later)
```

### 15.4 What Gets Logged

| Field | Purpose |
|-------|---------|
| User ID | Track who requested |
| Product | Which product |
| Request description | What they want |
| Use case | Why they need it |
| Timestamp | When requested |
| User metrics | Usage stats at time of request |

### 15.5 What Does NOT Happen

- ❌ No promise to implement
- ❌ No timeline given
- ❌ No prioritization communicated
- ❌ No voting system (adds complexity)
- ❌ No public roadmap tied to requests

### 15.6 Founder Review Process

- Periodic review (weekly/monthly as time allows)
- Pattern recognition (multiple users requesting same thing)
- Cost/benefit assessment
- If implementing: Add to internal roadmap
- If not: Leave in log (context may change later)

**Files:**
- `src/feedback/feature_requests.py`
- `src/accounts/power_user_tracker.py`
- `LogBook/feedback/feature_requests/` - Request notebook

### Power User Type Tags
`FeatureRequestLogging`, `PowerUserTracking`, `RequestNotCommitment`

---

## 16. UX Philosophy & Self-Service Standards

### 16.1 Core UX Principles

**Philosophy:** Less clicks, more intuitive, never overwhelming.

| Principle | Description |
|-----------|-------------|
| **Minimal clicks** | Every common action in ≤ 3 clicks from dashboard |
| **Intuitive** | Should make sense without reading documentation |
| **Not overwhelming** | Most-wanted features prominent, advanced features discoverable |
| **Progressive disclosure** | Simple first, complexity on demand |
| **Don't bury** | Settings not hidden in deep menus |
| **Consistent** | Same patterns across all products |

### 16.2 Self-Service Click Targets

**Standard:** All common actions reachable in ≤ 3 clicks from dashboard.

| Action | Path | Max Clicks |
|--------|------|------------|
| Update payment method | Dashboard → Billing → Update | ≤ 3 |
| Pause subscription | Dashboard → Subscription → Pause | ≤ 3 |
| Resume subscription | Dashboard → Subscription → Resume | ≤ 3 |
| Download my data | Dashboard → Account → Export | ≤ 3 |
| Close account | Dashboard → Account → Close | ≤ 4 |
| Contact support | Any page → Help icon | ≤ 2 |
| Change password | Dashboard → Security → Password | ≤ 3 |
| Update email | Dashboard → Account → Email | ≤ 3 |
| View invoices | Dashboard → Billing → History | ≤ 3 |
| Change plan | Dashboard → Subscription → Change | ≤ 3 |

### 16.3 One-Click Purchasing

**Requirements:**
- Saved payment method + saved preferences = one click to buy/renew
- No re-entering information for returning customers
- Single confirmation before charge
- "Buy again" for repeat purchases

**Implementation:**
- Store payment method securely (tokenized)
- Remember last-used preferences
- Pre-fill everything possible
- One button: "Confirm Purchase"

**Files to Check:**
- `src/checkout/one_click.py`
- `src/payments/saved_methods.py`
- `src/accounts/purchase_preferences.py`

### 16.4 Feature Visibility Hierarchy

**What customers see first (prominent):**
1. Core product functionality
2. Account status / subscription info
3. Help / Support access
4. Billing / Payment

**What customers find when needed (discoverable):**
1. Advanced settings
2. Data export
3. Account closure
4. Detailed preferences

**What is hidden but accessible:**
1. Developer options (if any)
2. API access (if any)
3. Debug/diagnostic info

### 16.5 What We DON'T Offer

**Explicitly NOT available (by design):**

| Channel | Status | Reason |
|---------|--------|--------|
| Phone support | ❌ NO | Solo operation, not sustainable |
| Callback scheduling | ❌ NO | Solo operation, not sustainable |
| Human chat agents | ❌ NO | AI chatbot handles all |
| Email with human response | ❌ NO | AI auto-response, logs for edge cases |
| Live video support | ❌ NO | Not scalable |

**What we offer instead:**
- AI chatbot (24/7, instant)
- AI voice bot (24/7, instant)
- Comprehensive FAQ / knowledge base
- Community forums (500+ customers)
- Conversation logs reviewed for edge cases

### 16.6 Anti-Patterns to Avoid

**Never do these:**

| Anti-Pattern | Why It's Bad |
|--------------|--------------|
| Bury cancel/close in deep menus | Frustrates users, damages trust |
| Require phone call to cancel | Dark pattern, illegal in some jurisdictions |
| Hide pricing until checkout | Destroys trust |
| Force account creation before browsing | Adds friction |
| Email-only password reset | Single point of failure |
| Settings spread across 5+ pages | Confusing, wastes time |
| Different UX per product | Inconsistent, confusing |

### 16.7 Click Count Audit

**Periodic Check:** Audit all common actions quarterly.

| Audit Item | Target | Action if Exceeded |
|------------|--------|-------------------|
| Any action > 5 clicks | 0 occurrences | Redesign flow |
| Common actions > 3 clicks | 0 occurrences | Simplify |
| Support access > 2 clicks | 0 occurrences | Add help icon globally |

**Files to Check:**
- `tools/ux_click_audit.py`- `LogBook/ux/click_audits/`

### UX Type Tags
`ClickCountGap`, `UXDepthGap`, `OneClickPurchaseGap`, `FeatureDiscoverabilityGap`, `BuriedSettingsGap`, `DarkPatternRisk`

---

## 17. Complete Type Tags Reference

### Payment Tags
`PaymentMethodGap`, `SavedPaymentGap`, `CardExpiryGap`, `CardDeclineUXGap`, `GracePeriodGap`, `FraudRecoveryGap`, `AccidentalDiscontinuationRisk`, `InvoiceAccessGap`, `SubscriptionPauseGap`, `ProrationGap`, `RefundPolicyGap`, `RefundAbuseGap`, `ChargebackGap`, `DisputeHandlingGap`, `FriendlyFraudGap`, `CancellationFlowGap`, `RetentionOfferGap`, `WinBackGap`

### Support Tags
`AIFirstSupportGap`, `ChatbotGap`, `VoiceBotGap`, `CommunityForumGap`, `SelfServeDocsGap`, `CommPrefsGap`, `LanguagePrefsGap`, `TimezoneGap`

### Security Tags
`SessionMgmtGap`, `LoginHistoryGap`, `SecurityAlertGap`, `2FAOptionsGap`, `PasswordSecurityGap`, `SocialLoginGap`, `RecoveryOptionsGap`, `HackedAccountGap`, `AccountMergeGap`, `EmailLookupGap`

### Onboarding Tags
`OnboardingGap`, `TutorialGap`, `WelcomeSequenceGap`, `InAppGuidanceGap`

### Notification Tags
`NotificationGap`, `RenewalWarningGap`, `SecurityNotificationGap`, `MaintenanceNoticeGap`, `OutageNotificationGap`

### Trust Tags
`HiddenFeeRisk`, `PolicyClarityGap`, `ContactVisibilityGap`, `TrustSignalGap`, `PriceTransparencyGap`, `FreeTierGap`

### Security Trust Tags
`SecurityReassuranceGap`, `DataOptInGap`, `AITrainingConsentGap`, `FairUseGap`

### Edge Case Tags
`DeceasedHandlingGap`, `MinorAccountGap`, `BusinessAccountGap`, `MultiUserAccessGap`, `AuthorizedUserGap`, `FraudFalsePositiveRisk`

### Exit Tags
`ExitSurveyGap`, `GracefulExitGap`, `DataExportGap`

### Loyalty Tags
`LoyaltyDeferred`, `PseudoInfrastructure`, `FounderApprovalRequired`, `TenureTrackingGap`

### Multi-Product Tags
`MultiProductGap`, `ProductPartitionGap`, `CrossProductGap`

### Infrastructure Tags
`CloudFailoverGap`, `OutageCommunicationGap`, `UpdateTimingGap`

### Accessibility Tags
`A11yScreenReaderGap`, `A11yKeyboardGap`, `A11yContrastGap`, `A11yFontScaleGap`, `A11yAltTextGap`, `A11yCaptionGap`

### Logging Tags
`ConversationLoggingActive`, `LogAnalysisDeferred`, `EdgeCaseDetectionDeferred`

### Power User Tags
`FeatureRequestLogging`, `PowerUserTracking`, `RequestNotCommitment`

### UX Tags
`ClickCountGap`, `UXDepthGap`, `OneClickPurchaseGap`, `FeatureDiscoverabilityGap`, `BuriedSettingsGap`, `DarkPatternRisk`

### Tax Tags
`TaxCalculationGap`, `TaxNexusGap`, `VATComplianceGap`, `GSTComplianceGap`, `TaxExemptionGap`, `TaxIDValidationGap`, `TaxReportingGap`, `TaxDisplayGap`, `MoRConsiderationGap`, `TaxRefundHandlingGap`, `TaxInvoiceGap`

---

## 18. Tax Handling & Compliance

### 18.1 Tax Strategy Overview

**Primary Tool:** Stripe Tax (automated calculation + collection)

| Approach | Description | Use Case |
|----------|-------------|----------|
| Stripe Tax | Auto-calculates, you file returns | CURRENT CHOICE |
| MoR (Paddle/Lemon Squeezy) | They handle everything | Consider if filing burden too high |

**Why Stripe Tax:**
- Solo founder cannot track 11,000+ US tax jurisdictions manually
- Real-time rate updates (tax law changes constantly)
- Automatic location detection (billing address, IP, card BIN)
- Handles 40+ countries
- Integrated with existing Stripe payments

**Files to Check:**
- `src/billing/stripe_tax_integration.py`
- `src/payments/providers/stripe.py`

### 18.2 US Sales Tax

**SaaS Taxability by State:**
| Category | States | Notes |
|----------|--------|-------|
| SaaS is taxable | TX, PA, NY, WA, AZ, CT, HI, NM, OH, RI, SD, TN, UT | Must collect |
| SaaS is NOT taxable | CA, FL, IL, NV, NJ, VA, and ~25 others | No collection needed |
| Unclear/Evolving | Several states with pending legislation | Monitor |

**Economic Nexus Thresholds (when you MUST register):**
- Most states: $100,000 revenue OR 200 transactions in that state
- Some states: $100,000 only (no transaction count)
- Stripe Tax tracks this automatically

**Nexus Monitoring:**
- Stripe Tax dashboard shows approaching thresholds
- Email alerts when registration required
- Must register in state before collecting

**Files to Check:**
- `src/billing/nexus_tracker.py`

### 18.3 International Tax Requirements

#### 18.3.1 European Union (VAT)

| Scenario | Treatment |
|----------|-----------|
| B2C customer in EU | Charge VAT at customer's country rate |
| B2B customer with verified VAT ID | Reverse charge (0% VAT, customer self-assesses) |
| B2B customer, no VAT ID | Charge VAT at customer's country rate |

**Registration Requirement:**
- OSS (One-Stop Shop): Register in ONE EU country, report all EU sales there
- Threshold: No threshold for digital services - must register from first sale
- Stripe Tax can handle EU VAT without your own registration

**VAT Rates (examples):**
| Country | Standard Rate |
|---------|--------------|
| Germany | 19% |
| France | 20% |
| Netherlands | 21% |
| Ireland | 23% |
| Luxembourg | 17% |

#### 18.3.2 United Kingdom (Post-Brexit)

| Threshold | Requirement |
|-----------|-------------|
| < £85,000/year UK sales | No UK VAT registration required |
| >= £85,000/year UK sales | Must register for UK VAT |

**Treatment:**
- B2C: Charge 20% UK VAT
- B2B with valid VAT number: Reverse charge (0%)
- Stripe Tax handles UK VAT automatically

#### 18.3.3 Canada (GST/HST/PST)

| Province | Tax Type | Rate |
|----------|----------|------|
| Ontario | HST | 13% |
| Quebec | GST + QST | 5% + 9.975% |
| BC | GST + PST | 5% + 7% |
| Alberta | GST only | 5% |

**Registration:**
- GST/HST registration required at $30,000 CAD threshold
- Stripe Tax handles Canadian taxes

#### 18.3.4 Australia (GST)

| Threshold | Requirement |
|-----------|-------------|
| < $75,000 AUD/year | No GST registration required |
| >= $75,000 AUD/year | Must register for GST (10%) |

#### 18.3.5 India (GST)

- IGST at 18% for most SaaS services
- Must collect GSTIN from business customers
- Complex compliance - consider MoR if significant India revenue

**Files to Check:**
- `src/billing/international_tax.py`
- `src/billing/vat_calculator.py`
- `src/billing/business_invoicing.py`

### 18.4 Price Display Strategy

**Dynamic Display by Customer Location:**

| Customer Location | Display Style | Example |
|-------------------|---------------|---------|
| United States | Tax-exclusive | "$30/mo + applicable tax" |
| UK / EU | Tax-inclusive | "£30/mo (incl. VAT)" |
| Canada | Tax-exclusive | "$30 CAD/mo + GST/HST" |
| Australia | Tax-inclusive | "$40 AUD/mo (incl. GST)" |
| Other | Tax-exclusive | Price + "taxes may apply" |

**Implementation:**
- Detect location via IP geolocation at page load
- Adjust displayed prices accordingly
- Always show final price with tax at checkout (no surprises)

**Files to Check:**
- `src/pricing/display.py`
- `src/pricing/geo_detection.py`
- `templates/pricing/price_display.jinja2`

### 18.5 Tax Exemptions

#### 18.5.1 B2B Exemptions

| Region | Exemption Type | Requirement |
|--------|----------------|-------------|
| EU | Reverse Charge | Valid, verified VAT ID |
| UK | Reverse Charge | Valid UK VAT number |
| US | Resale Certificate | Valid state resale cert |
| Canada | GST/HST Exempt | Registration number |

#### 18.5.2 Other Exemptions

| Entity Type | Treatment | Documentation Required |
|-------------|-----------|----------------------|
| Nonprofits (501(c)(3)) | Exempt in most US states | IRS determination letter |
| Government agencies | Exempt | Government purchase order |
| Educational institutions | Varies by state | School verification |

**Exemption Workflow:**
1. Customer provides exemption documentation
2. System validates format and authenticity
3. If valid: Mark account as tax-exempt for that jurisdiction
4. Store certificate with expiration date
5. Auto-remind before expiration

**Files to Check:**
- `src/billing/tax_exemptions.py`
- `src/billing/exemption_certificates.py`
- `src/accounts/account_types.py`

### 18.6 Tax ID Validation

**Validation by Type:**

| Tax ID Type | Format | Validation Method |
|-------------|--------|-------------------|
| EU VAT | Country prefix + 8-12 chars | VIES API lookup |
| UK VAT | GB + 9 or 12 digits | HMRC API |
| US EIN | XX-XXXXXXX | Format check only |
| Canada GST | 9 digits + RT + 4 digits | CRA lookup |
| Australia ABN | 11 digits | ABR lookup |
| India GSTIN | 15 alphanumeric | Format + checksum |

**Storage Requirements:**
- Store tax_id with account
- Store verification status and timestamp
- Re-verify periodically (annually)
- Log verification attempts

**Files to Check:**
- `src/billing/tax_validator.py`
- `src/billing/vies_client.py`
- `src/billing/business_invoicing.py`

### 18.7 Invoice Requirements by Jurisdiction

**US Invoices:**
- No federal requirements for B2B
- State-specific rules (most just need seller info + itemization)
- Include: Company name, address, invoice number, date, line items, tax amount

**EU Invoices (Mandatory Fields):**
- Seller name, address, VAT number
- Buyer name, address, VAT number (if B2B)
- Sequential invoice number
- Invoice date + supply date
- Net amount, VAT rate, VAT amount, gross total
- Currency
- "Reverse charge" notation if applicable

**UK Invoices:**
- Similar to EU requirements
- Must show UK VAT number separately from any EU VAT number

**Files to Check:**
- `src/billing/invoices.py`
- `src/billing/business_invoicing.py`
- `templates/invoices/eu_invoice.jinja2`
- `templates/invoices/us_invoice.jinja2`

### 18.8 Compliance & Reporting

**Filing Obligations:**

| Jurisdiction | Frequency | Deadline |
|--------------|-----------|----------|
| US States | Quarterly or Monthly | Varies by state |
| EU (OSS) | Quarterly | End of month following quarter |
| UK VAT | Quarterly | 1 month + 7 days after quarter |
| Canada GST | Quarterly or Annual | Depends on revenue |

**Record Retention:**
- US: 3-7 years (varies by state)
- EU: 10 years
- UK: 6 years
- Canada: 6 years
- Australia: 5 years

**Recommendation:** Retain all records for 10 years (covers all jurisdictions)

**Stripe Tax Reporting:**
- Automatic reports for filing
- Export transaction data by jurisdiction
- Tax liability summaries

**Files to Check:**
- `src/billing/tax_reports.py`
- `LogBook/billing/tax_reports/`

### 18.9 Edge Cases

#### 18.9.1 Refunds
- Refund includes original tax collected
- Adjust tax liability for reporting period
- Stripe Tax handles automatically

#### 18.9.2 Plan Changes (Proration)
- Calculate proration on net amount
- Apply tax to prorated amount
- Different tax rates if crossing billing period boundaries

#### 18.9.3 Currency Considerations
- Tax calculated in transaction currency
- Convert to reporting currency for filing
- Use exchange rate at transaction date

#### 18.9.4 Digital Services Classification
- SaaS = Digital Service (not physical goods)
- No customs/import duties
- Subject to digital services taxes where applicable

#### 18.9.5 Customer Relocation
- Tax based on billing address at time of transaction
- If customer moves: Update address, new tax applies next billing
- No retroactive tax adjustments

**Files to Check:**
- `src/billing/proration.py`
- `src/billing/refund_tax.py`
- `src/accounts/address_change.py`

### 18.10 When to Consider Merchant of Record (MoR)

**Consider switching to MoR (Paddle/Lemon Squeezy) if:**
- Filing burden exceeds founder's time capacity
- Nexus in 10+ US states
- Significant EU/UK revenue requiring OSS registration
- India GST compliance becomes required
- Tax audit risk increases

**MoR Trade-offs:**
| Factor | Stripe Tax | MoR (Paddle) |
|--------|------------|--------------|
| Fees | ~0.5% for tax calc | 5-10% of revenue |
| Filing responsibility | You file returns | They handle everything |
| Control | Full control | Less control |
| Payment options | All (Stripe ecosystem) | Limited to their options |
| Customer relationship | Direct | Through MoR |

**Files to Check:**
- `PLANNING/policies/tax_compliance.md`
- `PLANNING/policies/mor_evaluation.md`

### Tax Type Tags
`TaxCalculationGap`, `TaxNexusGap`, `VATComplianceGap`, `GSTComplianceGap`, `TaxExemptionGap`, `TaxIDValidationGap`, `TaxReportingGap`, `TaxDisplayGap`, `MoRConsiderationGap`, `TaxRefundHandlingGap`, `TaxInvoiceGap`

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 2.6.0 | 2026-01-09 | Claude | Added: Section 1.12 - Cancellation Flow & Retention (easy cancel, retention offers by tenure, pause vs cancel, downgrade path, win-back limits, exit feedback) |
| 2.5.0 | 2026-01-09 | Claude | Added: Section 1.11 - Chargeback & Dispute Handling (prevention, evidence collection, fight vs accept logic, ratio monitoring, friendly fraud tracking) |
| 2.4.0 | 2026-01-09 | Claude | Added: Section 1.10 - Refund Policy (monthly/annual pro-rata refunds, no-questions-asked process, abuse prevention with 3-strike tracking by IP/account/card) |
| 2.3.0 | 2026-01-09 | Claude | Added: Section 18 - Tax Handling & Compliance (US sales tax, international VAT/GST, Stripe Tax integration, tax exemptions, price display by region, compliance/reporting requirements) |
| 2.2.0 | 2026-01-02 | Claude | Added: UX Philosophy section (click targets, one-click purchasing, anti-patterns, explicit "what we don't offer") |
| 2.1.0 | 2026-01-02 | Claude | Added: conversation logging (active), power user feature requests (logged only), multi-cloud infrastructure (all 3 providers), removed founder backup requirement, clarified volume vs tenure discounts |
| 2.0.0 | 2026-01-02 | Claude | Major revision: AI-first support model, removed physical products, added loyalty pseudo-infrastructure, aligned with Enter Robotics solo-founder business model |
| 1.0.0 | 2026-01-02 | Claude | Initial comprehensive customer service standards |

---

*This is a Tier 2 Operational Guideline. Use as reference for Lane E issue hunting.*
