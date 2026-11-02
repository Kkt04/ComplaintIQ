"""Confidence Gate component for ComplaintIQ triage pipeline.

Evaluates prediction confidence against defined thresholds tau (product and issue).
Determines whether a prediction can safely be auto-routed or must divert to Human Review.
"""

import math
from typing import Optional, Tuple
from complaintiq.core.config import settings
from complaintiq.core.logging import logger
from complaintiq.serving.schemas import GateDecisionEnum


class ConfidenceGate:
    """Confidence gate evaluating whether automated triage is permitted."""

    def __init__(
        self,
        product_threshold: Optional[float] = None,
        issue_threshold: Optional[float] = None,
        strict_mode: Optional[bool] = None,
    ):
        self.product_threshold = (
            product_threshold
            if product_threshold is not None
            else settings.product_confidence_threshold
        )
        self.issue_threshold = (
            issue_threshold
            if issue_threshold is not None
            else settings.issue_confidence_threshold
        )
        self.strict_mode = (
            strict_mode
            if strict_mode is not None
            else bool(settings.thresholds.get("strict_mode", True))
        )

    def evaluate(
        self,
        product_confidence: float,
        issue_confidence: Optional[float] = None,
    ) -> Tuple[GateDecisionEnum, Optional[str]]:
        """
        Evaluate confidence values.

        Returns:
            Tuple of (GateDecisionEnum, reason_str)
        """
        # Validate confidence value: handle None, NaN, Inf, out of bounds
        if product_confidence is None:
            logger.warning("ConfidenceGate received None product_confidence")
            return GateDecisionEnum.HUMAN_REVIEW, "Product confidence value is missing"

        try:
            if math.isnan(product_confidence) or math.isinf(product_confidence):
                logger.warning(f"ConfidenceGate received invalid numerical confidence: {product_confidence}")
                return GateDecisionEnum.HUMAN_REVIEW, "Prediction confidence is NaN or Infinite"
        except (TypeError, ValueError):
            return GateDecisionEnum.HUMAN_REVIEW, "Prediction confidence is not a valid float"

        if product_confidence < 0.0 or product_confidence > 1.0:
            logger.warning(f"ConfidenceGate received out-of-range confidence: {product_confidence}")
            return GateDecisionEnum.HUMAN_REVIEW, f"Prediction confidence {product_confidence} is outside [0.0, 1.0]"

        # Check product confidence against threshold tau
        if product_confidence < self.product_threshold:
            reason = (
                f"Product confidence ({product_confidence:.2f}) is below required "
                f"threshold tau ({self.product_threshold:.2f}). Sent to Human Review Queue."
            )
            return GateDecisionEnum.HUMAN_REVIEW, reason

        # If strict mode is enabled and issue_confidence is present, evaluate issue threshold
        if self.strict_mode and issue_confidence is not None:
            if not math.isnan(issue_confidence) and not math.isinf(issue_confidence):
                if 0.0 <= issue_confidence <= 1.0 and issue_confidence < self.issue_threshold:
                    reason = (
                        f"Issue confidence ({issue_confidence:.2f}) is below secondary "
                        f"threshold ({self.issue_threshold:.2f}). Sent to Human Review Queue."
                    )
                    return GateDecisionEnum.HUMAN_REVIEW, reason

        # Confidence requirement satisfied
        return GateDecisionEnum.ALLOW_ROUTING, None
