"""
event study: abnormal stock returns around FDA approvals, net of the biotech sector (XBI).

market model (alpha, beta vs XBI over trading days [-250, -31]) and, as a robustness check,
market-adjusted returns (alpha = 0, beta = 1). event window [-10, +10] around day 0, the
first trading day on or after the approval date.

run from backend/:
    python -m analysis.event_study [--source auto|db|openfda] [--years 5]
writes analysis/results/event_study.json and three png charts.
"""
import argparse
import asyncio
import json
import logging
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # also runnable as a plain script

from app.config import settings  # noqa: E402

logger = logging.getLogger("event_study")

MARKET = "XBI"
WINDOW = 10  # event window [-WINDOW, +WINDOW]
EST_START, EST_END = -250, -31  # estimation window, trading days relative to day 0
MIN_EST_DAYS = 120
CLUSTER_DAYS = 10  # drop events with another event of the same ticker this close
LARGE_CAPS = {"PFE", "AMGN", "GILD", "REGN", "VRTX"}
DAYS = np.arange(-WINDOW, WINDOW + 1)
RESULTS_DIR = Path(__file__).resolve().parent / "results"

# known gaps in the approval data, not bugs
COVERAGE = {
    "note": "OpenFDA drugsfda covers CDER drugs and biologics only. CBER products (vaccines, gene "
            "therapies) are not in it, and some tracked companies have no approved product yet.",
    "not_in_drugsfda": {
        "MRNA": "vaccines (CBER)",
        "BNTX": "vaccines (CBER)",
        "CRSP": "gene therapy (CBER)",
    },
    "no_approved_products": ["BEAM", "NTLA"],
}

# site colors
BG, PANEL, TEXT, MUTED, GRID = "#07111d", "#0b1a2b", "#e2e8f0", "#94a3b8", "#1e2d3f"
BAR_MUTED = "#475569"
ACCENT, ACCENT2 = "#0ea5e9", "#f59e0b"


@dataclass
class Approval:
    ticker: str
    approval_date: date
    kind: str  # ORIG / EFFICACY


@dataclass
class Event:
    ticker: str
    day0: pd.Timestamp
    kind: str
    approvals: int  # approvals merged into this event


# ── approvals

def _kind(approval_id: str) -> str:
    # ids end in "-{submission_type}-{number}"; stored supplements are all EFFICACY ones
    return "ORIG" if "-ORIG-" in approval_id else "EFFICACY"


async def approvals_from_db(since: date) -> dict[str, list[Approval]]:
    from sqlalchemy import select

    from app.database import AsyncSessionLocal
    from app.models.models import DrugApproval

    logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.WARNING)  # DEBUG=true echoes sql
    async with AsyncSessionLocal() as db:
        rows = (await db.scalars(
            select(DrugApproval).where(
                DrugApproval.company_id.in_(list(settings.TRACKED_TICKERS)),
                DrugApproval.status == "Approved",
                DrugApproval.approval_date >= since,
            )
        )).all()
    out: dict[str, list[Approval]] = {}
    for r in rows:
        out.setdefault(r.company_id, []).append(Approval(r.company_id, r.approval_date, _kind(r.id)))
    return out


async def approvals_from_openfda(since: date) -> dict[str, list[Approval]]:
    """same request and ORIG / EFFICACY filter the app uses to fill drug_approvals; nothing is written"""
    from app.services.fda_service import fetch_all_openfda, manufacturer_search, parse_approvals

    out: dict[str, list[Approval]] = {}
    for ticker, name in settings.TRACKED_TICKERS.items():
        for a in parse_approvals(ticker, await fetch_all_openfda(manufacturer_search(name))):
            d = date.fromisoformat(a["approval_date"]) if a["approval_date"] else None
            if a["status"] == "Approved" and d and d >= since:
                out.setdefault(ticker, []).append(Approval(ticker, d, _kind(a["id"])))
    return out


async def load_approvals(source: str, since: date) -> tuple[dict[str, list[Approval]], str]:
    if source in ("auto", "db"):
        from_db = await approvals_from_db(since)
        missing = [t for t in settings.TRACKED_TICKERS if t not in from_db]
        if source == "db" or not missing:
            return from_db, "db"
        logger.warning("database has no approvals for %s: fetching all tickers from OpenFDA instead",
                       ", ".join(missing))
    return await approvals_from_openfda(since), "openfda"


