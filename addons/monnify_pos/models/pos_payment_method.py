from odoo import models


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    def _get_payment_terminal_selection(self):
        # use_payment_terminal is a lambda-backed Selection, so new terminals
        # are added by extending this method rather than with selection_add.
        # The value reaches the POS frontend automatically: use_payment_terminal
        # is already among the fields the POS loads for pos.payment.method.
        return super()._get_payment_terminal_selection() + [
            ("monnify", "Monnify (Pay by Transfer)"),
        ]
