# Monnify Pay-by-Transfer for Odoo POS
## Full Architecture and Build Guide

**Project codename:** `odoo-monnify-suite`
**Target:** API Conference Lagos 2026 Developer Challenge (Monnify)
**Deadline:** 12pm WAT, July 21, 2026
**Builder:** Emmanuel Sobowale
**Odoo version:** 18 (Community). Fall back to 17 only if something breaks badly in 18.

---

## 1. What this project is, in one paragraph

An Odoo addon suite that adds a "Pay by Transfer (Monnify)" payment method to Odoo Point of Sale. When the cashier selects it, Odoo calls Monnify to create a one-time dynamic virtual account tied to that exact order. The account details show on the POS screen. The customer transfers from their banking app. Monnify sends a webhook to Odoo, Odoo verifies it, marks the payment as done, and pushes a live update to the open POS session so the screen flips to "Payment received" automatically. A fallback "Verify Payment" button polls Monnify directly in case the webhook is delayed. Stretch goal: a standard Odoo website/invoice payment provider using Monnify's hosted checkout, plus an end-of-day reconciliation report.

---

## 2. Facts confirmed from Monnify's documentation (July 2026)

These shape the architecture. Re-verify each one in the docs before building, because APIs change.

1. **Auth:** Base64-encode `apiKey:secretKey`, call the login endpoint, get a Bearer token valid for **1 hour**. The client must cache the token and refresh when expired.
2. **Best-fit API for POS:** the **Checkout API "Pay with Bank Transfer" flow**. You first initialize a transaction (amount, reference, customer info), then call the Pay with Bank Transfer endpoint with the `transactionReference`. Monnify returns a **dynamic virtual account number valid for up to 40 minutes (2400 seconds)**. No BVN/NIN needed. This is better than Reserved Accounts (which require customer BVN/NIN for KYC) and simpler than Invoices for this use case.
3. **Dynamic invoices** also auto-generate a one-time virtual account per invoice with no KYC. Keep this as plan B if the Checkout transfer endpoint misbehaves in sandbox.
4. **Webhooks:** Monnify POSTs a JSON payload with `eventType` (e.g. `SUCCESSFUL_TRANSACTION`) and `eventData` (contains `transactionReference`, `paymentReference`, `amountPaid`, `paymentStatus`, etc.). Security is a **SHA-512 transaction hash computed from the raw request body and your client secret**. Best practices from their docs: validate the hash, optionally whitelist their webhook IP (35.242.133.146), check for duplicate notifications (they resend if you do not return HTTP 200), and return 200 fast, doing heavy work after acknowledging.
5. Webhook URLs are configured on the **Monnify dashboard** (Developer page, Webhook URLs section), not via API. For the demo this will be your ngrok URL.
6. There is a **Verify Transactions / Get Transaction Status** endpoint. This powers the fallback button.
7. Sandbox base URL and live base URL differ. Everything in this project uses **sandbox only** (hackathon rule).

**Open questions to answer on day 1 in the docs or Slack:**
- Exact sandbox base URL and the exact endpoint paths for: login, init transaction, pay with bank transfer, get transaction status.
- How to simulate an incoming transfer in sandbox (dashboard button, test endpoint, or test bank app). This is critical for the demo.
- The exact hash formula (which fields, or whole raw body) and header name the hash arrives in.
- Whether the dynamic account rejects wrong-amount transfers or accepts partial payment (affects how we treat `amountPaid` vs `totalPayable`).

---

## 3. High-level architecture

Actors and components:

1. **Cashier** uses the **Odoo POS frontend** (browser app, Owl framework) on a laptop or tablet.
2. **POS frontend** talks to the **Odoo backend** over standard RPC.
3. **Odoo backend** hosts three custom pieces:
   - `monnify_base` addon: Monnify API client, credentials config, transaction log model, webhook controller.
   - `monnify_pos` addon: POS payment method, POS frontend patches, live-update bus logic, verify button.
   - `payment_monnify` addon (stretch): website/invoice payment provider.
