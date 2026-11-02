# ComplaintIQ System Specification (SPEC.md)

## 1. Overview
ComplaintIQ is a professional, production-minded financial complaint triage platform powered by Natural Language Processing (NLP). It processes consumer complaints from the Consumer Financial Protection Bureau (CFPB) to automatically redact PII, classify financial products and issues, assess operational priority, enforce confidence safety gates, and route complaints across 9 specialized internal teams.

## 2. Ingestion & Validation Pipeline
1. **Endpoint**: `POST /v1/triage`
2. **Payload**: JSON containing:
   - `text`: String between 20 and 10,000 characters.
   - `metadata`: Optional key-value client metadata dictionary.
   - `client_id`: Optional caller identifier.
3. **Input Validation**: Enforced via Pydantic v2 schemas; rejects empty, whitespace-only, and out-of-boundary strings with HTTP 422.
4. **PII Redaction**: Intercepts narrative before inference; redacts SSNs, Emails, Phone Numbers, Credit Cards, and Bank Accounts.

## 3. NLP Prediction Protocol
Defined in `src/complaintiq/models/protocol.py` via `PredictorProtocol`:
- **Predictor Types**: `STUB` (active development skeleton), `BASELINE`, `TRANSFORMER`, `ONNX`.
- **Outputs**:
  - `predicted_product`: One of 9 primary CFPB products.
  - `predicted_issue`: Granular CFPB problem category.
  - `product_confidence`: Float in range `[0.0, 1.0]`.
  - `issue_confidence`: Float in range `[0.0, 1.0]`.
  - `model_version`: Semantic version string (e.g. `v1.0.0-stub`).
  - `predictor_type`: Architecture descriptor (`STUB`, `BASELINE`).

## 4. Confidence Gate Decision Mechanics
Configured in `configs/thresholds.yaml`:
- **Primary Threshold ($\tau$)**: `0.85` for product classification confidence.
- **Secondary Threshold**: `0.70` for issue classification confidence (evaluated when `strict_mode: true`).
- **Gate Evaluation**:
  - If $\text{product\_confidence} \ge \tau$: Evaluates to `ALLOW_ROUTING`.
  - If $\text{product\_confidence} < \tau$: Evaluates to `HUMAN_REVIEW` with destination `Human Review Queue` and review status `PENDING`.
  - Numerical Fault Tolerance: If confidence is `NaN`, `Inf`, `None`, negative, or $> 1.0$, the gate safely triggers `HUMAN_REVIEW` without raising exceptions.

## 5. B6 Team Routing & Fraud Overrides
Configured in `configs/routing.yaml`:
1. **B6 Product-to-Team Mapping**:
   - `Debt collection` $\rightarrow$ `Debt Collection Team` (`RULE_DEBT_COLLECTION`)
   - `Credit card or prepaid card` $\rightarrow$ `Credit Card Team` (`RULE_CREDIT_CARD`)
   - `Mortgage` $\rightarrow$ `Mortgage Team` (`RULE_MORTGAGE`)
   - `Student loan` $\rightarrow$ `Student Loan Team` (`RULE_STUDENT_LOAN`)
   - `Vehicle loan or lease` $\rightarrow$ `Auto Loan Team` (`RULE_AUTO_LOAN`)
   - `Checking or savings account` $\rightarrow$ `Bank Accounts Team` (`RULE_BANK_ACCOUNTS`)
   - `Money transfer, virtual currency, or money service` $\rightarrow$ `Payments Team` (`RULE_PAYMENTS`)
   - `Credit reporting, credit repair services, or reports` $\rightarrow$ `Credit Reporting Team` (`RULE_CREDIT_REPORTING`)
   - `Payday loan, title loan, or personal loan` $\rightarrow$ `Consumer Lending Team` (`RULE_CONSUMER_LENDING`)
2. **High-Priority Fraud Override (`OVERRIDE_FRAUD_RISK`)**:
   - If priority is `HIGH` or `CRITICAL` AND text contains fraud/identity indicators (`fraud`, `identity theft`, `unauthorized`, `scam`, `impersonation`, `hacked`, `stolen identity`), normal product routing is bypassed, directing to **Fraud and Risk**.
3. **Gate Fallback Override (`OVERRIDE_GATE_FALLBACK`)**:
   - If confidence gate evaluates to `HUMAN_REVIEW`, complaint routes directly to **Human Review Queue**.

## 6. Priority & Urgency Rules
Evaluated in `PriorityAssessmentService`:
- `CRITICAL`: Imminent foreclosure, repossession, active bankruptcy, legal lawsuits, frozen survival funds.
- `HIGH`: Unauthorized charges, severe debt harassment, credit score damage, disputes $> \$5,000$, urgent deadlines.
- `MEDIUM`: Disputed overdraft/late fees, APR discrepancies, customer service delays.
- `LOW`: Routine inquiries and informational requests.

## 7. Persistence & MongoDB Datastore
- **Collection `triage_requests`**: Stores request journey, PII redaction statistics, model predictions, confidence scores, gate decisions, routing explanations, review status, reviewer ID, and append-only stage timeline.
- **Collection `human_feedback`**: Stores operator feedback, star ratings, and accuracy confirmations.
- **Mock Fallback**: Automatic in-memory fallback using `mongomock-motor` when MongoDB is not running locally.

## 8. Human Review Workflow
- **`CORRECT`**: Operator updates product and issue with justification; service re-evaluates routing and sets status to `CORRECTED`.
- **`CONFIRM`**: Operator accepts prediction; service re-routes complaint to verified product queue and sets status to `CONFIRMED`.
