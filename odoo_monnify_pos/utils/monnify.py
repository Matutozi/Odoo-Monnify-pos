import hashlib
import hmac
from typing import Optional


STATUS_MAP = {
    "PAID": "done",
    "OVERPAID": "done",
    "PARTIALLY_PAID": "pending",
    "PENDING": "pending",
    "EXPIRED": "error",
    "FAILED": "error",
    "CANCELLED": "cancel",
}


def verify_monnify_signature(payload: bytes, signature: Optional[str], secret: Optional[str]) -> bool:
    if not signature or not secret:
        return False
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha512).hexdigest()
    return hmac.compare_digest(digest.lower(), signature.strip().lower())


def normalize_monnify_status(status: Optional[str]) -> str:
    if not status:
        return "pending"
    return STATUS_MAP.get(status.upper(), "pending")