4. **Monnify sandbox** receives API calls and sends webhooks.
5. **ngrok** (or Cloudflare Tunnel) exposes the local Odoo on a public HTTPS URL so Monnify webhooks can reach it.
6. **Customer's phone** (simulated in sandbox) makes the transfer.

Happy-path sequence for one sale:

1. Cashier taps "Pay by Transfer (Monnify)" on the POS payment screen.
2. POS frontend calls a backend RPC method `create_monnify_payment(pos_reference, amount)`.
3. Backend: init transaction on Monnify -> call Pay with Bank Transfer -> get account number, bank name, expiry seconds. Backend also creates a local `monnify.pos.payment` record with state `pending`.
4. Backend returns `{account_number, bank_name, account_name, amount, expires_in, monnify_tx_ref, local_id}` to the POS frontend.
5. POS frontend renders the account details, a countdown timer, and a "Verify Payment" button. State: waiting.
6. Customer transfers. Monnify POSTs the webhook to `https://<ngrok-host>/monnify/webhook`.
7. Webhook controller: verify SHA-512 hash -> find local record by `transactionReference` -> check not already processed (idempotency) -> check `paymentStatus == "PAID"` and amount matches -> set state `paid` -> return 200.
8. In the same flow (after commit), backend sends a bus notification on channel `monnify_pos_payments` with the local record id and status.
9. POS frontend, subscribed to that channel, receives the event, matches it to the pending payment line, marks the payment line as done, and shows "Payment received". Cashier validates the order, receipt prints.

Fallback path (webhook never arrives): cashier taps "Verify Payment" -> POS frontend calls backend RPC `verify_monnify_payment(local_id)` -> backend calls Monnify's Get Transaction Status -> if PAID, same completion logic as step 7 runs -> response goes straight back to the POS. This must reuse the exact same completion function as the webhook so there is only one code path that marks things paid.

---

## 4. Repository layout

One public GitHub repo. Monorepo of Odoo addons plus docs.

```
odoo-monnify-suite/
  README.md                  <- judged directly, write it like a tutorial
  docs/
    architecture.md          <- this file
    demo-script.md
    screenshots/
  addons/
    monnify_base/
      __init__.py
      __manifest__.py
      models/
        __init__.py
        res_config_settings.py     # sandbox API key, secret, contract code
        monnify_pos_payment.py     # local transaction log
      services/
        __init__.py
        monnify_client.py          # pure-Python API client
      controllers/
        __init__.py
        webhook.py                 # /monnify/webhook
      security/
        ir.model.access.csv
      views/
        res_config_settings_views.xml
        monnify_pos_payment_views.xml   # backend list/form for the log
      tests/
        test_client.py
        test_webhook.py
    monnify_pos/
      __init__.py
      __manifest__.py
      models/
        __init__.py
        pos_payment_method.py      # adds use_monnify flag / method type
        pos_session.py             # loads monnify fields into POS data
      static/src/
        app/
          payment_monnify.js       # PaymentInterface subclass
          monnify_popup.xml        # Owl template: account details + timer
          monnify_popup.js
        services/
          monnify_bus.js           # subscribes to bus channel
      views/
        pos_payment_method_views.xml
      tests/
    payment_monnify/               # STRETCH, only if POS is done by day 6
      (standard Odoo payment provider skeleton)
  scripts/
    dev_setup.sh                   # spins up Odoo + ngrok locally
  .gitignore                       # must exclude any .env / credentials
```

Why three addons instead of one: `monnify_base` holds everything shared (client, webhook, log). `monnify_pos` depends on it. If you later add `payment_monnify`, it depends on `monnify_base` too and reuses the client and webhook routing. This is also cleaner to explain to judges.

---

## 5. Component specs

### 5.1 `monnify_client.py` (build FIRST, standalone, before any Odoo code)

A plain Python class using `requests`. No Odoo imports, so it can be tested from a terminal script on day 1.

