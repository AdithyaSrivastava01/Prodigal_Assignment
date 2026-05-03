from __future__ import annotations

from abc import ABC, abstractmethod

import httpx

from payment_agent.config import API_BASE_URL, REQUEST_TIMEOUT_SECONDS
from payment_agent.models import AccountData


class PaymentAPIClientBase(ABC):
    """Abstract interface for the payment API. Enables dependency injection for testing."""

    @abstractmethod
    def lookup_account(self, account_id: str) -> tuple[AccountData | None, str | None]:
        """Fetch account by ID. Returns (account_data, None) or (None, error_message)."""
        ...

    @abstractmethod
    def process_payment(
        self, account_id: str, amount: float, card: dict
    ) -> tuple[bool, str | None, str | None]:
        """Process card payment. Returns (success, transaction_id, error_code)."""
        ...


class PaymentAPIClient(PaymentAPIClientBase):
    """httpx-based implementation targeting the Prodigal payment API."""

    def __init__(self, base_url: str = API_BASE_URL) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS)

    def lookup_account(self, account_id: str) -> tuple[AccountData | None, str | None]:
        try:
            resp = self._client.post(
                f"{self._base_url}/api/lookup-account",
                json={"account_id": account_id},
            )
            if resp.status_code == 200:
                return AccountData(**resp.json()), None
            if resp.status_code == 404:
                data = resp.json()
                return None, data.get("message", "Account not found.")
            return None, f"Unexpected error (HTTP {resp.status_code})."
        except httpx.RequestError:
            return None, "Unable to reach the server. Please try again later."

    def process_payment(
        self, account_id: str, amount: float, card: dict
    ) -> tuple[bool, str | None, str | None]:
        payload = {
            "account_id": account_id,
            "amount": amount,
            "payment_method": {"type": "card", "card": card},
        }
        try:
            resp = self._client.post(
                f"{self._base_url}/api/process-payment",
                json=payload,
            )
            data = resp.json()
            if resp.status_code == 200 and data.get("success"):
                return True, data.get("transaction_id"), None
            return False, None, data.get("error_code", "unknown_error")
        except httpx.RequestError:
            return False, None, "network_error"
