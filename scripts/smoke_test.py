"""Standalone smoke test for services/monnify_client.py.

Unlike auth.py (the original pre-client smoke test, kept at the repo root as
evidence the API was verified before the client existed), this exercises the
actual MonnifyClient class: token caching, create_invoice, get_transaction_status,
and the webhook hash helpers — no Odoo required.

Hits the REAL sandbox (network calls), using credentials from .env. Run from
the repo root:

    python3 scripts/smoke_test.py
"""

import importlib.util
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_dotenv(path=".env"):
    """Same minimal loader as auth.py — only sets vars not already set."""
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def _load_monnify_client():
    """Load by file path so this script needs no Odoo on the import path,
    matching monnify_client.py's own pure-Python design."""
    path = os.path.join(
        REPO_ROOT, "addons", "monnify_base", "services", "monnify_client.py"
    )
    spec = importlib.util.spec_from_file_location("monnify_client", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.MonnifyClient, module.MonnifyError


def main():
    _load_dotenv(os.path.join(REPO_ROOT, ".env"))
    MonnifyClient, MonnifyError = _load_monnify_client()

    try:
        api_key = os.environ["MONNIFY_API_KEY"]
        secret_key = os.environ["MONNIFY_SECRET_KEY"]
        contract_code = os.environ["MONNIFY_CONTRACT_CODE"]
    except KeyError as e:
        print(f"Missing {e} in .env — copy .env.example and fill it in.")
        sys.exit(1)

    client = MonnifyClient(
        api_key=api_key,
        secret_key=secret_key,
        contract_code=contract_code,
        base_url="https://sandbox.monnify.com",
    )

    print("=" * 60)
    print("1. Fetching auth token (client._get_token)...")
    token = client._get_token()
    print(f"   OK — got token, {len(token)} chars, cached on the client.")

    print("=" * 60)
    print("2. Creating a test invoice (client.create_invoice)...")
    import uuid

    # expiryDate is now generated inside create_invoice (in Nigerian time),
    # so the caller no longer passes it — see monnify_client._MONNIFY_TZ.
    invoice_reference = f"SMOKE-{uuid.uuid4().hex[:8]}"
    try:
        invoice = client.create_invoice(
            invoice_reference=invoice_reference,
            amount=1000,
            customer_name="Smoke Test Customer",
            customer_email="smoke-test@example.com",
            description="scripts/smoke_test.py run",
        )
    except MonnifyError as e:
        print(f"   FAILED: {e} (code {e.response_code})")
        sys.exit(1)

    print(json.dumps(invoice, indent=2))
    tx_ref = invoice["transactionReference"]
    print(f"   OK — accountNumber={invoice.get('accountNumber')} "
          f"bankName={invoice.get('bankName')} transactionReference={tx_ref}")

    print("=" * 60)
    print("3. Querying status of that invoice (client.get_transaction_status)...")
    try:
        status = client.get_transaction_status(tx_ref)
    except MonnifyError as e:
        print(f"   FAILED: {e} (code {e.response_code})")
        sys.exit(1)

    print(json.dumps(status, indent=2))
    print(f"   paymentStatus={status.get('paymentStatus')!r} "
          f"amountPaid={status.get('amountPaid')!r} "
          f"(type {type(status.get('amountPaid')).__name__})")

    print("=" * 60)
    print("4. Webhook hash helpers (no network — uses Monnify's own "
          "documented sample vector as a known-answer check)...")
    sample_secret = "91MUDL9N6U3BQRXBQ2PJ9M0PW4J22M1Y"
    sample_body = (
        b'{"eventData":{"product":{"reference":"111222333",'
        b'"type":"OFFLINE_PAYMENT_AGENT"},"transactionReference":'
        b'"MNFY|76|20211117154810|000001","paymentReference":'
        b'"0.01462001097368737","paidOn":"17/11/2021 3:48:10 PM",'
        b'"paymentDescription":"Mockaroo Jesse","metaData":{},'
        b'"destinationAccountInformation":{},"paymentSourceInformation":{},'
        b'"amountPaid":78000,"totalPayable":78000,'
        b'"offlineProductInformation":{"code":"41470","type":"DYNAMIC"},'
        b'"cardDetails":{},"paymentMethod":"CASH","currency":"NGN",'
        b'"settlementAmount":77600,"paymentStatus":"PAID","customer":'
        b'{"name":"Mockaroo Jesse","email":'
        b'"111222333@ZZAMZ4WT4Y3E.monnify"}},"eventType":'
        b'"SUCCESSFUL_TRANSACTION"}'
    )
    expected_hash = (
        "f04fb635e04d71648bd3cc7999003da6861483342c856d05ddfa9b2dafacb87"
        "3b0de1d0f8f67405d0010b4348b721c49fa171d317972618debba6b638aedcd3c"
    )
    computed = MonnifyClient.compute_transaction_hash(sample_body, sample_secret)
    print(f"   computed == expected: {computed == expected_hash}")

    print("=" * 60)
    print("Done. Pay the invoice above in sandbox and re-run step 3's query "
          "manually (or watch a real webhook hit /monnify/webhook) to "
          "observe the PAID response shape — still an open item per "
          "docs/monnify-api-reference.md section 7.")


if __name__ == "__main__":
    main()
