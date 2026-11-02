# ComplaintIQ: Autonomous Financial Complaint Triage & Confidence-Gated B6 Routing Platform

> **Production-minded NLP complaint triage platform processing Consumer Financial Protection Bureau (CFPB) complaints with strict confidence thresholds ($\tau = 0.85$), deterministic PII scrubbing, explainable B6 team routing, and human-in-the-loop exception handling.**

---

## 1. Executive Summary & Problem Statement

Financial institutions and regulatory bodies receive hundreds of thousands of consumer financial complaints annually via the **Consumer Financial Protection Bureau (CFPB)**. Traditional complaint management suffers from critical bottlenecks:
- **Manual Classification Bottlenecks**: Support staff spend minutes manually reading long narratives to classify financial products and issues.
- **Routing Errors & Misassignment**: Complaints get routed to the wrong internal departments, causing delayed responses and regulatory compliance violations.
- **Over-Automation of Uncertain Predictions**: Standard ML triage systems often make high-consequence routing decisions on low-confidence predictions, directing distressed consumers into incorrect workflows.
- **Privacy & PII Leakage**: Raw complaint narratives frequently contain Social Security Numbers (SSNs), payment card numbers, bank account numbers, and personal email addresses.

**ComplaintIQ** solves these challenges by implementing an automated, confidence-gated pipeline:
1. **PII Redaction**: All sensitive consumer identifiers (SSN, Email, Phone, Credit Card, Bank Accounts) are stripped before inference and logging.
2. **Multi-Target NLP Classification**: Classifies the CFPB financial product and predicts the associated complaint issue.
3. **Priority & Urgency Assessment**: Evaluates complaint text for legal threats, foreclosure risks, vehicle repossession, active bankruptcy, or financial hardship (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
4. **Confidence Gate ($\tau = 0.85$)**: Prediction confidence is compared against configured safety thresholds. Predictions with confidence $\ge \tau$ proceed to automated routing. Predictions with confidence $< \tau$ are diverted to a dedicated **Human Review Queue**.
5. **Explainable B6 Team Routing**: Directly maps products to 9 specialized internal operational teams with high-priority security overrides (`Fraud and Risk`).
6. **Human-in-the-Loop Operations Console**: Operators review low-confidence complaints, inspect full audit journeys, and either confirm or correct classifications—instantly re-evaluating routing.

---

## 2. System Architecture & Processing Journey

```
                              Incoming CFPB Complaint
                                        │
                                        ▼
                         ┌─────────────────────────────┐
                         │      1. PII Redaction       │
                         │  (SSN, Email, Phone, Card)  │
                         └──────────────┬──────────────┘
                                        │ Cleaned Narrative
                                        ▼
                         ┌─────────────────────────────┐
                         │   2. Multi-Target NLP       │
                         │ (Product & Issue Inference) │
                         └──────────────┬──────────────┘
                                        │
                                        ▼
                         ┌─────────────────────────────┐
                         │   3. Priority Assessment    │
                         │ (CRITICAL / HIGH / MED / LOW│
                         └──────────────┬──────────────┘
                                        │
                                        ▼
                         ┌─────────────────────────────┐
                         │   4. Confidence Gate        │
                         │  Product Confidence ≥ 0.85? │
                         └──────┬───────────────┬──────┘
                                │               │
                        YES (≥ 0.85)        NO (< 0.85)
                                │               │
                                ▼               ▼
                     ┌──────────────────┐ ┌───────────────────────────┐
                     │ 5. B6 Routing    │ │ Human Review Queue        │
                     │  - Fraud Override│ │ (Status: PENDING)         │
                     │  - 9 Product Team│ └─────────────┬─────────────┘
                     └─────────┬────────┘               │
                               │                        ▼
                               │             Human Specialist Review
                               │             (CORRECT / CONFIRM)
                               │                        │
                               ▼                        ▼
                     ┌──────────────────────────────────────────┐
                     │          6. MongoDB Storage              │
                     │ (Immutable Audit Timeline, Feedback logs)│
                     └──────────────────────────────────────────┘
```

---

## 3. Confidence Gate Specification

Automated routing is only as safe as its classification confidence. ComplaintIQ implements a strict **Confidence Gate** (`src/complaintiq/serving/gate.py`) governed by `configs/thresholds.yaml`:

- **Primary Threshold ($\tau$)**: `0.85` (Product classification confidence).
- **Secondary Threshold**: `0.70` (Issue classification confidence, evaluated in strict mode).
- **Gate Decisions**:
  - `ALLOW_ROUTING`: Confidence $\ge \tau$. The complaint proceeds to automated B6 routing.
  - `HUMAN_REVIEW`: Confidence $< \tau$, or numerical anomalies detected (e.g. `NaN`, `Inf`, `None`, out-of-range). The complaint is placed into the Human Review Queue.

### Robust Numerical Safety
The confidence gate verifies that confidence values are finite valid floats in $[0.0, 1.0]$. Invalid scores are diverted to Human Review without throwing unhandled exceptions.

---

## 4. B6 Team Routing Specification

ComplaintIQ maps all CFPB product taxonomies to dedicated internal operations teams (`configs/routing.yaml`):

| Rule ID | CFPB Consumer Financial Product | Destination Internal Team |
| :--- | :--- | :--- |
| `RULE_DEBT_COLLECTION` | Debt collection | **Debt Collection Team** |
| `RULE_CREDIT_CARD` | Credit card or prepaid card | **Credit Card Team** |
| `RULE_MORTGAGE` | Mortgage | **Mortgage Team** |
| `RULE_STUDENT_LOAN` | Student loan | **Student Loan Team** |
| `RULE_AUTO_LOAN` | Vehicle loan or lease | **Auto Loan Team** |
| `RULE_BANK_ACCOUNTS` | Checking or savings account | **Bank Accounts Team** |
| `RULE_PAYMENTS` | Money transfer, virtual currency, or money service | **Payments Team** |
| `RULE_CREDIT_REPORTING` | Credit reporting, credit repair services, or reports | **Credit Reporting Team** |
| `RULE_CONSUMER_LENDING` | Payday loan, title loan, or personal loan | **Consumer Lending Team** |

### Priority & Security Overrides
- **`OVERRIDE_FRAUD_RISK`**: Complaints flagged with `HIGH` or `CRITICAL` priority containing security indicators (`fraud`, `identity theft`, `unauthorized`, `scam`, `impersonation`, `hacked`, `stolen identity`) bypass product routing and are diverted immediately to **Fraud and Risk**.
- **`OVERRIDE_GATE_FALLBACK`**: Complaints failing the confidence gate are diverted directly to **Human Review Queue**.

---

## 5. Privacy & PII Scrubbing Engine

Consumer complaints routinely contain sensitive personal details. The privacy engine (`src/complaintiq/privacy/redactor.py`) intercepts every incoming narrative before model inference or database persistence:

- **SSNs**: Standard 9-digit formats (`XXX-XX-XXXX`, `XXX XX XXXX`) $\rightarrow$ `[REDACTED_SSN]`
- **Email Addresses**: RFC 5322 compliant regex $\rightarrow$ `[REDACTED_EMAIL]`
- **Phone Numbers**: 10-digit North American Numbering Plan $\rightarrow$ `[REDACTED_PHONE]`
- **Payment Cards**: 15–16 digit Visa, Mastercard, Amex, Discover $\rightarrow$ `[REDACTED_CARD]`
- **Account Numbers**: Direct account / routing patterns $\rightarrow$ `account [REDACTED_ACCOUNT]`

---

## 6. Model Architecture & Predictor Protocol

ComplaintIQ implements an explicit `PredictorProtocol` (`src/complaintiq/models/protocol.py`) enforcing clean separation between inference logic and the serving layer:

- **`STUB` (`v1.0.0-stub`)**: Deterministic keyword-based heuristic classifier used for testing pipeline mechanics, gate triggers, and routing.
- **`BASELINE` (`v1.2.0-baseline`)**: Statistical rule-based classifier extracting linguistic features.
- **`TRANSFORMER` & `ONNX`**: Extensible protocol slots for fine-tuned DeBERTa / RoBERTa models and ONNX Runtime deployment in future training milestones.

---

## 7. Technology Stack

- **Backend**: Python 3.12, FastAPI, Pydantic v2, Uvicorn
- **Database**: MongoDB (via `motor` / `pymongo`), with transparent `mongomock-motor` in-memory fallback
- **Data & ML**: pandas, NumPy, scikit-learn
- **Frontend**: Responsive Dark UI, Tailwind CSS, Vanilla JS, HTML5
- **Testing**: pytest, pytest-asyncio, httpx (100% pass rate across 50 tests)
- **Deployment**: Docker, Docker Compose, Uvicorn

---

## 8. REST API Specification

### Core Endpoints

#### 1. Ingest & Triage Complaint
- **`POST /v1/triage`**
- **Request Body**:
  ```json
  {
    "text": "Midland Credit Management keeps calling my workplace at 3:00 AM regarding a debt of $1,200. My SSN is 123-45-6789.",
    "client_id": "portal_user_1"
  }
  ```
- **Response (`200 OK`)**:
  ```json
  {
    "request_id": "req_1564fd045e4a",
    "original_text_preview": "Midland Credit Management keeps calling...",
    "redacted_text": "Midland Credit Management keeps calling my workplace at 3:00 AM regarding a debt of $1,200. My SSN is [REDACTED_SSN].",
    "pii_detected": true,
    "pii_entities_count": 1,
    "predicted_product": "Debt collection",
    "predicted_issue": "Attempts to collect debt not owed",
    "priority": "HIGH",
    "priority_reason": "Severe debt collector harassment / FDCPA violations",
    "product_confidence": 0.94,
    "threshold": 0.85,
    "gate_decision": "ALLOW_ROUTING",
    "route_type": "AUTOMATED",
    "assigned_team": "Debt Collection Team",
    "routing_rule_id": "RULE_DEBT_COLLECTION",
    "routing_explanation": "Routed to Debt Collection Team based on product classification 'Debt collection' under rule RULE_DEBT_COLLECTION.",
    "review_status": "NOT_REQUIRED",
    "model_version": "v1.0.0-stub",
    "predictor_type": "STUB",
    "latency_ms": 3.8
  }
  ```

#### 2. Human Review & Correction
- **`POST /v1/requests/{request_id}/review`**
- **Request Body**:
  ```json
  {
    "action": "CORRECT",
    "corrected_product": "Mortgage",
    "corrected_issue": "Trouble during payment process",
    "correction_reason": "Specialist verified documentation relates to home escrow calculation.",
    "reviewer_id": "operator_jane"
  }
  ```
- **Response (`200 OK`)**:
  ```json
  {
    "request_id": "req_aacd1a82ef84",
    "review_status": "CORRECTED",
    "previous_product": "Debt collection",
    "previous_assigned_team": "Human Review Queue",
    "updated_product": "Mortgage",
    "updated_assigned_team": "Mortgage Team",
    "reviewer_id": "operator_jane",
    "reviewed_at": "2026-11-02T09:35:00Z"
  }
  ```

#### 3. Operational Queries & Analytics
- **`GET /health`**: Health status, version, uptime, and database connectivity.
- **`GET /v1/model`**: Model metadata and confidence threshold configurations.
- **`GET /v1/requests`**: Paginated query filtering by team, priority, review status, and keyword search.
- **`GET /v1/requests/{request_id}`**: Comprehensive complaint audit journey.
- **`GET /v1/requests/{request_id}/history`**: Chronological audit timeline events.
- **`GET /v1/queues/human-review`**: Complaints awaiting human review.
- **`GET /v1/queues/{team_name}`**: Complaints assigned to a given team.
- **`GET /v1/analytics/overview`**: High-level KPI metrics (Total Ingested, Automation Rate, Pending Review, Avg Confidence, Team Queues).
- **`POST /v1/feedback`**: Submit quality ratings and operator feedback.

---

## 9. Front Page & Operations Console Web Experience

ComplaintIQ provides a modern interface:

1. **Front Page (`GET /`)**:
   - Hero section detailing autonomous triage, confidence gating, and CFPB B6 routing.
   - **Interactive Triage Sandbox**: Load presets (Debt Harassment, High Priority Fraud Override, Ambiguous Gate Trigger, Mortgage Foreclosure) or paste raw text. Live real-time visualization of PII scrubbing, model predictions, confidence meter, and team assignment.
   - Architecture & B6 routing breakdown cards.
2. **Operations Console (`GET /dashboard` or CTA)**:
   - Real-time KPI summary cards (Total Requests, Automation Rate, Pending Human Review, Avg Model Confidence).
   - Filter bar: Queue selector, Priority filter, Review status filter, and live text search.
   - Requests Table: Color-coded priority badges, confidence scores, and team queues.
   - **Audit Journey Modal**: Step-by-step immutable timeline of events (`PII_REDACTION`, `NLP_INFERENCE`, `PRIORITY_ASSESSMENT`, `CONFIDENCE_GATE`, `ROUTING_DECISION`, `HUMAN_CORRECTION`).
   - **Human Review Modal**: Allows operators to accept or correct classifications with reason notes, automatically re-routing the complaint to the correct team.

---

## 10. Local Installation & Development

### Prerequisites
- Python 3.11+ (Python 3.12 supported)
- Git

### Setup
```bash
# 1. Clone repository
git clone https://github.com/organization/ComplaintIQ.git
cd ComplaintIQ

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install package and dependencies
pip install -r requirements.txt

# 4. Run tests
pytest -v

# 5. Seed sample CFPB complaints
python scripts/seed_data.py

# 6. Start development server
uvicorn complaintiq.serving.app:app --host 0.0.0.0 --port 8000 --reload
```

Open your browser at `http://localhost:8000` to view the Front Page and Interactive Triage Sandbox, or `http://localhost:8000/docs` for the interactive Swagger OpenAPI documentation.

---

## 11. Docker Deployment

Deploy ComplaintIQ alongside MongoDB and Redis:

```bash
# Build and start all services
docker compose up --build -d

# Check service logs
docker compose logs -f api

# Shut down services
docker compose down
```

---

## 12. Automated Testing Suite

ComplaintIQ includes comprehensive unit and integration tests covering all critical boundaries:

```bash
./.venv/bin/pytest -v
```

### Test Coverage Highlights:
- **`test_gate.py`**: Exact threshold ($\tau=0.85$), above/below threshold, NaN/Inf/None protection, strict mode secondary thresholds.
- **`test_router.py`**: All 9 B6 product-to-team rules, case-insensitivity, high/critical fraud keyword overrides, gate precedence.
- **`test_priority.py`**: Urgency indicators for `CRITICAL`, `HIGH`, `MEDIUM`, and `LOW`.
- **`test_privacy.py`**: PII scrubbing of SSN, Email, Phone, Credit Card, and Account numbers.
- **`test_persistence.py`**: MongoDB storage, retrieval, human review corrections (`CORRECT` and `CONFIRM`), timeline audit trails.
- **`test_api.py`**: All REST endpoints, input validations, error responses, and analytics.

---

## 13. License

Distributed under the Apache 2.0 License. See `LICENSE` for details.
