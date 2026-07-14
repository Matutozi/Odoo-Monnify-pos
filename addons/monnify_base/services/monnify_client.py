"""Monnify API client. Pure Python, no Odoo imports (so it can be exercised
from a standalone script the same way ``auth.py`` was for the day-1 smoke
test).

See docs/monnify-api-reference.md for verified field names and endpoints,
and its section 7 "Local verification log" for what has actually been
confirmed against real sandbox calls vs. what is still assumed from docs.

Note: docs/architecture.md section 5.1 originally sketched this client
around a two-step Checkout API (init_transaction + pay_with_bank_transfer).
Verified sandbox testing (auth.py, and monnify-api-reference.md section 2)
showed a single POST /api/v1/invoice/create call does both steps at once,
so this client follows that verified flow instead of the original sketch.
"""

import base64
import hashlib
import hmac
import time

import requests


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
                        customer_email, description, expiry_date):
        """``expiry_date`` must already be formatted ``yyyy-MM-dd HH:mm:ss``
        and be in the future — that's the caller's responsibility (see
        docs/monnify-api-reference.md section 2). Returns the raw
        ``responseBody`` dict (accountNumber, bankName, accountName,
        transactionReference, etc.)."""
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
        # TODO [UNVERIFIED]: confirm the exact hash formula (raw body bytes
        # vs. specific concatenated fields) and header name against real
        # Monnify docs or an actual webhook delivery before relying on this
        # — see docs/monnify-api-reference.md section 4.
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
