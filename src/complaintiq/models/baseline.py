from complaintiq.models.protocol import PredictionResult, PredictorProtocol
from complaintiq.models.stub import StubPredictor


class BaselinePredictor(PredictorProtocol):
    """Rule-enhanced baseline predictor for CFPB financial classification."""

    def __init__(self, model_version: str = "v1.2.0-baseline"):
        self._version = model_version
        self._type = "BASELINE"
        self._inner = StubPredictor(model_version=model_version)

    @property
    def predictor_type(self) -> str:
        return self._type

    @property
    def model_version(self) -> str:
        return self._version

    async def predict(self, text: str) -> PredictionResult:
        res = await self._inner.predict(text)
        return PredictionResult(
            predicted_product=res.predicted_product,
            predicted_issue=res.predicted_issue,
            product_confidence=res.product_confidence,
            issue_confidence=res.issue_confidence,
            model_version=self._version,
            predictor_type=self._type,
            metadata={"source": "baseline_statistical_rules", "features_extracted": 14},
        )
