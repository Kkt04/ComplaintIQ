"""Triage Service orchestrating the complete ComplaintIQ processing pipeline.

PII Redaction -> NLP Classification -> Priority Assessment -> Confidence Gate -> Team Routing -> Persistent Storage
"""

from datetime import datetime, timezone
import time
import uuid
from typing import Optional
from complaintiq.core.config import settings
from complaintiq.core.logging import logger
from complaintiq.models.protocol import PredictorProtocol
from complaintiq.models.stub import StubPredictor
from complaintiq.privacy.redactor import PIIRedactor
from complaintiq.serving.gate import ConfidenceGate
from complaintiq.serving.repositories.request_repository import RequestRepository
from complaintiq.serving.router import RoutingEngine
from complaintiq.serving.schemas import (
    GateDecisionEnum,
    PriorityEnum,
    ReviewStatusEnum,
    TriageRequest,
    TriageResponse,
)
from complaintiq.serving.services.priority_service import PriorityAssessmentService


class TriageService:
    """End-to-end financial complaint triage orchestrator."""

    def __init__(
        self,
        predictor: Optional[PredictorProtocol] = None,
        redactor: Optional[PIIRedactor] = None,
        gate: Optional[ConfidenceGate] = None,
        router: Optional[RoutingEngine] = None,
        priority_service: Optional[PriorityAssessmentService] = None,
        request_repo: Optional[RequestRepository] = None,
    ):
        self.predictor = predictor or StubPredictor(
            model_version=settings.model_config_data.get("model", {}).get("default_version", "v1.0.0-stub")
        )
        self.redactor = redactor or PIIRedactor()
        self.gate = gate or ConfidenceGate()
        self.router = router or RoutingEngine()
        self.priority_service = priority_service or PriorityAssessmentService()
        self.repo = request_repo or RequestRepository()

    async def triage(self, request: TriageRequest, custom_request_id: Optional[str] = None) -> TriageResponse:
        start_time = time.perf_counter()
        request_id = custom_request_id or f"req_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        logger.info(f"Initiating triage pipeline for request {request_id}")

        # 1. PII Redaction
        redaction_result = self.redactor.redact(request.text)
        pii_detected = len(redaction_result.entities_found) > 0
        clean_text = redaction_result.redacted_text

        # 2. NLP Inference
        prediction = await self.predictor.predict(clean_text)

        # 3. Priority Assessment
        priority, priority_reason = self.priority_service.assess_priority(
            clean_text, prediction.predicted_issue
        )

        # 4. Confidence Gate Evaluation
        gate_decision, gate_reason = self.gate.evaluate(
            prediction.product_confidence, prediction.issue_confidence
        )

        # 5. B6 Team Routing
        routing_decision = self.router.route(
            predicted_product=prediction.predicted_product,
            priority=priority,
            gate_decision=gate_decision,
            complaint_text=clean_text,
            gate_reason=gate_reason,
        )

        # 6. Determine Review Status
        if gate_decision == GateDecisionEnum.HUMAN_REVIEW:
            review_status = ReviewStatusEnum.PENDING
            review_reason = gate_reason
        else:
            review_status = ReviewStatusEnum.NOT_REQUIRED
            review_reason = None

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # 7. Construct Audit Timeline
        timeline = [
            {
                "stage": "RECEIVED",
                "timestamp": now_iso,
                "details": {
                    "raw_length": len(request.text),
                    "client_id": request.client_id,
                },
            },
            {
                "stage": "PII_REDACTION",
                "timestamp": now_iso,
                "details": {
                    "pii_detected": pii_detected,
                    "entities_redacted_count": len(redaction_result.entities_found),
                    "detected_types": [e.entity_type for e in redaction_result.entities_found],
                },
            },
            {
                "stage": "NLP_INFERENCE",
                "timestamp": now_iso,
                "details": {
                    "predicted_product": prediction.predicted_product,
                    "predicted_issue": prediction.predicted_issue,
                    "product_confidence": prediction.product_confidence,
                    "issue_confidence": prediction.issue_confidence,
                    "model_version": prediction.model_version,
                    "predictor_type": prediction.predictor_type,
                },
            },
            {
                "stage": "PRIORITY_ASSESSMENT",
                "timestamp": now_iso,
                "details": {
                    "priority": priority.value,
                    "reason": priority_reason,
                },
            },
            {
                "stage": "CONFIDENCE_GATE",
                "timestamp": now_iso,
                "details": {
                    "gate_decision": gate_decision.value,
                    "threshold_tau": self.gate.product_threshold,
                    "gate_reason": gate_reason,
                },
            },
            {
                "stage": "ROUTING_DECISION",
                "timestamp": now_iso,
                "details": {
                    "destination_team": routing_decision.destination_team,
                    "route_type": routing_decision.route_type,
                    "rule_id": routing_decision.rule_id,
                    "explanation": routing_decision.routing_explanation,
                    "override_applied": routing_decision.override_applied,
                },
            },
        ]

        # 8. Persist Record to MongoDB
        storage_doc = {
            "request_id": request_id,
            "original_text": request.text,
            "original_text_preview": (request.text[:120] + "...") if len(request.text) > 120 else request.text,
            "redacted_text": clean_text,
            "pii_detected": pii_detected,
            "pii_entities_count": len(redaction_result.entities_found),
            "predicted_product": prediction.predicted_product,
            "predicted_issue": prediction.predicted_issue,
            "original_predicted_product": prediction.predicted_product,
            "original_predicted_issue": prediction.predicted_issue,
            "priority": priority.value,
            "priority_reason": priority_reason,
            "product_confidence": prediction.product_confidence,
            "issue_confidence": prediction.issue_confidence,
            "threshold": self.gate.product_threshold,
            "gate_decision": gate_decision.value,
            "route_type": routing_decision.route_type,
            "assigned_team": routing_decision.destination_team,
            "routing_rule_id": routing_decision.rule_id,
            "routing_explanation": routing_decision.routing_explanation,
            "review_status": review_status.value,
            "review_reason": review_reason,
            "model_version": prediction.model_version,
            "predictor_type": prediction.predictor_type,
            "metadata": request.metadata or {},
            "client_id": request.client_id,
            "created_at": now_iso,
            "updated_at": now_iso,
            "reviewed_at": None,
            "reviewer_id": None,
            "timeline": timeline,
            "feedback": [],
        }

        await self.repo.insert(storage_doc)

        logger.info(
            f"Triage complete for {request_id}: Product='{prediction.predicted_product}' "
            f"Conf={prediction.product_confidence:.2f} Route='{routing_decision.destination_team}'"
        )

        return TriageResponse(
            request_id=request_id,
            original_text_preview=storage_doc["original_text_preview"],
            redacted_text=clean_text,
            pii_detected=pii_detected,
            pii_entities_count=len(redaction_result.entities_found),
            predicted_product=prediction.predicted_product,
            predicted_issue=prediction.predicted_issue,
            priority=priority,
            priority_reason=priority_reason,
            product_confidence=prediction.product_confidence,
            issue_confidence=prediction.issue_confidence,
            threshold=self.gate.product_threshold,
            gate_decision=gate_decision,
            route_type=routing_decision.route_type,
            assigned_team=routing_decision.destination_team,
            routing_rule_id=routing_decision.rule_id,
            routing_explanation=routing_decision.routing_explanation,
            review_status=review_status,
            review_reason=review_reason,
            model_version=prediction.model_version,
            predictor_type=prediction.predictor_type,
            created_at=now_iso,
            latency_ms=latency_ms,
        )
