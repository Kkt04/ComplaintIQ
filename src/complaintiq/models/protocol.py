from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol, runtime_checkable


@dataclass
class PredictionResult:
    predicted_product: str
    predicted_issue: str
    product_confidence: float
    issue_confidence: Optional[float]
    model_version: str
    predictor_type: str  # STUB, BASELINE, TRANSFORMER, ONNX
    metadata: Dict[str, Any]


@runtime_checkable
class PredictorProtocol(Protocol):
    """Protocol for NLP complaint classifiers."""

    @property
    def predictor_type(self) -> str:
        ...

    @property
    def model_version(self) -> str:
        ...

    async def predict(self, text: str) -> PredictionResult:
        ...
