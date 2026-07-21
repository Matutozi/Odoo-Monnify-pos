"""Read-only JSON endpoint that feeds the standalone Monnify dashboard.

This exists so a separate frontend (the React dashboard) can read the POS
Monnify payments without going through the Odoo web client. It is:

  - token-guarded: the caller must send a token that matches the
    ``monnify_base.dashboard_token`` system parameter. If that parameter is
    unset the endpoint returns 403, so it is never open by default.
  - CORS-enabled: it answers the preflight and sets Access-Control headers so
    a browser app served from another origin can call it.

It only ever reads, and only from monnify.pos.payment. For a sandbox demo this
is fine; a production deployment would tighten CORS to a known origin.
"""

import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

# Payment states we treat as "collected" (money received).
_COLLECTED = ("paid",)
_ATTENTION = ("mismatch", "expired")


def _cors_headers():
    return [
        ("Access-Control-Allow-Origin", "*"),
        ("Access-Control-Allow-Methods", "GET, OPTIONS"),
        ("Access-Control-Allow-Headers", "Content-Type, X-Monnify-Dashboard-Token"),
    ]


def _json_response(payload, status=200):
    return request.make_response(
        json.dumps(payload),
        headers=[("Content-Type", "application/json")] + _cors_headers(),
        status=status,
    )


class MonnifyDashboardController(http.Controller):

    @http.route("/monnify/dashboard/data", type="http", auth="public",
                methods=["GET", "OPTIONS"], csrf=False)
    def dashboard_data(self, **kwargs):
        # CORS preflight.
        if request.httprequest.method == "OPTIONS":
            return request.make_response("", headers=_cors_headers(), status=204)

        icp = request.env["ir.config_parameter"].sudo()
        expected = icp.get_param("monnify_base.dashboard_token")
        got = (request.httprequest.headers.get("X-Monnify-Dashboard-Token")
               or kwargs.get("token"))
        if not expected or got != expected:
            return _json_response({"error": "Unauthorized"}, status=403)

        payments = request.env["monnify.pos.payment"].sudo().search(
            [], order="create_date desc", limit=200
        )
        currency = (
            payments[:1].currency_id.name
            or request.env.company.currency_id.name
        )

        collected = settled = awaiting = 0.0
        attention = 0
        rows = []
        for p in payments:
            if p.state in _COLLECTED:
                collected += p.amount_paid or p.amount
                # Settlement isn't tracked yet, so a paid payment is "awaiting".
                awaiting += p.amount_paid or p.amount
            if p.state in _ATTENTION:
                attention += 1
            rows.append({
                "id": p.id,
                "customer": p.account_name or "POS Customer",
                "amount": p.amount,
                "amount_paid": p.amount_paid,
                "status": p.state,
                "reference": p.monnify_tx_ref or p.name or "",
                "method": _payment_method(p),
                "settlement_status": "pending" if p.state in _COLLECTED else None,
                "bank_name": p.bank_name or "",
                "date": (p.paid_on or p.create_date).isoformat() if (p.paid_on or p.create_date) else None,
                # Full detail, shown when a row is opened.
                "our_reference": p.name or "",
                "monnify_reference": p.monnify_tx_ref or "",
                "account_number": p.account_number or "",
                "account_name": p.account_name or "",
                "pos_order": p.pos_order_uid or "",
                "session": p.pos_session_id.display_name if p.pos_session_id else "",
                "created": p.create_date.isoformat() if p.create_date else None,
                "paid_on": p.paid_on.isoformat() if p.paid_on else None,
                # What was actually ordered (looked up from the POS order).
                **_order_info(request.env, p.pos_order_uid),
            })

        return _json_response({
            "currency": currency,
            "summary": {
                "collected": round(collected, 2),
                "settled": round(settled, 2),
                "awaiting": round(awaiting, 2),
                "attention": attention,
            },
            "transactions": rows,
        })

    @http.route("/monnify/dashboard/insight", type="http", auth="public",
                methods=["GET", "OPTIONS"], csrf=False)
    def dashboard_insight(self, **kwargs):
        """AI briefing: a plain-English read of the day's collections.

        Same token guard and CORS as the data endpoint. The Claude API key is
        read from the ``monnify_base.claude_api_key`` system parameter — never
        hardcoded. Only an aggregated summary is sent to the model (totals,
        counts, product tallies), never raw payment records; and the model
        only ever *describes* the data, it never decides whether a payment is
        valid. That stays deterministic in action_mark_paid.
        """
        if request.httprequest.method == "OPTIONS":
            return request.make_response("", headers=_cors_headers(), status=204)

        icp = request.env["ir.config_parameter"].sudo()
        expected = icp.get_param("monnify_base.dashboard_token")
        got = (request.httprequest.headers.get("X-Monnify-Dashboard-Token")
               or kwargs.get("token"))
        if not expected or got != expected:
            return _json_response({"error": "Unauthorized"}, status=403)

        api_key = icp.get_param("monnify_base.claude_api_key")
        if not api_key:
            return _json_response({"insight": None, "error": "not_configured"})

        stats = _build_insight_input(request.env)
        insight, err = _generate_insight(stats, api_key)
        return _json_response({"insight": insight, "error": err, "stats": stats})


