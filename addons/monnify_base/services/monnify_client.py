"""Monnify API client.

Pure Python with no Odoo imports, so it can also be driven from a standalone
script (see scripts/smoke_test.py).

Endpoint paths and response shapes are documented in
docs/monnify-api-reference.md. A single POST /api/v1/invoice/create both
creates the transaction and returns the dynamic virtual account, so no
separate "pay with bank transfer" call is needed.
"""

import base64
import hashlib
import hmac
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

# Monnify interprets expiryDate as a Nigerian wall-clock time (West Africa
# Time, UTC+1). Compute it in that zone explicitly rather than from a naive
# datetime.now(): Odoo forces its process timezone to UTC, so a naive "now"
# is an hour behind real WAT and Monnify rejects the apparently-past date
# with "Invalid invoice expiry date" (confirmed live, 2026-07-16). Doing it
# here means no caller can reintroduce that timezone bug.
_MONNIFY_TZ = ZoneInfo("Africa/Lagos")
INVOICE_TTL_MINUTES = 40


class MonnifyError(Exception):
    def __init__(self, message, response_code=None, response_body=None):
        super().__init__(message)
        self.response_code = response_code
        self.response_body = response_body


class MonnifyClient:
    def __init__(self, api_key, secret_key, contract_code, base_url):
        self.api_key = api_key
        self.secret_key = secret_key
        self.contract_code = contract_code
        self.base_url = base_url.rstrip("/")
        self._token = None
        self._token_expires_at = 0

    def _get_token(self):
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token

        url = f"{self.base_url}/api/v1/auth/login"
        credentials = base64.b64encode(
            f"{self.api_key}:{self.secret_key}".encode()
        ).decode()
        headers = {"Authorization": f"Basic {credentials}"}
        resp = requests.post(url, headers=headers, timeout=(10, 30))
        data = resp.json()
        self._raise_if_failed(data)

        self._token = data["responseBody"]["accessToken"]
        self._token_expires_at = time.time() + data["responseBody"]["expiresIn"]
        return self._token

    def create_invoice(self, invoice_reference, amount, customer_name,
                        customer_email, description):
        """Create a one-time dynamic virtual account for ``amount``.

        The ``expiryDate`` is generated here (now + INVOICE_TTL_MINUTES, in
        Nigerian time) so callers can never get the timezone/format wrong —
        see the _MONNIFY_TZ note at the top of this module. Returns the raw
        ``responseBody`` dict (accountNumber, bankName, accountName,
        transactionReference, etc.)."""
        expiry_date = (
            datetime.now(_MONNIFY_TZ) + timedelta(minutes=INVOICE_TTL_MINUTES)
        ).strftime("%Y-%m-%d %H:%M:%S")
        url = f"{self.base_url}/api/v1/invoice/create"
        headers = {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
        }
        payload = {
            "invoiceReference": invoice_reference,
            "amount": amount,
            "invoiceDescription": description,
            "contractCode": self.contract_code,
            "customerEmail": customer_email,
            "customerName": customer_name,
            "expiryDate": expiry_date,
            "currencyCode": "NGN",
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=(10, 30))
        data = resp.json()
        self._raise_if_failed(data)
        return data["responseBody"]

    def get_transaction_status(self, transaction_reference):
        """Returns the raw ``responseBody`` dict. Note: ``amountPaid`` and
        ``totalPayable`` come back as STRINGS (e.g. "0.00"), confirmed
        against a real sandbox call — convert before comparing numerically.
        """
        url = f"{self.base_url}/api/v2/merchant/transactions/query"
        headers = {"Authorization": f"Bearer {self._get_token()}"}
        resp = requests.get(
            url, headers=headers,
            params={"transactionReference": transaction_reference},
            timeout=(10, 30),
        )
        data = resp.json()
        self._raise_if_failed(data)
        return data["responseBody"]

    @staticmethod
    def compute_transaction_hash(raw_body: bytes, secret_key: str) -> str:
        # SHA-512 HMAC keyed with the merchant secret, over the raw request
        # body bytes exactly as received. Re-serializing the parsed JSON would
        # change key order and spacing, which breaks the comparison.
        return hmac.new(secret_key.encode(), raw_body, hashlib.sha512).hexdigest()

    def verify_webhook(self, raw_body: bytes, received_hash: str) -> bool:
        expected = self.compute_transaction_hash(raw_body, self.secret_key)
        return hmac.compare_digest(expected, received_hash)

    @staticmethod
    def _raise_if_failed(data):
        if not data.get("requestSuccessful"):
            raise MonnifyError(
                data.get("responseMessage", "Unknown Monnify error"),
                response_code=data.get("responseCode"),
                response_body=data,
            )
