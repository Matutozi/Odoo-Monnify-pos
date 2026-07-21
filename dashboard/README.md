# Monnify Payments Dashboard (React)

A standalone React dashboard for the Monnify POS payments — collections,
settlement status, and a transaction table. It reads live data from Odoo
through a small read-only endpoint (`/monnify/dashboard/data`), so it runs
separately from Odoo but shows real payments.

## 1. Enable the endpoint in Odoo

The endpoint is token-guarded and returns 403 until you set a token.

**Settings → Technical → System Parameters → New:**

| Key | Value |
|---|---|
| `monnify_base.dashboard_token` | `monnify-demo` (or any secret you choose) |

Then restart Odoo so the new controller loads:

```bash
python3 ~/odoo18/community/odoo-bin -c ~/odoo18/odoo.conf -d monnify-ngn -u monnify_base --dev=all
```

## 2. Run the dashboard

```bash
cd dashboard
npm install
npm run dev        # opens http://localhost:5173
```

By default it reads from `http://localhost:8069/monnify/dashboard/data` with the
token `monnify-demo`. If your Odoo is elsewhere, or you chose a different token,
set them when running:

```bash
VITE_API_URL="http://<host>:8069/monnify/dashboard/data" \
VITE_API_TOKEN="<your-token>" \
npm run dev
```

(Or edit `src/config.js`.)

## Build a static bundle

```bash
npm run build      # outputs to dist/
npm run preview    # serve the built bundle locally
```

## Notes

- The endpoint sends permissive CORS headers so the browser can call Odoo from
  another origin. That is fine for a local/sandbox demo; a production deployment
  should restrict the allowed origin.
- It is **read-only** — it never writes, and only reads `monnify.pos.payment`.
- "Settlement" shows *Pending* for paid transactions: Monnify settles to the
  bank on its own schedule (and sandbox does not run real settlement cycles),
  so nothing has cleared yet.
