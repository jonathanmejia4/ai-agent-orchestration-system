# Business Guidelines Quick Reference

> Short examples of what we actively look for in code.
> Not full guidelines - just quick reference for common patterns.

---

## Payment & Billing

### Card Expiry Handling
**Look for:** Expired card checks, expiry notifications
**Why:** Prevent failed renewals, reduce churn
**Files:** `payments/`, `subscriptions/`
**Example issue:** "No card expiry warning before renewal"

### Payment Failures & Grace Period
**Look for:** Retry logic, grace period handling, dunning emails
**Why:** Recover failed payments without losing customers
**Files:** `billing/retry.py`, `subscriptions/grace_period.py`
**Example issue:** "Subscription cancelled immediately on first failed payment"

### Refund Processing
**Look for:** Refund policy enforcement, proration, abuse tracking
**Why:** Fair refunds while preventing abuse
**Files:** `billing/refunds.py`, `billing/abuse_tracker.py`
**Example issue:** "No abuse tracking for repeat refund requesters"

### Chargeback Handling
**Look for:** Evidence collection, dispute responses, ratio monitoring
**Why:** Keep chargeback ratio under 1%, maintain payment processor access
**Files:** `billing/chargebacks.py`, `billing/dispute_responder.py`
**Example issue:** "No automated evidence collection for chargebacks"

---

## Customer Support

### Self-Service First
**Look for:** Help docs, FAQ, troubleshooting guides
**Why:** < 2 hours/week support time - automate everything
**Files:** `docs/`, `help/`, `support/`
**Example issue:** "Missing troubleshooting guide for common error"

### AI Chatbot
**Look for:** Product knowledge base, escalation paths
**Why:** Handle 90%+ of questions without human
**Files:** `support/ai_chatbot.py`, `support/product_knowledge/`
**Example issue:** "Chatbot missing answers for pricing questions"

### Escalation Paths
**Look for:** Human handoff triggers, urgent issue detection
**Why:** Some issues need human (billing disputes, angry customers)
**Files:** `support/escalation.py`
**Example issue:** "No way to reach human for billing issues"

---

## Data Protection

### PII Handling
**Look for:** Personal data encryption, access logs, retention policies
**Why:** GDPR compliance, customer trust
**Files:** `data/pii.py`, `data/encryption.py`
**Example issue:** "Unencrypted customer emails in database"

### Data Export (GDPR)
**Look for:** Data export functionality, deletion requests
**Why:** Legal requirement (GDPR Article 20)
**Files:** `accounts/data_export.py`, `accounts/deletion.py`
**Example issue:** "No way for customer to download their data"

### Audit Logging
**Look for:** Access logs, change tracking, admin actions
**Why:** Security, compliance, debugging
**Files:** `audit/`, `logging/`
**Example issue:** "Admin actions not logged"

---

## Subscription Management

### Cancellation Flow
**Look for:** Easy cancel, retention offers, exit surveys
**Why:** Low friction = trust, retention offers reduce churn
**Files:** `subscriptions/cancellation.py`, `subscriptions/retention.py`
**Example issue:** "Cancellation requires support ticket"

### Pause vs Cancel
**Look for:** Pause option before cancel
**Why:** Keeps customer in funnel, easier win-back
**Files:** `subscriptions/pause.py`
**Example issue:** "No pause option - only cancel"

### Downgrade Path
**Look for:** Plan downgrade flow, proration
**Why:** Keep customer at lower tier vs losing them entirely
**Files:** `subscriptions/downgrade.py`, `billing/proration.py`
**Example issue:** "No way to downgrade - must cancel and re-subscribe"

---

## Fraud & Abuse

### Payment Fraud
**Look for:** Fraud detection, block recovery flow
**Why:** Reduce fraud losses while helping legitimate blocked users
**Files:** `payments/fraud_detection.py`, `payments/block_recovery.py`
**Example issue:** "No way for fraud-blocked user to verify identity"

### Refund Abuse
**Look for:** Refund history tracking, abuse flags
**Why:** Stop repeat abusers from draining revenue
**Files:** `billing/abuse_tracker.py`
**Example issue:** "Same customer got 5 refunds - no flag"

### Account Sharing
**Look for:** Concurrent login limits, device tracking
**Why:** Prevent revenue loss from shared accounts
**Files:** `accounts/session_limits.py`
**Example issue:** "Unlimited concurrent logins on single-user plan"

---

## Customer Accounts

### Account Creation
**Look for:** Email verification, duplicate prevention, bot protection
**Why:** Prevent fake accounts, reduce spam signups
**Files:** `accounts/registration.py`, `auth/verification.py`
**Example issue:** "No email verification - fake accounts flooding system"

