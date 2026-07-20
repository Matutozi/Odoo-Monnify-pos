import logging
import time

import requests

from odoo import _, models
from odoo.exceptions import UserError

from odoo.addons.monnify_base.services.monnify_client import (
    INVOICE_TTL_MINUTES,
    MonnifyError,
)

_logger = logging.getLogger(__name__)


class PosSession(models.Model):
    _inherit = "pos.session"

    def _monnify_error(self, exc):
        """Turn a client exception into an accurate cashier-facing UserError.

        MonnifyError is an API *rejection* (amount too low, bad contract code,
        expiry, etc.) — its message is actionable, so surface it. A requests
        error is a genuine connectivity problem, and only then is "check your
        internet" the right thing to tell the cashier.
        """
        if isinstance(exc, MonnifyError):
            _logger.warning("Monnify rejected the request: %s", exc)
            return UserError(_("Monnify could not process this payment: %s") % exc)
        _logger.warning("Could not reach Monnify: %s", exc)
        return UserError(
            _("Could not reach Monnify. Check your internet connection and try again.")
        )

    def create_monnify_payment(self, pos_order_uid, amount, customer_name=None):
        """RPC entry point called from the POS frontend."""
        self.ensure_one()
        client = self.env["res.config.settings"].sudo()._get_monnify_client()

        invoice_reference = f"POS-{self.id}-{pos_order_uid}-{int(time.time())}"
        try:
            invoice = client.create_invoice(
                invoice_reference=invoice_reference,
                amount=amount,
                customer_name=customer_name or "POS Customer",
                customer_email="pos-customer@example.com",
                description=f"POS order {pos_order_uid}",
            )
        except (MonnifyError, requests.exceptions.RequestException) as exc:
            raise self._monnify_error(exc)

        payment = self.env["monnify.pos.payment"].sudo().create({
            "name": invoice_reference,
            "monnify_tx_ref": invoice["transactionReference"],
            "pos_order_uid": pos_order_uid,
            "pos_session_id": self.id,
            "amount": amount,
            "account_number": invoice.get("accountNumber"),
            "bank_name": invoice.get("bankName"),
            "account_name": invoice.get("accountName"),
            "state": "pending",
        })

        return {
            "local_id": payment.id,
            "account_number": payment.account_number,
            "bank_name": payment.bank_name,
            "account_name": payment.account_name,
            "amount": payment.amount,
            "expires_in": INVOICE_TTL_MINUTES * 60,
            "monnify_tx_ref": payment.monnify_tx_ref,
            # Not stored — passed straight through as a sandbox testing aid so
            # the cashier/tester can open Monnify's hosted page and complete a
            # payment. The real transfer flow doesn't use it.
            "checkout_url": invoice.get("checkoutUrl"),
        }

    def verify_monnify_payment(self, local_id):
        """RPC fallback entry point (the safety net if the webhook is
        delayed/missed). Polls Monnify directly and, if paid, completes
        through the SAME action_mark_paid the webhook uses.
        """
        payment = self.env["monnify.pos.payment"].sudo().browse(local_id)
        if not payment.exists():
            raise UserError(_("Unknown Monnify payment record."))

        if payment.state == "pending":
            client = self.env["res.config.settings"].sudo()._get_monnify_client()
            try:
                status = client.get_transaction_status(payment.monnify_tx_ref)
            except (MonnifyError, requests.exceptions.RequestException) as exc:
                raise self._monnify_error(exc)

            if status.get("paymentStatus") == "PAID":
                payment.action_mark_paid(status)

        return {"state": payment.state, "amount_paid": payment.amount_paid}

    def cancel_monnify_payment(self, local_id):
        """RPC called when the cashier cancels a still-pending transfer
        (popup cancel button, or removing the waiting payment line).

        Only a 'pending' record is touched — never override a payment that
        already reached 'paid' (a webhook may have landed between the
        cashier deciding to cancel and this call arriving). Best-effort:
        the frontend does not block on the result.
        """
        payment = self.env["monnify.pos.payment"].sudo().browse(local_id)
        if payment.exists() and payment.state == "pending":
            payment.state = "cancelled"
        return {"state": payment.state if payment.exists() else "unknown"}

    # No _load_pos_data_fields override is needed: use_payment_terminal is
    # already loaded to the POS frontend for pos.payment.method, so the
    # "monnify" selection value added in pos_payment_method.py reaches it.
