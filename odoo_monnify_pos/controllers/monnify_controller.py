import json
import logging

from odoo import http
from odoo.http import request
from werkzeug.wrappers import Response

from ..utils import verify_monnify_signature

_logger = logging.getLogger(__name__)


class MonnifyController(http.Controller):
    @http.route("/payment/monnify/webhook", type="http", auth="public", methods=["POST"], csrf=False, save_session=False)
    def monnify_webhook(self, **kwargs):
        payload = request.httprequest.data or b""
        signature = request.httprequest.headers.get("monnify-signature") or request.httprequest.headers.get("Monnify-Signature")
        provider = request.env["payment.provider"].sudo().search([("code", "=", "monnify"), ("state", "!=", "disabled")], limit=1)
        if not provider or not verify_monnify_signature(payload, signature, provider.monnify_webhook_secret):
            _logger.warning("Rejected Monnify webhook due to missing provider or invalid signature.")
            return Response(status=403)

        try:
            data = json.loads(payload.decode("utf-8") or "{}")
            request.env["payment.transaction"].sudo()._handle_notification_data("monnify", data)
        except Exception:
            _logger.exception("Failed processing Monnify webhook payload")
            return Response(status=400)

        return Response("OK", status=200)

    @http.route("/pos/monnify/initiate", type="json", auth="user")
    def pos_monnify_initiate(self, amount, reference, currency=None, partner_id=None, **kwargs):
        provider = request.env["payment.provider"].sudo().search([("code", "=", "monnify"), ("state", "=", "enabled")], limit=1)
        if not provider:
            return {"error": "Monnify payment provider is not enabled."}

        company = request.env.company
        currency_id = request.env["res.currency"].sudo().search([("name", "=", currency)], limit=1).id if currency else company.currency_id.id
        tx_vals = {
            "provider_id": provider.id,
            "reference": reference,
            "amount": amount,
            "currency_id": currency_id,
            "partner_id": partner_id or request.env.user.partner_id.id,
            "operation": "online_redirect",
        }
        tx = request.env["payment.transaction"].sudo().create(tx_vals)
        provider.monnify_initialize_transaction(tx)
        return {
            "reference": tx.reference,
            "checkout_url": tx.monnify_checkout_url,
            "account_number": tx.monnify_account_number,
            "bank_name": tx.monnify_bank_name,
            "expires_at": tx.monnify_expiry_datetime,
            "state": tx.state,
        }

    @http.route("/pos/monnify/status", type="json", auth="user")
    def pos_monnify_status(self, reference, **kwargs):
        tx = request.env["payment.transaction"].sudo().search([("reference", "=", reference), ("provider_code", "=", "monnify")], limit=1)
        if not tx:
            return {"error": "Payment transaction not found."}
        return tx.action_monnify_sync_status()
