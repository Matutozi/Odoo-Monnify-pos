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
          2. read + verify hash (header name UNVERIFIED, commonly
             "monnify-signature" per docs) -> 401 on mismatch, no detail leak
          3. parse JSON, ignore (return 200) unless
             eventType == "SUCCESSFUL_TRANSACTION"
          4. find monnify.pos.payment by eventData.transactionReference
             (sudo(), auth is public) -> not found: return 200 anyway
          5. already state == "paid" -> return 200 (dedupe, Monnify resends
             on anything but HTTP 200)
          6. validate eventData amount vs record.amount -> mismatch: state
             "mismatch", do not complete
          7. call record.action_mark_paid(event_data) — the ONE shared
             completion method, also used by verify_monnify_payment RPC
          8. return 200 fast; no heavy work inline

        TODO: implement. All eventData field names here are marked
        UNVERIFIED in docs/monnify-api-reference.md section 4 — confirm
        against a real webhook delivery before trusting them.
        """
        raw_body = request.httprequest.data
        received_hash = request.httprequest.headers.get("monnify-signature")  # noqa: F841 — TODO confirm header name

        # TODO: build a MonnifyClient via
        # request.env["res.config.settings"].sudo()._get_monnify_client()
        # and call client.verify_webhook(raw_body, received_hash).
        raise NotImplementedError
