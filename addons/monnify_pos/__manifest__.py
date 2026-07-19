{
    "name": "Monnify POS Payment",
    "summary": "Pay by Transfer (Monnify) payment method for Odoo Point of Sale.",
    "version": "18.0.1.0.0",
    "category": "Point of Sale",
    "author": "Emmanuel Sobowale",
    "license": "LGPL-3",
    "depends": ["point_of_sale", "monnify_base"],
    "data": [],
    "assets": {
        # Bundle name confirmed against point_of_sale/__manifest__.py
        # (Odoo 18, "point_of_sale._assets_pos" at its line ~129).
        # Bus subscription lives inside payment_monnify.js, not a separate
        # monnify_bus.js: the bus handler must resolve the in-flight Promise
        # that the PaymentInterface owns, so co-locating it avoids reaching
        # into that instance's private state from another module.
        "point_of_sale._assets_pos": [
            "monnify_pos/static/src/app/payment_monnify.js",
            "monnify_pos/static/src/app/monnify_popup.js",
            "monnify_pos/static/src/app/monnify_popup.xml",
            "monnify_pos/static/src/app/monnify_popup.css",
        ],
    },
    "installable": True,
    "application": False,
}
