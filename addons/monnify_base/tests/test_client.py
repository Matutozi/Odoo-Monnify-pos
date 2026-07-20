"""Tests for the webhook signature helpers in services/monnify_client.py.

Known-answer tests against the sample secret, payload and hash published in
Monnify's webhook documentation, plus negative cases for a tampered body and
a wrong secret.

Pure Python — no network and no Odoo required:
    python3 addons/monnify_base/tests/test_client.py -v
"""

import importlib.util
import os
import unittest

_CLIENT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "services", "monnify_client.py"
)
_spec = importlib.util.spec_from_file_location("monnify_client", _CLIENT_PATH)
_monnify_client = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_monnify_client)
MonnifyClient = _monnify_client.MonnifyClient


SAMPLE_SECRET = "91MUDL9N6U3BQRXBQ2PJ9M0PW4J22M1Y"
SAMPLE_BODY = (
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
SAMPLE_HASH = (
    "f04fb635e04d71648bd3cc7999003da6861483342c856d05ddfa9b2dafacb87"
    "3b0de1d0f8f67405d0010b4348b721c49fa171d317972618debba6b638aedcd3c"
)


class TestComputeTransactionHash(unittest.TestCase):
    def test_matches_monnify_reference_vector(self):
        self.assertEqual(
            MonnifyClient.compute_transaction_hash(SAMPLE_BODY, SAMPLE_SECRET),
            SAMPLE_HASH,
        )


class TestVerifyWebhook(unittest.TestCase):
    def setUp(self):
        self.client = MonnifyClient(
            api_key="k", secret_key=SAMPLE_SECRET,
            contract_code="c", base_url="https://sandbox.monnify.com",
        )

    def test_true_for_correct_hash(self):
        self.assertTrue(self.client.verify_webhook(SAMPLE_BODY, SAMPLE_HASH))

    def test_false_for_tampered_body(self):
        tampered = SAMPLE_BODY.replace(b'"amountPaid":78000', b'"amountPaid":1')
        self.assertFalse(self.client.verify_webhook(tampered, SAMPLE_HASH))

    def test_false_for_wrong_secret(self):
        wrong_secret_client = MonnifyClient(
            api_key="k", secret_key="not-the-real-secret",
            contract_code="c", base_url="https://sandbox.monnify.com",
        )
        self.assertFalse(
            wrong_secret_client.verify_webhook(SAMPLE_BODY, SAMPLE_HASH)
        )


if __name__ == "__main__":
    unittest.main()
