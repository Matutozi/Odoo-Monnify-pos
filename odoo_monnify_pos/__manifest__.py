{
    "name": "Monnify Payments for POS",
    "summary": "Monnify transfer payments for POS, website checkout, and invoices",
    "version": "17.0.1.0.0",
    "category": "Accounting/Payment Providers",
    "author": "Matutozi",
    "license": "LGPL-3",
    "depends": ["payment", "point_of_sale", "website_sale"],
    "data": [
        "views/payment_provider_views.xml",
        "views/payment_templates.xml",
        "data/payment_provider_data.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "odoo_monnify_pos/static/src/js/pos_monnify_payment.js",
        ],
    },
    "installable": True,
    "application": False,
}