### Password Security
**Look for:** Hashing (bcrypt/argon2), min complexity, breach checks
**Why:** Protect customer credentials
**Files:** `auth/password.py`, `auth/password_policy.py`
**Example issue:** "Passwords stored in plain text"

### Session Management
**Look for:** Session timeouts, secure cookies, logout everywhere
**Why:** Prevent session hijacking
**Files:** `auth/sessions.py`, `auth/tokens.py`
**Example issue:** "Sessions never expire - token stolen, used forever"

### Account Recovery
**Look for:** Password reset flow, account lockout, recovery options
**Why:** Let legitimate users back in, block attackers
**Files:** `auth/recovery.py`, `auth/lockout.py`
**Example issue:** "No rate limit on password reset - email bomb"

### Account Deletion
**Look for:** Soft delete, data cleanup, GDPR compliance
**Why:** Legal requirement, customer trust
**Files:** `accounts/deletion.py`, `data/cleanup.py`
**Example issue:** "Account deleted but data still in database"

---

## Backend Security

### Authentication
**Look for:** JWT validation, token expiry, refresh tokens
**Why:** Prevent unauthorized access
**Files:** `auth/jwt.py`, `auth/middleware.py`
**Example issue:** "JWTs never expire"

### Authorization
**Look for:** Role checks, permission validation, admin guards
**Why:** Users only access what they should
**Files:** `auth/permissions.py`, `auth/roles.py`
**Example issue:** "Any user can access /admin endpoint"

### API Security
**Look for:** Rate limiting, input validation, CORS config
**Why:** Prevent abuse, injection attacks
**Files:** `api/rate_limit.py`, `api/validation.py`
**Example issue:** "No rate limiting - API can be DDoS'd"

### Database Security
**Look for:** Parameterized queries, connection pooling, encryption at rest
**Why:** Prevent SQL injection, data theft
**Files:** `db/queries.py`, `db/connection.py`
**Example issue:** "String concatenation in SQL query"

### Secrets Management
**Look for:** No hardcoded secrets, env vars, secret rotation
**Why:** Prevent credential leaks
**Files:** `.env`, `config/secrets.py`
**Example issue:** "API key hardcoded in source code"

---

## Protection from Malicious Activity

### Brute Force Protection
**Look for:** Login attempt limits, CAPTCHA, progressive delays
**Why:** Stop credential stuffing attacks
**Files:** `auth/brute_force.py`, `auth/captcha.py`
**Example issue:** "Unlimited login attempts - account takeover"

### Input Sanitization
**Look for:** XSS prevention, SQL injection, command injection
**Why:** Prevent attackers from injecting malicious code
**Files:** `utils/sanitize.py`, `api/validation.py`
**Example issue:** "User input rendered as HTML without escaping"

### File Upload Security
**Look for:** Type validation, size limits, malware scanning
**Why:** Prevent malicious file uploads
**Files:** `uploads/validation.py`, `uploads/scanner.py`
**Example issue:** "Can upload .exe files as 'images'"

### Webhook Validation
**Look for:** Signature verification, replay prevention
**Why:** Prevent fake webhook attacks (fake payment confirmations)
**Files:** `webhooks/validation.py`, `webhooks/stripe.py`
**Example issue:** "No signature check on Stripe webhooks"

### IP Blocking & Geofencing
**Look for:** IP blacklists, geo restrictions, VPN detection
**Why:** Block known bad actors, comply with sanctions
**Files:** `security/ip_block.py`, `security/geo.py`
**Example issue:** "No way to block abusive IP addresses"

---

## Infrastructure & Operations

### Logging & Monitoring
**Look for:** Error tracking, performance monitoring, alerts
**Why:** Know when things break, debug issues
**Files:** `logging/`, `monitoring/`
**Example issue:** "Errors silently swallowed - no visibility"

### Backups & Recovery
**Look for:** Automated backups, restore testing, disaster recovery
**Why:** Don't lose customer data
**Files:** `ops/backup.py`, `ops/restore.py`
**Example issue:** "No database backups - one failure = total loss"

### Rate Limiting
**Look for:** Per-user limits, per-endpoint limits, burst handling
**Why:** Prevent abuse, ensure fair usage
**Files:** `api/rate_limit.py`, `middleware/throttle.py`
**Example issue:** "One user can consume all API capacity"

### Health Checks
**Look for:** Endpoint health, dependency health, automated alerts
**Why:** Know when services are down
**Files:** `health/checks.py`, `health/alerts.py`
**Example issue:** "Database down for hours before anyone noticed"

---

## Governance & Audit Trails

### Complete Audit Entries
**Look for:** Timestamp, actor, action, target, result on every log
**Why:** Compliance, debugging, traceability - "who did what when"
**Files:** `logging/audit.py`, `middleware/audit.py`
**Example issue:** "Log entries missing actor field - can't trace who made change"