# ── prices

def closes(symbol: str, start: date, end: date) -> pd.Series:
    """adjusted daily closes indexed by tz-naive date"""
    hist = yf.Ticker(symbol).history(start=start, end=end, auto_adjust=True)
    if hist is None or hist.empty:
        return pd.Series(dtype=float)
    s = hist["Close"].dropna()
    s.index = pd.DatetimeIndex(s.index).tz_localize(None).normalize()
    return s[~s.index.duplicated()]


# ── events

def build_events(approvals: list[Approval], trading_days: pd.DatetimeIndex) -> tuple[list[Event], int]:
    """
    one ticker's approvals -> events: day 0 = first trading day on or after the approval date,
    same-day approvals merged (ORIG wins), events with another one within CLUSTER_DAYS dropped.
    returns (events, dropped)
    """
    by_day: dict[int, list[Approval]] = {}
    for a in approvals:
        pos = trading_days.searchsorted(pd.Timestamp(a.approval_date))
        if pos < len(trading_days):
            by_day.setdefault(int(pos), []).append(a)
    positions = sorted(by_day)
    kept = []
    for i, pos in enumerate(positions):
        neighbours = [p for p in positions if p != pos and abs(p - pos) <= CLUSTER_DAYS]
        if neighbours:
            continue
        group = by_day[pos]
        kind = "ORIG" if any(a.kind == "ORIG" for a in group) else "EFFICACY"
        kept.append(Event(group[0].ticker, trading_days[pos], kind, len(group)))
    return kept, len(positions) - len(kept)


# ── abnormal returns

def abnormal_returns(stock: pd.Series, market: pd.Series, day0: pd.Timestamp) -> dict | None:
    """
    AR over [-WINDOW, +WINDOW] for one event, market model and market-adjusted.
    stock / market: closes. None if the estimation or event window is incomplete.
    """
    prices = pd.concat([stock, market], axis=1, join="inner").dropna()
    rets = prices.pct_change().iloc[1:]
    if day0 not in rets.index:
        return None
    p0 = rets.index.get_loc(day0)
    if p0 - WINDOW < 0 or p0 + WINDOW >= len(rets):
        return None
    est = rets.iloc[max(p0 + EST_START, 0): p0 + EST_END + 1]
    if len(est) < MIN_EST_DAYS:
        return None
    beta, alpha = np.polyfit(est.iloc[:, 1].to_numpy(), est.iloc[:, 0].to_numpy(), 1)
    win = rets.iloc[p0 - WINDOW: p0 + WINDOW + 1]
    r, m = win.iloc[:, 0].to_numpy(), win.iloc[:, 1].to_numpy()
    return {"alpha": float(alpha), "beta": float(beta), "est_days": len(est),
            "ar_mm": r - (alpha + beta * m), "ar_ma": r - m}


def _window_stat(values: np.ndarray) -> dict:
    n = len(values)
    mean = float(np.mean(values)) if n else None
    if n < 2:
        return {"n": n, "mean": mean, "se": None, "t": None, "p": None}
    se = float(np.std(values, ddof=1) / np.sqrt(n))
    t = mean / se if se > 0 else None
    p = float(2 * stats.t.sf(abs(t), n - 1)) if t is not None else None
    return {"n": n, "mean": mean, "se": se, "t": t, "p": p}


