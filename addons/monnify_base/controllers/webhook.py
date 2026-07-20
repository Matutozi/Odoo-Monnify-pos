import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class MonnifyWebhookController(http.Controller):

    @http.route("/monnify/webhook", type="http", auth="public",
                methods=["POST"], csrf=False)
    def monnify_webhook(self, **kwargs):
        """Receive a Monnify payment notification.

        The ordering here is security-critical: the signature is verified
        against the raw request body before any part of the payload is
        trusted, and a bad signature gets a bare 401 with no detail.

        Monnify retries anything that does not return HTTP 200, so every
        other outcome — unknown reference, already-processed payment,
        irrelevant event type — still acknowledges with 200 to stop the
        retries. State is the dedupe key: only a "pending" record is acted
        on, so a repeated delivery is a no-op.

        A rejected payment is recorded as a mismatch directly; only a
        successful one goes through action_mark_paid, which is the single
        completion path shared with the verify RPC and does its own
        amount check.
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
