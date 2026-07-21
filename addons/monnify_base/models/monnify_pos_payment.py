import json

from odoo import fields, models

AMOUNT_TOLERANCE = 0.01


class MonnifyPosPayment(models.Model):
    _name = "monnify.pos.payment"
    _description = "Local log of a Monnify dynamic-account payment tied to one POS order"

    name = fields.Char(
        required=True, index=True, copy=False,
        help="Our own invoiceReference sent to Monnify. Also our idempotency key.",
    )
    monnify_tx_ref = fields.Char(string="Monnify Transaction Reference", index=True)
    pos_order_uid = fields.Char(string="POS Order UID")
    pos_session_id = fields.Many2one("pos.session")
    amount = fields.Monetary()
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id
    )
    account_number = fields.Char()
    bank_name = fields.Char()
    account_name = fields.Char()
    payer_name = fields.Char(
        help="Name on the account the customer actually paid from, as reported "
        "by Monnify — shown on the POS confirmation.",
    )
    amount_paid = fields.Monetary()
    paid_on = fields.Datetime()
    raw_webhook = fields.Text()
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("paid", "Paid"),
            ("expired", "Expired"),
            ("mismatch", "Amount Mismatch"),
            ("cancelled", "Cancelled"),
        ],
        default="pending",
        required=True,
    )

    _sql_constraints = [
        ("name_uniq", "unique(name)", "Payment reference must be unique."),
    ]

    def action_mark_paid(self, payload):
        """THE single completion function.

        Called by both the webhook controller and the verify_monnify_payment
        RPC — must be idempotent (this is the single completion path; both
        entry points converge here so "mark as paid" is never duplicated).

        ``payload`` is either a webhook's ``eventData`` dict (amountPaid is a
        JSON number there) or a get_transaction_status responseBody dict
        (amountPaid is a STRING there) — see docs/monnify-api-reference.md
        sections 3 and 4. float() handles both shapes, so no caller-specific
        branching is needed.
        """
        self.ensure_one()
        if self.state != "pending":
            return

        amount_paid = float(payload.get("amountPaid") or 0)
        raw_webhook = json.dumps(payload)

        if abs(amount_paid - self.amount) > AMOUNT_TOLERANCE:
            self.write({
                "state": "mismatch",
                "amount_paid": amount_paid,
                "raw_webhook": raw_webhook,
            })
            return

        self.write({
            "state": "paid",
            "amount_paid": amount_paid,
            "paid_on": fields.Datetime.now(),
            "raw_webhook": raw_webhook,
            "payer_name": self._extract_payer_name(payload),
        })
        self._notify_pos()

    @staticmethod
    def _extract_payer_name(payload):
        """The name on the account the customer paid from.

        The webhook (eventData) reports it under paymentSourceInformation; the
        status-query responseBody reports it under accountDetails /
        accountPayments — try each shape, then fall back to the customer name.
        Returns "" when nothing usable is present (e.g. a card payment).
        """
        source = payload.get("paymentSourceInformation")
        if isinstance(source, list) and source:
            source = source[0]
        if isinstance(source, dict) and source.get("accountName"):
            return source["accountName"]

        details = payload.get("accountDetails")
        if isinstance(details, dict) and details.get("accountName"):
            return details["accountName"]

        payments = payload.get("accountPayments")
        if isinstance(payments, list) and payments and payments[0].get("accountName"):
            return payments[0]["accountName"]

        customer = payload.get("customer")
        if isinstance(customer, dict) and customer.get("name"):
            return customer["name"]
        return ""

    def _notify_pos(self):
        """Push a live update to the open POS session.

        pos.config._notify() publishes on the session's private bus channel —
        the same mechanism the POS uses for its own events. The frontend
        listens on "MONNIFY_PAYMENT_STATUS" and completes the payment line.
        """
        self.ensure_one()
        if not self.pos_session_id:
            return
        self.pos_session_id.config_id._notify("MONNIFY_PAYMENT_STATUS", {
            "local_id": self.id,
            "pos_order_uid": self.pos_order_uid,
            "status": self.state,
            "payer_name": self.payer_name or "",
        })
