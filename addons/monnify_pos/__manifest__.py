{
    "name": "Monnify POS Payment",
    "summary": "Pay by Transfer (Monnify) payment method for Odoo Point of Sale.",
    "version": "18.0.1.0.0",
    "category": "Point of Sale",
    "author": "Emmanuel Sobowale",
    "license": "LGPL-3",
    "depends": ["point_of_sale", "monnify_base"],
    "data": [
        "views/pos_payment_method_views.xml",
    ],
    "assets": {
        # TODO: confirm this is the correct Odoo 18 POS assets bundle name
        # before relying on it — verify against point_of_sale's own
        # __manifest__.py (see CLAUDE.md non-negotiable rules).
        "point_of_sale._assets_pos": [
            "monnify_pos/static/src/app/payment_monnify.js",
            "monnify_pos/static/src/app/monnify_popup.js",
            "monnify_pos/static/src/app/monnify_popup.xml",
            "monnify_pos/static/src/services/monnify_bus.js",
        ],
    },
    "installable": True,
    "application": False,
}