```python
class MonnifyClient:
    def __init__(self, api_key, secret_key, contract_code, base_url):
        ...

    def _get_token(self):
        # base64(api_key:secret_key) -> POST login endpoint
        # cache token + expiry timestamp, refresh if < 60s left
        ...

    def init_transaction(self, amount, reference, customer_name,
                         customer_email, description):
        # returns transactionReference and checkoutUrl
        ...

    def pay_with_bank_transfer(self, transaction_reference, bank_code=None):
        # returns accountNumber, bankName, accountName,
        # expiresIn (seconds), ussdPayment (if bank_code given)
        ...

    def get_transaction_status(self, transaction_reference):
        # returns paymentStatus, amountPaid, totalPayable, paidOn
        ...

    @staticmethod
    def compute_transaction_hash(raw_body: bytes, secret_key: str) -> str:
        # SHA-512 per Monnify docs. Confirm exact formula in docs first.
        ...

    def verify_webhook(self, raw_body: bytes, received_hash: str) -> bool:
        # constant-time compare (hmac.compare_digest)
        ...
```

Rules for this file:
- Timeouts on every request (10s connect, 30s read).
- Raise a single custom exception `MonnifyError(message, status_code, response_body)` so callers handle one thing.
- Log request/response at debug level but **never log the secret key or full auth header**.
- Amounts: Odoo works in floats/decimals of NGN. Confirm whether Monnify expects naira or kobo (their sample payloads show plain amounts like 78000, which reads as naira, but confirm). Centralize conversion in one function either way.

Acceptance test for phase 1: a throwaway script `scripts/smoke_test.py` that inits a 500 NGN transaction, gets a bank transfer account, prints it, then polls status. If this works in sandbox, phase 1 is done.

### 5.2 `res_config_settings.py` and settings view

Fields (stored as `ir.config_parameter` values, all sandbox):
- `monnify_api_key` (char)
- `monnify_secret_key` (char, password widget in the view)
- `monnify_contract_code` (char)
- `monnify_base_url` (char, default sandbox URL)
- A "Test Connection" button that calls `_get_token()` and toasts success/failure.

Helper on the settings model or a mixin: `_get_monnify_client()` that reads the params and returns a configured `MonnifyClient`. Every other component gets the client through this one function.

### 5.3 `monnify_pos_payment` model (the local transaction log)

This is the source of truth for idempotency, the fallback button, and the reconciliation report.

Fields:
- `name` (char): our payment reference sent to Monnify, e.g. `POS/<session>/<order_uid>/<timestamp>`. Must be unique.
- `monnify_tx_ref` (char, indexed): Monnify's `transactionReference`.
- `pos_order_uid` (char): the frontend order uid so the POS can match bus events.
- `pos_session_id` (many2one `pos.session`).
- `amount` (monetary), `currency_id`.
- `account_number`, `bank_name`, `account_name` (char): what was shown to the customer.
- `state` (selection): `pending`, `paid`, `expired`, `mismatch`, `cancelled`.
- `amount_paid` (monetary): from webhook/verify, for detecting under/overpayment.
- `paid_on` (datetime), `raw_webhook` (text, for debugging), `processed_webhook_ids` (text or separate model if time allows, to dedupe).

Methods:
- `action_mark_paid(payload)`: THE single completion function. Validates amount, sets state, stores payload, triggers the bus notification. Called by both the webhook controller and the verify RPC. Idempotent: if already `paid`, do nothing and return quietly.
- `_notify_pos(self)`: sends bus message. In Odoo 17/18 the pattern is `self.env["bus.bus"]._sendone(channel, notification_type, payload)`. Channel: use the POS session's standard channel or a custom one like `("monnify_pos", session.id)`. Confirm the exact bus API for the chosen Odoo version at build time, it moved between 16, 17, and 18.
- Cron (optional, 10-minute interval): mark `pending` records older than 45 minutes as `expired`.

### 5.4 Webhook controller (`/monnify/webhook`)

```python
class MonnifyWebhookController(http.Controller):

    @http.route("/monnify/webhook", type="http", auth="public",
                methods=["POST"], csrf=False)
    def monnify_webhook(self, **kwargs):
        ...
```

