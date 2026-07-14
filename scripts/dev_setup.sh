#!/usr/bin/env bash
# Local dev helper: start Odoo with these addons + ngrok, per
# docs/architecture.md section 8. NOT YET FILLED IN — this needs your
# actual local Odoo 18 source path and addons-path/db name before it does
# anything real.
set -euo pipefail

echo "TODO: set ODOO_BIN, ODOO_CONFIG/DB name, and this repo's addons/ path,"
echo "      then run something like:"
echo "      \$ODOO_BIN -c <config> -d <db> --addons-path=<odoo-addons>,addons -u monnify_base,monnify_pos"
echo
echo "TODO: in another terminal: ngrok http 8069"
echo "      then paste the printed HTTPS URL into the Monnify dashboard's"
echo "      Developer > Webhook URLs field, pointed at /monnify/webhook."
