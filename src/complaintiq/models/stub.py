import re
from typing import Optional
from complaintiq.models.protocol import PredictionResult, PredictorProtocol


class StubPredictor(PredictorProtocol):
    """Stub predictor providing deterministic CFPB financial classifications for development and testing."""

    def __init__(self, model_version: str = "v1.0.0-stub"):
        self._version = model_version
        self._type = "STUB"

    @property
    def predictor_type(self) -> str:
        return self._type

    @property
    def model_version(self) -> str:
        return self._version

    async def predict(self, text: str) -> PredictionResult:
        t = text.lower()

        # Check for explicitly triggered low-confidence flag for testing confidence gate
        if "low confidence" in t or "uncertain" in t or "ambiguous financial issue" in t:
            return PredictionResult(
                predicted_product="Debt collection",
                predicted_issue="Communication tactics",
                product_confidence=0.62,
                issue_confidence=0.55,
                model_version=self._version,
                predictor_type=self._type,
                metadata={"heuristic": "explicit_uncertainty_trigger"},
            )

        # Keyword-based deterministic classification matching CFPB taxonomies
        if re.search(r"\b(debt|collector|collection|owed|harass)\b", t):
            product = "Debt collection"
            issue = "Attempts to collect debt not owed"
            conf = 0.94
        elif re.search(r"\b(credit card|prepaid|visa|mastercard|card charge|apr)\b", t):
            product = "Credit card or prepaid card"
            issue = "Billing disputes"
            conf = 0.92
        elif re.search(r"\b(mortgage|escrow|home loan|foreclosure|refinance)\b", t):
            product = "Mortgage"
            issue = "Trouble during payment process"
            conf = 0.95
        elif re.search(r"\b(student loan|fafsa|tuition|sallie mae|navient)\b", t):
            product = "Student loan"
            issue = "Dealing with your lender or servicer"
            conf = 0.91
        elif re.search(r"\b(vehicle|car loan|auto loan|lease|repossession)\b", t):
            product = "Vehicle loan or lease"
            issue = "Managing the loan or lease"
            conf = 0.89
        elif re.search(r"\b(checking|savings|overdraft|atm|deposit|bank account)\b", t):
            product = "Checking or savings account"
            issue = "Managing an account"
            conf = 0.93
        elif re.search(r"\b(credit report|equifax|experian|transunion|bureau|dispute)\b", t):
            product = "Credit reporting, credit repair services, or other personal consumer reports"
            issue = "Incorrect information on your report"
            conf = 0.96
        elif re.search(r"\b(wire|remittance|crypto|bitcoin|transfer|western union)\b", t):
            product = "Money transfer, virtual currency, or money service"
            issue = "Money was not available when promised"
            conf = 0.88
        elif re.search(r"\b(payday|title loan|installment loan|cash advance)\b", t):
            product = "Payday loan, title loan, or personal loan"
            issue = "Charged fees or interest you were not expecting"
            conf = 0.87
        else:
            # General financial query
            product = "Checking or savings account"
            issue = "Problem with a lender or other company"
            conf = 0.74  # Falls below 0.85 threshold, routing to Human Review

        return PredictionResult(
            predicted_product=product,
            predicted_issue=issue,
            product_confidence=conf,
            issue_confidence=round(conf - 0.05, 2),
            model_version=self._version,
            predictor_type=self._type,
            metadata={"source": "stub_heuristic_engine", "text_length": len(text)},
        )
