"""
"sell the news" backtest on top of the FDA approval event study (same events, prices, market model).

three trades per event, close-to-close:
  A  sell before the news: buy the close of day -11, sell the close of day -1
  B  hold through the news: buy the close of day -11, sell the close of day +10
  C  buy the news: buy the close of day +1 (approvals are mostly announced after the close,
     so the close of day +1 is the first realistic entry), sell the close of day +10
abnormal return = sum of the market-model abnormal returns (vs XBI) over the days held.

then the actual test: do stocks that ran up before approval do worse after it?

run from backend/:
    python -m analysis.sell_the_news [--source auto|db|openfda] [--years 5]
writes analysis/results/sell_the_news.json and two png charts.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # also runnable as a plain script

from analysis import event_study as es  # noqa: E402

COST = 0.001  # 0.10% round trip
GROUPS = {"all": None, "ORIG": "ORIG", "EFFICACY": "EFFICACY"}
# days held: the first day's return is close(day-1) -> close(day), so buying the close before it
STRATEGIES = {
    "A": {"name": "Sell before the news", "buy": "close of day -11", "sell": "close of day -1", "hold": (-10, -1)},
    "B": {"name": "Hold through the news", "buy": "close of day -11", "sell": "close of day +10", "hold": (-10, 10)},
    "C":{"name": "Buy the news", "buy": "close of day +1", "sell": "close of day +10", "hold": (2, 10)},
}
WINDOWS = {"CAR[0,+10]": (0, 10), "CAR[+2,+10]": (2, 10)}
RUNUP = (-10, -1)  # CAR[-10,-1]


def _cols(first: int, last: int) -> slice:
    # position in the 21-day window arrays (day -10 is column 0)
    return slice(first + es.WINDOW, last + es.WINDOW + 1)


def trade_returns(ret, mkt, ar, cost: float = COST) -> dict:
    """
    A / B / C returns for one event from its 21 daily returns (days -10..+10): the stock (ret),
    XBI (mkt) and the market-model abnormal returns (ar). raw and xbi are compounded; abnormal is
    the sum of daily ARs. the _net versions subtract the round-trip cost.
    """
    ret, mkt, ar = (np.asarray(a, dtype=float) for a in (ret, mkt, ar))
    out = {}
    for key, strategy in STRATEGIES.items():
        sl = _cols(*strategy["hold"])
        raw = float(np.prod(1 + ret[sl]) - 1)
        abnormal = float(ar[sl].sum())
        out[key] = {"raw": raw, "xbi": float(np.prod(1 + mkt[sl]) - 1), "abnormal": abnormal,
                    "raw_net": raw - cost, "abnormal_net": abnormal - cost}
    return out


def enrich(events:list[dict]) -> list[dict]:
    """per-event strategy returns and the run-up / after windows used by the sell-the-news test"""
    out = []
    for e in events:
        ar = np.asarray(e["ar_mm"])
        out.append({
            "ticker": e["ticker"], "day0": e["day0"], "kind": e["kind"],
            "runup": float(ar[_cols(*RUNUP)].sum()),
            **{name: float(ar[_cols(*days)].sum()) for name, days in WINDOWS.items()},
            "trades": trade_returns(e["ret"], e["mkt"], ar),
        })
    return out


# ── statistics
def describe(values) -> dict:
    """n, mean, median, hit rate (share > 0), t-test against 0 and a 95% interval for the mean"""
    v = np.asarray(values, dtype=float)
    out = es._window_stat(v)
    out["median"] = float(np.median(v)) if len(v) else None
    out["hit_rate"] = float(np.mean(v > 0)) if len(v) else None
    out["ci95"] = None
    if out["se"] is not None:
        half = float(stats.t.ppf(0.975, len(v) - 1) * out["se"])
        out["ci95"] = [out["mean"] - half, out["mean"] + half]
    return out


def by_company(values, tickers) -> dict | None:
    """t-test on per-company means: events of one company are not independent, companies are closer to it"""
    per: dict[str, list[float]] = {}
    for value, ticker in zip(values, tickers):
        per.setdefault(ticker, []).append(value)
    if len(per) < 3:
        return None
    return {"companies": len(per), **describe([np.mean(v) for v in per.values()])}


def strategy_table(events: list[dict]) -> dict:
    out = {}
    for key in STRATEGIES:
        trades = [e["trades"][key] for e in events]
        out[key] = {field: describe([t[field] for t in trades])
                    for field in ("raw", "xbi", "abnormal", "raw_net", "abnormal_net")}
        out[key]["abnormal_by_company"] = by_company([t["abnormal"] for t in trades], [e["ticker"] for e in events])
    return out


def runup_split(events: list[dict]) -> dict:
    """events above the group's median run-up CAR[-10,-1] vs the rest (the median event goes to 'low')"""
    median = float(np.median([e["runup"] for e in events]))
    high = [e for e in events if e["runup"] > median]
    low=[e for e in events if e["runup"] <= median]
    out = {"median_runup": median, "mean_runup_high": float(np.mean([e["runup"] for e in high])),
           "mean_runup_low": float(np.mean([e["runup"] for e in low])) }
    for name in WINDOWS:
        h, l = [e[name] for e in high], [e[name] for e in low]
        diff = None
        if len(h) >= 2 and len(l) >= 2:
            t, p = stats.ttest_ind(h, l, equal_var=False)  # welch
            diff = {"diff": float(np.mean(h) - np.mean(l)), "t": float(t), "p": float(p)}
        out[name] = {"high": describe(h), "low": describe(l), "high_minus_low": diff}
    return out


