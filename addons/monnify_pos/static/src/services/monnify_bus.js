/**
 * Subscribes the POS session to live payment-confirmation updates pushed
 * from the backend (see monnify.pos.payment._notify_pos on the Python
 * side).
 *
 * NOT YET IMPLEMENTED. TODO: confirm the current Odoo 18 frontend bus
 * service API (commonly `bus_service`, e.g.
 * `this.env.services.bus_service.subscribe(type, callback)`) against Odoo
 * 18 source before writing this — it moved between 16/17/18. See
 * docs/architecture.md section 5.5 and CLAUDE.md non-negotiable rules.
 *
 * On receiving {local_id, pos_order_uid, status: "paid"}: find the
 * matching pending payment line and call its handlePaid. If the popup is
 * open, flip it to a success state briefly, then close and complete.
 */
