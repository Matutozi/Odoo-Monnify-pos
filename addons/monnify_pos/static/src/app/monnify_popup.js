/**
 * Owl component for the Monnify account-details popup shown on the POS
 * payment screen.
 *
 * Presentation only — it holds no payment logic and talks to no RPC. The
 * PaymentMonnify interface owns the flow and passes in callbacks:
 *   - onVerify(): async, resolves true if paid (interface then closes this
 *     popup) or false to keep it open for another attempt;
 *   - onCancel(): abandon the transfer.
 *
 * ``ui`` is a reactive object shared with the interface, so the interface can
 * flip the popup to its "paid" state when the webhook lands, before closing.
 *
 * Built on the real Odoo 18 Dialog component (confirmed props/slots in
 * web/core/dialog/dialog.js), with Dialog's own header/footer/padding disabled
 * so the popup renders its own branded chrome. No reusable countdown exists in
 * core POS, so the mm:ss timer here follows the useTime() hook's
 * setInterval/clearInterval pattern (point_of_sale/utils/time_hook.js).
 */

import { Component, useState, onWillUnmount } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

export class MonnifyPopup extends Component {
    static template = "monnify_pos.MonnifyPopup";
    static components = { Dialog };
    static props = {
        close: Function, // injected by the dialog service
        accountNumber: String,
        bankName: String,
        accountName: String,
        amount: String, // pre-formatted currency string
        expiresIn: Number, // seconds
        checkoutUrl: { type: [String, { value: false }], optional: true }, // sandbox testing aid
        ui: Object, // reactive: { paid, payerName } — owned by the interface
        onVerify: Function,
        onCancel: Function,
    };

    setup() {
        this.state = useState({
            remaining: this.props.expiresIn,
            verifying: false,
            copied: false,
            hint: "",
        });
        // Shared with PaymentMonnify so a bus push can flip us to "paid".
        this.ui = useState(this.props.ui);

        this._tick = setInterval(() => {
            if (this.state.remaining > 0) {
                this.state.remaining -= 1;
            } else {
                clearInterval(this._tick);
            }
        }, 1000);
        onWillUnmount(() => {
            clearInterval(this._tick);
            clearTimeout(this._copyTimer);
        });
    }

    get countdown() {
        const s = Math.max(0, this.state.remaining);
        return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
    }

    get expired() {
        return this.state.remaining <= 0;
    }

    async onVerifyClick() {
        if (this.state.verifying) {
            return;
        }
        this.state.verifying = true;
        this.state.hint = "";
        const paid = await this.props.onVerify();
        if (paid) {
            return; // the interface flips us to "paid" and closes; don't touch state
        }
        this.state.verifying = false;
        this.state.hint = _t(
            "Payment not received yet. Once the customer has transferred, tap Verify again."
        );
    }

    onCancelClick() {
        this.props.onCancel();
    }

    async onCopy() {
        try {
            await navigator.clipboard.writeText(this.props.accountNumber);
            this.state.copied = true;
            clearTimeout(this._copyTimer);
            this._copyTimer = setTimeout(() => (this.state.copied = false), 1500);
        } catch {
            // Clipboard blocked (e.g. non-secure context) — cashier can read it out.
        }
    }
}