def cluster_slope(x, y, groups) -> dict | None:
    """ols slope with company-clustered standard errors (CR1), t-distribution with companies - 1 df"""
    labels = sorted(set(groups))
    g = len(labels)
    if g < 3:
        return None
    X = np.column_stack([np.ones(len(x)), x])
    n, k = X.shape
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    u = y - X @ beta
    meat = np.zeros((k, k))
    for label in labels:
        idx = [i for i, grp in enumerate(groups) if grp == label]
        score = X[idx].T @ u[idx]
        meat += np.outer(score, score)
    bread = np.linalg.inv(X.T @ X)
    cov = bread @ meat @ bread * (g / (g - 1)) * ((n - 1) / (n - k))
    se = float(np.sqrt(cov[1, 1]))
    t = float(beta[1] / se)
    return {"companies": g, "se": se, "t": t, "p": float(2 * stats.t.sf(abs(t), g - 1))}


def regression(events: list[dict]) ->dict:
    """CAR[+2,+10] on CAR[-10,-1]: a negative slope means a bigger run-up is followed by a worse reaction"""
    x = np.array([e["runup"] for e in events])
    y = np.array([e["CAR[+2,+10]"] for e in events])
    if len(x) < 3:
        return {"n": len(x)}
    fit = stats.linregress(x, y)
    return {"n": len(x), "slope": float(fit.slope), "intercept": float(fit.intercept),
            "t": float(fit.slope / fit.stderr), "p": float(fit.pvalue), "r2": float(fit.rvalue ** 2),
            "clustered": cluster_slope(x, y, [e["ticker"] for e in events])}


def analyze(results: dict) -> dict:
    events =enrich(results["events"])
    groups = {}
    for name, kind in GROUPS.items():
        sel = [e for e in events if kind is None or e["kind"] == kind]
        groups[name] = {"n": len(sel), "companies": len({e["ticker"] for e in sel}),
                        "strategies": strategy_table(sel), "runup_split": runup_split(sel),
                        "regression": regression(sel)} if len(sel) >= 4 else {"n": len(sel)}
    return {
        "settings": {
            **results["settings"], "round_trip_cost": COST, "strategies": STRATEGIES,
            "runup_window": list(RUNUP), "after_windows": {k: list(v) for k, v in WINDOWS.items()},
            "split": "run-up above the group's median vs at or below it",
        },
        "data": results["data"],
        "coverage": results["coverage"],
        "groups": groups,
        "events": events,
    }


# ── output
def _style(ax, title: str, xlabel: str, ylabel: str):
    ax.set_facecolor(es.PANEL)
    ax.set_title(title, color=es.TEXT, fontsize=13, pad=12, loc="left")
    ax.set_xlabel(xlabel, color=es.MUTED, fontsize=11)
    ax.set_ylabel(ylabel, color=es.MUTED, fontsize=11)
    ax.tick_params(colors=es.MUTED, labelsize=10)
    for spine in ax.spines.values():
        spine.set_color(es.GRID)
    ax.grid(color=es.GRID, linewidth=0.8, zorder=0)
    ax.axhline(0, color=es.MUTED, linewidth=0.8, zorder=1)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v * 100:+.0f}%")