Order of operations, exactly:
1. Read the **raw** request body (`request.httprequest.data`). Hash must be computed over raw bytes, not re-serialized JSON.
2. Read the hash header (confirm header name in docs, commonly `monnify-signature`).
3. Verify hash with `hmac.compare_digest`. If invalid, return 401 and log a warning. Do not reveal why in the response body.
4. Parse JSON. If `eventType != "SUCCESSFUL_TRANSACTION"`, return 200 immediately (acknowledge and ignore).
5. Find `monnify.pos.payment` by `transactionReference` (use `sudo()`, auth is public). Not found: return 200 anyway (it may belong to the stretch payment provider later; route there if that module is installed).
6. Duplicate check: if record already `paid`, return 200.
7. Call `action_mark_paid(event_data)`.
8. Return 200 with a tiny JSON body. Total handler time must stay well under a few seconds. Anything slow (emails, reports) goes to a queued job or post-commit hook, not inline.

Security notes for the README: hash validation, idempotency, optional IP allowlist for production (35.242.133.146 per their docs), public route justified because authenticity comes from the hash.

### 5.5 `monnify_pos` frontend (the hard part, budget the most time here)

Odoo 17/18 POS frontend is Owl. The clean integration point is the **`PaymentInterface`** class: electronic payment methods (like existing Adyen/Stripe terminal integrations in Odoo core) subclass it. Read Odoo's own Adyen/Stripe POS terminal modules in the Odoo source as the reference pattern before writing anything.

Pieces:

1. **`pos_payment_method.py`:** add a selection option or boolean so a payment method can be marked as Monnify type, and make sure that flag reaches the frontend (in 17/18 this means adding the field to the data loaded by the POS, via `_load_pos_data_fields` or the equivalent loader method for the chosen version; verify the exact hook name in the Odoo source).

2. **`payment_monnify.js`:** subclass `PaymentInterface`:
   - `send_payment_request(uuid)`: call backend RPC (`this.env.services.orm.call`) to `create_monnify_payment`, store the returned account details on the payment line, set payment line status to `waitingCard`/`waiting` (use whatever status the version uses to show a spinner), and open the account-details popup.
   - `send_payment_cancel()`: mark the local record `cancelled` via RPC, close popup.
   - A method `handlePaid(localId)` that resolves the pending payment (sets the line to `done`), called by the bus handler or the verify button.

3. **Account details popup (Owl component):** shows bank name, account number (big font, tap to copy), account name, exact amount, countdown from `expires_in`, a "Verify Payment" button, and a cancel button. Keep it one template plus one small component.

4. **`monnify_bus.js`:** on POS startup, subscribe to the bus channel for the session (in 17/18 the frontend service is `bus_service`; `this.env.services.bus_service.subscribe(type, callback)` after adding the channel). On receiving `{local_id, pos_order_uid, status: "paid"}`, find the matching pending payment line and call `handlePaid`. If the popup is open, flip it to a green success state for 1.5 seconds, then close and complete.

5. **Verify button:** calls RPC `verify_monnify_payment(local_id)`. Backend polls Monnify, runs `action_mark_paid` if paid, returns the state. Frontend acts on the returned state directly (does not wait for the bus). This means the demo works even if ngrok dies.

Cut line (decided in advance): if the bus live-update fights you past day 5, ship with the Verify button as the only completion trigger and add a 5-second auto-poll loop in the popup instead. Judges still see auto-confirmation, just powered by polling.

### 5.6 Backend RPC endpoints for the POS

On `pos.session` or a dedicated model, two methods callable from the frontend:
- `create_monnify_payment(pos_order_uid, amount, customer_name=None)`: builds the reference, calls client init + bank transfer, creates the log record, returns the display payload.
- `verify_monnify_payment(local_id)`: polls Monnify, completes if paid, returns `{state, amount_paid}`.

Both wrap Monnify errors into friendly messages (`"Could not reach Monnify, check your internet"`), never raw tracebacks to the cashier.

### 5.6.1 Accounting/reconciliation approach (decided)

Deliberately does NOT copy the `pos_online_payment` core module's pattern (creating an `account.payment` immediately at webhook time via `pos_order.add_payment()`, bypassing session close). That pattern exists for payment methods whose money movement is already fully accounted for by the payment-provider infrastructure at settlement time; adopting it here would mean building and maintaining a parallel accounting path instead of using the one Odoo already has.

