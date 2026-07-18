# Monnify API Reference

This file documents exactly what parameters each Monnify call needs and what it
returns. The VERIFIED sections were confirmed by real sandbox test calls.
Anything marked UNVERIFIED still needs confirming against a live response before
it is relied on.

Environment for this whole project: SANDBOX ONLY.
Base URL: https://sandbox.monnify.com
(Live is https://api.monnify.com. Never use it here.)

All amounts are in NAIRA, not kobo. (Confirmed: amount 10000 == N10,000.)
Minimum invoice amount is N20.

--------------------------------------------------------------------------------
## 1. Authentication  [VERIFIED]

Purpose: get a Bearer token used by every other call. Token lasts ~1 hour.
Cache it and refresh when it has under ~60 seconds left. Do not log in on every
request.

Request:
  METHOD: POST
  URL:    https://sandbox.monnify.com/api/v1/auth/login
  AUTH:   HTTP Basic. Username = API key, Password = secret key.
          i.e. header "Authorization: Basic base64(API_KEY:SECRET_KEY)"
  BODY:   none

Response body path to the token:
  responseBody.accessToken   (string)
  responseBody.expiresIn     (seconds, use to schedule refresh)

Credentials come from config, NEVER hardcoded:
  - API_KEY        (starts with MK_TEST_ in sandbox)
  - SECRET_KEY
  - CONTRACT_CODE  (10-digit, from dashboard Settings > Contract Setup)
All three must belong to the SAME sandbox account, or calls fail with
"Unknown Contract Code provided".

--------------------------------------------------------------------------------
## 2. Create Invoice (dynamic)  [VERIFIED]  <-- this is the POS payment call

Purpose: create a one-time virtual account for a specific order amount. Returns
the account details the cashier shows the customer. One call, no KYC.

Request:
  METHOD: POST
  URL:    https://sandbox.monnify.com/api/v1/invoice/create
  AUTH:   header "Authorization: Bearer <accessToken>"
  HEADER: "Content-Type: application/json"
  BODY (all fields required unless noted):
    invoiceReference   string  MUST be unique per invoice. This is our own
                               reference and our idempotency key. Use a scheme
                               like "POS-<session_id>-<order_uid>-<epoch>".
                               Reusing one returns "Invoice with this reference
                               already exists".
    amount             number  In naira. Must be > 20.
    invoiceDescription string  Free text.
    contractCode       string  From config (Settings > Contract Setup).
    customerEmail      string  Can be a placeholder for walk-in POS customers.
    customerName       string  Can be a generic "POS Customer" for walk-ins.
    expiryDate         string  Format EXACTLY "yyyy-MM-dd HH:mm:ss". MUST be in
                               the future. Generate it, never hardcode:
                               (now + 40 minutes) formatted to that string.
                               Wrong format -> "Invalid invoice expiry date
                               format". Past date -> "Invalid invoice expiry
                               date".
    currencyCode       string  "NGN".

Response (responseBody), fields we rely on:
    accountNumber          string  Virtual account. SHOW ON POS.
    bankName               string  e.g. "Wema bank". SHOW ON POS.
    bankCode               string  e.g. "035".
    accountName            string  SHOW ON POS (may be ugly, cosmetic only).
    amount                 number  Echoed back. SHOW ON POS.
    transactionReference   string  Monnify's ref, format "MNFY|..|..|..".
                                   STORE + INDEX. This is the match key for the
                                   webhook and the status query.
    invoiceReference       string  Our own ref, echoed back. STORE.
    invoiceStatus          string  "PENDING" at creation.
    checkoutUrl            string  Hosted Monnify page. Not needed for POS
                                   transfer flow; used by the stretch website
                                   payment provider only.
    expiryDate              string
    createdOn               string

Mapping into the monnify.pos.payment model:
    name                 <- invoiceReference (we generate it)
    monnify_tx_ref       <- responseBody.transactionReference
    amount               <- responseBody.amount
    account_number       <- responseBody.accountNumber
    bank_name            <- responseBody.bankName
    account_name         <- responseBody.accountName
    state                <- "pending"

Known sample response (real, from sandbox) for shape reference:
  requestSuccessful: true, responseCode: "0"
  responseBody: { amount, invoiceReference, invoiceStatus:"PENDING",
    contractCode, customerEmail, customerName, expiryDate, createdBy,
    createdOn, checkoutUrl, accountNumber, accountName, bankName, bankCode,
    transactionReference, metaData:{} }

--------------------------------------------------------------------------------
## 3. Query Transaction Status  [PARTIALLY VERIFIED]  <-- Verify button + polling

Purpose: ask Monnify whether a transaction has been paid. Powers the fallback
"Verify Payment" button and any polling.

Request:
  METHOD: GET
  URL:    https://sandbox.monnify.com/api/v2/merchant/transactions/query
  AUTH:   header "Authorization: Bearer <accessToken>"
  QUERY PARAM: exactly ONE of these two:
    transactionReference   Monnify's ref, the "MNFY|..." value from the create
                           response. USE THIS ONE. It is what our create call
                           returns and what the webhook sends.
    paymentReference       our own reference, if we generated one at init.
                           NOTE: the invoice/create response does NOT return a
                           paymentReference. [UNVERIFIED] whether our
                           invoiceReference works as this param. Test once; if
                           it does, we can query by our own reference too.

  IMPORTANT: the reference contains pipe characters "|". Do NOT build the URL by
  string concatenation. Pass it via the request library's params argument so it
  is URL-encoded automatically (| becomes %7C). In Python requests:
      requests.get(url, headers=headers,
                   params={"transactionReference": tx_ref}, timeout=30)

This is the AUTHORITATIVE payment check. Per Monnify docs: never trust a
client-side callback or redirect; always verify server-to-server before
fulfilling. Our Verify button and any polling use this endpoint.

Response (responseBody) fields we rely on:
    paymentStatus              string. THE authoritative status. Values below.
    amountPaid                 naira. MUST be checked against our expected
                               amount, never trusted on status alone.
    totalPayable               naira. What the customer was charged.
    transactionReference       string, echoed back.
    paymentReference           string, Monnify's payment ref.
    paymentMethod              string: ACCOUNT_TRANSFER | CARD | USSD |
                               PHONE_NUMBER. Ours will be ACCOUNT_TRANSFER.
    paidOn, completedOn        ISO timestamps.
    settlementAmount, fee      numbers. Not needed for POS logic.
    customerDTO {email,name,mobileNumber}
    paymentSourceInformation   list. For bank transfers, contains the payer's
                               real accountName, accountNumber, bankCode,
                               sessionId. NICE TO HAVE: show "Payment received
                               from <accountName>" on the POS screen, and store
                               for reconciliation.

Confirmed against a real (unpaid) sandbox invoice on 2026-07-14:
    responseBody.paymentStatus   confirmed field name and value "PENDING" for
                                 an unpaid invoice.
    responseBody.amountPaid      confirmed field name, BUT comes back as a
                                 STRING, e.g. "0.00", not a JSON number.
                                 Convert with float()/Decimal() before
                                 comparing to the stored amount.
    responseBody.totalPayable    also a string, e.g. "0.00".
    responseBody.paidOn          null when unpaid.
    responseBody.paymentMethod   e.g. "ACCOUNT_TRANSFER".
  [UNVERIFIED] the exact shape of a PAID response (whether amountPaid then
  reflects the real paid amount as a string too, what paidOn/settlementAmount/
  paymentSourceInformation look like) has NOT been confirmed yet — sandbox
  payment simulation is still an open item. When you write completion code,
  read paymentStatus == "PAID" but ADD A COMMENT that the exact field/values
  for the paid case must be confirmed against a real PAID response, and treat
  amountPaid/totalPayable as strings that need numeric conversion.

paymentStatus values and what our code must do:
    PAID            Full payment received  -> complete the POS payment.
    PENDING         Not yet confirmed      -> keep waiting / re-poll.
    FAILED          Attempt failed         -> show error, allow retry.
    EXPIRED         Session expired        -> state "expired", new payment
                                             needed.
    REVERSED        Reversed after confirm -> state "reversed", do not fulfil.
    PARTIALLY_PAID  Underpaid              -> state "mismatch", DO NOT complete.
    OVERPAID        Overpaid              -> state "mismatch", flag for manager.
  [UNVERIFIED] only "PENDING" has actually been observed against a real
  sandbox call so far (see section 7); the rest are from Monnify's docs.

IMPORTANT CONTRACT BEHAVIOUR (affects our design, in our favour):
  By DEFAULT Monnify REJECTS over- and under-payments. The funds are returned to
  the sender and a REJECTED_PAYMENT webhook is sent instead of a success one.
  PARTIALLY_PAID and OVERPAID only ever appear if the contract is explicitly
  configured to accept them (Settings > Contracts Setup > Edit Contract).
  DECISION: leave the default. This gives us exact-amount enforcement for free,
  which is exactly what a POS order needs. Still handle PARTIALLY_PAID/OVERPAID
  defensively in code, but they should not occur. [UNVERIFIED against a real
  reject event — from Monnify docs, not yet observed in this sandbox account.]

--------------------------------------------------------------------------------
## 4. Webhook (payment notification)  [VERIFIED FROM OFFICIAL MONNIFY DOCS,
   still not yet hit end-to-end against our own server/ngrok]

