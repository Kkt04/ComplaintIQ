"""Pydantic schemas for ComplaintIQ serving, triage, and human review."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class PriorityEnum(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class GateDecisionEnum(str, Enum):
    ALLOW_ROUTING = "ALLOW_ROUTING"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class ReviewStatusEnum(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    CORRECTED = "CORRECTED"
    CONFIRMED = "CONFIRMED"


class TriageRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    text: str = Field(
        ...,
        min_length=20,
        max_length=10000,
        description="Raw financial complaint narrative from CFPB consumer or operator.",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Optional client metadata (e.g. channel, account_id).",
    )
    client_id: Optional[str] = Field(
        default=None,
        description="Optional identifier of the client initiating the request.",
    )


class TriageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    request_id: str
    original_text_preview: str
    redacted_text: str
    pii_detected: bool
    pii_entities_count: int

    predicted_product: str
    predicted_issue: str
    priority: PriorityEnum
    priority_reason: str

    product_confidence: float
    issue_confidence: Optional[float] = None
    threshold: float
    gate_decision: GateDecisionEnum

    route_type: str
    assigned_team: str
    routing_rule_id: str
    routing_explanation: str

    review_status: ReviewStatusEnum
    review_reason: Optional[str] = None

    model_version: str
    predictor_type: str
    created_at: str
    latency_ms: Optional[float] = None


class HumanReviewRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    action: str = Field(
        default="CORRECT",
        description="Action to perform: 'CORRECT' to modify labels or 'CONFIRM' to accept current predictions.",
    )
    corrected_product: Optional[str] = Field(
        default=None,
        description="Human-corrected financial product category.",
    )
    corrected_issue: Optional[str] = Field(
        default=None,
        description="Human-corrected complaint issue.",
    )
    correction_reason: Optional[str] = Field(
        default=None,
        description="Detailed reason or note explaining why the model prediction was corrected or confirmed.",
    )
    reviewer_id: str = Field(
        ...,
        min_length=1,
        description="Identifier of the human triage specialist performing the review.",
    )


class HumanReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    request_id: str
    review_status: ReviewStatusEnum
    previous_product: str
    previous_issue: str
    previous_assigned_team: str
    updated_product: str
    updated_issue: str
    updated_assigned_team: str
    reviewer_id: str
    reviewed_at: str
    notes: Optional[str] = None


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    request_id: str
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    is_accurate: Optional[bool] = None
    comments: Optional[str] = None
    user_id: Optional[str] = None


class FeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    feedback_id: str
    request_id: str
    rating: Optional[int]
    is_accurate: Optional[bool]
    comments: Optional[str]
    created_at: str


class TimelineEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stage: str
    timestamp: str
    details: Dict[str, Any]


class RequestDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    request_id: str
    original_text: str
    redacted_text: str
    pii_detected: bool

    predicted_product: str
    predicted_issue: str
    priority: PriorityEnum
    priority_reason: str

    product_confidence: float
    issue_confidence: Optional[float]
    threshold: float
    gate_decision: GateDecisionEnum

    assigned_team: str
    route_type: str
    routing_rule_id: str
    routing_explanation: str

    review_status: ReviewStatusEnum
    review_reason: Optional[str]

    model_version: str
    predictor_type: str

    created_at: str
    updated_at: str
    reviewed_at: Optional[str] = None
    reviewer_id: Optional[str] = None

    timeline: List[TimelineEvent] = Field(default_factory=list)
    feedback: List[FeedbackResponse] = Field(default_factory=list)


class RequestListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: List[RequestDetailResponse]
    total: int
    page: int
    size: int
    pages: int


class QueueCountItem(BaseModel):
    queue_name: str
    count: int
    critical_count: int


class AnalyticsOverviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_requests: int
    automated_count: int
    human_review_count: int
    automation_rate: float
    avg_confidence: float
    review_status_breakdown: Dict[str, int]
    priority_breakdown: Dict[str, int]
    top_products: List[Dict[str, Any]]
    team_queues: List[QueueCountItem]
    model_version: str


class HealthResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    version: str
    model_version: str
    database_status: str
    is_mock_database: bool
    uptime_seconds: float
    timestamp: str
