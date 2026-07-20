#!/usr/bin/env bash
#
# Start Odoo locally with the Monnify addons loaded.
#
#   ./scripts/dev_setup.sh          start the server
#   ./scripts/dev_setup.sh -u       start and upgrade the Monnify modules
#                                   (needed after changing views or assets)
#
# Override any of the settings below via the environment, e.g.
#   DB_NAME=my-db ./scripts/dev_setup.sh
#
# Your odoo.conf must list this repository's addons/ directory in its
# addons_path, otherwise Odoo will not find monnify_base / monnify_pos.

set -euo pipefail

ODOO_SRC="${ODOO_SRC:-$HOME/odoo18/community}"
ODOO_CONF="${ODOO_CONF:-$HOME/odoo18/odoo.conf}"
DB_NAME="${DB_NAME:-monnify-ngn}"

REPO_ADDONS="$(cd "$(dirname "$0")/.." && pwd)/addons"

if [ ! -f "$ODOO_SRC/odoo-bin" ]; then
    echo "odoo-bin not found at $ODOO_SRC" >&2
    echo "Set ODOO_SRC to your Odoo 18 source checkout." >&2
    exit 1
fi

if [ ! -f "$ODOO_CONF" ]; then
    echo "Config file not found at $ODOO_CONF" >&2
    echo "Set ODOO_CONF to your Odoo configuration file." >&2
    exit 1
fi

if ! grep -q "$REPO_ADDONS" "$ODOO_CONF"; then
    echo "Warning: $REPO_ADDONS is not in the addons_path of $ODOO_CONF." >&2
    echo "         Odoo may not find the Monnify modules." >&2
fi

UPGRADE=()
if [ "${1:-}" = "-u" ]; then
    UPGRADE=(-u monnify_base,monnify_pos)
fi

echo "Odoo source : $ODOO_SRC"
echo "Config      : $ODOO_CONF"
echo "Database    : $DB_NAME"
echo
echo "For automatic payment confirmation, run 'ngrok http 8069' in another"
echo "terminal and set the printed HTTPS URL + /monnify/webhook on the Monnify"
echo "dashboard under Developer > Webhook URLs."
echo

exec python3 "$ODOO_SRC/odoo-bin" \
    -c "$ODOO_CONF" \
    -d "$DB_NAME" \
    "${UPGRADE[@]}" \
    --dev=all
