"""PII Redaction Engine for ComplaintIQ."""

from dataclasses import dataclass
import re
from typing import Dict, List, NamedTuple, Tuple


@dataclass
class RedactedEntity:
    entity_type: str
    matched_value: str = ""


class RedactionResult(NamedTuple):
    redacted_text: str
    counts: Dict[str, int]

    @property
    def entities_found(self) -> List[RedactedEntity]:
        res = []
        for etype, cnt in self.counts.items():
            for _ in range(cnt):
                res.append(RedactedEntity(entity_type=etype))
        return res

    @property
    def entities_count(self) -> int:
        return sum(self.counts.values())

    @property
    def pii_detected(self) -> bool:
        return self.entities_count > 0


class PIIRedactor:
    """Detects and redacts sensitive personally identifiable information (PII) from complaint text."""

    PATTERNS = {
        "SSN": re.compile(r"\b(?!000|666|9\d{2})\d{3}[- ]?(?!00)\d{2}[- ]?(?!0000)\d{4}\b"),
        "EMAIL": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
        "PHONE": re.compile(r"\b(?:\+?1[-. ]?)?\(?([0-9]{3})\)?[-. ]?([0-9]{3})[-. ]?([0-9]{4})\b"),
        "CREDIT_CARD": re.compile(r"\b(?:\d{4}[- ]?){3}\d{4}\b|\b\d{15,16}\b"),
        "ACCOUNT_NO": re.compile(r"\b(?:acct|account|acc|routing)\s*(?:#|no\.?|number)?\s*[:=]?\s*([0-9A-Za-z]{6,16})\b", re.IGNORECASE),
    }

    def redact(self, text: str) -> RedactionResult:
        """Redacts sensitive PII entities from the input text and counts redaction occurrences."""
        if not text:
            return RedactionResult(redacted_text="", counts={})

        redacted_text = text
        counts: Dict[str, int] = {}

        # 1. Redact SSN
        matches_ssn = len(self.PATTERNS["SSN"].findall(redacted_text))
        if matches_ssn:
            counts["SSN"] = matches_ssn
            redacted_text = self.PATTERNS["SSN"].sub("[REDACTED_SSN]", redacted_text)

        # 2. Redact Email
        matches_email = len(self.PATTERNS["EMAIL"].findall(redacted_text))
        if matches_email:
            counts["EMAIL"] = matches_email
            redacted_text = self.PATTERNS["EMAIL"].sub("[REDACTED_EMAIL]", redacted_text)

        # 3. Redact Phone
        matches_phone = len(self.PATTERNS["PHONE"].findall(redacted_text))
        if matches_phone:
            counts["PHONE"] = matches_phone
            redacted_text = self.PATTERNS["PHONE"].sub("[REDACTED_PHONE]", redacted_text)

        # 4. Redact Credit Card
        matches_cc = len(self.PATTERNS["CREDIT_CARD"].findall(redacted_text))
        if matches_cc:
            counts["CREDIT_CARD"] = matches_cc
            redacted_text = self.PATTERNS["CREDIT_CARD"].sub("[REDACTED_CARD]", redacted_text)

        # 5. Redact Account Number
        matches_acc = len(self.PATTERNS["ACCOUNT_NO"].findall(redacted_text))
        if matches_acc:
            counts["ACCOUNT_NO"] = matches_acc
            redacted_text = self.PATTERNS["ACCOUNT_NO"].sub("account [REDACTED_ACCOUNT]", redacted_text)

        return RedactionResult(redacted_text=redacted_text, counts=counts)


redactor = PIIRedactor()
