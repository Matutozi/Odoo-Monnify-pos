"""Tests for services/monnify_client.py.

TODO: cover, per docs/architecture.md section 5.1 acceptance criteria:
- token caching/refresh behaviour (mock time + responses, don't hit sandbox)
- create_invoice payload shape and response parsing
- get_transaction_status response parsing, including that amountPaid/
  totalPayable arrive as strings (see docs/monnify-api-reference.md
  section 7)
- MonnifyError raised with responseMessage on requestSuccessful == False
- verify_webhook hash comparison (once the hash formula is confirmed —
  currently marked UNVERIFIED, see monnify_client.compute_transaction_hash)

The verified end-to-end behaviour (real sandbox calls) already lives in
auth.py at the repo root — these tests should mock requests rather than
hit the network.
"""
