"""API Integration tests for ComplaintIQ FastAPI endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check_endpoint(async_client: AsyncClient):
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "model_version" in data
    assert "database_status" in data


@pytest.mark.asyncio
async def test_model_metadata_endpoint(async_client: AsyncClient):
    response = await async_client.get("/v1/model")
    assert response.status_code == 200
    data = response.json()
    assert "model_version" in data
    assert data["confidence_threshold"] == 0.85
    assert data["predictor_type"] in ["STUB", "BASELINE", "TRANSFORMER", "ONNX"]


@pytest.mark.asyncio
async def test_triage_endpoint_valid_complaint(async_client: AsyncClient):
    payload = {
        "text": "I am experiencing repeated harassment from debt collectors demanding payments on a disputed bill.",
        "metadata": {"source": "web_portal"},
    }
    response = await async_client.post("/v1/triage", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["request_id"].startswith("req_")
    assert data["predicted_product"] == "Debt collection"
    assert data["assigned_team"] == "Debt Collection Team"
    assert data["product_confidence"] >= 0.85
    assert data["gate_decision"] == "ALLOW_ROUTING"
    assert data["route_type"] == "AUTOMATED"
    assert response.headers.get("X-Request-ID") is not None


@pytest.mark.asyncio
async def test_triage_endpoint_validation_failure(async_client: AsyncClient):
    # Text shorter than 20 characters
    payload = {"text": "Too short"}
    response = await async_client.post("/v1/triage", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_triage_low_confidence_gate_routing(async_client: AsyncClient):
    payload = {
        "text": "I have an ambiguous financial issue with completely uncertain terms on my account.",
    }
    response = await async_client.post("/v1/triage", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["product_confidence"] < 0.85
    assert data["gate_decision"] == "HUMAN_REVIEW"
    assert data["assigned_team"] == "Human Review Queue"
    assert data["review_status"] == "PENDING"
    assert data["review_reason"] is not None


@pytest.mark.asyncio
async def test_list_requests_and_detail(async_client: AsyncClient):
    # Ingest a complaint first
    triage_res = await async_client.post(
        "/v1/triage",
        json={"text": "Credit card dispute regarding unauthorized transaction on my monthly statement."},
    )
    req_id = triage_res.json()["request_id"]

    # List requests
    list_res = await async_client.get("/v1/requests?page=1&size=10")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] >= 1
    assert any(item["request_id"] == req_id for item in list_data["items"])

    # Detail request
    detail_res = await async_client.get(f"/v1/requests/{req_id}")
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["request_id"] == req_id
    assert len(detail_data["timeline"]) >= 4

    # History endpoint
    history_res = await async_client.get(f"/v1/requests/{req_id}/history")
    assert history_res.status_code == 200
    assert history_res.json()["request_id"] == req_id


@pytest.mark.asyncio
async def test_human_review_api_workflow(async_client: AsyncClient):
    # Create gated complaint
    triage_res = await async_client.post(
        "/v1/triage",
        json={"text": "Ambiguous financial issue with low confidence and uncertain statements."},
    )
    req_id = triage_res.json()["request_id"]

    # Check pending review queue
    queue_res = await async_client.get("/v1/queues/human-review")
    assert queue_res.status_code == 200
    assert any(item["request_id"] == req_id for item in queue_res.json()["items"])

    # Submit review correction
    review_res = await async_client.post(
        f"/v1/requests/{req_id}/review",
        json={
            "action": "CORRECT",
            "corrected_product": "Credit card or prepaid card",
            "correction_reason": "Verified that this relates to prepaid gift card issue.",
            "reviewer_id": "senior_agent_42",
        },
    )
    assert review_res.status_code == 200
    review_data = review_res.json()
    assert review_data["review_status"] == "CORRECTED"
    assert review_data["updated_assigned_team"] == "Credit Card Team"


@pytest.mark.asyncio
async def test_feedback_api(async_client: AsyncClient):
    triage_res = await async_client.post(
        "/v1/triage",
        json={"text": "There are incorrect records on my credit report from the credit bureau."},
    )
    req_id = triage_res.json()["request_id"]

    fb_res = await async_client.post(
        "/v1/feedback",
        json={
            "request_id": req_id,
            "rating": 5,
            "is_accurate": True,
            "comments": "Routing to Credit Reporting Team was correct.",
            "user_id": "ops_analyst",
        },
    )
    assert fb_res.status_code == 200
    assert fb_res.json()["feedback_id"].startswith("fb_")


@pytest.mark.asyncio
async def test_analytics_endpoints(async_client: AsyncClient):
    overview_res = await async_client.get("/v1/analytics/overview")
    assert overview_res.status_code == 200
    data = overview_res.json()
    assert "total_requests" in data
    assert "automation_rate" in data
    assert "review_status_breakdown" in data

    routing_res = await async_client.get("/v1/analytics/routing")
    assert routing_res.status_code == 200

    priority_res = await async_client.get("/v1/analytics/priority")
    assert priority_res.status_code == 200