def summarize(ar: np.ndarray) -> dict:
    """cross-sectional stats for an (events x days) AR matrix"""
    n = ar.shape[0]
    car = np.cumsum(ar, axis=1)  # cumulative from day -WINDOW
    out = {"n": n}
    if n == 0:
        return out
    tcrit = stats.t.ppf(0.975, n - 1) if n > 1 else np.nan
    for name, m in (("ar", ar), ("car", car)):
        mean = m.mean(axis=0)
        se = m.std(axis=0, ddof=1) / np.sqrt(n) if n > 1 else np.full(len(DAYS), np.nan)
        out[name] = {"mean": mean.tolist(), "se": se.tolist(),
                     "lo95": (mean - tcrit * se).tolist(), "hi95": (mean + tcrit * se).tolist()}
    i = lambda d: d + WINDOW  # day -> column
    out["windows"] = {
        "CAR[-10,-1]": _window_stat(ar[:, i(-10): i(-1) + 1].sum(axis=1)),
        "AR[0]": _window_stat(ar[:, i(0)]),
        "CAR[0,+1]": _window_stat(ar[:, i(0): i(1) + 1].sum(axis=1)),
        "CAR[+1,+10]": _window_stat(ar[:, i(1): i(10) + 1].sum(axis=1)),
    }
    return out


# ── output

def _style(ax, title: str, ylabel: str = "Cumulative abnormal return"):
    ax.set_facecolor(PANEL)
    ax.set_title(title, color=TEXT, fontsize=13, pad=12, loc="left")
    ax.set_xlabel("Trading days relative to approval (day 0)", color=MUTED, fontsize=11)
    ax.set_ylabel(ylabel, color=MUTED, fontsize=11)
    ax.tick_params(colors=MUTED, labelsize=10)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    ax.grid(color=GRID, linewidth=0.8)
    ax.axhline(0, color=MUTED, linewidth=0.8)
    ax.axvline(0, color=MUTED, linewidth=0.8, linestyle=":")
    ax.yaxis.set_major_formatter(lambda v, _: f"{v * 100:+.1f}%")
    ax.set_xticks(range(-WINDOW, WINDOW + 1, 2))


def _legend(ax):
    leg = ax.legend(facecolor=BG, edgecolor=GRID, fontsize=10, loc="upper left")
    for text in leg.get_texts():
        text.set_color(TEXT)


def plot_car(results: dict, path: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    mm, ma = results["groups"]["all"]["market_model"], results["groups"]["all"]["market_adjusted"]
    fig, ax = plt.subplots(figsize=(10, 5.6), facecolor=BG)
    _style(ax, f"Average CAR around FDA approvals vs {MARKET}")
    if mm["n"]:
        ax.fill_between(DAYS, mm["car"]["lo95"], mm["car"]["hi95"], color=ACCENT, alpha=0.28, linewidth=0,
                        label="95% confidence band")
        for edge in ("lo95", "hi95"):  # thin outline so the band reads against the dark panel
            ax.plot(DAYS, mm["car"][edge], color=ACCENT, linewidth=0.8, alpha=0.55)
        ax.plot(DAYS, mm["car"]["mean"], color=ACCENT, linewidth=2.4, label=f"Market model (n={mm['n']})")
        ax.plot(DAYS, ma["car"]["mean"], color=TEXT, linewidth=1.6, linestyle="--",
                label=f"Market-adjusted, beta = 1 (n={ma['n']})")
    _legend(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=BG)
    plt.close(fig)


def plot_by_kind(results: dict, path: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 5.6), facecolor=BG)
    _style(ax, f"Average CAR by approval type vs {MARKET} (market model)")
    for key, label, color in (("ORIG", "Original approval", ACCENT), ("EFFICACY", "New indication", ACCENT2)):
        g = results["groups"][key]["market_model"]
        if not g["n"]:
            continue
        if g["n"] > 1:
            ax.fill_between(DAYS, g["car"]["lo95"], g["car"]["hi95"], color=color, alpha=0.14, linewidth=0)
        ax.plot(DAYS, g["car"]["mean"], color=color, linewidth=2.2, label=f"{label} (n={g['n']}), 95% band")
    _legend(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=BG)
    plt.close(fig)


