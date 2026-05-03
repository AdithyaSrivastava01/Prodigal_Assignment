from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from payment_agent.api_client import PaymentAPIClient


class TestLookupAccount:
    def test_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "account_id": "ACC1001",
            "full_name": "Nithin Jain",
            "dob": "1990-05-14",
            "aadhaar_last4": "4321",
            "pincode": "400001",
            "balance": 1250.75,
        }
        with patch.object(httpx.Client, "post", return_value=mock_resp):
            client = PaymentAPIClient()
            account, error = client.lookup_account("ACC1001")
            assert account is not None
            assert account.full_name == "Nithin Jain"
            assert account.balance == 1250.75
            assert error is None

    def test_not_found(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.json.return_value = {
            "error_code": "account_not_found",
            "message": "No account found with the provided account_id.",
        }
        with patch.object(httpx.Client, "post", return_value=mock_resp):
            client = PaymentAPIClient()
            account, error = client.lookup_account("ACC9999")
            assert account is None
            assert error is not None
            assert "account" in error.lower()

    def test_server_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        with patch.object(httpx.Client, "post", return_value=mock_resp):
            client = PaymentAPIClient()
            account, error = client.lookup_account("ACC1001")
            assert account is None
            assert "500" in error

    def test_network_error(self):
        with patch.object(
            httpx.Client, "post", side_effect=httpx.ConnectError("connection refused")
        ):
            client = PaymentAPIClient()
            account, error = client.lookup_account("ACC1001")
            assert account is None
            assert "server" in error.lower()


class TestProcessPayment:
    def test_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "success": True,
            "transaction_id": "txn_abc123",
        }
        with patch.object(httpx.Client, "post", return_value=mock_resp):
            client = PaymentAPIClient()
            success, txn_id, err = client.process_payment("ACC1001", 500.0, {})
            assert success is True
            assert txn_id == "txn_abc123"
            assert err is None

    def test_validation_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 422
        mock_resp.json.return_value = {
            "success": False,
            "error_code": "invalid_card",
        }
        with patch.object(httpx.Client, "post", return_value=mock_resp):
            client = PaymentAPIClient()
            success, txn_id, err = client.process_payment("ACC1001", 500.0, {})
            assert success is False
            assert txn_id is None
            assert err == "invalid_card"

    def test_network_error(self):
        with patch.object(
            httpx.Client, "post", side_effect=httpx.ConnectError("timeout")
        ):
            client = PaymentAPIClient()
            success, txn_id, err = client.process_payment("ACC1001", 500.0, {})
            assert success is False
            assert err == "network_error"
