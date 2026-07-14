from odoo import api, fields, models
from odoo.http import request

from ..utils import normalize_monnify_status


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    monnify_payment_reference = fields.Char(copy=False, index=True)
    monnify_checkout_url = fields.Char(copy=False)
    monnify_account_number = fields.Char(copy=False)
    monnify_bank_name = fields.Char(copy=False)
    monnify_expiry_datetime = fields.Datetime(copy=False)
    monnify_status = fields.Char(copy=False)

    def _get_specific_rendering_values(self, processing_values):
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != "monnify":
            return res
        self.provider_id.monnify_initialize_transaction(self)
        return {
            **res,
            "api_url": self.monnify_checkout_url,
            "reference": self.reference,
            "monnify_account_number": self.monnify_account_number,
            "monnify_bank_name": self.monnify_bank_name,
            "monnify_expiry_datetime": self.monnify_expiry_datetime,
        }

    @api.model
    def _get_tx_from_notification_data(self, provider_code, notification_data):
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != "monnify":
            return tx
        body = notification_data.get("responseBody") or notification_data
        references = [
            body.get("paymentReference"),
            body.get("transactionReference"),
            body.get("product", {}).get("reference"),
        ]
        references = [ref for ref in references if ref]
        tx = self.search([
            "|",
            ("reference", "in", references),
            ("monnify_payment_reference", "in", references),
        ], limit=1)
        return tx

    def _process_notification_data(self, notification_data):
        super()._process_notification_data(notification_data)
        if self.provider_code != "monnify":
            return
        body = notification_data.get("responseBody") or notification_data
        monnify_status = body.get("paymentStatus") or body.get("status")
        status = normalize_monnify_status(monnify_status)
        self.write(
            {
                "provider_reference": body.get("transactionReference") or self.provider_reference,
                "monnify_payment_reference": body.get("paymentReference") or self.monnify_payment_reference,
                "monnify_status": monnify_status,
            }
        )
        if status == "done":
            self._set_done()
        elif status == "error":
            self._set_error("Monnify reported payment failure.")
        elif status == "cancel":
            self._set_canceled("Monnify payment was cancelled.")
        else:
            self._set_pending()

    def action_monnify_sync_status(self):
        self.ensure_one()
        if self.provider_code != "monnify":
            return {"state": self.state}
        payment_reference = self.monnify_payment_reference or self.reference
        response = self.provider_id.monnify_fetch_status(payment_reference)
        status = response.get("paymentStatus") or response.get("status")
        self._process_notification_data({"responseBody": response, "status": status})
        return {
            "state": self.state,
            "status": self.monnify_status,
            "reference": self.reference,
            "is_done": self.state == "done",
            "poll_url": f"{request.httprequest.host_url}pos/monnify/status" if request else "",
        }
