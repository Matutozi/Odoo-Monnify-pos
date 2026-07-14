"""Tests for controllers/webhook.py.

TODO: cover, per docs/architecture.md section 5.4:
- valid hash + SUCCESSFUL_TRANSACTION -> record moves to "paid"
- invalid hash -> 401, record untouched
- unknown transactionReference -> 200, no error
- duplicate delivery on an already-paid record -> 200, no-op, no double
  processing
- amount mismatch -> state "mismatch", not "paid"
- non-SUCCESSFUL_TRANSACTION eventType -> 200, ignored
"""
