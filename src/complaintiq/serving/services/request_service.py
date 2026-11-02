"""Query and retrieval service for ComplaintIQ requests, queues, and analytics."""

import math
from typing import Any, Dict, List, Optional
from complaintiq.core.config import settings
from complaintiq.serving.repositories.feedback_repository import FeedbackRepository
from complaintiq.serving.repositories.request_repository import RequestRepository
from complaintiq.serving.schemas import (
    AnalyticsOverviewResponse,
    QueueCountItem,
    RequestDetailResponse,
    RequestListResponse,
)


class RequestService:
    """Manages complaint queries, filtering by team queue, and operational metrics."""

    def __init__(
        self,
        request_repo: Optional[RequestRepository] = None,
        feedback_repo: Optional[FeedbackRepository] = None,
    ):
        self.request_repo = request_repo or RequestRepository()
        self.feedback_repo = feedback_repo or FeedbackRepository()

    async def get_request_by_id(self, request_id: str) -> Optional[RequestDetailResponse]:
        doc = await self.request_repo.get_by_request_id(request_id)
        if not doc:
            return None

        # Fetch any feedback records
        feedback_docs = await self.feedback_repo.get_by_request_id(request_id)
        doc["feedback"] = feedback_docs
        return RequestDetailResponse(**doc)

    async def list_requests(
        self,
        team: Optional[str] = None,
        priority: Optional[str] = None,
        review_status: Optional[str] = None,
        gate_decision: Optional[str] = None,
        search_query: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> RequestListResponse:
        filter_query: Dict[str, Any] = {}

        if team:
            filter_query["assigned_team"] = team
        if priority:
            filter_query["priority"] = priority.upper()
        if review_status:
            filter_query["review_status"] = review_status.upper()
        if gate_decision:
            filter_query["gate_decision"] = gate_decision.upper()
        if search_query:
            filter_query["$or"] = [
                {"request_id": {"$regex": search_query, "$options": "i"}},
                {"redacted_text": {"$regex": search_query, "$options": "i"}},
                {"predicted_product": {"$regex": search_query, "$options": "i"}},
            ]

        skip = (page - 1) * size
        total = await self.request_repo.count_requests(filter_query)
        items = await self.request_repo.list_requests(
            filter_query=filter_query,
            skip=skip,
            limit=size,
        )

        detail_items = []
        for item in items:
            detail_items.append(RequestDetailResponse(**item))

        pages = math.ceil(total / size) if size > 0 else 1

        return RequestListResponse(
            items=detail_items,
            total=total,
            page=page,
            size=size,
            pages=pages,
        )

    async def get_analytics_overview(self) -> AnalyticsOverviewResponse:
        metrics = await self.request_repo.get_analytics_metrics()
        model_version = settings.model_config_data.get("model", {}).get("default_version", "v1.0.0-stub")

        return AnalyticsOverviewResponse(
            total_requests=metrics["total_requests"],
            automated_count=metrics["automated_count"],
            human_review_count=metrics["human_review_count"],
            automation_rate=metrics["automation_rate"],
            avg_confidence=metrics["avg_confidence"],
            review_status_breakdown=metrics["review_status_breakdown"],
            priority_breakdown=metrics["priority_breakdown"],
            top_products=metrics["top_products"],
            team_queues=[QueueCountItem(**item) for item in metrics["team_queues"]],
            model_version=model_version,
        )
