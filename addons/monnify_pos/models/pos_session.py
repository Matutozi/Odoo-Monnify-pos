from odoo import models


class PosSession(models.Model):
    _inherit = "pos.session"

    def create_monnify_payment(self, pos_order_uid, amount, customer_name=None):
        """RPC entry point called from the POS frontend.

        TODO: implement per docs/architecture.md section 5.6 — build an
        invoiceReference (scheme: "POS-<session_id>-<order_uid>-<epoch>"),
        call MonnifyClient.create_invoice via
        self.env["res.config.settings"]._get_monnify_client(), create a
        monnify.pos.payment record (state "pending"), return the display
        payload: {account_number, bank_name, account_name, amount,
        expires_in, monnify_tx_ref, local_id}. Wrap MonnifyError into a
        friendly message ("Could not reach Monnify, check your internet"),
        never a raw traceback back to the cashier.
        """
        raise NotImplementedError

    def verify_monnify_payment(self, local_id):
        """RPC fallback entry point (the safety net if the webhook is
        delayed/missed).

        TODO: implement per docs/architecture.md section 5.6 — poll
        MonnifyClient.get_transaction_status, call the target record's
        action_mark_paid(...) if paid (the SAME method the webhook calls),
        return {state, amount_paid}.
        """
        raise NotImplementedError

    # TODO: confirm the real Odoo 18 POS data-loading hook (e.g.
    # _load_pos_data_fields / _loader_params_pos_payment_method or the
    # equivalent for this version) before wiring Monnify fields into the
    # POS frontend's initial data load. Do not invent the method name —
    # read Odoo 18 source first.