### Write Boundaries
**Look for:** Role-based path restrictions, who can write where
**Why:** Prevent unauthorized changes, separation of concerns
**Files:** `auth/boundaries.py`, `middleware/write_guard.py`
**Example issue:** "Any service can write to billing tables"

### Escalation Procedures
**Look for:** When to escalate, who to escalate to, timeout limits
**Why:** Humans must handle edge cases, security issues, disputes
**Files:** `support/escalation.py`, `workflows/approval.py`
**Example issue:** "Security alert went unnoticed for 3 days - no escalation"

### No Self-Approval
**Look for:** Review requirements, separation of duties
**Why:** Prevent fraud, catch mistakes, accountability
**Files:** `workflows/approval.py`, `billing/refund_approval.py`
**Example issue:** "Employee approved their own refund request"

---

## Marketing & Legal Compliance

### CAN-SPAM Compliance
**Look for:** Physical address, unsubscribe link, honest subjects
**Why:** $50,120 per violation - can kill company
**Files:** `email/templates/`, `email/compliance.py`
**Example issue:** "Marketing emails missing physical address"

### Web Scraping Rules
**Look for:** robots.txt respect, no bypass of protections, rate limits
**Why:** Legal liability, IP bans, reputation damage
**Files:** `scrapers/`, `data/collection.py`
**Example issue:** "Scraper ignoring robots.txt - could get sued"

### Cookie Consent
**Look for:** GDPR consent banner, preference storage, opt-out
**Why:** EU requirement, fines up to 4% of revenue
**Files:** `frontend/consent.js`, `api/consent.py`
**Example issue:** "Tracking cookies set before user consent"

### Terms of Service
**Look for:** Clear terms, user agreement tracking, version history
**Why:** Legal protection, dispute resolution
**Files:** `legal/tos.md`, `accounts/agreement_tracker.py`
**Example issue:** "No record of which TOS version user agreed to"

---

## Market Validation (Pre-Build)

### Pain Point Evidence
**Look for:** 3+ sources (Reddit, reviews, forums) documenting pain
**Why:** Build for real problems, not imaginary ones
**Files:** `research/pain_points.md`, `validation/evidence/`
**Example issue:** "Building feature nobody asked for"

### Competitor Analysis
**Look for:** Pricing comparison, feature gaps, user complaints
**Why:** Find positioning, avoid crowded markets
**Files:** `research/competitors.md`, `pricing/competitive_analysis.py`
**Example issue:** "Didn't know competitor launched same feature"

### TAM/SAM Estimation
**Look for:** Market size calculation, realistic capture rate
**Why:** Too small = not worth it, too large = attracts big players
**Files:** `research/market_size.md`
**Example issue:** "Market is only $100K/year - not worth building"

---

## Solo Founder Economics

### Support Automation
**Look for:** Self-serve solutions, knowledge base, chatbot
**Why:** <2 hours/week support time - can't scale otherwise
**Files:** `support/automation/`, `docs/help/`
**Example issue:** "Spending 10 hours/week on email support"

### Pricing Model
**Look for:** Per-seat, usage-based, flat rate comparison
**Why:** Wrong model = revenue leakage or churn
**Files:** `billing/pricing.py`, `subscriptions/tiers.py`
**Example issue:** "Enterprise customers paying same as hobbyists"

### Cost Tracking
**Look for:** Infrastructure costs, third-party APIs, margins
**Why:** Know true cost per customer, maintain profitability
**Files:** `ops/cost_tracker.py`, `reports/margins.py`
**Example issue:** "Didn't know OpenAI calls cost $50/customer/month"

---

## Code Integrity & Testing

### Idempotence
**Look for:** Same operation twice = same result, no side effects
**Why:** Safe retries, predictable deployments
**Files:** `jobs/`, `tasks/`, `migrations/`
**Example issue:** "Running job twice creates duplicate records"

### Test Pyramid
**Look for:** 70% unit, 20% integration, 10% E2E balance
**Why:** Fast feedback, maintainable tests
**Files:** `tests/unit/`, `tests/integration/`, `tests/e2e/`
**Example issue:** "All E2E tests - take 30 minutes to run"

### Quality Tiers
**Look for:** Critical (>=95%), Important (>=85%), Best Effort (>=70%)
**Why:** Not everything needs 100% - prioritize
**Files:** `.github/workflows/quality.yml`, `tests/coverage.py`
**Example issue:** "100% coverage on logging, 40% on payments"

### File Integrity
**Look for:** Checksums, tampering detection, baseline comparisons
**Why:** Detect unauthorized changes, security
**Files:** `security/integrity.py`, `ops/checksums.py`
**Example issue:** "Critical config file modified without audit trail"

