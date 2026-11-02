"""Unit tests for B6 RoutingEngine."""

import pytest
from complaintiq.serving.router import RoutingEngine
from complaintiq.serving.schemas import GateDecisionEnum, PriorityEnum


@pytest.fixture
def router():
    return RoutingEngine()


@pytest.mark.parametrize(
    "product,expected_team,expected_rule",
    [
        ("Debt collection", "Debt Collection Team", "RULE_DEBT_COLLECTION"),
        ("Credit card or prepaid card", "Credit Card Team", "RULE_CREDIT_CARD"),
        ("Mortgage", "Mortgage Team", "RULE_MORTGAGE"),
        ("Student loan", "Student Loan Team", "RULE_STUDENT_LOAN"),
        ("Vehicle loan or lease", "Auto Loan Team", "RULE_AUTO_LOAN"),
        ("Checking or savings account", "Bank Accounts Team", "RULE_BANK_ACCOUNTS"),
        ("Money transfer, virtual currency, or money service", "Payments Team", "RULE_PAYMENTS"),
        ("Credit reporting, credit repair services, or other personal consumer reports", "Credit Reporting Team", "RULE_CREDIT_REPORTING"),
        ("Payday loan, title loan, or personal loan", "Consumer Lending Team", "RULE_CONSUMER_LENDING"),
    ],
)
def test_b6_standard_product_routing(router, product, expected_team, expected_rule):
    decision = router.route(
        predicted_product=product,
        priority=PriorityEnum.MEDIUM,
        gate_decision=GateDecisionEnum.ALLOW_ROUTING,
        complaint_text="Standard service complaint without fraud triggers.",
    )
    assert decision.destination_team == expected_team
    assert decision.rule_id == expected_rule
    assert decision.route_type == "AUTOMATED"
    assert decision.override_applied is False
    assert expected_team in decision.routing_explanation


def test_b6_case_insensitivity_and_whitespace(router):
    decision = router.route(
        predicted_product="  mOrTgAgE  ",
        priority=PriorityEnum.LOW,
        gate_decision=GateDecisionEnum.ALLOW_ROUTING,
    )
    assert decision.destination_team == "Mortgage Team"
    assert decision.rule_id == "RULE_MORTGAGE"


def test_confidence_gate_precedence(router):
    """When confidence gate triggers HUMAN_REVIEW, complaint must route to Human Review Queue."""
    decision = router.route(
        predicted_product="Debt collection",
        priority=PriorityEnum.HIGH,
        gate_decision=GateDecisionEnum.HUMAN_REVIEW,
        gate_reason="Confidence 0.65 below tau",
    )
    assert decision.destination_team == "Human Review Queue"
    assert decision.route_type == "HUMAN_REVIEW_QUEUE"
    assert decision.rule_id == "OVERRIDE_GATE_FALLBACK"
    assert decision.override_applied is True
    assert "0.65" in decision.routing_explanation


def test_fraud_and_risk_override_high_priority(router):
    """Complaints with HIGH priority and fraud keywords divert to Fraud and Risk team."""
    decision = router.route(
        predicted_product="Checking or savings account",
        priority=PriorityEnum.HIGH,
        gate_decision=GateDecisionEnum.ALLOW_ROUTING,
        complaint_text="Someone committed identity theft and made unauthorized transactions on my checking account.",
    )
    assert decision.destination_team == "Fraud and Risk"
    assert decision.route_type == "OVERRIDE_FRAUD"
    assert decision.rule_id == "OVERRIDE_FRAUD_RISK"
    assert decision.override_applied is True


def test_fraud_and_risk_override_critical_priority(router):
    decision = router.route(
        predicted_product="Credit card or prepaid card",
        priority=PriorityEnum.CRITICAL,
        gate_decision=GateDecisionEnum.ALLOW_ROUTING,
        complaint_text="My credit card was stolen in a massive scam and criminal syndicate hacked my details.",
    )
    assert decision.destination_team == "Fraud and Risk"
    assert decision.route_type == "OVERRIDE_FRAUD"
    assert decision.rule_id == "OVERRIDE_FRAUD_RISK"
    assert decision.override_applied is True


def test_low_priority_fraud_keyword_does_not_override(router):
    """If priority is LOW, fraud keyword alone should not trigger high-risk override."""
    decision = router.route(
        predicted_product="Credit card or prepaid card",
        priority=PriorityEnum.LOW,
        gate_decision=GateDecisionEnum.ALLOW_ROUTING,
        complaint_text="I read an article about fraud protection on credit cards and want to inquire.",
    )
    assert decision.destination_team == "Credit Card Team"
    assert decision.override_applied is False


def test_unknown_product_fallback(router):
    decision = router.route(
        predicted_product="Unknown Unlisted Product XYZ",
        priority=PriorityEnum.MEDIUM,
        gate_decision=GateDecisionEnum.ALLOW_ROUTING,
    )
    assert decision.destination_team == "General Financial Support"
    assert decision.rule_id == "RULE_DEFAULT_FALLBACK"
