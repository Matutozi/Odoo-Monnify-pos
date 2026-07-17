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
 * Built on the real Odoo 18 Dialog component (confirmed props/slots in
 * web/core/dialog/dialog.js). No reusable countdown exists in core POS, so
 * the mm:ss timer here follows the useTime() hook's setInterval/clearInterval
 * pattern (point_of_sale/utils/time_hook.js).
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
        onVerify: Function,
        onCancel: Function,
    };

    setup() {
        this.state = useState({
            remaining: this.props.expiresIn,
            verifying: false,
            hint: "",
        });
        this._tick = setInterval(() => {
            if (this.state.remaining > 0) {
                this.state.remaining -= 1;
            } else {
                clearInterval(this._tick);
            }
        }, 1000);
        onWillUnmount(() => clearInterval(this._tick));
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
            return; // interface is closing this popup; don't touch state
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
            this.state.hint = _t("Account number copied.");
        } catch {
            // Clipboard blocked (e.g. non-secure context) — cashier can read it out.
        }
    }
}
