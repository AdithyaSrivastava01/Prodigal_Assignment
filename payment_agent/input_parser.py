from __future__ import annotations

import re


class InputParser:
    """Regex-based extraction of structured data from free-text user input."""

    _ACCOUNT_ID_RE = re.compile(r"\b(ACC\d+)\b", re.IGNORECASE)
    _DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
    _NAME_PREFIX_RE = re.compile(
        r"(?:my\s+name\s+is|i'?m|i\s+am|this\s+is|name\s*:\s*)\s*(.+)",
        re.IGNORECASE,
    )

    def extract_account_id(self, text: str) -> str | None:
        """Extract ACC-prefixed account ID from text."""
        match = self._ACCOUNT_ID_RE.search(text)
        return match.group(1).upper() if match else None

    def extract_name_from_context(self, text: str) -> str:
        """Extract name when explicitly asked for it. Strips common prefixes."""
        match = self._NAME_PREFIX_RE.search(text)
        if match:
            name = match.group(1).strip()
        else:
            name = text.strip()
        return " ".join(name.split())

    def extract_name_from_any(self, text: str) -> str | None:
        """Try to extract name from any message using prefix patterns only."""
        match = self._NAME_PREFIX_RE.search(text)
        if match:
            name = match.group(1).strip()
            return " ".join(name.split())
        return None

    def extract_secondary_factors(self, text: str) -> dict[str, str]:
        """Extract all recognizable secondary verification factors from text.

        Returns dict with keys: 'dob', 'aadhaar_last4', 'pincode' (whichever found).
        Extraction order: DOB first, then pincode (6 digits), then aadhaar (4 digits).
        """
        factors: dict[str, str] = {}
        remaining = text

        date_match = self._DATE_RE.search(text)
        if date_match:
            factors["dob"] = date_match.group(1)
            remaining = remaining.replace(date_match.group(0), " ")

        pincode_match = re.search(r"\b(\d{6})\b", remaining)
        if pincode_match:
            factors["pincode"] = pincode_match.group(1)
            remaining = remaining.replace(pincode_match.group(0), " ")

        aadhaar_match = re.search(r"\b(\d{4})\b", remaining)
        if aadhaar_match:
            factors["aadhaar_last4"] = aadhaar_match.group(1)

        return factors

    def extract_amount(self, text: str, balance: float | None = None) -> float | None:
        """Extract payment amount. Recognizes 'full'/'all' as full balance."""
        if re.search(r"\b(full|all|entire|complete|total)\b", text, re.IGNORECASE):
            return balance

        match = re.search(
            r"(?:\u20b9|rs\.?|inr|rupees?)\s*(\d+(?:\.\d+)?)",
            text,
            re.IGNORECASE,
        )
        if match:
            return float(match.group(1))

        match = re.search(r"\b(\d+(?:\.\d+)?)\b", text)
        if match:
            return float(match.group(1))

        return None

    def extract_card_details(self, text: str) -> dict[str, str | int]:
        """Extract card details from text. Returns dict with found fields."""
        details: dict[str, str | int] = {}
        remaining = text

        card_match = re.search(
            r"\b(\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{1,7})\b", text
        )
        if card_match:
            details["card_number"] = re.sub(r"[\s\-]", "", card_match.group(1))
            remaining = remaining.replace(card_match.group(0), " ")

        expiry_match = re.search(r"\b(\d{1,2})\s*/\s*(\d{2,4})\b", remaining)
        if expiry_match:
            month = int(expiry_match.group(1))
            year = int(expiry_match.group(2))
            if year < 100:
                year += 2000
            details["expiry_month"] = month
            details["expiry_year"] = year
            remaining = remaining.replace(expiry_match.group(0), " ")

        cvv_labeled = re.search(
            r"(?:cvv|cvc|security\s*code)\s*[:\s]\s*(\d{3,4})\b",
            remaining,
            re.IGNORECASE,
        )
        if cvv_labeled:
            details["cvv"] = cvv_labeled.group(1)
            remaining = remaining.replace(cvv_labeled.group(0), " ")
        else:
            cvv_standalone = re.search(r"\b(\d{3,4})\b", remaining)
            if cvv_standalone:
                details["cvv"] = cvv_standalone.group(1)
                remaining = remaining.replace(cvv_standalone.group(0), " ")

        name_labeled = re.search(
            r"(?:name|cardholder)\s*[:\-]?\s*([^\d,\n:]+)",
            remaining,
            re.IGNORECASE,
        )
        if name_labeled:
            name = name_labeled.group(1).strip()
            name = re.sub(
                r"\s+(?:card|cvv|cvc|expiry|number|security|code)\s*$",
                "",
                name,
                flags=re.IGNORECASE,
            )
            name = name.strip()
            if name and len(name) > 1:
                details["cardholder_name"] = name
        else:
            words = re.findall(r"\b[A-Za-z]{2,}\b", remaining)
            skip = {
                "card",
                "number",
                "cvv",
                "cvc",
                "expiry",
                "name",
                "cardholder",
                "security",
                "code",
                "my",
                "is",
                "the",
                "please",
                "pay",
                "with",
                "using",
                "details",
                "and",
                "or",
            }
            name_words = [w for w in words if w.lower() not in skip]
            if len(name_words) >= 2:
                details["cardholder_name"] = " ".join(name_words)

        return details

    def is_decline(self, text: str) -> bool:
        """Check if user is declining/cancelling."""
        return bool(
            re.search(
                r"\b(no|cancel|exit|quit|stop|decline|nevermind|never\s*mind)\b",
                text,
                re.IGNORECASE,
            )
        )

    def is_affirmative(self, text: str) -> bool:
        """Check if user is confirming/agreeing."""
        return bool(
            re.search(
                r"\b(yes|yeah|yep|sure|ok|okay|proceed|go\s*ahead|pay|confirm)\b",
                text,
                re.IGNORECASE,
            )
        )