---

## Dependency & Wiring

### Ghost References
**Look for:** Links/imports pointing to files that don't exist
**Why:** Runtime failures, broken features
**Files:** All code referencing other files
**Example issue:** "Import statement for deleted module"

### Circular Dependencies
**Look for:** A imports B, B imports A patterns
**Why:** Initialization errors, hard to refactor
**Files:** `src/`, module dependency graphs
**Example issue:** "Service A and Service B import each other"

### Version Consistency
**Look for:** Same library version across package files
**Why:** Prevent "works on my machine" issues
**Files:** `package.json`, `requirements.txt`, `Pipfile`
**Example issue:** "Different axios versions in frontend and backend"

### Missing Artifacts
**Look for:** Referenced files, configs, or schemas that don't exist
**Why:** Deployment failures, missing features
**Files:** Config files, documentation, schemas
**Example issue:** "Docs reference config.example.yaml - file doesn't exist"

---

## Enforcement & Policy Gates

### Policy Defined But Not Enforced
**Look for:** Rules in docs that aren't in CI/automation
**Why:** Rules are useless if not automated
**Files:** `.github/workflows/`, `pre-commit hooks`
**Example issue:** "Style guide says 2 spaces - not checked by linter"

### CI Gate Completeness
**Look for:** Tests, linting, security scans in pipeline
**Why:** Catch issues before merge, not in production
**Files:** `.github/workflows/ci.yml`
**Example issue:** "Security scanner in docs but not in CI"

### Pre-Commit Hooks
**Look for:** Hooks installed, not bypassed, actually running
**Why:** Catch issues at commit time, not PR time
**Files:** `.pre-commit-config.yaml`, `.husky/`
**Example issue:** "Developers all running with --no-verify"

---

## Single Source of Truth (SSOT)

### One Definition
**Look for:** Concepts defined in one place, not duplicated
**Why:** Updates in one place, no drift
**Files:** `config/`, `constants/`, `types/`
**Example issue:** "Error codes defined in 5 different files"

### Count Consistency
**Look for:** Same numbers across docs (stages, limits, versions)
**Why:** Contradictions cause confusion and bugs
**Files:** Documentation, configs, code
**Example issue:** "Docs say 3 retries, code says 5"

### Terminology Alignment
**Look for:** Same name for same concept everywhere
**Why:** Avoid confusion (is it "user" or "customer" or "account"?)
**Files:** All docs and code
**Example issue:** "Frontend calls it 'workspace', API calls it 'project'"

---

## State Persistence & Recovery

### Write Before Action
**Look for:** State saved before risky operations
**Why:** Recovery from failures, audit trail
**Files:** `jobs/`, `tasks/`, `workflows/`
**Example issue:** "Job failed halfway - no way to resume"

### Rollback Procedures
**Look for:** Documented rollback, tested recovery paths
**Why:** Production incidents need quick recovery
**Files:** `ops/rollback.py`, `migrations/`, `deploy/`
**Example issue:** "Deploy failed - no rollback procedure"

### Atomic Writes
**Look for:** All-or-nothing transactions, no partial updates
**Why:** Data integrity, no corrupted state
**Files:** `db/transactions.py`, `services/`
**Example issue:** "Order created but payment failed - orphan record"

---

## Quick Checklist

When reviewing code, ask:

**Business:**
- [ ] **Payment failures:** Is there retry logic? Grace period?
- [ ] **Card expiry:** Do we warn before renewal fails?
- [ ] **Chargebacks:** Can we auto-collect evidence?
- [ ] **Support:** Can customer self-serve this?
- [ ] **Cancellation:** Is it easy? Is there a pause option?

**Security:**
- [ ] **PII:** Is personal data encrypted?
- [ ] **Fraud:** Are we tracking abuse patterns?
- [ ] **Auth:** Do tokens expire? Is there rate limiting?
- [ ] **Input:** Is all user input sanitized?

**Governance:**
- [ ] **Audit:** Is this action logged with who/what/when?
- [ ] **Approval:** Does this need review before going live?
- [ ] **Escalation:** Who gets alerted if this fails?

**Code Quality:**
- [ ] **Idempotence:** Can this safely run twice?
- [ ] **SSOT:** Is this defined in one place only?
- [ ] **Dependencies:** Do all referenced files exist?
- [ ] **Tests:** Is the critical path tested?

**Legal:**
- [ ] **Email:** Does it have unsubscribe + physical address?
- [ ] **Consent:** Is tracking after consent only?
- [ ] **Terms:** Do we record which version user agreed to?

---

*These are starting points. Create full guidelines as patterns emerge.*
