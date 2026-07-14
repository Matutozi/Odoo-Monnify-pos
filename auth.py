import requests
import base64
import os
import uuid
import json
from datetime import datetime, timedelta


def _load_dotenv(path=".env"):
    """Minimal .env loader so this script has no extra dependency.
    Only sets vars that aren't already in the environment."""
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()

API_KEY = os.environ["MONNIFY_API_KEY"]
SECRET_KEY = os.environ["MONNIFY_SECRET_KEY"]
CONTRACT_CODE = os.environ["MONNIFY_CONTRACT_CODE"]
# ---------------------------------------------------

BASE_URL = "https://sandbox.monnify.com"

def get_token():
    url = f"{BASE_URL}/api/v1/auth/login"
    credentials = base64.b64encode(f"{API_KEY}:{SECRET_KEY}".encode()).decode()
    headers = {"Authorization": f"Basic {credentials}"}
    resp = requests.post(url, headers=headers, timeout=30)
    data = resp.json()
    if not data.get("requestSuccessful"):
        print("LOGIN FAILED:")
        print(json.dumps(data, indent=2))
        raise SystemExit(1)
    return data["responseBody"]["accessToken"]

def create_invoice(token):
    url = f"{BASE_URL}/api/v1/invoice/create"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    expiry = (datetime.now() + timedelta(minutes=40)).strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "invoiceReference": f"INV-TEST-{uuid.uuid4().hex[:8]}",  # unique every run
        "amount": 10000,
        "invoiceDescription": "POS test payment",
        "contractCode": CONTRACT_CODE,
        "customerEmail": "jane@example.com",
        "customerName": "Jane Smith",
        "expiryDate": expiry,
        "currencyCode": "NGN",
    }
    print("Sending payload:")
    print(json.dumps(payload, indent=2))
    print("-" * 40)
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    return resp.json()

def check_transaction_status(token, transaction_reference):
    url = f"{BASE_URL}/api/v2/merchant/transactions/query"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"transactionReference": transaction_reference}  # requests encodes the | for you
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    return resp.json()
if __name__ == "__main__":
    token = get_token()
    print("Got token OK")
    print("-" * 40)

    # Create the invoice and grab the real transaction reference
    result = create_invoice(token)
    print("CREATE RESPONSE:")
    print(json.dumps(result, indent=2))

    tx_ref = result["responseBody"]["transactionReference"]
    checkout_url = result["responseBody"]["checkoutUrl"]
    print("-" * 40)
    print("Transaction reference:", tx_ref)
    print("Pay here to test:", checkout_url)
    print("-" * 40)

    status = check_transaction_status(token, tx_ref)
    print("STATUS RESPONSE:")
    print(json.dumps(status, indent=2))