"""Priority assessment service for ComplaintIQ financial complaints.

Deterministically assigns complaint priority (CRITICAL, HIGH, MEDIUM, LOW)
based on financial urgency indicators, legal threats, fraud signals, and harm severity.
"""

import re
from typing import Tuple
from complaintiq.serving.schemas import PriorityEnum


class PriorityAssessmentService:
    """Evaluates complaint severity and urgency to assign operational priority."""

    CRITICAL_PATTERNS = [
        (r"\b(foreclosure|foreclose|auction|evict|eviction)\b", "Imminent loss of home or property foreclosure"),
        (r"\b(repossession|repossessed|repo order)\b", "Vehicle repossession threat or action"),
        (r"\b(bankruptcy|chapter 7|chapter 13)\b", "Active legal bankruptcy proceedings"),
        (r"\b(lawsuit|attorney general|cfpb complaint|sue you|legal action|court date|subpoena)\b", "Formal legal action or regulatory escalation"),
        (r"\b(identity theft|stolen identity|ssn compromised|syndicate|fraud ring)\b", "Severe identity theft or systemic compromise"),
        (r"\b(all my money|penniless|cannot buy food|starving|homeless|frozen account.*rent)\b", "Immediate existential consumer hardship / frozen survival funds"),
    ]

    HIGH_PATTERNS = [
        (r"\b(unauthorized (charge|transaction|transfer|withdrawal)|fraudulent charges)\b", "Unauthorized financial transactions or account takeover"),
        (r"\b(harass|threatening|calling at work|called my employer|frequent calls at 3am)\b", "Severe debt collector harassment / FDCPA violations"),
        (r"\b(ruined my credit|dropped my score \d+|100 points|derogatory mark)\b", "Substantial negative impact on consumer credit profile"),
        (r"\b(scam|phishing|stolen card|wire scam)\b", "Suspected financial fraud or wire theft"),
        (r"(?:\$|\busd\s*)\s*([5-9],\d{3}|[5-9]\d{3}|[1-9]\d{1,2},\d{3}|[1-9]\d{4,})\b", "High monetary value dispute exceeding $5,000"),
        (r"\b(deadline|time sensitive|urgent|within 24 hours|within 48 hours)\b", "Time-critical regulatory or payment deadline"),
    ]

    MEDIUM_PATTERNS = [
        (r"\b(dispute|incorrect fee|overdraft fee|late fee|apr rate|billing error)\b", "Direct financial dispute or disputed account fees"),
        (r"\b(delayed|slow|waiting for weeks|no response|ignored my emails)\b", "Protracted operational delay or customer service breakdown"),
        (r"\b(escrow calculation|interest calculation|refinance rate)\b", "Loan servicing calculation or rate discrepancy"),
    ]

    def assess_priority(self, text: str, predicted_issue: str = "") -> Tuple[PriorityEnum, str]:
        """
        Assess narrative text and issue to determine priority and rationale.
        """
        text_lower = text.lower()
        issue_lower = predicted_issue.lower()
        combined = f"{text_lower} {issue_lower}"

        # 1. Critical priority check
        for pattern, explanation in self.CRITICAL_PATTERNS:
            if re.search(pattern, combined):
                return PriorityEnum.CRITICAL, explanation

        # 2. High priority check
        for pattern, explanation in self.HIGH_PATTERNS:
            if re.search(pattern, combined):
                return PriorityEnum.HIGH, explanation

        # 3. Medium priority check
        for pattern, explanation in self.MEDIUM_PATTERNS:
            if re.search(pattern, combined):
                return PriorityEnum.MEDIUM, explanation

        # 4. Low priority fallback for routine inquiries
        return PriorityEnum.LOW, "Standard routine complaint or informational query with no high-risk urgency indicators."