Purpose: Monnify POSTs here when a payment lands, so the POS can auto-confirm.
The webhook URL is set on the Monnify DASHBOARD (Developer > Webhook URLs), not
via API. For local dev it is the ngrok HTTPS URL + our route.

Our route: POST /monnify/webhook  (Odoo http controller, auth="public",
csrf=False).

Payload shape [confirmed against Monnify's official webhook docs, 2026-07-15]:
  Top level: eventType (string), eventData (object).
  eventTypes we care about:
    "SUCCESSFUL_TRANSACTION"  -> the payment landed, complete the POS payment.
    "REJECTED_PAYMENT"        -> Monnify rejected an over/under payment and
                                 returned the funds to the sender. Set state
                                 "mismatch" and tell the cashier the customer
                                 must pay the exact amount. This is the DEFAULT
                                 behaviour for wrong amounts (see section 3's
                                 "IMPORTANT CONTRACT BEHAVIOUR"), so it is a
                                 real path, not an edge case.
  All other eventTypes exist (SUCCESSFUL_DISBURSEMENT, FAILED_DISBURSEMENT,
  REVERSED_DISBURSEMENT, SUCCESSFUL_REFUND, FAILED_REFUND, SETTLEMENT,
  MANDATE_UPDATE, ACCOUNT_ACTIVITY, LOW_BALANCE_ALERT) but are irrelevant to
  the POS collection flow -> return 200 and ignore, unmatched.

  eventData for SUCCESSFUL_TRANSACTION (confirmed field names, official docs
  sample):
    product { reference, type }        type e.g. "RESERVED_ACCOUNT" or
                                        "OFFLINE_PAYMENT_AGENT"; ours will be
                                        whatever invoice/create implies.
    transactionReference               matches our stored monnify_tx_ref.
    paymentReference                   Monnify's payment ref; may differ from
                                        our invoiceReference.
    paidOn                             string, e.g.
                                        "2021-11-17 11:28:42.615" (space
                                        separator, not ISO "T"; has ms).
                                        NOT used for paid_on in our code — we
                                        stamp fields.Datetime.now() instead, to
                                        avoid parsing an UNVERIFIED-for-writes
                                        format string.
    paymentDescription, metaData       misc, not used.
    paymentSourceInformation           LIST of {bankCode, amountPaid,
                                        accountName, sessionId, accountNumber}
                                        — the payer's real account. Nice to
                                        have for "paid from <accountName>".
    destinationAccountInformation      { bankCode, bankName, accountNumber } —
                                        our own virtual account, not the payer.
    amountPaid                         **JSON NUMBER here** (e.g. 3000, 78000),
                                        NOT a string. This DIFFERS from the
                                        status-query endpoint (section 3), which
                                        returns amountPaid as a STRING. float()
                                        handles both, so normalize with float()
                                        regardless of caller.
    totalPayable                       JSON number, same caveat as amountPaid.
    paymentMethod                      "ACCOUNT_TRANSFER" | "CASH" | etc.
    currency                           "NGN".
    settlementAmount                   number or string depending on event
                                        variant (seen as both int and "1234.00"
                                        string across samples) — not used for
                                        completion logic, ignore precision here.
    paymentStatus                      "PAID".
    customer { name, email }

  eventData for REJECTED_PAYMENT (confirmed field names, official docs
  sample):
    product { reference, type }
    amount                              expected amount (JSON number).
    paymentSourceInformation             SINGULAR object here (not a list):
                                          { bankCode, amountPaid, accountName,
                                          sessionId, accountNumber } — what the
                                          payer actually sent.
    transactionReference                 matches our stored monnify_tx_ref.
    paymentReference
    paymentRejectionInformation           { bankCode, destinationAccountNumber,
                                          bankName, rejectionReason (e.g.
                                          "UNDER_PAYMENT"), expectedAmount }
    paymentDescription, customer{name,email}
  On REJECTED_PAYMENT: write state "mismatch" directly (do NOT route through
  action_mark_paid — that method is specifically the "mark as PAID" completion
  path, our one-completion-function rule; a rejection is inherently not a
  completion).

Security (confirmed against Monnify's official webhook docs, 2026-07-15):
  - Header name is exactly "monnify-signature" (lowercase, confirmed — matches
    what the code already guessed).
  - Hash formula (CONFIRMED): SHA-512 HMAC, KEY = merchant secret key,
    MESSAGE = the raw stringified JSON request body Monnify actually sent
    (equivalent to Python hmac.new(secret_key.encode(), raw_body_bytes,
    hashlib.sha512).hexdigest()). This is exactly what
    monnify_client.compute_transaction_hash already implements — no code
    change needed there, just remove the UNVERIFIED marker.
  - Hash over request.httprequest.data (the exact raw bytes Odoo received),
    never json.dumps(parsed_payload) re-serialized — Monnify's
    JS/PHP/Java samples stringify their OWN payload to produce the reference
    hash, but on our end we must hash the bytes AS RECEIVED, since re-encoding
    (key order, spacing) would silently break every real delivery.
  - Compare with hmac.compare_digest. Reject with 401 on mismatch, no detail
    leak in the response body.
  - Monnify webhook source IP (production): 35.242.133.146 (optional allowlist,
    not implemented — sandbox dev traffic goes through ngrok anyway).
  - Idempotency: Monnify RESENDS if it does not get HTTP 200. Track processed
    transactionReferences (via monnify.pos.payment.state) and no-op on repeat.
  - Return HTTP 200 quickly; do heavy work after acknowledging.

Controller order of operations (must match architecture.md section 5.4;
implemented in controllers/webhook.py):
  1. Read raw body bytes (request.httprequest.data).
  2. Read "monnify-signature" header + verify hash via
     client.verify_webhook(raw_body, received_hash). Invalid/missing -> 401.
  3. Parse JSON. If eventType not in (SUCCESSFUL_TRANSACTION, REJECTED_PAYMENT)
     -> return 200, ignore.
  4. Find monnify.pos.payment by transactionReference (sudo). Not found -> 200.
  5. state != "pending" already -> 200 (dedupe: already paid/mismatch/etc).
  6. If eventType == REJECTED_PAYMENT -> write state "mismatch" directly, 200.
  7. Else call the ONE shared completion method action_mark_paid(event_data) —
     it does its own amountPaid-vs-expected check internally (mismatch ->
     state "mismatch", never auto-completes on a bad amount).
  8. Return 200.

--------------------------------------------------------------------------------
## 5. Response envelope (all endpoints)  [VERIFIED]

Every Monnify response is wrapped:
  requestSuccessful  bool
  responseMessage    string  ("success" on success, or the error message)
  responseCode       string  ("0" on success, "99" on many errors)
  responseBody       object  (present on success)

Client rule: check requestSuccessful is true before reading responseBody. If
false, raise MonnifyError(responseMessage, responseCode). Map known messages to
friendly text: "Unknown Contract Code provided", "Invoice with this reference
already exists", "Amount must be greater than 20", "Invalid invoice expiry
date", "Invalid invoice expiry date format".

--------------------------------------------------------------------------------
## 6. Implementation rules

- SANDBOX base URL only. No live URL anywhere.
- No secret in code, XML, logs, or git. Config only. Never log the auth header,
  secret, or full token.
- One shared completion method marks a payment paid; webhook and verify button
  both call it. Never duplicate that logic.
- Amounts in naira. Centralize any conversion in one helper. Remember
  amountPaid/totalPayable come back as STRINGS from the status query — convert
  before comparing.
- NEVER complete a payment on paymentStatus alone. Always check amountPaid
  against the expected amount too. A PAID status with a wrong amount must be
  treated as a mismatch, not a success.
- Handle REJECTED_PAYMENT as a real webhook path (Monnify's default behaviour
  for wrong amounts), not just PARTIALLY_PAID/OVERPAID as edge cases — see
  section 3's "IMPORTANT CONTRACT BEHAVIOUR" and section 4.
- Never trust a client-side callback or redirect to confirm payment. Only the
  server-to-server query (section 3) or a hash-verified webhook (section 4) is
  authoritative.
- Every request has a timeout.
- Anything marked UNVERIFIED above gets a code comment flagging it must be
  confirmed against a real response.

--------------------------------------------------------------------------------
## 7. Local verification log

- 2026-07-14: `auth.py` smoke test run against real sandbox credentials
  (loaded from `.env`, not hardcoded). Confirmed: login/token issuance,
  invoice creation (full field shape as documented above), and status query
  on an unpaid invoice (`paymentStatus: "PENDING"`, `amountPaid`/
  `totalPayable` as strings `"0.00"`). Still open: triggering an actual
  sandbox transfer to observe the PAID shape of both the status query and a
  real webhook delivery.
- 2026-07-16: First live Odoo run. Hit "Invalid invoice expiry date" from
  invoice/create when called through the addon (the standalone smoke test
  never showed it). Root cause: Odoo forces its process timezone to UTC, so
  a naive `datetime.now()+40min` was an hour behind real WAT; Monnify reads
  expiryDate as Nigerian time and saw an apparently-past date. (Note the
  message is "Invalid invoice expiry date" — the past-date case — NOT
  "...date format".) Fix: `create_invoice` now generates expiryDate itself
  in `ZoneInfo("Africa/Lagos")`, so no caller can reintroduce the bug; the
  `expiry_date` parameter was removed from the client API. Confirms the
  format `yyyy-MM-dd HH:mm:ss` and the future-date requirement against a real
  reject.
- 2026-07-15: Confirmed against Monnify's official webhook documentation
  (pasted into the session, not a live delivery yet): the `monnify-signature`
  header name, the SHA-512 HMAC hash formula (key = secret, message = raw
  body), the full event-type catalog, and the exact `eventData` field names
  for `SUCCESSFUL_TRANSACTION` and `REJECTED_PAYMENT` (see section 4). Also
  learned `amountPaid`/`totalPayable` in the `SUCCESSFUL_TRANSACTION` webhook
  arrive as plain JSON numbers, unlike the status-query endpoint's strings —
  code normalizes both with `float()`. Implemented the webhook controller,
  `_get_monnify_client()`, and `action_mark_paid()` off the back of this.
  Still open: an actual live delivery to our `/monnify/webhook` route (needs
  ngrok + a triggered sandbox transfer) to confirm nothing about our own
  server/routing breaks the theoretical formula above.
