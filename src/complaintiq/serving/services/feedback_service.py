"""Feedback and Human Review Service for ComplaintIQ.

Manages human-in-the-loop corrections, audit logging, model feedback collection,
and re-routing of verified complaints.
"""

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, Optional
from complaintiq.core.logging import logger
from complaintiq.serving.gate import ConfidenceGate
from complaintiq.serving.repositories.feedback_repository import FeedbackRepository
from complaintiq.serving.repositories.request_repository import RequestRepository
from complaintiq.serving.router import RoutingEngine
from complaintiq.serving.schemas import (
    FeedbackRequest,
    FeedbackResponse,
    GateDecisionEnum,
    HumanReviewRequest,
    HumanReviewResponse,
    PriorityEnum,
    ReviewStatusEnum,
)


class FeedbackService:
    """Handles operator feedback, human-in-the-loop review actions, and re-routing."""

    def __init__(
        self,
        request_repo: Optional[RequestRepository] = None,
        feedback_repo: Optional[FeedbackRepository] = None,
        router: Optional[RoutingEngine] = None,
    ):
        self.request_repo = request_repo or RequestRepository()
        self.feedback_repo = feedback_repo or FeedbackRepository()
        self.router = router or RoutingEngine()

    async def submit_review(
        self,
        request_id: str,
        review_data: HumanReviewRequest,
    ) -> HumanReviewResponse:
        """
        Process human review action (CORRECT or CONFIRM) on an existing complaint request.
        """
        req_doc = await self.request_repo.get_by_request_id(request_id)
        if not req_doc:
            raise ValueError(f"Request with ID '{request_id}' not found.")

        now_iso = datetime.now(timezone.utc).isoformat()
        prev_prod = req_doc.get("predicted_product", "")
        prev_issue = req_doc.get("predicted_issue", "")
        prev_team = req_doc.get("assigned_team", "")
        priority = PriorityEnum(req_doc.get("priority", "MEDIUM"))

        if review_data.action.upper() == "CORRECT":
            updated_prod = review_data.corrected_product or prev_prod
            updated_issue = review_data.corrected_issue or prev_issue
            review_status = ReviewStatusEnum.CORRECTED

            # Re-evaluate routing with human-verified product (bypassing low-confidence gate)
            reroute = self.router.route(
                predicted_product=updated_prod,
                priority=priority,
                gate_decision=GateDecisionEnum.ALLOW_ROUTING,
                complaint_text=req_doc.get("redacted_text", ""),
            )

            updated_team = reroute.destination_team
            new_explanation = (
                f"Re-routed to {updated_team} following human correction by reviewer "
                f"{review_data.reviewer_id}. Reason: {review_data.correction_reason or 'No reason supplied'}."
            )
            route_type = "HUMAN_CORRECTED"

            timeline_event = {
                "stage": "HUMAN_CORRECTION",
                "timestamp": now_iso,
                "details": {
                    "reviewer_id": review_data.reviewer_id,
                    "previous_product": prev_prod,
                    "corrected_product": updated_prod,
                    "previous_issue": prev_issue,
                    "corrected_issue": updated_issue,
                    "previous_team": prev_team,
                    "new_team": updated_team,
                    "reason": review_data.correction_reason,
                },
            }

        else:  # CONFIRM
            updated_prod = prev_prod
            updated_issue = prev_issue
            review_status = ReviewStatusEnum.CONFIRMED

            # Confirm model prediction: execute team route bypassing the gate
            reroute = self.router.route(
                predicted_product=updated_prod,
                priority=priority,
                gate_decision=GateDecisionEnum.ALLOW_ROUTING,
                complaint_text=req_doc.get("redacted_text", ""),
            )
            updated_team = reroute.destination_team
            new_explanation = (
                f"Prediction confirmed by reviewer {review_data.reviewer_id}; "
                f"routed to {updated_team}."
            )
            route_type = "HUMAN_CONFIRMED"

            timeline_event = {
                "stage": "HUMAN_CONFIRMATION",
                "timestamp": now_iso,
                "details": {
                    "reviewer_id": review_data.reviewer_id,
                    "confirmed_product": updated_prod,
                    "destination_team": updated_team,
                    "notes": review_data.correction_reason,
                },
            }

        updates: Dict[str, Any] = {
            "predicted_product": updated_prod,
            "predicted_issue": updated_issue,
            "assigned_team": updated_team,
            "route_type": route_type,
            "routing_rule_id": reroute.rule_id,
            "routing_explanation": new_explanation,
            "review_status": review_status.value,
            "reviewed_at": now_iso,
            "reviewer_id": review_data.reviewer_id,
            "updated_at": now_iso,
        }

        await self.request_repo.update_by_request_id(request_id, updates)
        await self.request_repo.append_timeline_event(request_id, timeline_event)

        logger.info(
            f"Human review applied for {request_id}: {review_status.value} "
            f"by {review_data.reviewer_id} -> {updated_team}"
        )

        return HumanReviewResponse(
            request_id=request_id,
            review_status=review_status,
            previous_product=prev_prod,
            previous_issue=prev_issue,
            previous_assigned_team=prev_team,
            updated_product=updated_prod,
            updated_issue=updated_issue,
            updated_assigned_team=updated_team,
            reviewer_id=review_data.reviewer_id,
            reviewed_at=now_iso,
            notes=review_data.correction_reason,
        )

    async def submit_feedback(self, feedback: FeedbackRequest) -> FeedbackResponse:
        """Collect quality rating and comments on a processed request."""
        now_iso = datetime.now(timezone.utc).isoformat()
        feedback_id = f"fb_{uuid.uuid4().hex[:10]}"

        doc = {
            "feedback_id": feedback_id,
            "request_id": feedback.request_id,
            "rating": feedback.rating,
            "is_accurate": feedback.is_accurate,
            "comments": feedback.comments,
            "user_id": feedback.user_id,
            "created_at": now_iso,
        }

        await self.feedback_repo.insert(doc)

        # Append feedback reference to the request doc
        await self.request_repo.append_timeline_event(
            feedback.request_id,
            {
                "stage": "USER_FEEDBACK",
                "timestamp": now_iso,
                "details": {
                    "feedback_id": feedback_id,
                    "rating": feedback.rating,
                    "is_accurate": feedback.is_accurate,
                },
            },
        )

        return FeedbackResponse(
            feedback_id=feedback_id,
            request_id=feedback.request_id,
            rating=feedback.rating,
            is_accurate=feedback.is_accurate,
            comments=feedback.comments,
            created_at=now_iso,
        )
