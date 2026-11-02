"""ComplaintIQ FastAPI serving application.

Provides REST APIs for consumer complaint triage, confidence gating,
explainable B6 routing, human review workflows, and operational metrics.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from complaintiq.core.config import settings
from complaintiq.core.database import close_db_connection, get_database, is_mock_database
from complaintiq.core.logging import logger
from complaintiq.serving.gate import ConfidenceGate
from complaintiq.serving.middleware.request_id import RequestIDMiddleware
from complaintiq.serving.router import RoutingEngine
from complaintiq.serving.schemas import (
    AnalyticsOverviewResponse,
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    HumanReviewRequest,
    HumanReviewResponse,
    RequestDetailResponse,
    RequestListResponse,
    TriageRequest,
    TriageResponse,
)
from complaintiq.serving.services.feedback_service import FeedbackService
from complaintiq.serving.services.request_service import RequestService
from complaintiq.serving.services.triage_service import TriageService

APP_START_TIME = time.time()
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
STATIC_DIR = BASE_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing ComplaintIQ application services...")
    # Initialize database connection
    await get_database()
    logger.info(f"ComplaintIQ initialized. Database mock mode: {is_mock_database()}")
    yield
    logger.info("Shutting down ComplaintIQ application...")
    await close_db_connection()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="NLP-Powered CFPB Consumer Complaint Triage, Confidence Gating, and B6 Routing Platform",
    lifespan=lifespan,
)

# Middleware
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Services
triage_service = TriageService()
feedback_service = FeedbackService()
request_service = RequestService()

# Static Files
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# Root and UI Routes
@app.get("/", include_in_schema=False)
async def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return JSONResponse(
        content={
            "service": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "message": "ComplaintIQ API is operational. Visit /docs for OpenAPI documentation.",
        }
    )


@app.get("/dashboard", include_in_schema=False)
async def serve_dashboard():
    dashboard_file = STATIC_DIR / "dashboard.html"
    if dashboard_file.exists():
        return FileResponse(str(dashboard_file))
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return JSONResponse(content={"error": "Dashboard template not found"}, status_code=404)


# Health & Metadata Endpoints
@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    db_status = "connected"
    try:
        db = await get_database()
        if not is_mock_database():
            await db.client.admin.command("ping")
        db_status = "mock_in_memory" if is_mock_database() else "connected_mongodb"
    except Exception as e:
        db_status = f"error: {str(e)}"

    model_version = settings.model_config_data.get("model", {}).get("default_version", "v1.0.0-stub")
    uptime = round(time.time() - APP_START_TIME, 2)
    now_iso = datetime.now(timezone.utc).isoformat()

    return HealthResponse(
        status="healthy",
        version=settings.VERSION,
        model_version=model_version,
        database_status=db_status,
        is_mock_database=is_mock_database(),
        uptime_seconds=uptime,
        timestamp=now_iso,
    )


@app.get("/v1/model", tags=["Model"])
async def get_model_info():
    model_cfg = settings.model_config_data.get("model", {})
    return {
        "model_version": model_cfg.get("default_version", "v1.0.0-stub"),
        "predictor_type": triage_service.predictor.predictor_type,
        "confidence_threshold": settings.product_confidence_threshold,
        "issue_confidence_threshold": settings.issue_confidence_threshold,
        "strict_mode": settings.thresholds.get("strict_mode", True),
        "target_latency_ms": model_cfg.get("target_latency_ms", 25.0),
        "supported_products_count": len(settings.routing.get("teams", [])),
    }


# Core Triage Endpoint
@app.post("/v1/triage", response_model=TriageResponse, tags=["Triage"])
async def triage_complaint(request_body: TriageRequest, request: Request):
    try:
        req_id = getattr(request.state, "request_id", None)
        response = await triage_service.triage(request_body, custom_request_id=req_id)
        return response
    except Exception as e:
        logger.error(f"Error during triage execution: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Triage pipeline failure: {str(e)}")


# Human Review & Feedback Endpoints
@app.post("/v1/feedback", response_model=FeedbackResponse, tags=["Feedback"])
async def submit_feedback(feedback: FeedbackRequest):
    try:
        return await feedback_service.submit_feedback(feedback)
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/requests/{request_id}/review", response_model=HumanReviewResponse, tags=["Human Review"])
async def submit_review(request_id: str, review_body: HumanReviewRequest):
    try:
        return await feedback_service.submit_review(request_id, review_body)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing human review for {request_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Request Queries & Queues
@app.get("/v1/requests", response_model=RequestListResponse, tags=["Requests"])
async def list_requests(
    team: Optional[str] = Query(None, description="Filter by assigned team"),
    priority: Optional[str] = Query(None, description="Filter by priority (CRITICAL, HIGH, MEDIUM, LOW)"),
    review_status: Optional[str] = Query(None, description="Filter by review status"),
    gate_decision: Optional[str] = Query(None, description="Filter by gate decision"),
    q: Optional[str] = Query(None, description="Search query string"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    return await request_service.list_requests(
        team=team,
        priority=priority,
        review_status=review_status,
        gate_decision=gate_decision,
        search_query=q,
        page=page,
        size=size,
    )


@app.get("/v1/requests/{request_id}", response_model=RequestDetailResponse, tags=["Requests"])
async def get_request(request_id: str):
    res = await request_service.get_request_by_id(request_id)
    if not res:
        raise HTTPException(status_code=404, detail=f"Request '{request_id}' not found.")
    return res


@app.get("/v1/requests/{request_id}/history", tags=["Requests"])
async def get_request_history(request_id: str):
    res = await request_service.get_request_by_id(request_id)
    if not res:
        raise HTTPException(status_code=404, detail=f"Request '{request_id}' not found.")
    return {
        "request_id": request_id,
        "timeline": res.timeline,
        "review_status": res.review_status,
        "reviewed_at": res.reviewed_at,
        "reviewer_id": res.reviewer_id,
    }


@app.get("/v1/queues/human-review", response_model=RequestListResponse, tags=["Queues"])
async def get_human_review_queue(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)):
    """Fetch pending complaints waiting in the Human Review Queue."""
    return await request_service.list_requests(
        review_status="PENDING",
        page=page,
        size=size,
    )


@app.get("/v1/queues/{team_name}", response_model=RequestListResponse, tags=["Queues"])
async def get_team_queue(team_name: str, page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)):
    """Fetch complaints assigned to a specific internal team."""
    return await request_service.list_requests(
        team=team_name,
        page=page,
        size=size,
    )


# Operational Analytics Endpoints
@app.get("/v1/analytics/overview", response_model=AnalyticsOverviewResponse, tags=["Analytics"])
async def get_analytics_overview():
    return await request_service.get_analytics_overview()


@app.get("/v1/analytics/routing", tags=["Analytics"])
async def get_routing_analytics():
    overview = await request_service.get_analytics_overview()
    return {
        "team_queues": overview.team_queues,
        "total_requests": overview.total_requests,
        "automated_count": overview.automated_count,
        "human_review_count": overview.human_review_count,
    }


@app.get("/v1/analytics/priority", tags=["Analytics"])
async def get_priority_analytics():
    overview = await request_service.get_analytics_overview()
    return {
        "priority_breakdown": overview.priority_breakdown,
        "total_requests": overview.total_requests,
    }
