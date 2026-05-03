from __future__ import annotations

import re
from datetime import date


def luhn_check(card_number: str) -> bool:
    """Validate card number using the Luhn algorithm."""
    digits = [int(d) for d in card_number]
    digits.reverse()
    total = 0
    for i, d in enumerate(digits):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def validate_card_number(raw: str) -> tuple[bool, str]:
    """Returns (is_valid, cleaned_number_or_error_message)."""
    cleaned = re.sub(r"[\s\-]", "", raw)
    if not cleaned.isdigit():
        return False, "Card number must contain only digits."
    if len(cleaned) < 13 or len(cleaned) > 19:
        return False, "Card number must be between 13 and 19 digits."
    if not luhn_check(cleaned):
        return False, "Card number is invalid."
    return True, cleaned


def validate_cvv(cvv: str, card_number: str = "") -> tuple[bool, str]:
    """Returns (is_valid, cvv_or_error_message)."""
    if not cvv.isdigit():
        return False, "CVV must contain only digits."
    is_amex = card_number.startswith(("34", "37"))
    expected = 4 if is_amex else 3
    if len(cvv) != expected:
        return False, f"CVV must be {expected} digits."
    return True, cvv


def validate_expiry(month: int, year: int) -> tuple[bool, str]:
    """Returns (is_valid, error_message)."""
    if month < 1 or month > 12:
        return False, "Expiry month must be between 1 and 12."
    today = date.today()
    if year < today.year or (year == today.year and month < today.month):
        return False, "Card has expired."
    return True, ""


def validate_date_format(date_str: str) -> tuple[bool, str]:
    """Validate YYYY-MM-DD date string including leap year handling."""
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", date_str)
    if not match:
        return False, "Date must be in YYYY-MM-DD format."
    try:
        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
        date(year, month, day)
        return True, date_str
    except ValueError:
        return False, "Invalid date."


def validate_amount(amount: float, balance: float) -> tuple[bool, str]:
    """Returns (is_valid, error_message)."""
    if amount <= 0:
        return False, "Amount must be greater than zero."
    rounded = round(amount, 2)
    if abs(rounded - amount) > 1e-9:
        return False, "Amount can have at most 2 decimal places."
    if amount > balance:
        return (
            False,
            f"Amount \u20b9{amount:.2f} exceeds the outstanding balance of \u20b9{balance:.2f}.",
        )
    return True, ""
