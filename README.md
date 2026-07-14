# Odoo-Monnify-pos

This repository now contains an Odoo addon: `/home/runner/work/Odoo-Monnify-pos/Odoo-Monnify-pos/odoo_monnify_pos`.

## What it provides
- Monnify payment provider configuration in Odoo.
- Pay-by-transfer transaction initialization for POS (`/pos/monnify/initiate`) and real-time status polling (`/pos/monnify/status`).
- Website/invoice checkout rendering support using Monnify transfer details.
- Secure Monnify webhook endpoint at `/payment/monnify/webhook` with HMAC-SHA512 signature verification.