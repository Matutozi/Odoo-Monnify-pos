import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class MonnifyWebhookController(http.Controller):

    @http.route("/monnify/webhook", type="http", auth="public",
                methods=["POST"], csrf=False)
    def monnify_webhook(self, **kwargs):
        """Order of operations fixed by docs/architecture.md section 5.4 and
        docs/monnify-api-reference.md section 4 — do not reorder:

          1. read raw body bytes (request.httprequest.data)
          2. read + verify hash ("monnify-signature" header, confirmed
             against official Monnify docs) -> 401 on mismatch, no detail
             leak
          3. parse JSON, ignore (return 200) unless eventType is
             SUCCESSFUL_TRANSACTION or REJECTED_PAYMENT
          4. find monnify.pos.payment by eventData.transactionReference
             (sudo(), auth is public) -> not found: return 200 anyway
          5. state != "pending" -> return 200 (dedupe, Monnify resends
             on anything but HTTP 200)
          6. REJECTED_PAYMENT -> state "mismatch" directly, not via
             action_mark_paid (that method is the PAID-completion path only)
          7. SUCCESSFUL_TRANSACTION -> call record.action_mark_paid(event_data)
             — the ONE shared completion method, also used by the
             verify_monnify_payment RPC. It does its own amount check.
          8. return 200 fast; no heavy work inline
        """
        raw_body = request.httprequest.data
        received_hash = request.httprequest.headers.get("monnify-signature")

        client = request.env["res.config.settings"].sudo()._get_monnify_client()
        if not received_hash or not client.verify_webhook(raw_body, received_hash):
            _logger.warning("Monnify webhook: invalid or missing signature")
            return request.make_response("Invalid signature", status=401)

        payload = json.loads(raw_body)
        event_type = payload.get("eventType")
        if event_type not in ("SUCCESSFUL_TRANSACTION", "REJECTED_PAYMENT"):
            return request.make_response("OK", status=200)

        event_data = payload.get("eventData", {})
        tx_ref = event_data.get("transactionReference")
        payment = request.env["monnify.pos.payment"].sudo().search(
            [("monnify_tx_ref", "=", tx_ref)], limit=1
        )
        if not payment or payment.state != "pending":
            return request.make_response("OK", status=200)

        if event_type == "REJECTED_PAYMENT":
            payment.write({
                "state": "mismatch",
                "raw_webhook": json.dumps(payload),
            })
        else:
            payment.action_mark_paid(event_data)

        return request.make_response("OK", status=200)
