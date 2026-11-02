"""Unit tests for PriorityAssessmentService."""

import pytest
from complaintiq.serving.schemas import PriorityEnum
from complaintiq.serving.services.priority_service import PriorityAssessmentService


@pytest.fixture
def priority_service():
    return PriorityAssessmentService()


def test_priority_critical_foreclosure(priority_service):
    priority, reason = priority_service.assess_priority(
        "The mortgage servicer filed foreclosure papers and scheduled an auction for my house next week."
    )
    assert priority == PriorityEnum.CRITICAL
    assert "foreclosure" in reason.lower()


def test_priority_critical_bankruptcy(priority_service):
    priority, reason = priority_service.assess_priority(
        "I filed for Chapter 7 bankruptcy and creditors are continuing to violate the automatic stay."
    )
    assert priority == PriorityEnum.CRITICAL
    assert "bankruptcy" in reason.lower()


def test_priority_critical_lawsuit(priority_service):
    priority, reason = priority_service.assess_priority(
        "I received a court date and lawsuit from an aggressive collection agency."
    )
    assert priority == PriorityEnum.CRITICAL
    assert "legal action" in reason.lower()


def test_priority_high_unauthorized_transaction(priority_service):
    priority, reason = priority_service.assess_priority(
        "There was an unauthorized transaction on my bank account for several hundred dollars."
    )
    assert priority == PriorityEnum.HIGH
    assert "unauthorized" in reason.lower()


def test_priority_high_debt_harassment(priority_service):
    priority, reason = priority_service.assess_priority(
        "The collectors are calling at work and threatening my employer daily."
    )
    assert priority == PriorityEnum.HIGH
    assert "harassment" in reason.lower()


def test_priority_high_large_disputed_amount(priority_service):
    priority, reason = priority_service.assess_priority(
        "The wire transfer error involved $9,500 that never reached the recipient."
    )
    assert priority == PriorityEnum.HIGH
    assert "$5,000" in reason


def test_priority_medium_billing_dispute(priority_service):
    priority, reason = priority_service.assess_priority(
        "There is a $35 overdraft fee and incorrect fee on my recent account statement."
    )
    assert priority == PriorityEnum.MEDIUM
    assert "fee" in reason.lower() or "dispute" in reason.lower()


def test_priority_low_routine_inquiry(priority_service):
    priority, reason = priority_service.assess_priority(
        "I would like to inquire about the terms and general policies regarding savings accounts."
    )
    assert priority == PriorityEnum.LOW
    assert "routine" in reason.lower()