Instead: the Monnify `pos.payment.method` is configured exactly like any plain manual "Bank Transfer" method — `journal_id` set to a real `type='bank'` journal, `outstanding_account_id` auto-filled by Odoo's own `_onchange_journal_id` (no custom code). Every Monnify payment becomes a normal `pos.payment` row through the standard POS payment-line lifecycle. At session close, Odoo's own unmodified `_create_account_move` → `_accumulate_amounts` → `_create_bank_payment_moves` aggregates every Monnify payment of the session into one `account.payment` in Outstanding Receipts — the exact same path a manual bank-transfer method already uses. No `account.payment` is created early, and no new fields are needed on `monnify.pos.payment` or `pos.payment` for this.

`monnify.pos.payment` remains what it already is — a per-transaction audit log, unrelated to accounting on its own — but it joins to the aggregate for free: `_create_combine_account_payment` stamps `pos_session_id` on the `account.payment` it creates, and `monnify.pos.payment` already has `pos_session_id` too. So an accountant can always drill from one session's aggregate Outstanding Receipts line down to the individual Monnify transactions (transaction ref, exact amount, timestamp) that made it up, without any extra plumbing.

One real settlement-specific opportunity, not yet built: Monnify's own `SETTLEMENT` webhook event lists the exact `transactionReference`s included in a payout, which is a more precise signal than generic bank-statement amount/date fuzzy-matching for closing out the Outstanding Receipts entry. Worth a future phase, not required for the POS flow to work correctly.

### 5.7 Reconciliation report (nice-to-have, day 6 or 7 only)

A backend list view on `monnify.pos.payment` already gives 80% of this for free (filter by session, group by state). The upgrade: a "Session Summary" button on `pos.session` that renders counts and totals of paid / expired / mismatch records. Optional AI touch, only if everything else is done: one API call that takes the day's mismatch/expired rows and returns a three-sentence plain-language summary for the manager. Keep AI out of the payment path entirely.

### 5.8 `payment_monnify` (STRETCH)

Standard Odoo `payment.provider` using Monnify's hosted checkout: init transaction -> redirect customer to `checkoutUrl` -> webhook or return-URL confirms -> `payment.transaction` set to done. Reuses `MonnifyClient` and the webhook controller (route on `paymentReference` prefix: POS references start with `POS/`, ecommerce with `WEB/`). Reference implementation to copy patterns from: Odoo's own `payment_flutterwave` or `payment_paystack` community modules, they are the closest analogues (Nigerian PSPs, redirect flow). Do not start this before the POS flow works end to end through ngrok.

---

## 6. Security checklist (judges explicitly check for exposed secrets)

- No keys in code, XML, or git history. Keys live only in `ir.config_parameter` set through the settings UI. `.gitignore` covers `.env`, `*.local.conf`.
- Webhook: SHA-512 hash verification with constant-time compare, idempotency check, 401 on bad hash, no detail leakage.
- `sudo()` used narrowly in the webhook (only to read/write the log model), never to execute arbitrary logic from payload data.
- Never trust `amountPaid` blindly: compare against the local record's amount, flag `mismatch` state if different, never auto-complete a mismatched payment.
- Access rules: `monnify.pos.payment` readable by POS users, writable only by system/backend logic.
- Sandbox keys only, per hackathon rules. Say so in the README.

---

## 7. Build plan: 8 days, phase by phase

General strategy:
- One phase per session, each ending in a small, verifiable outcome; write the test or smoke script for each phase before moving on.
- For anything touching Odoo internals (POS loader hooks, bus API, PaymentInterface), **read the relevant Odoo 18 source files first** (grep the odoo repo for `PaymentInterface`, `_load_pos_data`, `bus_service`) and confirm the actual signatures before writing code — these moved between versions.
- Commit at the end of every working phase.

**Day 1 (Mon Jul 13 or Tue Jul 14): docs + client.**
Get sandbox keys. Answer the four open questions from section 2. Build `monnify_client.py` standalone plus `smoke_test.py`. Definition of done: script prints a real sandbox virtual account and polls its status.

