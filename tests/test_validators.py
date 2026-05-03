from __future__ import annotations

from datetime import date

import pytest

from payment_agent.validators import (
    luhn_check,
    validate_amount,
    validate_card_number,
    validate_cvv,
    validate_date_format,
    validate_expiry,
)


class TestLuhnCheck:
    def test_valid_visa(self):
        assert luhn_check("4532015112830366") is True

    def test_valid_test_card(self):
        assert luhn_check("4111111111111111") is True

    def test_invalid_card(self):
        assert luhn_check("4532015112830367") is False

    def test_single_zero(self):
        assert luhn_check("0") is True

    def test_invalid_single_digit(self):
        assert luhn_check("1") is False


class TestValidateCardNumber:
    def test_valid_number(self):
        valid, result = validate_card_number("4532015112830366")
        assert valid is True
        assert result == "4532015112830366"

    def test_valid_with_spaces(self):
        valid, result = validate_card_number("4532 0151 1283 0366")
        assert valid is True
        assert result == "4532015112830366"

    def test_valid_with_dashes(self):
        valid, result = validate_card_number("4532-0151-1283-0366")
        assert valid is True
        assert result == "4532015112830366"

    def test_too_short(self):
        valid, msg = validate_card_number("123456789012")
        assert valid is False
        assert "13" in msg

    def test_too_long(self):
        valid, msg = validate_card_number("12345678901234567890")
        assert valid is False

    def test_non_digits(self):
        valid, msg = validate_card_number("4532abcd11283036")
        assert valid is False
        assert "digits" in msg.lower()

    def test_luhn_failure(self):
        valid, msg = validate_card_number("4532015112830367")
        assert valid is False
        assert "invalid" in msg.lower()


class TestValidateCVV:
    def test_valid_3_digits(self):
        valid, _ = validate_cvv("123")
        assert valid is True

    def test_valid_4_digits_amex(self):
        valid, _ = validate_cvv("1234", "3456789012345")
        assert valid is True

    def test_wrong_length_standard(self):
        valid, msg = validate_cvv("1234", "4111111111111111")
        assert valid is False
        assert "3 digits" in msg

    def test_wrong_length_amex(self):
        valid, msg = validate_cvv("123", "3456789012345")
        assert valid is False
        assert "4 digits" in msg

    def test_non_digits(self):
        valid, msg = validate_cvv("abc")
        assert valid is False

    def test_leading_zeros(self):
        valid, _ = validate_cvv("007")
        assert valid is True


class TestValidateExpiry:
    def test_future_date(self):
        valid, _ = validate_expiry(12, 2030)
        assert valid is True

    def test_past_date(self):
        valid, msg = validate_expiry(1, 2020)
        assert valid is False
        assert "expired" in msg.lower()

    def test_invalid_month_zero(self):
        valid, msg = validate_expiry(0, 2030)
        assert valid is False

    def test_invalid_month_13(self):
        valid, msg = validate_expiry(13, 2030)
        assert valid is False

    def test_current_month(self):
        today = date.today()
        valid, _ = validate_expiry(today.month, today.year)
        assert valid is True


class TestValidateDateFormat:
    def test_valid_date(self):
        valid, result = validate_date_format("1990-05-14")
        assert valid is True
        assert result == "1990-05-14"

    def test_leap_year_valid(self):
        valid, result = validate_date_format("1988-02-29")
        assert valid is True
        assert result == "1988-02-29"

    def test_leap_year_invalid(self):
        valid, msg = validate_date_format("1990-02-29")
        assert valid is False

    def test_wrong_format(self):
        valid, msg = validate_date_format("14-05-1990")
        assert valid is False
        assert "YYYY-MM-DD" in msg

    def test_invalid_month(self):
        valid, msg = validate_date_format("1990-13-01")
        assert valid is False

    def test_garbage(self):
        valid, msg = validate_date_format("not-a-date")
        assert valid is False


class TestValidateAmount:
    def test_valid_amount(self):
        valid, _ = validate_amount(500.0, 1250.75)
        assert valid is True

    def test_exact_balance(self):
        valid, _ = validate_amount(1250.75, 1250.75)
        assert valid is True

    def test_zero(self):
        valid, msg = validate_amount(0, 1250.75)
        assert valid is False
        assert "greater than zero" in msg.lower()

    def test_negative(self):
        valid, _ = validate_amount(-100, 1250.75)
        assert valid is False

    def test_exceeds_balance(self):
        valid, msg = validate_amount(2000.0, 1250.75)
        assert valid is False
        assert "exceeds" in msg.lower()

    def test_too_many_decimals(self):
        valid, msg = validate_amount(500.123, 1250.75)
        assert valid is False
        assert "decimal" in msg.lower()

    def test_two_decimals_ok(self):
        valid, _ = validate_amount(500.12, 1250.75)
        assert valid is True

    def test_small_amount(self):
        valid, _ = validate_amount(0.01, 1250.75)
        assert valid is True
