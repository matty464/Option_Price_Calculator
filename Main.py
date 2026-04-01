"""
Streamlit app: multi-symbol / multi-strike / multi-expiry options, VIX stress, Greeks, what-if, P/L.
Run: streamlit run Main.py
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from black_scholes import bs_price, bs_price_greeks
from iv_solve import implied_volatility
from market_data import (
    fetch_option_at_strike,
    get_spot,
    get_us_10y_yield_percent,
    get_vix,
    list_option_expiries,
)

MULT = 100


def intrinsic_value(S: float, K: float, option_type: str) -> float:
    if option_type == "call":
        return max(S - K, 0.0)
    return max(K - S, 0.0)


def effective_iv_from_vix(
    iv_chain: float,
    scenario_vix: float,
    live_vix: float | None,
    *,
    enabled: bool,
    vix_floor: float = 1.0,
    iv_min: float = 0.02,
    iv_max: float = 2.5,
) -> tuple[float, str]:
    if not enabled:
        return iv_chain, "Using IV from the option chain (scenario VIX is display-only)."

    anchor = float(live_vix) if live_vix is not None and live_vix > 0 else 20.0
    anchor = max(anchor, vix_floor)
    ratio = max(scenario_vix, vix_floor) / anchor
    iv_eff = float(np.clip(iv_chain * ratio, iv_min, iv_max))
    if live_vix is None:
        note = (
            f"IV scaled by VIX ratio: {scenario_vix:.2f} ÷ {anchor:.2f} × chain IV "
            "(live VIX missing; anchor 20 used)."
        )
    else:
        note = f"IV scaled by VIX ratio: {scenario_vix:.2f} ÷ {anchor:.2f} × chain IV."
    return iv_eff, note


def _heatmap_grid_points(
    label: str,
    n_total: int,
    cap: int,
    default: int,
    key: str,
    help_txt: str,
) -> int:
    """Slider for number of grid points; avoids min==max which Streamlit rejects."""
    hi = int(min(cap, max(n_total, 1)))
    if n_total <= 1:
        return 1
    if hi <= 1:
        return 1
    lo = min(4, hi - 1)
    lo = max(1, lo)
    if lo >= hi:
        return hi
    val_default = int(np.clip(default, lo, hi))
    return int(st.slider(label, min_value=lo, max_value=hi, value=val_default, key=key, help=help_txt))


def greeks_row(label: str, g, contracts: int = 1) -> dict:
    m = MULT * contracts
    return {
        "Scenario": label,
        "Model price ($/share)": g.price,
        "Contract value ($)": g.price * m,
        "Delta (total $ / $1 spot)": g.delta * m,
        "Gamma (total $ / $1 spot²)": g.gamma * m,
        "Vega (total $ / vol pt)": g.vega * m,
        "Theta (total $ / day)": g.theta * m,
        "Rho (total $ / 1% rate)": g.rho * m,
    }


@st.cache_data(ttl=300, show_spinner=False)
def _cached_expiries(sym: str) -> tuple[str, ...]:
    return tuple(list_option_expiries(sym.strip().upper()))


@st.cache_data(ttl=60, show_spinner=False)
def _cached_spot(sym: str) -> float | None:
    return get_spot(sym.strip().upper())


@st.cache_data(ttl=60, show_spinner=False)
def _cached_option_mid(sym: str, expiry: str, strike: float, side: str) -> float | None:
    ot = "call" if side == "call" else "put"
    sn = fetch_option_at_strike(sym.strip().upper(), expiry.strip(), float(strike), ot)
    if sn is None:
        return None
    return float(sn.mid_price)


@dataclass
class LegInput:
    symbol: str
    expiry: str
    strike: float
    side: str  # "call" | "put"
    qty: int
    trade_price: float = 0.0  # $/sh; 0 means use quote mid for entry & P/L


def _legs_cache_key(legs: list[LegInput]) -> tuple:
    return tuple((x.symbol, x.expiry, round(x.strike, 4), x.side, x.qty) for x in legs)


st.set_page_config(page_title="Options & VIX Lab", layout="wide", initial_sidebar_state="expanded")

st.markdown("## Options & VIX lab")
st.caption(
    "Build **multiple legs** (symbols, expiries, strikes). Quotes from Yahoo Finance. "
    "Scenario **VIX** optionally rescales chain IV."
)

if "quote_cache" not in st.session_state:
    st.session_state.quote_cache = None


@st.cache_data(ttl=600, show_spinner=False)
def _cached_10y_yield_pct() -> float | None:
    return get_us_10y_yield_percent()


if "risk_free_rate_pct" not in st.session_state:
    _y0 = _cached_10y_yield_pct()
    st.session_state.risk_free_rate_pct = float(round(_y0, 3)) if _y0 is not None else 4.5

# Apply 10Y sync before the risk-free widget is created (cannot set session_state after widget bind).
if st.session_state.pop("_pending_sync_rfr", False):
    _pv = st.session_state.pop("_pending_rfr_value", None)
    if _pv is not None:
        st.session_state.risk_free_rate_pct = float(_pv)

with st.sidebar:
    st.markdown("### Book")
    n_legs = st.slider("Number of legs", min_value=1, max_value=12, value=1)
    _y_live = _cached_10y_yield_pct()
    st.caption(
        f"10Y Treasury (^TNX): **{_y_live:.3f}%**" if _y_live is not None else "10Y Treasury: — (using manual rate)"
    )
    rate_pct = st.number_input(
        "Risk-free rate (annual %)",
        min_value=0.0,
        step=0.05,
        key="risk_free_rate_pct",
        help="Pulled from 10Y yield on first load and when you Refresh quotes. Edit anytime.",
    )
    r = float(rate_pct) / 100.0
    refresh = st.button("Refresh quotes", type="primary", use_container_width=True)

st.subheader("Positions")
st.caption(
    "Pick **expiry** from the dropdown (loads for that symbol). "
    "**Your trade** defaults to the quoted mid; edit for your cost basis (set **0** to use live quote mid for P/L)."
)

leg_inputs: list[LegInput] = []
for i in range(n_legs):
    st.markdown(f"**Leg {i + 1}**")
    c0, c1, c2, c3, c4, c5 = st.columns([1.0, 1.25, 0.95, 0.75, 0.55, 0.85])
    sym = c0.text_input("Symbol", value="SPY" if i == 0 else "", key=f"sym_{i}").strip().upper()
    expiries = list(_cached_expiries(sym)) if sym else []
    if expiries:
        exp = c1.selectbox("Expiry", options=expiries, key=f"exp_{sym or 'x'}_{i}")
    else:
        exp = c1.text_input("Expiry (YYYY-MM-DD)", value="", key=f"exp_txt_{i}", placeholder="YYYY-MM-DD").strip()
    k_key = f"k_{i}"
    _strike_anchor = f"_strike_anchor_sym_{i}"
    _fallback_k = 500.0 if i == 0 else 100.0
    if sym:
        spot = _cached_spot(sym)
        prev_sym = st.session_state.get(_strike_anchor)
        if prev_sym != sym:
            st.session_state[_strike_anchor] = sym
            if spot is not None:
                st.session_state[k_key] = float(max(0.01, round(spot / 0.5) * 0.5))
            elif k_key not in st.session_state:
                st.session_state[k_key] = _fallback_k
    elif _strike_anchor in st.session_state:
        del st.session_state[_strike_anchor]
    strike = c2.number_input(
        "Strike",
        min_value=0.01,
        value=_fallback_k,
        step=0.5,
        key=k_key,
        help="Defaults to underlying spot (rounded to $0.50) when you set or change the symbol.",
    )
    side = c3.selectbox("Type", ["call", "put"], key=f"side_{i}")
    qty = c4.number_input("Qty", min_value=1, value=1, step=1, key=f"q_{i}")
    tp_key = f"tp_{i}"
    _trade_anchor = f"_trade_anchor_{i}"
    if sym and exp:
        cur_trade = (sym, exp, round(float(strike), 4), side)
        prev_trade = st.session_state.get(_trade_anchor)
        if prev_trade != cur_trade:
            st.session_state[_trade_anchor] = cur_trade
            mid = _cached_option_mid(sym, exp, float(strike), side)
            if mid is not None:
                st.session_state[tp_key] = round(mid, 2)
            else:
                st.session_state[tp_key] = 0.0
    elif _trade_anchor in st.session_state:
        del st.session_state[_trade_anchor]
    trade_px = c5.number_input(
        "Your trade",
        min_value=0.0,
        value=0.0,
        step=0.01,
        format="%.2f",
        key=tp_key,
        help="$/share — defaults to quoted mid when symbol, expiry, strike, or type changes. **0** = use live quote mid for P/L.",
    )
    if sym and exp:
        leg_inputs.append(
            LegInput(
                symbol=sym,
                expiry=exp,
                strike=float(strike),
                side=side,
                qty=int(qty),
                trade_price=float(trade_px),
            )
        )
    st.divider()

if not leg_inputs:
    st.warning("Enter at least one symbol and expiry.")
    st.stop()

legs_key = _legs_cache_key(leg_inputs)

if refresh or st.session_state.quote_cache is None or st.session_state.quote_cache.get("legs_key") != legs_key:
    with st.spinner("Fetching VIX, 10Y yield, and option chains…"):
        vx = get_vix()
        y10 = get_us_10y_yield_percent()
        snaps = []
        for lg in leg_inputs:
            snaps.append(fetch_option_at_strike(lg.symbol, lg.expiry, lg.strike, lg.side))
    st.session_state.quote_cache = {
        "vix": vx,
        "yield_10y": y10,
        "snaps": snaps,
        "legs_key": legs_key,
    }
    vl = float(vx) if vx is not None else 20.0
    st.session_state.scenario_vix = float(np.clip(vl, 5.0, 90.0))
    if y10 is not None:
        st.session_state["_pending_rfr_value"] = float(round(y10, 3))
        st.session_state["_pending_sync_rfr"] = True
    _cached_10y_yield_pct.clear()
    st.rerun()

cache = st.session_state.quote_cache
vix_live = cache["vix"]
snaps: list = cache["snaps"]
if len(snaps) != len(leg_inputs):
    st.warning("Leg structure changed vs cached quotes — click **Refresh quotes**.")
    st.stop()

if "scenario_vix" not in st.session_state:
    _sv0 = float(vix_live) if vix_live is not None else 20.0
    st.session_state.scenario_vix = float(np.clip(_sv0, 5.0, 90.0))

with st.sidebar:
    st.markdown("### VIX scenario")
    scenario_vix = st.number_input(
        "Scenario VIX level",
        min_value=5.0,
        max_value=90.0,
        step=0.5,
        key="scenario_vix",
        help="Refresh quotes sets scenario VIX to the live print.",
    )
    scale_iv_with_vix = st.checkbox(
        "Scale model IV with scenario VIX",
        value=True,
        help="Effective IV ≈ chain IV × (scenario VIX ÷ live VIX). Anchor 20 if live missing.",
    )
    if st.button("Set scenario VIX to live quote", use_container_width=True):
        if vix_live is not None:
            st.session_state.scenario_vix = float(np.clip(vix_live, 5.0, 90.0))
            st.rerun()
        else:
            st.warning("Live VIX not available right now.")

# --- Resolve IV / errors ---
errors: list[str] = []
resolved: list[dict] = []

for idx, (lg, snap) in enumerate(zip(leg_inputs, snaps)):
    if snap is None:
        errors.append(
            f"Leg {idx + 1} ({lg.symbol} {lg.side} K={lg.strike} {lg.expiry}): "
            "no quote (check symbol, expiry on Yahoo’s list, strike, hours)."
        )
        continue
    entry_px = float(lg.trade_price) if lg.trade_price and lg.trade_price > 0 else float(snap.mid_price)
    T = max(snap.days_to_expiry / 365.0, 1e-6)
    iv_chain = implied_volatility(snap.mid_price, snap.underlying_spot, snap.strike, T, r, snap.option_type)
    if iv_chain is None:
        iv_chain = snap.iv_yahoo if snap.iv_yahoo is not None else 0.25
    iv_eff, iv_note = effective_iv_from_vix(
        iv_chain, scenario_vix, vix_live, enabled=scale_iv_with_vix
    )
    g0 = bs_price_greeks(snap.underlying_spot, snap.strike, T, r, iv_eff, snap.option_type)
    resolved.append(
        {
            "leg_i": idx + 1,
            "input": lg,
            "snap": snap,
            "T": T,
            "iv_chain": iv_chain,
            "iv_eff": iv_eff,
            "iv_note": iv_note,
            "g0": g0,
            "entry_px": entry_px,
        }
    )

if not resolved:
    st.error("No valid legs. " + " ".join(errors))
    st.stop()

# One IV note (same formula for all legs when scaling; when off, same message)
iv_note = resolved[0]["iv_note"]

# --- Top metrics & mark spot (override stale Yahoo prints, e.g. weekend) ---
uniq_syms = sorted({x["snap"].ticker for x in resolved})
spot_fetched: dict[str, float] = {}
for x in resolved:
    sn = x["snap"]
    if sn.ticker not in spot_fetched:
        spot_fetched[sn.ticker] = float(sn.underlying_spot)

with st.sidebar:
    st.markdown("### Underlying spot (mark)")
    st.caption(
        "Yahoo spot can be **stale** (e.g. last close). Edit to the price you want for marks, Greeks, and P/L."
    )
    spot_eff: dict[str, float] = {}
    for sym in uniq_syms:
        q = spot_fetched[sym]
        spot_eff[sym] = float(
            st.number_input(
                f"{sym} spot ($)",
                min_value=0.01,
                value=float(round(q, 2)),
                step=0.01,
                format="%.2f",
                key=f"sov_{sym}",
            )
        )

for x in resolved:
    sn = x["snap"]
    S = spot_eff[sn.ticker]
    x["S_mark"] = S
    x["g0"] = bs_price_greeks(S, sn.strike, x["T"], r, x["iv_eff"], sn.option_type)

spots_line = " · ".join(f"{s} ${spot_eff[s]:,.2f}" for s in uniq_syms)

m1, m2, m3 = st.columns(3)
m1.metric("Live VIX", f"{vix_live:.2f}" if vix_live is not None else "—")
dv = round(scenario_vix - vix_live, 2) if vix_live is not None else None
m2.metric("Scenario VIX", f"{scenario_vix:.2f}", delta=dv, delta_color="inverse")
m3.metric("Underlyings (mark)", spots_line if len(spots_line) < 80 else f"{len(uniq_syms)} symbols")

st.info(iv_note)
if errors:
    for e in errors:
        st.warning(e)

# --- Summary table ---
rows = []
for x in resolved:
    sn = x["snap"]
    lg = x["input"]
    g = x["g0"]
    q = lg.qty
    m = MULT * q
    rows.append(
        {
            "Leg": x["leg_i"],
            "Symbol": sn.ticker,
            "Expiry": sn.expiry,
            "Strike": sn.strike,
            "Type": sn.option_type,
            "Qty": q,
            "Fetched spot": sn.underlying_spot,
            "Mark spot": x["S_mark"],
            "Quote mid": sn.mid_price,
            "Entry $/sh": x["entry_px"],
            "IV chain %": round(x["iv_chain"] * 100, 2),
            "IV model %": round(x["iv_eff"] * 100, 2),
            "Value $": g.price * m,
            "P/L vs entry $": (g.price - x["entry_px"]) * m,
            "Delta $": g.delta * m,
            "Gamma $": g.gamma * m,
            "Vega $": g.vega * m,
            "Theta $/d": g.theta * m,
        }
    )

sum_df = pd.DataFrame(rows)
tot = {
    "Leg": "TOTAL",
    "Symbol": "",
    "Expiry": "",
    "Strike": np.nan,
    "Type": "",
    "Qty": int(sum_df["Qty"].sum()),
    "Fetched spot": np.nan,
    "Mark spot": np.nan,
    "Quote mid": np.nan,
    "Entry $/sh": np.nan,
    "IV chain %": np.nan,
    "IV model %": np.nan,
    "Value $": sum_df["Value $"].sum(),
    "P/L vs entry $": sum_df["P/L vs entry $"].sum(),
    "Delta $": sum_df["Delta $"].sum(),
    "Gamma $": sum_df["Gamma $"].sum(),
    "Vega $": sum_df["Vega $"].sum(),
    "Theta $/d": sum_df["Theta $/d"].sum(),
}
sum_out = pd.concat([sum_df, pd.DataFrame([tot])], ignore_index=True)

tab_summary, tab_spot, tab_pl = st.tabs(["Summary", "Stock what-if", "P/L & charts"])

with tab_summary:
    st.subheader("Book & Greeks")
    st.dataframe(sum_out, use_container_width=True, hide_index=True)
    with st.expander("How to read the Greeks"):
        st.markdown(
            """
            - **Mark spot**: underlying used for Greeks and marks (edit in sidebar if Yahoo is stale). **Fetched spot** is what Yahoo returned.
            - **P/L vs entry $**: mark-to-model option value minus **your trade** (or quote mid if trade is 0).
            - **Delta $**: ~P/L for a **$1** move in that leg’s underlying (per position size).
            - **Vega $**: ~P/L per **one vol point** on that option’s IV.
            - **Theta $/d**: one calendar day, holding spot & IV flat.
            - Multiple symbols: each leg uses its own spot; **totals** add dollars across legs.
            """
        )

with tab_spot:
    st.subheader("Hypothetical spot(s)")
    st.caption(
        "Per symbol: **IV unchanged** (scenario σ) vs **entry premium unchanged** (repriced IV at your trade price). "
        "Totals sum legs."
    )
    spots_new: dict[str, float] = {}
    cols = st.columns(min(len(uniq_syms), 4))
    for j, sym in enumerate(uniq_syms):
        S_sym = spot_eff[sym]
        with cols[j % len(cols)]:
            spots_new[sym] = st.number_input(
                f"{sym} price",
                min_value=0.01,
                value=float(round(S_sym, 2)),
                step=0.01,
                format="%.2f",
                key=f"wf_{sym}",
            )

    rows_iv = []
    rows_mid = []
    for x in resolved:
        sn = x["snap"]
        lg = x["input"]
        q = lg.qty
        S_new = spots_new[sn.ticker]
        iv_c = x["iv_eff"]
        g1 = bs_price_greeks(S_new, sn.strike, x["T"], r, iv_c, sn.option_type)
        iv_r = implied_volatility(x["entry_px"], S_new, sn.strike, x["T"], r, sn.option_type)
        if iv_r is None:
            iv_r = iv_c
        g2 = bs_price_greeks(S_new, sn.strike, x["T"], r, iv_r, sn.option_type)
        gr1 = greeks_row("", g1, q)
        gr2 = greeks_row("", g2, q)
        del gr1["Scenario"]
        del gr2["Scenario"]
        base = {"Leg": x["leg_i"], "Symbol": sn.ticker, "Spot what-if": S_new}
        rows_iv.append({**base, "σ %": round(iv_c * 100, 2), **gr1})
        rows_mid.append({**base, "σ %": round(iv_r * 100, 2), **gr2})

    st.markdown("**Scenario A — IV unchanged**")
    st.dataframe(pd.DataFrame(rows_iv), use_container_width=True, hide_index=True)
    st.markdown("**Scenario B — your entry premium unchanged (repriced IV)**")
    st.dataframe(pd.DataFrame(rows_mid), use_container_width=True, hide_index=True)

with tab_pl:
    st.subheader("Option price & P/L")
    single_sym = len(uniq_syms) == 1
    if not single_sym:
        st.caption(
            "Underlyings differ: charts use **one leg** you select. "
            "**By date** uses the **spot you set** for that underlying’s time path."
        )
        leg_labels = [f"Leg {x['leg_i']}: {x['snap'].ticker} {x['snap'].option_type} {x['snap'].strike:g} {x['snap'].expiry}" for x in resolved]
        pick = st.selectbox("Leg for charts", range(len(resolved)), format_func=lambda i: leg_labels[i])
        chart_entries = [resolved[pick]]
    else:
        chart_entries = resolved
        st.caption(
            "Same underlying: **portfolio** P/L sums legs (**your trade** or mid × qty per leg). "
            "**By date** uses the **spot you set** for the time path; **By stock price** sweeps price at current DTE."
        )

    chart_xs = chart_entries
    sym_chart = chart_xs[0]["snap"].ticker
    S_chart = float(chart_xs[0]["S_mark"])

    st.markdown("**Time-decay path (By date)**")
    S_time = st.number_input(
        f"{sym_chart} spot to hold for the date path ($)",
        min_value=0.01,
        value=float(round(S_chart, 2)),
        step=0.01,
        format="%.2f",
        key="pl_S_time",
        help=(
            "Theta-style path: same stock price on every date. Defaults to your **mark spot**; "
            "change it to stress a different level (e.g. Sunday mark vs Friday close)."
        ),
    )

    def model_price_on_date(S_spot: float, snap, iv_eff: float, d: date) -> float:
        exp_d = datetime.strptime(snap.expiry, "%Y-%m-%d").date()
        if d > exp_d:
            return 0.0
        rem_days = (exp_d - d).days
        if rem_days <= 0:
            return intrinsic_value(S_spot, snap.strike, snap.option_type)
        return bs_price(S_spot, snap.strike, max(rem_days / 365.0, 1e-8), r, iv_eff, snap.option_type)

    def portfolio_equiv_pnl_for_date(S_spot: float, xs: list, d: date) -> tuple[float, float]:
        tv = 0.0
        ent = 0.0
        wq = 0
        for x in xs:
            sn = x["snap"]
            lg = x["input"]
            px = model_price_on_date(S_spot, sn, x["iv_eff"], d)
            tv += lg.qty * MULT * px
            ent += lg.qty * MULT * x["entry_px"]
            wq += lg.qty
        denom = wq * MULT
        eq = tv / denom if denom else 0.0
        return eq, tv - ent

    def portfolio_equiv_pnl_for_spot(S_spot: float, xs: list) -> tuple[float, float]:
        tv = 0.0
        ent = 0.0
        wq = 0
        for x in xs:
            sn = x["snap"]
            lg = x["input"]
            px = bs_price(S_spot, sn.strike, x["T"], r, x["iv_eff"], sn.option_type)
            tv += lg.qty * MULT * px
            ent += lg.qty * MULT * x["entry_px"]
            wq += lg.qty
        denom = wq * MULT
        eq = tv / denom if denom else 0.0
        return eq, tv - ent

    max_exp = max(datetime.strptime(x["snap"].expiry, "%Y-%m-%d").date() for x in chart_xs)
    today_d = date.today()
    time_rows = []
    chart_dates: list[date] = []
    day_i = 0
    while True:
        d = today_d + timedelta(days=day_i)
        if d > max_exp:
            break
        chart_dates.append(d)
        eq, pnl = portfolio_equiv_pnl_for_date(float(S_time), chart_xs, d)
        min_dte = min(max((datetime.strptime(x["snap"].expiry, "%Y-%m-%d").date() - d).days, 0) for x in chart_xs)
        time_rows.append({"Date": d.isoformat(), "Min DTE": min_dte, "Price ($/sh eq)": eq, "P/L ($)": pnl})
        day_i += 1
        if day_i > 4000:
            break

    df_time = pd.DataFrame(time_rows)

    c_lo, c_hi, c_n = st.columns(3)
    with c_lo:
        spot_lo = st.slider("Chart: spot range low (% of spot)", 50, 100, 85, key="pl_lo")
    with c_hi:
        spot_hi = st.slider("Chart: spot range high (% of spot)", 100, 150, 115, key="pl_hi")
    with c_n:
        n_spots = st.slider("Chart: spot grid points", 21, 121, 61, step=10, key="pl_n")

    spots = np.linspace(S_chart * (spot_lo / 100.0), S_chart * (spot_hi / 100.0), int(n_spots))

    prices_spot = []
    pnl_spot = []
    for s in spots:
        pe, pn = portfolio_equiv_pnl_for_spot(float(s), chart_xs)
        prices_spot.append(pe)
        pnl_spot.append(pn)

    df_spot = pd.DataFrame({f"{sym_chart} price": spots, "Price ($/sh eq)": prices_spot, "P/L ($)": pnl_spot})

    t_time, t_spot, t_heat, t_tbl = st.tabs(["By date", "By stock price", "P/L: date & price", "Tables"])

    with t_time:
        st.markdown(f"**By date** — {sym_chart} @ **${S_time:,.2f}**")
        st.caption("Underlying held at this level through time (adjust in **Time-decay path** above). IV unchanged.")
        fig_t = make_subplots(specs=[[{"secondary_y": True}]])
        fig_t.add_trace(
            go.Scatter(x=df_time["Date"], y=df_time["Price ($/sh eq)"], name="Model price (equiv)", mode="lines"),
            secondary_y=False,
        )
        fig_t.add_trace(
            go.Scatter(x=df_time["Date"], y=df_time["P/L ($)"], name="P/L ($)", mode="lines"),
            secondary_y=True,
        )
        fig_t.update_xaxes(title_text="Date")
        fig_t.update_yaxes(title_text="Price ($/sh equivalent)", secondary_y=False)
        fig_t.update_yaxes(title_text="P/L ($)", secondary_y=True)
        fig_t.update_layout(
            height=500,
            margin=dict(t=16, b=96),
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.18,
                yref="paper",
                x=0.5,
                xanchor="center",
            ),
        )
        st.plotly_chart(fig_t, use_container_width=True)

    with t_spot:
        fig_s = make_subplots(specs=[[{"secondary_y": True}]])
        fig_s.add_trace(
            go.Scatter(x=spots, y=prices_spot, name="Model price (equiv)", mode="lines"),
            secondary_y=False,
        )
        fig_s.add_trace(
            go.Scatter(x=spots, y=pnl_spot, name="P/L ($)", mode="lines"),
            secondary_y=True,
        )
        fig_s.add_vline(x=S_chart, line_dash="dash", line_color="rgba(128,128,128,0.8)")
        fig_s.update_xaxes(title_text=f"{sym_chart} price ($)")
        fig_s.update_yaxes(title_text="Price ($/sh equivalent)", secondary_y=False)
        fig_s.update_yaxes(title_text="P/L ($)", secondary_y=True)
        fig_s.update_layout(
            height=500,
            margin=dict(t=16, b=96),
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.18,
                yref="paper",
                x=0.5,
                xanchor="center",
            ),
        )
        st.plotly_chart(fig_s, use_container_width=True)

    with t_heat:
        st.caption(
            "Each cell is **total book P/L ($)** vs **your entry** (or quote mid if trade left at 0) at that "
            "**calendar date** and **stock price**, holding **scenario model IV** fixed."
        )
        ncd = len(chart_dates)
        nsd = len(spots)
        h1, h2 = st.columns(2)
        with h1:
            n_d_heat = _heatmap_grid_points(
                "Heatmap: date grid points",
                ncd,
                cap=80,
                default=min(28, ncd),
                key="hm_nd",
                help_txt="Evenly spaced over the date range to expiry.",
            )
        with h2:
            n_s_heat = _heatmap_grid_points(
                "Heatmap: spot grid points",
                nsd,
                cap=60,
                default=min(26, nsd),
                key="hm_ns",
                help_txt="Evenly spaced between low and high spot from the sliders above.",
            )

        n_d_heat = int(np.clip(n_d_heat, 1, max(ncd, 1)))
        n_s_heat = int(np.clip(n_s_heat, 1, max(nsd, 1)))
        idx_d = np.unique(np.linspace(0, ncd - 1, n_d_heat, dtype=int))
        idx_s = np.unique(np.linspace(0, nsd - 1, n_s_heat, dtype=int))
        sub_dates = [chart_dates[i] for i in idx_d]
        sub_date_labels = [d.isoformat() for d in sub_dates]
        sub_spots = spots[idx_s].astype(float)

        z_heat = np.zeros((len(sub_spots), len(sub_dates)), dtype=float)
        for i, s_val in enumerate(sub_spots):
            for j, d_val in enumerate(sub_dates):
                _, pnl_ij = portfolio_equiv_pnl_for_date(float(s_val), chart_xs, d_val)
                z_heat[i, j] = pnl_ij

        hm_hover = f"Date=%{{x}}<br>{sym_chart}=%{{y:.2f}}<br>P/L=$%{{z:,.0f}}<extra></extra>"
        fig_hm = go.Figure(
            data=go.Heatmap(
                x=sub_date_labels,
                y=sub_spots,
                z=z_heat,
                colorscale="RdYlGn",
                zmid=0.0,
                colorbar=dict(title="P/L ($)"),
                hovertemplate=hm_hover,
            )
        )
        fig_hm.update_layout(
            title="P/L ($) vs date and stock price",
            xaxis_title="Date",
            yaxis_title=f"{sym_chart} price ($)",
            height=560,
            margin=dict(t=50),
        )
        fig_hm.update_xaxes(tickangle=-45)
        st.plotly_chart(fig_hm, use_container_width=True)

        show_3d = st.checkbox("Also show 3D surface", value=False, key="hm_3d")
        if show_3d:
            lim = float(np.nanmax(np.abs(z_heat))) if z_heat.size else 1.0
            if lim <= 0 or np.isnan(lim):
                lim = 1.0
            fig_3d = go.Figure(
                data=go.Surface(
                    x=sub_date_labels,
                    y=sub_spots,
                    z=z_heat,
                    colorscale="RdYlGn",
                    cmin=-lim,
                    cmax=lim,
                    hovertemplate="Date=%{x}<br>Spot=%{y:.2f}<br>P/L=$%{z:,.0f}<extra></extra>",
                )
            )
            fig_3d.update_layout(
                title="P/L surface ($)",
                scene=dict(
                    xaxis_title="Date",
                    yaxis_title=f"{sym_chart} ($)",
                    zaxis_title="P/L ($)",
                ),
                height=600,
            )
            st.plotly_chart(fig_3d, use_container_width=True)

    with t_tbl:
        u1, u2 = st.columns(2)
        with u1:
            st.markdown("**By date**")
            st.dataframe(df_time, use_container_width=True, hide_index=True, height=380)
        with u2:
            st.markdown("**By stock price**")
            st.dataframe(df_spot, use_container_width=True, hide_index=True, height=380)

st.divider()
st.markdown("**Disclaimer**")
st.caption(
    "This application is for **education and information only**. It is **not** financial, investment, tax, or legal "
    "advice, and **not** a recommendation to buy, sell, or hold any security or derivative."
)
st.caption(
    "Market data may be **delayed or wrong**. Model outputs (including Greeks, implied volatility, and P/L scenarios) "
    "are **approximations** and may differ materially from your broker, exchanges, or actual results. Options involve "
    "substantial risk."
)
st.caption(
    "**You are solely responsible** for your trading decisions. The authors and contributors **disclaim liability** for "
    "any loss or damage arising from use of this software."
)