def _build_insight_input(env):
    """Aggregate recent payments into a small, PII-free summary for the model."""
    payments = env["monnify.pos.payment"].sudo().search(
        [], order="create_date desc", limit=100
    )
    currency = payments[:1].currency_id.name or env.company.currency_id.name
    stats = {
        "currency": currency,
        "total_transactions": len(payments),
        "collected": 0.0,
        "paid_count": 0,
        "pending_count": 0,
        "mismatch_count": 0,
        "expired_count": 0,
        "cancelled_count": 0,
        "largest_payment": 0.0,
    }
    product_qty = {}
    for p in payments:
        key = f"{p.state}_count"
        if key in stats:
            stats[key] += 1
        if p.state == "paid":
            amount = p.amount_paid or p.amount
            stats["collected"] += amount
            stats["largest_payment"] = max(stats["largest_payment"], amount)
            if p.pos_order_uid:
                order = env["pos.order"].sudo().search(
                    [("uuid", "=", p.pos_order_uid)], limit=1
                )
                for line in order.lines:
                    name = line.full_product_name or line.product_id.display_name
                    product_qty[name] = product_qty.get(name, 0) + line.qty
    stats["collected"] = round(stats["collected"], 2)
    stats["largest_payment"] = round(stats["largest_payment"], 2)
    top = sorted(product_qty.items(), key=lambda kv: kv[1], reverse=True)[:5]
    stats["top_products"] = [{"product": n, "qty": q} for n, q in top]
    return stats


def _generate_insight(stats, api_key):
    """Ask Claude for a short manager briefing. Returns (text, error)."""
    try:
        import anthropic
    except ImportError:
        return None, "anthropic_not_installed"
    system = (
        "You are a concise assistant for a Nigerian shop owner. You receive a "
        "JSON summary of Point-of-Sale payments collected via Monnify bank "
        "transfer. Write a 2-3 sentence plain-English briefing for the owner: "
        "how much came in, standout products, and anything needing attention "
        "(amount mismatches, or expired/unpaid attempts). Be specific with "
        "figures and the given currency. No preamble, no bullet points, no "
        "markdown. If nothing stands out, say the day looks clean."
    )
    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=1024,
            thinking={"type": "adaptive"},
            system=system,
            messages=[{"role": "user", "content": json.dumps(stats)}],
        )
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        return (text or None), (None if text else "empty_response")
    except Exception as exc:  # noqa: BLE001 - surface a friendly error, log detail
        _logger.warning("Claude insight generation failed: %s", exc)
        return None, "generation_failed"


def _payment_method(payment):
    """Best-effort payment method label, pulled from the stored webhook if any."""
    if not payment.raw_webhook:
        return None
    try:
        data = json.loads(payment.raw_webhook)
    except (ValueError, TypeError):
        return None
    return data.get("paymentMethod") or data.get("eventData", {}).get("paymentMethod")


def _order_info(env, pos_order_uid):
    """Look up the POS order behind a payment and return what was ordered.

    Our payment stores the frontend order uid, which matches pos.order.uuid.
    The order may not exist yet (e.g. an abandoned/expired payment), in which
    case we just return empty details.
    """
    empty = {
        "order_ref": "",
        "cashier": "",
        "partner": "",
        "order_total": 0.0,
        "order_lines": [],
    }
    if not pos_order_uid:
        return empty
    order = env["pos.order"].sudo().search(
        [("uuid", "=", pos_order_uid)], limit=1
    )
    if not order:
        return empty
    return {
        "order_ref": order.pos_reference or order.name or "",
        "cashier": order.user_id.name or "",
        "partner": order.partner_id.display_name if order.partner_id else "",
        "order_total": order.amount_total,
        "order_lines": [
            {
                "product": line.full_product_name or line.product_id.display_name,
                "qty": line.qty,
                "subtotal": line.price_subtotal_incl,
            }
            for line in order.lines
        ],
    }