**Day 2: base addon.**
`monnify_base` skeleton, settings view, test-connection button, `monnify.pos.payment` model with backend views, webhook controller. Test the webhook with `curl` posting a sample payload with a locally computed hash. Set up ngrok, register the URL on the Monnify dashboard, trigger a sandbox payment on the day-1 account, watch the webhook land. Definition of done: a sandbox payment flips a log record to `paid` with no manual step.

**Day 3: POS backend wiring + frontend reading.**
`pos_payment_method` extension, the two RPC methods, POS data loading. Read Odoo's Stripe/Adyen POS terminal modules and summarize the PaymentInterface contract for your version first. Definition of done: selecting the method in POS triggers the RPC and the log record is created (even with an ugly or missing popup).

**Day 4: POS frontend popup + PaymentInterface.**
The popup component, countdown, cancel flow, wiring `send_payment_request`. Definition of done: full visual flow up to "waiting for payment".

**Day 5: live completion.**
Bus notification backend + frontend subscription, plus the Verify button (build Verify FIRST, it is the safety net). Full end-to-end test: POS order -> transfer simulated in sandbox -> webhook -> POS auto-completes. Definition of done: the money-shot demo works on your machine.

**Day 6: hardening + stretch decision.**
Error states (Monnify down, expired account, wrong amount), the expiry cron, session summary view. Decision point: only start `payment_monnify` if everything above is green. Otherwise polish.

**Day 7: README + demo video.**
README as a step-by-step local setup tutorial (fresh Odoo, addon install, keys, ngrok, dashboard webhook config, sandbox simulation steps), architecture diagram, screenshots. Record the 2 to 5 minute video: 20 seconds on the problem (cashier checking bank alerts), then the live flow, then 20 seconds on how it works. Post on social with #APIConfXMonnify #DeveloperChallenge, join their Slack if not already.

**Day 8 (buffer, submit morning of Jul 21 at the latest, deadline is 12pm WAT):**
Re-run the README on a clean environment (fresh virtualenv or container) to prove the setup guide actually works. Fix, submit.

---

## 8. Demo environment

- Odoo 18 Community running locally (source install or Docker, whichever you already use at ICIT).
- PostgreSQL local.
- ngrok: `ngrok http 8069`. Paste the HTTPS URL into the Monnify dashboard webhook field. Note: the free ngrok URL changes on every restart, so re-paste it each session, or pay for a static domain for the week, or use a Cloudflare Tunnel with a stable hostname.
- Set Odoo's `web.base.url` is NOT required for the webhook (Monnify calls the ngrok URL directly), but proxy mode (`proxy_mode = True`) should be on so Odoo behaves behind ngrok.
- Sandbox payment simulation: whatever mechanism Monnify provides (day-1 open question). If none exists, their sandbox usually marks transfers paid via a test flow in the checkout page; confirm in #apiconf-hackathon Slack early.

---

## 9. README skeleton (write it for a judge who has never seen Odoo)

1. What it does (3 sentences + GIF of the auto-confirm moment)
2. Why it matters (the Nigerian transfer-at-POS problem, 4 sentences)
3. Architecture diagram + 1 paragraph
4. Prerequisites (Python version, PostgreSQL, Odoo 18 source, ngrok, Monnify sandbox account)
5. Setup, numbered, copy-pasteable commands, including addons path config and module install
6. Monnify configuration (where to get keys, where to paste them, dashboard webhook setup with screenshot)
7. Running the demo flow, step by step, including how to simulate the sandbox transfer
8. How the webhook security works (short)
9. Project structure
10. Roadmap (payment provider for website/invoices, multi-terminal, live keys checklist)
11. License

---

## 10. Definition of the money shot (what the video must show)

Split screen or cut between: POS payment screen showing the virtual account and a waiting spinner on the left, the sandbox transfer being triggered on the right, then the POS flipping to "Payment received" with zero clicks. That 10 seconds is the whole pitch. Everything in this document exists to make those 10 seconds reliable.

---

*Verify the Monnify endpoint paths, payload field names, and Odoo 18 POS/bus APIs referenced here against the official docs and Odoo source before building on them.*
