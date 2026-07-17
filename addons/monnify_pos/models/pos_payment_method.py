from odoo import models


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    def _get_payment_terminal_selection(self):
        # Confirmed against real Odoo 18 source
        # (point_of_sale/models/pos_payment_method.py) — this is the actual
        # extension point for use_payment_terminal, following the same
        # pattern as pos_adyen/pos_razorpay, NOT a selection_add. The value
        # reaches the POS frontend for free: core's own
        # _load_pos_data_fields already includes use_payment_terminal.
        return super()._get_payment_terminal_selection() + [
            ("monnify", "Monnify (Pay by Transfer)"),
        ]
