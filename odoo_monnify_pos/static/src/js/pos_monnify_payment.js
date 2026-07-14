/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";

patch(PaymentScreen.prototype, {
    async addNewPaymentLine(paymentMethod) {
        const result = await super.addNewPaymentLine(...arguments);
        const isMonnifyMethod = (paymentMethod?.name || "").toLowerCase().includes("monnify");
        if (!isMonnifyMethod) {
            return result;
        }

        const paymentLine = this.currentOrder?.selected_paymentline;
        if (!paymentLine) {
            return result;
        }

        const transfer = await this._monnifyCreateTransfer(paymentLine);
        if (transfer.error) {
            this.env.services.notification.add(transfer.error, { type: "danger" });
            return result;
        }

        paymentLine.set_payment_status?.("waiting");
        paymentLine.set_payment_ref?.(transfer.reference);

        const status = await this._monnifyPollStatus(transfer.reference);
        if (status.is_done) {
            paymentLine.set_payment_status?.("done");
        } else {
            paymentLine.set_payment_status?.("retry");
        }
        return result;
    },

    async _monnifyCreateTransfer(paymentLine) {
        const order = this.currentOrder;
        const payload = {
            amount: paymentLine.amount,
            reference: order.name,
            currency: this.pos.currency.name,
            partner_id: order.get_partner()?.id || false,
        };
        return this.env.services.rpc("/pos/monnify/initiate", payload);
    },

    async _monnifyPollStatus(reference) {
        for (let attempt = 0; attempt < 30; attempt += 1) {
            const status = await this.env.services.rpc("/pos/monnify/status", { reference });
            if (status.is_done) {
                return status;
            }
            await new Promise((resolve) => setTimeout(resolve, 2000));
        }
        return { is_done: false };
    },
});
