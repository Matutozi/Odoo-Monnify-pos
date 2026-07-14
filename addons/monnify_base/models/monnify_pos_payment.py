from odoo import fields, models


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
        RPC — must be idempotent (see CLAUDE.md non-negotiable rules).

        TODO: implement per docs/architecture.md section 5.3:
        - if self.state == "paid", no-op and return
        - validate payload's paid amount against self.amount. Remember
          Monnify's status-query endpoint returns amountPaid/totalPayable as
          STRINGS (see docs/monnify-api-reference.md section 3/7) — convert
          before comparing. Confirm the webhook payload's type too before
          trusting it's numeric.
        - on mismatch: set state "mismatch", do NOT mark paid
        - on match: set state "paid", amount_paid, paid_on, raw_webhook
        - call self._notify_pos()
        """
        raise NotImplementedError

    def _notify_pos(self):
        """Send a bus.bus notification so the open POS session updates live.

        TODO: confirm the exact Odoo 18 bus.bus API before implementing —
        it moved between 16/17/18 (see CLAUDE.md non-negotiable rules).
        """
        raise NotImplementedError
