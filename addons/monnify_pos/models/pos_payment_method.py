from odoo import fields, models


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment_method"

    use_payment_terminal_monnify = fields.Boolean(
        string="Use Monnify (Pay by Transfer)",
    )
    # TODO: confirm the real Odoo 18 mechanism for flagging an electronic
    # payment method's terminal/interface (there may already be a
    # use_payment_terminal selection field to extend, rather than a new
    # boolean) against actual Odoo 18 source before relying on this field —
    # see docs/architecture.md section 5.5 and CLAUDE.md non-negotiable
    # rules: do not invent Odoo APIs.
