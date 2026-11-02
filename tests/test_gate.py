"""Unit tests for ConfidenceGate component."""

import math
import pytest
from complaintiq.serving.gate import ConfidenceGate
from complaintiq.serving.schemas import GateDecisionEnum


def test_confidence_gate_exact_threshold():
    gate = ConfidenceGate(product_threshold=0.85, strict_mode=False)
    decision, reason = gate.evaluate(product_confidence=0.85)
    assert decision == GateDecisionEnum.ALLOW_ROUTING
    assert reason is None


def test_confidence_gate_above_threshold():
    gate = ConfidenceGate(product_threshold=0.85, strict_mode=False)
    decision, reason = gate.evaluate(product_confidence=0.94)
    assert decision == GateDecisionEnum.ALLOW_ROUTING
    assert reason is None


def test_confidence_gate_below_threshold():
    gate = ConfidenceGate(product_threshold=0.85, strict_mode=False)
    decision, reason = gate.evaluate(product_confidence=0.84)
    assert decision == GateDecisionEnum.HUMAN_REVIEW
    assert "below required threshold" in reason
    assert "0.84" in reason


def test_confidence_gate_far_below_threshold():
    gate = ConfidenceGate(product_threshold=0.85, strict_mode=False)
    decision, reason = gate.evaluate(product_confidence=0.42)
    assert decision == GateDecisionEnum.HUMAN_REVIEW
    assert "Sent to Human Review Queue" in reason


def test_confidence_gate_nan_handling():
    gate = ConfidenceGate(product_threshold=0.85)
    decision, reason = gate.evaluate(product_confidence=float("nan"))
    assert decision == GateDecisionEnum.HUMAN_REVIEW
    assert "NaN or Infinite" in reason


def test_confidence_gate_inf_handling():
    gate = ConfidenceGate(product_threshold=0.85)
    decision, reason = gate.evaluate(product_confidence=float("inf"))
    assert decision == GateDecisionEnum.HUMAN_REVIEW
    assert "NaN or Infinite" in reason


def test_confidence_gate_none_handling():
    gate = ConfidenceGate(product_threshold=0.85)
    decision, reason = gate.evaluate(product_confidence=None)  # type: ignore
    assert decision == GateDecisionEnum.HUMAN_REVIEW
    assert "missing" in reason


def test_confidence_gate_out_of_bounds():
    gate = ConfidenceGate(product_threshold=0.85)
    decision_neg, reason_neg = gate.evaluate(product_confidence=-0.1)
    assert decision_neg == GateDecisionEnum.HUMAN_REVIEW
    assert "outside [0.0, 1.0]" in reason_neg

    decision_high, reason_high = gate.evaluate(product_confidence=1.2)
    assert decision_high == GateDecisionEnum.HUMAN_REVIEW
    assert "outside [0.0, 1.0]" in reason_high


def test_confidence_gate_secondary_issue_strict_mode():
    gate = ConfidenceGate(product_threshold=0.85, issue_threshold=0.70, strict_mode=True)
    # Product passes (0.90 >= 0.85), but issue fails (0.65 < 0.70)
    decision, reason = gate.evaluate(product_confidence=0.90, issue_confidence=0.65)
    assert decision == GateDecisionEnum.HUMAN_REVIEW
    assert "Issue confidence (0.65) is below secondary threshold (0.70)" in reason

    # Both pass
    decision_ok, reason_ok = gate.evaluate(product_confidence=0.90, issue_confidence=0.75)
    assert decision_ok == GateDecisionEnum.ALLOW_ROUTING
    assert reason_ok is None