def plot_daily_ar(results: dict, path: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    mm = results["groups"]["all"]["market_model"]
    fig, ax = plt.subplots(figsize=(10, 5.6), facecolor=BG)
    _style(ax, f"Average daily abnormal return around FDA approvals vs {MARKET}",
           ylabel="Average abnormal return")
    if mm["n"]:
        mean = np.array(mm["ar"]["mean"])
        err = mean - np.array(mm["ar"]["lo95"])  # symmetric t-based 95% interval
        colors = [ACCENT if d in (0, 1) else BAR_MUTED for d in DAYS]
        ax.bar(DAYS, mean, color=colors, width=0.7, zorder=2,
               label=f"Market model, all events (n={mm['n']})")
        ax.errorbar(DAYS, mean, yerr=err, fmt="none", ecolor=TEXT, elinewidth=1, capsize=3, alpha=0.8,
                    zorder=3, label="95% confidence interval")
    ax.set_xticks(range(-WINDOW, WINDOW + 1))
    _legend(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=BG)
    plt.close(fig)


def _pct(v):
    return "   n/a" if v is None else f"{v * 100:+6.2f}%"


def _num(v, fmt):
    return "  n/a" if v is None else format(v, fmt)


def print_table(results: dict):
    print(f"\n{'group':<10} {'method':<16} {'window':<12} {'n':>3} {'mean':>8} {'t':>6} {'p':>6}")
    print("-" * 66)
    for gname, group in results["groups"].items():
        for method in ("market_model", "market_adjusted"):
            for wname, w in group[method].get("windows", {}).items():
                print(f"{gname:<10} {method:<16} {wname:<12} {w['n']:>3} {_pct(w['mean'])} "
                      f"{_num(w['t'], '6.2f')} {_num(w['p'], '6.3f')}")


def plain_summary(results: dict) -> str:
    g = results["groups"]["all"]["market_model"]
    if g["n"] < 2:
        return f"Only {g['n']} usable event(s): too few to say anything."
    w = g["windows"]

    def describe(key, phrase):
        s = w[key]
        sig = s["p"] is not None and s["p"] < 0.05
        direction = "up" if s["mean"] > 0 else "down"
        verdict = (f"statistically significant (p = {s['p']:.3f})" if sig
                   else f"not statistically significant (p = {s['p']:.2f}), so it could be noise")
        return f"{phrase} the average stock moved {direction} {abs(s['mean']) * 100:.1f}% beyond what XBI explains; {verdict}."

    lines = [
        f"Based on {g['n']} approval events from {results['data']['tickers_with_events']} companies "
        f"({results['data']['first_event']} to {results['data']['last_event']}):",
        "- " + describe("CAR[-10,-1]", "In the 10 trading days before approval"),
        "- " + describe("AR[0]", "On the approval day itself"),
        "- " + describe("CAR[0,+1]", "Over the approval day and the next day"),
        "- " + describe("CAR[+1,+10]", "In the 10 days after"),
    ]
    big, small = results["groups"]["large_cap"]["market_model"], results["groups"]["small_cap"]["market_model"]
    if big["n"] and small["n"]:
        lines.append(f"- Large caps (n={big['n']}) moved {_pct(big['windows']['CAR[0,+1]']['mean']).strip()} over days 0 to +1, "
                     f"smaller companies (n={small['n']}) {_pct(small['windows']['CAR[0,+1]']['mean']).strip()}.")
    mm_t = w["CAR[0,+1]"]["mean"]
    ma_t = results["groups"]["all"]["market_adjusted"]["windows"]["CAR[0,+1]"]["mean"]
    lines.append(f"- The market-adjusted check (beta = 1) gives {_pct(ma_t).strip()} for days 0 to +1 "
                 f"vs {_pct(mm_t).strip()} with the market model.")
    lines.append(f"- Coverage: no events for {', '.join(COVERAGE['not_in_drugsfda'])} (CBER vaccines / gene "
                 f"therapies are not in OpenFDA's drugsfda data) or {', '.join(COVERAGE['no_approved_products'])} "
                 "(no approved products yet), so this is about CDER drugs of the other companies.")
    lines.append("Caveats: with this few events the confidence bands are wide; approvals are often expected "
                 "(PDUFA dates are public), so much of the news is priced in before day 0; OpenFDA dates are "
                 "the FDA action date, not always the announcement time; one ticker can dominate a small sample.")
    return "\n".join(lines)


# ── main

def run(approvals: dict[str, list[Approval]], source: str, years: int, today: date | None = None) -> dict:
    today = today or date.today()
    since = today - timedelta(days=365 * years)
    start, end = since - timedelta(days=420), today + timedelta(days=1)  # room for the estimation window
    market = closes(MARKET, start, end)
    if market.empty:
        raise RuntimeError(f"no price data for {MARKET}")

    rows, dropped_cluster, skipped = [], 0, {"no_prices": 0, "estimation_window": 0, "event_window": 0}
    for ticker, items in sorted(approvals.items()):
        stock = closes(ticker, start, end)
        if stock.empty:
            skipped["no_prices"] += len(items)
            logger.warning("no price data for %s", ticker)
            continue
        days = stock.index.intersection(market.index)
        events, dropped = build_events(items, days)
        dropped_cluster += dropped
        for ev in events:
            res = abnormal_returns(stock, market, ev.day0)
            if res is None:
                pos = days.get_loc(ev.day0)
                skipped["event_window" if pos + WINDOW >= len(days) else "estimation_window"] += 1
                continue
            rows.append({"ticker": ticker, "day0": ev.day0.date().isoformat(), "kind": ev.kind,
                         "approvals": ev.approvals, "size": "large_cap" if ticker in LARGE_CAPS else "small_cap",
                         **{k: res[k] for k in ("alpha", "beta", "est_days")},
                         "ar_mm": res["ar_mm"].tolist(), "ar_ma": res["ar_ma"].tolist()})
    logger.info("events kept: %d, dropped for another event within %d trading days: %d, skipped: %s",
                len(rows), CLUSTER_DAYS, dropped_cluster, skipped)

    def group(filter_fn):
        sel = [r for r in rows if filter_fn(r)]
        return {method: summarize(np.array([r[key] for r in sel]).reshape(len(sel), len(DAYS)))
                for method, key in (("market_model", "ar_mm"), ("market_adjusted", "ar_ma"))}

    return {
        "settings": {"market": MARKET, "event_window": [-WINDOW, WINDOW], "estimation_window": [EST_START, EST_END],
                     "min_estimation_days": MIN_EST_DAYS, "cluster_days": CLUSTER_DAYS, "years": years,
                     "large_caps": sorted(LARGE_CAPS), "approval_source": source, "run_date": today.isoformat()},
        "data": {"approvals": sum(len(v) for v in approvals.values()),
                 "approvals_per_ticker": {t: len(approvals.get(t, [])) for t in settings.TRACKED_TICKERS},
                 "events": len(rows),
                 "dropped_clustered": dropped_cluster, "skipped": skipped,
                 "tickers_with_events": len({r["ticker"] for r in rows}),
                 "first_event": min((r["day0"] for r in rows), default=None),
                 "last_event": max((r["day0"] for r in rows), default=None),
                 "events_per_ticker": {t: sum(r["ticker"] == t for r in rows) for t in sorted({r["ticker"] for r in rows})}},
        "coverage": COVERAGE,
        "days": DAYS.tolist(),
        "groups": {
            "all": group(lambda r: True),
            "ORIG": group(lambda r: r["kind"] == "ORIG"),
            "EFFICACY": group(lambda r: r["kind"] == "EFFICACY"),
            "large_cap": group(lambda r: r["size"] == "large_cap"),
            "small_cap": group(lambda r: r["size"] == "small_cap"),
        },
        "events": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", choices=["auto", "db", "openfda"], default="auto",
                        help="approvals from the database, OpenFDA, or the database if it has every ticker")
    parser.add_argument("--years", type=int, default=5)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    for noisy in ("httpx", "yfinance", "peewee"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    since = date.today() - timedelta(days=365 * args.years)
    approvals, source = asyncio.run(load_approvals(args.source, since))
    logger.info("approvals since %s from %s: %d", since, source, sum(len(v) for v in approvals.values()))
    results = run(approvals, source, args.years)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "event_study.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    plot_car(results, RESULTS_DIR / "event_study_car.png")
    plot_by_kind(results, RESULTS_DIR / "event_study_car_by_type.png")
    plot_daily_ar(results, RESULTS_DIR / "event_study_daily_ar.png")
    print_table(results)
    print("\n" + plain_summary(results))
    print(f"\nwrote {RESULTS_DIR}")


if __name__ == "__main__":
    main()
