import unittest

from odoo_monnify_pos.utils.monnify import normalize_monnify_status, verify_monnify_signature


class TestMonnifyUtils(unittest.TestCase):
    def test_verify_signature(self):
        payload = b'{"eventType":"SUCCESSFUL_TRANSACTION"}'
        secret = "secret"
        signature = "eb62fa917c21258bc4d746434ffa89ab908c19fb562dcaaabd362bd9614f846f5b1044be0ed0eed02b82be811cb3d9162b84a1d1cb70f1a828c98a3a493e7915"
        self.assertTrue(verify_monnify_signature(payload, signature, secret))

    def test_verify_signature_invalid(self):
        payload = b'{"eventType":"SUCCESSFUL_TRANSACTION"}'
        self.assertFalse(verify_monnify_signature(payload, "invalid", "secret"))

    def test_status_normalization(self):
        self.assertEqual(normalize_monnify_status("PAID"), "done")
        self.assertEqual(normalize_monnify_status("pending"), "pending")
        self.assertEqual(normalize_monnify_status("FAILED"), "error")
        self.assertEqual(normalize_monnify_status(None), "pending")


if __name__ == "__main__":
    unittest.main()
