# ComplaintIQ System Specification (SPEC.md)

## 1. Overview
ComplaintIQ is a financial complaint triage platform designed for financial institutions handling consumer complaints filed through the Consumer Financial Protection Bureau (CFPB).

## 2. Ingestion & Validation Pipeline
1. **Endpoint**: `POST /v1/triage`
2. **Payload**: JSON with `text` (string, 20–10,000 characters).
3. **Validation**: Rejects whitespace-only, empty, malformed JSON, and oversized narratives.
4. **PII Redaction**: Regex-based redaction of SSNs, Emails, Phone Numbers, and Account Numbers before model prediction.

## 3. NLP Prediction Protocol
- **Predictor Types**: `STUB` (active dev skeleton), `BASELINE`, `TRANSFORMER`, `ONNX`.
- **Outputs**:
  - `predicted_product`: One of 9 primary CFPB products.
  - `predicted_issue`: Specific granular issue.
  - `product_confidence`: Float in range `[0.0, 1.0]`.
  - `issue_confidence`: Float in range `[0.0, 1.0]`.
  - `model_version`: Semantic version string.
  - `predictor_type`: Indicator of model implementation.

## 4. Confidence Gate Decision
Let $\tau$ be the product confidence threshold configured in `configs/thresholds.yaml` (default: 0.85).
- If $\text{confidence} \ge \tau$: Triage passes through the gate to B6 team routing.
- If $\text{confidence} < \tau$: Gate diverts complaint to `HUMAN_REVIEW` with destination `Human Review Queue` and review status `PENDING`.

## 5. B6 Team Routing & Fraud Overrides
1. Case-insensitive matching against `configs/routing.yaml`.
2. **High-Priority Fraud Override**:
   If priority is `HIGH` or `CRITICAL` and issue/narrative contains fraud or identity indicators (`fraud`, `identity theft`, `unauthorized`, `scam`, `impersonation`), the destination team is overridden to **Fraud and Risk**.
3. **Confidence Precedence**: The confidence gate takes absolute precedence over normal team routing.

## 6. Persistence & MongoDB Datastore
All requests and human feedback are stored in MongoDB:
- **Collection `triage_requests`**: Stores request journey, PII redaction audit, model prediction, gate decision, routing explanation, and review status.
- **Collection `human_feedback`**: Stores reviewer corrections, original vs. corrected label diffs, correction reasons, and recomputed routing.
