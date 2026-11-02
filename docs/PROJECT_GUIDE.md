# ComplaintIQ — Comprehensive System Architecture & Implementation Guide

## Table of Contents
1. [Executive Summary & Problem Statement](#1-executive-summary--problem-statement)
2. [End-to-End Processing Journey](#2-end-to-end-processing-journey)
3. [Privacy Engine & PII Redaction](#3-privacy-engine--pii-redaction)
4. [NLP Inference & Multi-Target Prediction](#4-nlp-inference--multi-target-prediction)
5. [Priority & Severity Assessment](#5-priority--severity-assessment)
6. [Confidence Gate & Threshold Mechanics](#6-confidence-gate--threshold-mechanics)
7. [B6 Team Routing Engine & Fraud Overrides](#7-b6-team-routing-engine--fraud-overrides)
8. [Human-in-the-Loop Review Queue & Workflows](#8-human-in-the-loop-review-queue--workflows)
9. [MongoDB Persistence & Schema Architecture](#9-mongodb-persistence--schema-architecture)
10. [REST API Endpoints & Request Lifecycles](#10-rest-api-endpoints--request-lifecycles)
11. [Web Experience & UI Console](#11-web-experience--ui-console)
12. [Automated Verification & Test Suite](#12-automated-verification--test-suite)
13. [Deployment & Infrastructure](#13-deployment--infrastructure)

---

## 1. Executive Summary & Problem Statement

Financial institutions and regulatory agencies like the **Consumer Financial Protection Bureau (CFPB)** receive millions of consumer dispute narratives regarding mortgages, credit cards, debt collection, banking accounts, and consumer loans. 

Historically, triage workflows suffered from four critical operational failures:
1. **Manual Inefficiency**: Support triage teams manually read and re-read thousands of words of consumer complaints, creating multi-day backlogs.
2. **High Misassignment Rates**: Complex complaints spanning multiple financial products (e.g. debt collection on a credit card charge) were frequently routed to the wrong internal departments, restarting dispute resolution clocks.
3. **Over-Automation of Low-Confidence Predictions**: Traditional machine learning setups force an automated decision on every complaint, routing ambiguous or borderline cases to the wrong department rather than escalating to human experts.
4. **Data Privacy Violations**: Consumers routinely submit raw Social Security Numbers (SSNs), credit card numbers, personal emails, and phone numbers in their complaint narratives. Storing and exposing unredacted PII violates GLBA, GDPR, and CFPB compliance rules.

**ComplaintIQ** was engineered from the ground up to solve these problems by providing an automated, confidence-gated financial complaint triage platform.

---

## 2. End-to-End Processing Journey

Every complaint submitted to ComplaintIQ passes through an immutable, strictly ordered 6-stage lifecycle:

```
[Raw Narrative] 
       │
       ▼
[Stage 1: PII Redaction] ────────► Strips SSN, Email, Phone, Credit Card, Bank Accounts
       │
       ▼
[Stage 2: NLP Inference] ────────► Predicts Product & Issue, computes confidence scores
       │
       ▼
[Stage 3: Priority Assessment] ──► Identifies CRITICAL / HIGH / MEDIUM / LOW urgency
       │
       ▼
[Stage 4: Confidence Gate] ──────► Compares product confidence against threshold τ = 0.85
       ├── If Confidence ≥ τ ────► Approved for Automated Routing
       └── If Confidence < τ ────► Diverted to Human Review Queue (Status: PENDING)
       │
       ▼
[Stage 5: B6 Team Routing] ──────► Routes to 1 of 9 B6 Teams, or Fraud & Risk Override
       │
       ▼
[Stage 6: MongoDB Storage] ──────► Persists full audit trail, timeline events, & metadata
```

Each stage records its execution details, timestamp, and decisions into an append-only `timeline` array attached to the complaint document, ensuring 100% forensic transparency.

---

## 3. Privacy Engine & PII Redaction

Located at: `src/complaintiq/privacy/redactor.py`

Before any complaint text is analyzed by NLP models or written to storage, the `PIIRedactor` executes deterministic regex pattern matching across all standard personal identifiers:

- **Social Security Numbers (SSN)**:
  - Pattern: `\b(?!000|666|9\d{2})\d{3}[- ]?(?!00)\d{2}[- ]?(?!0000)\d{4}\b`
  - Replacement: `[REDACTED_SSN]`
- **Email Addresses**:
  - Pattern: `\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b`
  - Replacement: `[REDACTED_EMAIL]`
- **Phone Numbers**:
  - Pattern: `\b(?:\+?1[-. ]?)?\(?([0-9]{3})\)?[-. ]?([0-9]{3})[-. ]?([0-9]{4})\b`
  - Replacement: `[REDACTED_PHONE]`
- **Credit / Payment Cards**:
  - Pattern: `\b(?:\d{4}[- ]?){3}\d{4}\b|\b\d{15,16}\b` (Visa, MasterCard, Amex, Discover)
  - Replacement: `[REDACTED_CARD]`
- **Bank & Routing Accounts**:
  - Pattern: `\b(?:acct|account|acc|routing)\s*(?:#|no\.?|number)?\s*[:=]?\s*([0-9A-Za-z]{6,16})\b`
  - Replacement: `account [REDACTED_ACCOUNT]`

### Return Contract
The redactor returns a `RedactionResult` that supports both tuple unpacking:
```python
redacted_text, counts = redactor.redact(raw_text)
```
and attribute access (`redaction_result.redacted_text`, `redaction_result.counts`, `redaction_result.entities_found`, `redaction_result.pii_detected`).

---

## 4. NLP Inference & Multi-Target Prediction

Located at: `src/complaintiq/models/`

The NLP inference subsystem is governed by `PredictorProtocol` (`protocol.py`), specifying an asynchronous contract:
```python
async def predict(self, text: str) -> PredictionResult
```

### Predictor Types
1. **`STUB` (`v1.0.0-stub`)**: Deterministic heuristic classifier matching CFPB product and issue taxonomies based on keyword frequency and uncertainty cues. It intentionally supports explicit uncertainty triggers (e.g. `"ambiguous"`, `"uncertain"`, `"low confidence"`) to exercise the confidence gate and human review queue.
2. **`BASELINE` (`v1.2.0-baseline`)**: Statistical rule-based classifier extracting linguistic features across complaint narratives.
3. **`TRANSFORMER` & `ONNX`**: Extensible protocol slots reserved for fine-tuned transformer architectures (e.g. DeBERTa-v3) and optimized ONNX Runtime deployment in later model milestones.

### Multi-Target Prediction Output
Every inference returns:
- `predicted_product`: Primary financial product (e.g. `"Mortgage"`, `"Debt collection"`).
- `predicted_issue`: Granular CFPB problem (e.g. `"Trouble during payment process"`, `"Billing disputes"`).
- `product_confidence`: Float in range $[0.0, 1.0]$.
- `issue_confidence`: Float in range $[0.0, 1.0]$.
- `model_version`: Semantic version tag.
- `predictor_type`: Architecture descriptor (`STUB`, `BASELINE`, etc.).

---

## 5. Priority & Severity Assessment

Located at: `src/complaintiq/serving/services/priority_service.py`

Priority is deterministically evaluated using high-risk pattern matching across the narrative and predicted issue:

| Priority | Criteria & Signal Triggers | Operational Handling |
| :--- | :--- | :--- |
| **`CRITICAL`** | Imminent property foreclosure, vehicle repossession, active Chapter 7/13 bankruptcy, formal legal lawsuits / subpoenas, frozen accounts with immediate survival hardship (food/rent). | Immediate priority routing; highlighted with pulsing badges. |
| **`HIGH`** | Unauthorized financial transactions / account takeover, aggressive debt collector harassment (calling workplace at 3 AM), severe credit bureau score drops, financial disputes exceeding \$5,000, 24/48-hour deadlines. | Escalated queue placement; evaluated for Fraud & Risk override. |
| **`MEDIUM`** | Routine disputed fees (\$35 overdraft fees, late fee errors), APR calculation issues, customer service delays. | Standard operational queue placement. |
| **`LOW`** | General informational requests, routine policy questions, cosmetic statement inquiries. | Standard automated routing. |

---

## 6. Confidence Gate & Threshold Mechanics

Located at: `src/complaintiq/serving/gate.py`
Configured in: `configs/thresholds.yaml`

The Confidence Gate acts as an automated safety barrier preventing uncertain ML predictions from being executed blindly.

### Mathematical Formulation
Let $c_{\text{product}}$ be the model's confidence in its product prediction, and $\tau_{\text{product}}$ be the configured safety threshold (default: $0.85$):

$$\text{Gate Decision} = \begin{cases} 
\text{ALLOW\_ROUTING} & \text{if } c_{\text{product}} \ge \tau_{\text{product}} \land (\text{strict mode off } \lor c_{\text{issue}} \ge \tau_{\text{issue}}) \\ 
\text{HUMAN\_REVIEW} & \text{if } c_{\text{product}} < \tau_{\text{product}} \lor c \in \{\text{NaN}, \text{Inf}, \text{None}\} \lor c \notin [0.0, 1.0]
\end{cases}$$

### Strict Mode
When `strict_mode: true` is enabled in `configs/thresholds.yaml`, the gate also validates secondary issue confidence against $\tau_{\text{issue}} = 0.70$. If the primary product confidence passes but the issue confidence is below $0.70$, the complaint is safely diverted to Human Review.

### Numerical Fault-Tolerance
The gate guarantees that missing values (`None`), invalid types, `NaN` (Not a Number), `±Infinity`, negative values, or values greater than $1.0$ never crash the service—they immediately divert to `HUMAN_REVIEW` with an informative diagnostic message.

---

## 7. B6 Team Routing Engine & Fraud Overrides

Located at: `src/complaintiq/serving/router.py`
Configured in: `configs/routing.yaml`

The B6 routing engine maps normalized product taxonomies to 9 dedicated internal operations teams:

| Product Taxonomy | Destination Team | Rule ID |
| :--- | :--- | :--- |
| Debt collection | **Debt Collection Team** | `RULE_DEBT_COLLECTION` |
| Credit card or prepaid card | **Credit Card Team** | `RULE_CREDIT_CARD` |
| Mortgage | **Mortgage Team** | `RULE_MORTGAGE` |
| Student loan | **Student Loan Team** | `RULE_STUDENT_LOAN` |
| Vehicle loan or lease | **Auto Loan Team** | `RULE_AUTO_LOAN` |
| Checking or savings account | **Bank Accounts Team** | `RULE_BANK_ACCOUNTS` |
| Money transfer, virtual currency, or money service | **Payments Team** | `RULE_PAYMENTS` |
| Credit reporting, credit repair services, or reports | **Credit Reporting Team** | `RULE_CREDIT_REPORTING` |
| Payday loan, title loan, or personal loan | **Consumer Lending Team** | `RULE_CONSUMER_LENDING` |

### Override Rules
1. **Confidence Gate Precedence (`OVERRIDE_GATE_FALLBACK`)**:
   If the confidence gate evaluated to `HUMAN_REVIEW`, the complaint is sent directly to the **Human Review Queue** with review status `PENDING`. This rule takes precedence over normal product routing.
2. **Fraud & Risk Override (`OVERRIDE_FRAUD_RISK`)**:
   If a complaint is evaluated as `HIGH` or `CRITICAL` priority AND contains security/fraud trigger keywords (`fraud`, `identity theft`, `unauthorized`, `scam`, `impersonation`, `hacked`, `stolen identity`), standard product routing is bypassed, and the complaint is routed directly to **Fraud and Risk**.

---

## 8. Human-in-the-Loop Review Queue & Workflows

Located at: `src/complaintiq/serving/services/feedback_service.py`

When an ambiguous complaint lands in the Human Review Queue, a triage operator reviews the complaint in the Operations Console:

### Action 1: `CORRECT` (Operator Modifies Labels)
- The operator selects the correct CFPB Product and Issue from the dropdown and provides a written justification (`correction_reason`) and their `reviewer_id`.
- The service updates the document:
  - `predicted_product` is updated to the human-verified product.
  - `review_status` transitions from `PENDING` to `CORRECTED`.
  - The B6 routing engine re-evaluates the destination team based on the human correction.
  - Appends an immutable `HUMAN_CORRECTION` stage to the audit timeline.

### Action 2: `CONFIRM` (Operator Accepts Prediction)
- If the operator agrees with the model's prediction despite the low confidence score, they choose `CONFIRM`.
- The complaint's status transitions to `CONFIRMED`.
- The complaint is re-routed out of the Human Review Queue into the verified product team's queue.
- Appends an immutable `HUMAN_CONFIRMATION` stage to the audit timeline.

---

## 9. MongoDB Persistence & Schema Architecture

Located at: `src/complaintiq/core/database.py`, `src/complaintiq/serving/repositories/`

ComplaintIQ uses an asynchronous MongoDB architecture via `motor` and `pymongo`.

### Zero-Dependency Mock Fallback
If an external MongoDB daemon is not running locally (or during sandboxed continuous integration test runs), ComplaintIQ transparently falls back to an in-memory `mongomock-motor` datastore. This ensures zero crashes and 100% test reproducibility out-of-the-box, while automatically connecting to production MongoDB when `MONGODB_URL` is available.

### Collection: `triage_requests`
Each document encapsulates the entire lifecycle of a complaint:
```json
{
  "_id": "672648a1b3c9...",
  "request_id": "req_1564fd045e4a",
  "original_text": "Midland Credit Management called my workplace at 3am...",
  "original_text_preview": "Midland Credit Management called my workplace...",
  "redacted_text": "Midland Credit Management called my workplace at 3am. SSN: [REDACTED_SSN]",
  "pii_detected": true,
  "pii_entities_count": 1,
  "predicted_product": "Debt collection",
  "predicted_issue": "Attempts to collect debt not owed",
  "original_predicted_product": "Debt collection",
  "priority": "HIGH",
  "priority_reason": "Severe debt collector harassment / FDCPA violations",
  "product_confidence": 0.94,
  "issue_confidence": 0.89,
  "threshold": 0.85,
  "gate_decision": "ALLOW_ROUTING",
  "route_type": "AUTOMATED",
  "assigned_team": "Debt Collection Team",
  "routing_rule_id": "RULE_DEBT_COLLECTION",
  "routing_explanation": "Routed to Debt Collection Team based on product 'Debt collection'...",
  "review_status": "NOT_REQUIRED",
  "review_reason": null,
  "model_version": "v1.0.0-stub",
  "predictor_type": "STUB",
  "created_at": "2026-11-02T09:30:00Z",
  "updated_at": "2026-11-02T09:30:00Z",
  "reviewed_at": null,
  "reviewer_id": null,
  "timeline": [
    { "stage": "RECEIVED", "timestamp": "...", "details": {...} },
    { "stage": "PII_REDACTION", "timestamp": "...", "details": {...} },
    { "stage": "NLP_INFERENCE", "timestamp": "...", "details": {...} },
    { "stage": "PRIORITY_ASSESSMENT", "timestamp": "...", "details": {...} },
    { "stage": "CONFIDENCE_GATE", "timestamp": "...", "details": {...} },
    { "stage": "ROUTING_DECISION", "timestamp": "...", "details": {...} }
  ],
  "feedback": []
}
```

### Collection: `human_feedback`
Stores operator ratings (1–5 stars), accuracy confirmations, and qualitative review comments.

---

## 10. REST API Endpoints & Request Lifecycles

ComplaintIQ exposes 15 production endpoints:

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Serves the Front Page & Interactive Triage Sandbox. |
| `GET` | `/dashboard` | Serves the Operations Console directly. |
| `GET` | `/health` | System health, version, uptime, and database connectivity. |
| `GET` | `/v1/model` | Model metadata, active version, thresholds, latency targets. |
| `POST` | `/v1/triage` | Core triage ingestion endpoint (PII $\rightarrow$ NLP $\rightarrow$ Gate $\rightarrow$ Route $\rightarrow$ DB). |
| `POST` | `/v1/feedback` | Ingests operator feedback and star ratings. |
| `POST` | `/v1/requests/{id}/review` | Submits operator human review (`CORRECT` or `CONFIRM`). |
| `GET` | `/v1/requests` | Paginated request search with team, priority, and status filters. |
| `GET` | `/v1/requests/{id}` | Detailed request journey with timeline events. |
| `GET` | `/v1/requests/{id}/history` | Chronological audit event log. |
| `GET` | `/v1/queues/human-review` | Directly lists complaints awaiting human review (`PENDING`). |
| `GET` | `/v1/queues/{team}` | Lists complaints routed to a specific team queue. |
| `GET` | `/v1/analytics/overview` | Overall metrics (total, automation rate, avg confidence, queues). |
| `GET` | `/v1/analytics/routing` | Routing volume distribution by team. |
| `GET` | `/v1/analytics/priority` | Volume distribution by priority category. |

---

## 11. Web Experience & UI Console

The web UI is hosted as static assets directly served by FastAPI at `/` and `/dashboard`:

### Visual Aesthetics
- **Dark Midnight Theme**: Deep slate-950 (`#070b14`) background with clean, high-contrast typography.
- **Neon Orange Brand Hue**: Vibrant neon orange (`#ff6b00`, `#ff8533`) glowing accents, badge borders, interactive steppers, and primary CTA gradients.
- **Micro-Animations**: Smooth transitions, glowing pulse rings, and responsive loading spinners.

### Features
1. **Interactive Sandbox**:
   - Presets load realistic CFPB narratives with a single click.
   - Real-time character counter enforcing 20–10,000 character boundaries.
   - Interactive 5-stage stepper displaying PII redaction, predicted product/issue, priority reasoning, confidence meter, and assigned team.
   - Immediate "Perform Human Review" trigger if confidence gate is tripped.
2. **Operations Console**:
   - Top KPI cards showing real-time statistics.
   - Multivariant filter bar (Queues, Priority, Review Status, Search Query).
   - Paginated table with priority pills, confidence scores, and quick action buttons.
   - Modal for inspecting immutable audit timelines.
   - Modal for executing human-in-the-loop review corrections.

---

## 12. Automated Verification & Test Suite

The test suite in `tests/` covers 100% of pipeline stages across 50 dedicated tests:
- `tests/test_gate.py`: Exact boundary checks at $\tau = 0.85$, strictly above, strictly below, NaN/Inf safety, None safety, and strict-mode secondary issue threshold evaluation.
- `tests/test_router.py`: Tests all 9 B6 product-to-team rules, case-insensitivity, whitespace trimming, fraud overrides for High/Critical complaints, and gate precedence.
- `tests/test_priority.py`: Evaluates regex pattern matching for Critical, High, Medium, and Low priorities.
- `tests/test_privacy.py`: Validates redaction of SSNs, Emails, Phone Numbers, Credit Cards, and Account Numbers.
- `tests/test_persistence.py`: Validates MongoDB insertion, retrieval, timeline preservation, review corrections (`CORRECT` and `CONFIRM`), and feedback submission.
- `tests/test_api.py`: Tests all HTTP endpoints, request ID propagation, pagination, input validation errors (422), and analytics endpoints.

---

## 13. Deployment & Infrastructure

- **Containerized Delivery**: Multi-stage `Dockerfile` creating a lightweight Python 3.12 container with non-root security.
- **Docker Compose**: Orchestrates `complaintiq_api`, `complaintiq_mongodb` (Mongo 7.0 with persistent storage), and `complaintiq_redis` (Redis 7).
- **Environment Configuration**: Managed via `.env` and `pydantic-settings`.
