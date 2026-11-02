"""Unit tests for PII Redactor."""

import pytest
from complaintiq.privacy.redactor import PIIRedactor


@pytest.fixture
def redactor():
    return PIIRedactor()


def test_redact_ssn(redactor):
    text = "My Social Security number is 123-45-6789 and you are collecting incorrectly."
    result = redactor.redact(text)
    assert "[REDACTED_SSN]" in result.redacted_text
    assert "123-45-6789" not in result.redacted_text
    assert any(e.entity_type == "SSN" for e in result.entities_found)


def test_redact_email(redactor):
    text = "Please reach out to victim.user@financialservice.org to verify payment."
    result = redactor.redact(text)
    assert "[REDACTED_EMAIL]" in result.redacted_text
    assert "victim.user@financialservice.org" not in result.redacted_text
    assert any(e.entity_type == "EMAIL" for e in result.entities_found)


def test_redact_phone_number(redactor):
    text = "They called me repeatedly at (800) 555-1212 and 555-987-6543."
    result = redactor.redact(text)
    assert "[REDACTED_PHONE]" in result.redacted_text
    assert "800" not in result.redacted_text
    assert any(e.entity_type == "PHONE" for e in result.entities_found)


def test_redact_credit_card(redactor):
    text = "My credit card ending with 4532-1111-2222-3333 had an unauthorized charge."
    result = redactor.redact(text)
    assert "[REDACTED_CARD]" in result.redacted_text
    assert "4532-1111-2222-3333" not in result.redacted_text


def test_no_pii_present(redactor):
    clean_text = "I am requesting an explanation of the late fee assessed on my account."
    result = redactor.redact(clean_text)
    assert result.redacted_text == clean_text
    assert len(result.entities_found) == 0
