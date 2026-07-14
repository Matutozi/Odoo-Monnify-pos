{
    "name": "Monnify Base",
    "summary": "Shared Monnify API client, credentials config, transaction log, and webhook controller.",
    "version": "18.0.1.0.0",
    "category": "Accounting/Payment",
    "author": "Emmanuel Sobowale",
    "license": "LGPL-3",
    "depends": ["base", "web"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        "views/monnify_pos_payment_views.xml",
    ],
    "installable": True,
    "application": False,
}
