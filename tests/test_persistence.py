"""Integration tests for MongoDB persistence and Human Review Service."""

import pytest
from complaintiq.serving.repositories.feedback_repository import FeedbackRepository
from complaintiq.serving.repositories.request_repository import RequestRepository
from complaintiq.serving.schemas import (
    FeedbackRequest,
    HumanReviewRequest,
    ReviewStatusEnum,
    TriageRequest,
)
from complaintiq.serving.services.feedback_service import FeedbackService
from complaintiq.serving.services.triage_service import TriageService


@pytest.mark.asyncio
async def test_triage_pipeline_persistence():
    service = TriageService()
    req = TriageRequest(
        text="I have a dispute regarding excessive overdraft fees on my checking account at Main Bank.",
        client_id="client_test_01",
    )
    res = await service.triage(req)

    assert res.request_id.startswith("req_")
    assert res.predicted_product == "Checking or savings account"
    assert res.assigned_team == "Bank Accounts Team"

    # Verify document in repository
    repo = RequestRepository()
    saved = await repo.get_by_request_id(res.request_id)
    assert saved is not None
    assert saved["request_id"] == res.request_id
    assert saved["predicted_product"] == "Checking or savings account"
    assert len(saved["timeline"]) >= 5


@pytest.mark.asyncio
async def test_human_review_correction_workflow():
    service = TriageService()
    feedback_service = FeedbackService()

    # Generate a complaint that triggers low confidence (e.g. uncertain text)
    req = TriageRequest(
        text="I am writing about an ambiguous financial issue that is completely uncertain and confusing to me.",
    )
    triage_res = await service.triage(req)
    assert triage_res.assigned_team == "Human Review Queue"
    assert triage_res.review_status == ReviewStatusEnum.PENDING

    # Specialist submits human correction: corrected to Mortgage
    review_req = HumanReviewRequest(
        action="CORRECT",
        corrected_product="Mortgage",
        corrected_issue="Trouble during payment process",
        correction_reason="Operator verified from loan contract that this relates to home mortgage escrow.",
        reviewer_id="specialist_jane_doe",
    )
    review_res = await feedback_service.submit_review(triage_res.request_id, review_req)

    assert review_res.review_status == ReviewStatusEnum.CORRECTED
    assert review_res.updated_product == "Mortgage"
    assert review_res.updated_assigned_team == "Mortgage Team"

    # Verify MongoDB state after correction
    repo = RequestRepository()
    doc = await repo.get_by_request_id(triage_res.request_id)
    assert doc["predicted_product"] == "Mortgage"
    assert doc["assigned_team"] == "Mortgage Team"
    assert doc["review_status"] == "CORRECTED"
    assert doc["reviewer_id"] == "specialist_jane_doe"
    assert any(t["stage"] == "HUMAN_CORRECTION" for t in doc["timeline"])


@pytest.mark.asyncio
async def test_human_review_confirmation_workflow():
    service = TriageService()
    feedback_service = FeedbackService()

    # Trigger low confidence
    req = TriageRequest(
        text="An ambiguous financial issue with uncertain calculations.",
    )
    triage_res = await service.triage(req)

    # Specialist confirms the model's prediction
    confirm_req = HumanReviewRequest(
        action="CONFIRM",
        correction_reason="Prediction confirmed accurate by specialist inspection.",
        reviewer_id="specialist_john",
    )
    confirm_res = await feedback_service.submit_review(triage_res.request_id, confirm_req)

    assert confirm_res.review_status == ReviewStatusEnum.CONFIRMED
    # Team re-routed out of Human Review Queue to the actual product team
    assert confirm_res.updated_assigned_team != "Human Review Queue"


@pytest.mark.asyncio
async def test_user_feedback_submission():
    service = TriageService()
    feedback_service = FeedbackService()
    fb_repo = FeedbackRepository()

    triage_res = await service.triage(
        TriageRequest(text="Disputing a collection notice for medical debt of $650.")
    )

    fb_req = FeedbackRequest(
        request_id=triage_res.request_id,
        rating=5,
        is_accurate=True,
        comments="Accurately routed to debt collection team.",
        user_id="operator_02",
    )
    fb_res = await feedback_service.submit_feedback(fb_req)

    assert fb_res.feedback_id.startswith("fb_")
    assert fb_res.rating == 5

    stored_fb = await fb_repo.get_by_request_id(triage_res.request_id)
    assert len(stored_fb) == 1
    assert stored_fb[0]["rating"] == 5
