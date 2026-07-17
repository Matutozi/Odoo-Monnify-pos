/**
 * Monnify "Pay by Transfer" payment interface for Odoo POS.
 *
 * Subclasses the real Odoo 18 PaymentInterface (confirmed against
 * point_of_sale/static/src/app/payment/payment_interface.js). The frontend
 * never talks to Monnify directly — it only calls the Odoo backend over RPC
 * and listens on the POS bus. All method/service names here were traced to
 * real Odoo 18 source (see the research notes in CLAUDE.md / architecture.md
 * 5.5); nothing is invented.
 *
 * Three things can end a pending payment, and all resolve the single Promise
 * returned by send_payment_request via one guarded `settle(paid)`:
 *   1. the MONNIFY_PAYMENT_STATUS bus push (automatic, primary path);
 *   2. the popup's "Verify Payment" button (manual fallback if the webhook
 *      is delayed/lost — polls Monnify server-to-server);
 *   3. cancellation (popup Cancel, dismissing the dialog, or removing the
 *      waiting payment line).
 */

import { _t } from "@web/core/l10n/translation";
import { PaymentInterface } from "@point_of_sale/app/payment/payment_interface";
import { register_payment_method } from "@point_of_sale/app/store/pos_store";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { ConnectionLostError } from "@web/core/network/rpc";
import { MonnifyPopup } from "@monnify_pos/app/monnify_popup";

export class PaymentMonnify extends PaymentInterface {
    setup() {
        super.setup(...arguments);
        // uuid (payment line) -> { settle, localId } for in-flight payments.
        this._pending = new Map();
        // localId -> callback, so a bus push can complete the right payment.
        this._busCallbacks = new Map();

        // Same backend/bus pairing core uses for SYNCHRONISATION / CLOSING_SESSION:
        // pos.config._notify("MONNIFY_PAYMENT_STATUS", ...) on the Python side
        // (monnify.pos.payment._notify_pos) lands here.
        this.pos.data.connectWebSocket("MONNIFY_PAYMENT_STATUS", (payload) => {
            if (payload?.status === "paid") {
                this._busCallbacks.get(payload.local_id)?.();
            }
        });
    }

    send_payment_request(uuid) {
        super.send_payment_request(uuid);
        return this._processMonnify(uuid);
    }

    /**
     * The waiting line is removed (trash icon) or the payment screen is left.
     * Cancel the pending transfer backend-side and resolve the in-flight
     * Promise. Returning true lets the POS delete the line.
     */
    send_payment_cancel(order, uuid) {
        super.send_payment_cancel(order, uuid);
        const pending = this._pending.get(uuid);
        if (pending) {
            this._cancelBackend(pending.localId);
            pending.settle(false);
        }
        return Promise.resolve(true);
    }

    async _processMonnify(uuid) {
        const order = this.pos.get_order();
        const line = order.get_selected_paymentline();
        if (!line || line.amount <= 0) {
            this._showError(_t("Enter a positive amount before paying by transfer."));
            return false;
        }
        // Spinner on the payment line while we reach Monnify; pay() overwrites
        // this with "done"/"retry" based on the boolean we return.
        line.set_payment_status("waitingCard");

        let payload;
        try {
            payload = await this._call("create_monnify_payment", [
                order.uuid,
                line.amount,
                order.get_partner()?.name || undefined,
            ]);
        } catch (error) {
            this._handleError(error);
            return false;
        }
        line.monnify_local_id = payload.local_id;

        return new Promise((resolve) => {
            let removePopup = () => {};
            const settle = (paid) => {
                if (!this._pending.has(uuid)) {
                    return; // already settled — guard against double resolution
                }
                this._pending.delete(uuid);
                this._busCallbacks.delete(payload.local_id);
                removePopup();
                resolve(paid);
            };
            this._pending.set(uuid, { settle, localId: payload.local_id });
            this._busCallbacks.set(payload.local_id, () => settle(true));

            removePopup = this.env.services.dialog.add(
                MonnifyPopup,
                {
                    accountNumber: payload.account_number,
                    bankName: payload.bank_name,
                    accountName: payload.account_name,
                    amount: this.env.utils.formatCurrency(payload.amount),
                    expiresIn: payload.expires_in,
                    checkoutUrl: payload.checkout_url,
                    onVerify: () => this._verify(payload.local_id, settle),
                    onCancel: () => {
                        this._cancelBackend(payload.local_id);
                        settle(false);
                    },
                },
                {
                    // Dismissing the dialog (X / Escape) counts as a cancel,
                    // unless we already settled it programmatically.
                    onClose: () => {
                        if (this._pending.has(uuid)) {
                            this._cancelBackend(payload.local_id);
                            settle(false);
                        }
                    },
                }
            );
        });
    }

    /**
     * "Verify Payment" handler. Returns true if paid (popup then closes via
     * settle), false to keep the popup open for another attempt.
     */
    async _verify(localId, settle) {
        let res;
        try {
            res = await this._call("verify_monnify_payment", [localId]);
        } catch (error) {
            this._handleError(error);
            return false;
        }
        if (res.state === "paid") {
            settle(true);
            return true;
        }
        if (res.state === "mismatch") {
            this._showError(
                _t(
                    "The amount received doesn't match the order total. Do not complete the sale — check with the customer."
                )
            );
        }
        return false;
    }

    _cancelBackend(localId) {
        // Best-effort: the cashier is cancelling regardless of the result.
        this._call("cancel_monnify_payment", [localId]).catch(() => {});
    }

    _call(method, args) {
        return this.env.services.orm.silent.call("pos.session", method, [
            [this.pos.session.id],
            ...args,
        ]);
    }

    _handleError(error) {
        let message;
        if (error instanceof ConnectionLostError) {
            message = _t(
                "Connection to the server was lost. Check your internet connection and try again."
            );
        } else {
            message = error?.data?.message || _t("Could not reach Monnify. Please try again.");
        }
        this._showError(message);
    }

    _showError(body, title) {
        this.env.services.dialog.add(AlertDialog, {
            title: title || _t("Monnify"),
            body,
        });
    }
}

register_payment_method("monnify", PaymentMonnify);
