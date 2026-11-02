"""B6 Team Routing Engine for ComplaintIQ.

Maps consumer financial products and priority overrides to specialized internal teams
conforming to configs/routing.yaml and CFPB product taxonomy.
"""

from dataclasses import dataclass
import re
from typing import Any, Dict, List, Optional
from complaintiq.core.config import settings
from complaintiq.core.logging import logger
from complaintiq.serving.schemas import GateDecisionEnum, PriorityEnum, ReviewStatusEnum


@dataclass
class RoutingDecision:
    destination_team: str
    route_type: str  # AUTOMATED, OVERRIDE_FRAUD, HUMAN_REVIEW_QUEUE, DEFAULT_FALLBACK
    rule_id: str
    routing_explanation: str
    override_applied: bool


class RoutingEngine:
    """Evaluates product classification, priority, and confidence gate to route complaints."""

    def __init__(self, routing_config: Optional[Dict[str, Any]] = None):
        cfg = routing_config or settings.routing
        self.teams_list: List[Dict[str, Any]] = cfg.get("teams", [])
        self.overrides: Dict[str, Any] = cfg.get("overrides", {})
        self.default_team: str = cfg.get("default_team", "General Financial Support")

        # Build normalized lookup map: normalized_product_name -> (destination_team, rule_id, description)
        self.product_map: Dict[str, Dict[str, str]] = {}
        for item in self.teams_list:
            prod_norm = self._normalize_product_name(item.get("product", ""))
            self.product_map[prod_norm] = {
                "team": item.get("destination_team", self.default_team),
                "rule_id": item.get("id", "UNKNOWN_RULE"),
                "description": item.get("description", ""),
            }

    @staticmethod
    def _normalize_product_name(name: str) -> str:
        """Strip whitespace and lower-case product name for robust lookup."""
        return re.sub(r"\s+", " ", name.strip().lower())

    def route(
        self,
        predicted_product: str,
        priority: PriorityEnum,
        gate_decision: GateDecisionEnum,
        complaint_text: str = "",
        gate_reason: Optional[str] = None,
    ) -> RoutingDecision:
        """
        Determine routing decision following B6 rules, confidence gating, and fraud overrides.
        """
        # 1. Check Confidence Gate: If gate evaluated to HUMAN_REVIEW, divert immediately to Human Review Queue
        if gate_decision == GateDecisionEnum.HUMAN_REVIEW:
            return RoutingDecision(
                destination_team="Human Review Queue",
                route_type="HUMAN_REVIEW_QUEUE",
                rule_id="OVERRIDE_GATE_FALLBACK",
                routing_explanation=gate_reason or "Low model prediction confidence requires operator human verification.",
                override_applied=True,
            )

        # 2. Check High/Critical Fraud & Identity Theft Override
        fraud_cfg = self.overrides.get("fraud_and_risk", {})
        applicable_priorities = fraud_cfg.get("applicable_priorities", ["HIGH", "CRITICAL"])
        if priority.value in applicable_priorities:
            keywords = fraud_cfg.get("trigger_keywords", [
                "fraud", "identity theft", "unauthorized", "scam", "impersonation", "hacked", "stolen identity"
            ])
            text_lower = complaint_text.lower()
            matched_keywords = [kw for kw in keywords if kw in text_lower]
            if matched_keywords:
                rule_id = fraud_cfg.get("rule_id", "OVERRIDE_FRAUD_RISK")
                team = fraud_cfg.get("destination_team", "Fraud and Risk")
                explanation = (
                    f"Complaint flagged as {priority.value} priority with fraud/security indicators "
                    f"({', '.join(matched_keywords)}). Diverted to {team}."
                )
                return RoutingDecision(
                    destination_team=team,
                    route_type="OVERRIDE_FRAUD",
                    rule_id=rule_id,
                    routing_explanation=explanation,
                    override_applied=True,
                )

        # 3. Standard B6 Product-to-Team Routing
        norm_prod = self._normalize_product_name(predicted_product)
        if norm_prod in self.product_map:
            rule_info = self.product_map[norm_prod]
            team = rule_info["team"]
            rule_id = rule_info["rule_id"]
            explanation = f"Routed to {team} based on product classification '{predicted_product}' under rule {rule_id}."
            return RoutingDecision(
                destination_team=team,
                route_type="AUTOMATED",
                rule_id=rule_id,
                routing_explanation=explanation,
                override_applied=False,
            )

        # Partial matching fallback for near-matches
        for key, rule_info in self.product_map.items():
            if key in norm_prod or norm_prod in key:
                team = rule_info["team"]
                rule_id = rule_info["rule_id"]
                explanation = (
                    f"Routed to {team} via partial product match '{predicted_product}' "
                    f"under rule {rule_id}."
                )
                return RoutingDecision(
                    destination_team=team,
                    route_type="AUTOMATED",
                    rule_id=rule_id,
                    routing_explanation=explanation,
                    override_applied=False,
                )

        # 4. Unknown product fallback
        logger.warning(f"Unrecognized product '{predicted_product}', routing to default team: {self.default_team}")
        return RoutingDecision(
            destination_team=self.default_team,
            route_type="DEFAULT_FALLBACK",
            rule_id="RULE_DEFAULT_FALLBACK",
            routing_explanation=f"Product '{predicted_product}' not matched in routing table; assigned to default queue.",
            override_applied=False,
        )
