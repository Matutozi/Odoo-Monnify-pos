/**
 * Monnify "Pay by Transfer" payment interface for Odoo POS.
 *
 * NOT YET IMPLEMENTED. TODO before writing any code here: read Odoo 18's
 * actual PaymentInterface contract — grep the Odoo source, and read Odoo's
 * own Adyen / Stripe Terminal POS modules as reference patterns — and
 * confirm the real class name, import path, and method signatures
 * (send_payment_request, send_payment_cancel, etc.) for this Odoo version.
 * See docs/architecture.md section 5.5 and CLAUDE.md non-negotiable rules:
 * do not invent Odoo APIs, they moved between 16/17/18.
 *
 * Intended shape once confirmed (section 5.5):
 *   - send_payment_request(uuid): RPC to create_monnify_payment, store the
 *     returned account details on the payment line, set the line to a
 *     waiting/spinner status, open the account-details popup.
 *   - send_payment_cancel(): mark the local record cancelled via RPC,
 *     close the popup.
 *   - handlePaid(localId): resolve the pending payment (line -> done),
 *     called by the bus handler or the Verify button.
 */