def plot_strategies(res: dict, path: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    table =res["groups"]["all"]["strategies"]
    fig, ax = plt.subplots(figsize=(10, 5.6), facecolor=es.BG)
    _style(ax, f"Average abnormal return per trade by strategy (vs {es.MARKET}, market model)",
           "", "Average abnormal return per trade")
    ax.yaxis.set_major_formatter(lambda v, _: f"{v * 100:+.1f}%")  # steps of 0.5%
    xs = np.arange(len(STRATEGIES))
    mean = np.array([table[k]["abnormal"]["mean"] for k in STRATEGIES])
    half = np.array([mean[i] - table[k]["abnormal"]["ci95"][0] for i, k in enumerate(STRATEGIES)])
    ax.bar(xs, mean, width=0.5, color=es.ACCENT, zorder=2, label="Mean abnormal return")
    ax.errorbar(xs, mean, yerr=half, fmt="none", ecolor=es.TEXT, elinewidth=1.2, capsize=5, zorder=3,
                label="95% confidence interval")
    ax.set_xticks(xs)
    ax.set_xticklabels(
        [f"{k}: {s['name']}\nbuy {s['buy']}\nsell {s['sell']}\nn={table[k]['abnormal']['n']}"
         for k, s in STRATEGIES.items()], color=es.MUTED, fontsize=10)
    es._legend(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=es.BG)
    plt.close(fig)


def plot_scatter(res: dict, path: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    events, reg = res["events"], res["groups"]["all"]["regression"]
    fig, ax = plt.subplots(figsize=(10, 5.6), facecolor=es.BG)
    _style(ax, "Run-up before approval vs reaction after it, one dot per event",
           "Run-up: CAR[-10,-1]", "After: CAR[+2,+10]")
    ax.xaxis.set_major_formatter(lambda v, _: f"{v * 100:+.0f}%")
    ax.axvline(0, color=es.MUTED, linewidth=0.8, zorder=1)
    for kind, label, color in (("ORIG", "Original approval", es.ACCENT), ("EFFICACY", "New indication", es.ACCENT2)):
        sel= [e for e in events if e["kind"] == kind]
        ax.scatter([e["runup"] for e in sel], [e["CAR[+2,+10]"] for e in sel], s=42, color=color, alpha=0.9,
                   edgecolors=es.BG, linewidths=1, zorder=3, label=f"{label} (n={len(sel)})")
    xs = np.array([e["runup"] for e in events])
    line = np.linspace(xs.min(), xs.max(), 50)
    ax.plot(line, reg["intercept"] + reg["slope"] * line, color=es.TEXT, linewidth=1.8, linestyle="--", zorder=4,
            label=f"OLS fit, all events: slope {reg['slope']:+.2f}, p = {reg['p']:.2f}, R² = {reg['r2']:.3f}")
    es._legend(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=es.BG)
    plt.close(fig)


def _pct(v):
    return "    n/a" if v is None else f"{v * 100:+6.2f}%"

def _p(v):
    return "  n/a" if v is None else f"{v:5.3f}"


def print_tables(res: dict):
    print(f"\nstrategies: mean per trade, abnormal = market model vs {es.MARKET}; net = after {COST * 100:.2f}% cost")
    print(f"{'group':<9}{'':<4}{'n':>3} {'raw':>8} {'XBI':>8} {'abnormal':>9} {'median':>8} {'hit':>5} "
          f"{'t':>6} {'p':>6} {'p(co.)':>7} {'net abn':>8} {'net hit':>7}")
    print("-" * 100)
    for name, g in res["groups"].items():
        for key, s in g.get("strategies", {}).items():
            a, co = s["abnormal"], s["abnormal_by_company"]
            t = "   n/a" if a["t"] is None else f"{a['t']:6.2f}"
            print(f"{name:<9}{key:<4}{a['n']:>3} {_pct(s['raw']['mean']):>8} {_pct(s['xbi']['mean']):>8} "
                  f"{_pct(a['mean']):>9} {_pct(a['median']):>8} {a['hit_rate'] * 100:4.0f}% {t} {_p(a['p']):>6} "
                  f"{_p(co['p'] if co else None):>7} {_pct(s['abnormal_net']['mean']):>8} "
                  f"{s['abnormal_net']['hit_rate'] * 100:6.0f}%")

    print("\nrun-up split: mean abnormal return after approval, high vs low run-up CAR[-10,-1]")
    print(f"{'group':<9}{'window':<12}{'n hi/lo':>8} {'high':>8} {'low':>8} {'high-low':>9} {'p':>6}")
    print("-" * 66)
    for name, g in res["groups"].items():
        for window in WINDOWS:
            if "runup_split" not in g:
                continue
            s = g["runup_split"][window]
            d = s["high_minus_low"]
            print(f"{name:<9}{window:<12}{s['high']['n']:>3}/{s['low']['n']:<4} {_pct(s['high']['mean']):>8} "
                  f"{_pct(s['low']['mean']):>8} {_pct(d['diff'] if d else None):>9} {_p(d['p'] if d else None):>6}")

    print("\nregression: CAR[+2,+10] on CAR[-10,-1] (negative slope = sell-the-news)")
    print(f"{'group':<9}{'n':>3} {'slope':>7} {'t':>6} {'p':>6} {'R2':>6} {'p(clustered)':>13}")
    print("-" * 56)
    for name, g in res["groups"].items():
        r = g.get("regression")
        if r and "slope" in r:
            c = r["clustered"]
            print(f"{name:<9}{r['n']:>3} {r['slope']:>+7.2f} {r['t']:>6.2f} {r['p']:>6.3f} {r['r2']:>6.3f} "
                  f"{_p(c['p'] if c else None):>13}")


def plain_summary(res: dict) -> str:
    g = res["groups"]["all"]
    s, split, reg = g["strategies"], g["runup_split"] ["CAR[+2,+10]"], g["regression"]
    sig = lambda p: p is not None and p < 0.05
    verdict = lambda p: f"significant (p = {p:.3f})" if sig(p) else f"not significant (p = {p:.2f})"

    def trade_line(key):
        a = s[key]["abnormal"]
        word = "gained" if a["mean"] > 0 else "lost"
        return (f"- {key}, {STRATEGIES[key]['name'].lower()}: {word} {abs(a['mean']) * 100:.2f}% per trade beyond XBI "
                f"(median {a['median'] * 100:+.2f}%, {a['hit_rate'] * 100:.0f}% of trades positive); "
                f"{s[key]['abnormal_net']['mean'] * 100:+.2f}% after costs; {verdict(a['p'])}.")

    d = split["high_minus_low"]
    lines = [
        f"Based on {g['n']} approval events from {g['companies']} companies "
        f"({res['data']['first_event']} to {res['data']['last_event']}):",
        trade_line("A"), trade_line("B"), trade_line("C"),
        "",
        f"Sell-the-news test: stocks that ran up more than the median before approval earned "
        f"{split['high']['mean'] * 100:+.2f}% in days +2 to +10, those that ran up less {split['low']['mean'] * 100:+.2f}% "
        f"(n = {split['high']['n']} and {split['low']['n']}); difference {d['diff'] * 100:+.2f}%, {verdict(d['p'])}.",
    ]
    cl = reg["clustered"]
    reg_text =(f"Regression of the after-move on the run-up: slope {reg['slope']:+.2f} "
                f"(R² = {reg['r2']:.3f}), {verdict(reg['p'])}")
    if cl:
        reg_text += f"; with company-clustered errors p = {cl['p']:.2f} ({cl['companies']} companies)"
    lines.append(reg_text + ".")
    if d["diff"] < 0 and sig(d["p"]) and sig(reg["p"]) and reg["slope"] < 0:
        lines.append("So: there is some evidence for sell-the-news, but it needs more events and companies to trust.")
    elif d["diff"] < 0 or reg["slope"] < 0:
        lines.append("So: the direction is the sell-the-news one, but it is not statistically distinguishable from "
                     "no relationship, so this data does not show that a run-up predicts a worse reaction.")
    else:
        lines.append("So: no sign of sell-the-news here; stocks that ran up did not do worse afterwards.")
    o, e = res["groups"].get("ORIG", {}), res["groups"].get("EFFICACY", {})
    if "regression" in o and "regression" in e:
        lines.append(f"By type the slope is {o['regression']['slope']:+.2f} for original approvals (n={o['n']}, "
                     f"p = {o['regression']['p']:.2f}) and {e['regression']['slope']:+.2f} for new indications "
                     f"(n={e['n']}, p = {e['regression']['p']:.2f}); the original-approval groups are very small.")
    lines += [
        "",
        f"Caveats: the {g['n']} events come from only {g['companies']} companies, and events of one company are not "
        "independent, so p-values are optimistic (p(co.) in the table tests per-company averages instead). A and B "
        "assume you knew the action date 11 trading days ahead, which is only true when the PDUFA date is public. "
        "Several strategies and windows were tested on the same small sample, so one 'significant' result can be luck.",
        "Historical analysis, not investment advice; ignores slippage, taxes and position sizing.",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    es.add_source_args(parser)
    args = parser.parse_args()
    es.setup_logging()

    res = analyze(es.compute(args.source, args.years))
    es.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (es.RESULTS_DIR / "sell_the_news.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    plot_strategies(res, es.RESULTS_DIR / "sell_the_news_strategies.png")
    plot_scatter(res, es.RESULTS_DIR / "sell_the_news_scatter.png")
    print_tables(res)
    print("\n" + plain_summary(res))
    print(f"\nwrote {es.RESULTS_DIR}")


if __name__ == "__main__":
    main()