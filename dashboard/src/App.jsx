import { useCallback, useEffect, useState } from "react";
import { API_URL, API_TOKEN } from "./config.js";

const INSIGHT_URL = API_URL.replace("/data", "/insight");

const STATUS = {
  paid: { label: "Paid", cls: "good" },
  pending: { label: "Pending", cls: "warn" },
  mismatch: { label: "Mismatch", cls: "crit" },
  expired: { label: "Expired", cls: "muted" },
  cancelled: { label: "Cancelled", cls: "muted" },
};

function money(value, currency) {
  const symbol = currency === "NGN" ? "₦" : "";
  const n = Number(value || 0).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return symbol + n;
}

function when(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function App() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [insight, setInsight] = useState({ state: "loading", text: "", msg: "" });

  const loadInsight = useCallback(async () => {
    setInsight({ state: "loading", text: "", msg: "" });
    try {
      const res = await fetch(INSIGHT_URL, {
        headers: { "X-Monnify-Dashboard-Token": API_TOKEN },
      });
      const body = await res.json().catch(() => ({}));
      if (res.status === 403) {
        setInsight({ state: "error", text: "", msg: "Unauthorized." });
      } else if (body.error === "not_configured" || body.error === "anthropic_not_installed") {
        setInsight({
          state: "off",
          text: "",
          msg: "Add a Claude API key in Odoo to enable the daily briefing.",
        });
      } else if (body.insight) {
        setInsight({ state: "ready", text: body.insight, msg: "" });
      } else {
        setInsight({ state: "error", text: "", msg: "Couldn't generate the briefing right now." });
      }
    } catch {
      setInsight({ state: "error", text: "", msg: "Can't reach Odoo." });
    }
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(API_URL, {
        headers: { "X-Monnify-Dashboard-Token": API_TOKEN },
      });
      if (!res.ok) {
        throw new Error(
          res.status === 403
            ? "Unauthorized — the dashboard token doesn't match Odoo."
            : `Request failed (${res.status}).`
        );
      }
      setData(await res.json());
    } catch (e) {
      setError(
        e.message?.includes("Failed to fetch")
          ? "Can't reach Odoo. Is it running, and is CORS allowed?"
          : e.message || "Something went wrong."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    loadInsight();
  }, [load, loadInsight]);

  const currency = data?.currency || "NGN";
  const s = data?.summary || {};
  const txns = data?.transactions || [];

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <span className="mark">M</span>
          <div>
            <h1>Payments</h1>
            <p>POS collections &amp; settlement &middot; Monnify</p>
          </div>
        </div>
        <button className="btn" onClick={load} disabled={loading}>
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </header>

      {error && <div className="banner">{error}</div>}

      <section className="briefing">
        <div className="briefing-head">
          <span className="briefing-tag">✦ Daily briefing</span>
          <button
            className="briefing-refresh"
            onClick={loadInsight}
            disabled={insight.state === "loading"}
          >
            {insight.state === "loading" ? "Thinking…" : "Regenerate"}
          </button>
        </div>
        {insight.state === "ready" && <p className="briefing-text">{insight.text}</p>}
        {insight.state === "loading" && (
          <p className="briefing-text muted">Reading today's payments…</p>
        )}
        {(insight.state === "off" || insight.state === "error") && (
          <p className="briefing-text muted">{insight.msg}</p>
        )}
      </section>

      <section className="tiles">
        <Tile label="Collected" value={money(s.collected, currency)} />
        <Tile label="Settled to bank" dot="good" value={money(s.settled, currency)} sub="cleared payouts" />
        <Tile label="Awaiting settlement" dot="warn" value={money(s.awaiting, currency)} sub="expected T+1" />
        <Tile label="Needs attention" dot="crit" value={String(s.attention ?? 0)} sub="mismatch / expired" />
      </section>

      <section className="card">
        <div className="card-head">
          <h2>Transactions</h2>
          <span className="count">{txns.length}</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Customer</th>
                <th className="r">Amount</th>
                <th>Status</th>
                <th>Reference</th>
                <th>Method</th>
                <th>Settlement</th>
                <th>Date</th>
                <th aria-label="Open"></th>
              </tr>
            </thead>
            <tbody>
              {txns.map((t) => {
                const st = STATUS[t.status] || { label: t.status, cls: "muted" };
                return (
                  <tr key={t.id} className="clickable" onClick={() => setSelected(t)}>
                    <td>
                      <span className="cust">
                        <span className="avatar">{(t.customer || "?").slice(0, 2).toUpperCase()}</span>
                        {t.customer}
                      </span>
                    </td>
                    <td className="r amount">{money(t.amount_paid || t.amount, currency)}</td>
                    <td><span className={`pill ${st.cls}`}>{st.label}</span></td>
                    <td className="ref" title={t.reference}>{t.reference || "—"}</td>
                    <td>{t.method ? <span className="chip">{t.method}</span> : "—"}</td>
                    <td>{t.settlement_status ? <span className="pill warn">Pending</span> : <span className="muted">—</span>}</td>
                    <td className="date">{when(t.date)}</td>
                    <td className="chev">›</td>
                  </tr>
                );
              })}
              {!loading && txns.length === 0 && (
                <tr><td className="empty" colSpan="8">No Monnify payments yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <footer className="foot">Monnify &middot; Odoo POS &mdash; live from your Odoo instance</footer>

      {selected && (
        <Detail t={selected} currency={currency} onClose={() => setSelected(null)} />
      )}
    </div>
  );
}

function Detail({ t, currency, onClose }) {
  const st = STATUS[t.status] || { label: t.status, cls: "muted" };
  const items = t.order_lines || [];
  const rows = [
    ["Status", <span className={`pill ${st.cls}`}>{st.label}</span>],
    ["Amount expected", money(t.amount, currency)],
    ["Amount received", t.amount_paid ? money(t.amount_paid, currency) : "—"],
    ["Receipt no.", t.order_ref || "—"],
    ["Cashier", t.cashier || "—"],
    ["Customer", t.partner || "—"],
    ["Payer", t.customer || "—"],
    ["Bank", t.bank_name || "—"],
    ["Account number", t.account_number || "—"],
    ["Method", t.method || "—"],
    ["Settlement", t.settlement_status ? "Pending" : "—"],
    ["Monnify reference", t.monnify_reference || t.reference || "—"],
    ["Session", t.session || "—"],
    ["Created", when(t.created || t.date)],
    ["Paid on", t.paid_on ? when(t.paid_on) : "—"],
  ];
  return (
    <div className="overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <div>
            <h3>Transaction</h3>
            <p className="modal-ref">{t.monnify_reference || t.reference || t.our_reference}</p>
          </div>
          <button className="modal-x" onClick={onClose} aria-label="Close">×</button>
        </div>
        <div className="modal-amount">
          <span className="tlabel">{t.status === "paid" ? "Received" : "Expected"}</span>
          <span className="modal-amt">{money(t.amount_paid || t.amount, currency)}</span>
        </div>

        {items.length > 0 && (
          <div className="items">
            <span className="tlabel items-title">Items ordered</span>
            {items.map((it, i) => (
              <div className="item" key={i}>
                <span className="iqty">{Number(it.qty)}×</span>
                <span className="iname">{it.product}</span>
                <span className="iprice">{money(it.subtotal, currency)}</span>
              </div>
            ))}
            {t.order_total ? (
              <div className="item item-total">
                <span className="iqty"></span>
                <span className="iname">Order total</span>
                <span className="iprice">{money(t.order_total, currency)}</span>
              </div>
            ) : null}
          </div>
        )}

        <dl className="detail">
          {rows.map(([k, v]) => (
            <div className="drow" key={k}>
              <dt>{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  );
}

function Tile({ label, value, dot, sub }) {
  return (
    <div className="tile">
      <span className="tlabel">
        {dot && <span className={`dot ${dot}`} />}
        {label}
      </span>
      <span className="tvalue">{value}</span>
      {sub && <span className="tsub">{sub}</span>}
    </div>
  );
}
