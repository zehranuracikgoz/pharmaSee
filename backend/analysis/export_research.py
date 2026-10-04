"""
export the event study and the sell-the-news backtest as the small static file the Research page
reads (frontend/public/data/research.json): summary numbers only, no raw price series.

run from backend/:
    python -m analysis.export_research [--source auto|db|openfda] [--years 5]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # also runnable as a plain script

from analysis import event_study as es  # noqa: E402
from analysis import sell_the_news as st  # noqa: E402

OUT_PATH = Path(__file__).resolve().parents[2] / "frontend" / "public" / "data" / "research.json"
WINDOW_NAMES = ["CAR[-10,-1]", "AR[0]", "CAR[0,+1]", "CAR[+1,+10]"]


def _round(values, digits: int = 5):
    if isinstance(values, (list, tuple)):
        return [_round(v, digits) for v in values]
    return None if values is None else round(float(values), digits)


def _band(stat: dict, kind: str) -> dict:
    # mean + 95% confidence band of the daily ("ar") or cumulative ("car") series
    s = stat[kind]
    return {"n": stat["n"], "mean": _round(s["mean"]), "lo": _round(s["lo95"]), "hi": _round(s["hi95"])}


def _window_groups(results: dict) -> list[dict]:
    events = results["events"]
    others = sorted({e["ticker"] for e in events if e["size"] == "small_cap"})
    larges = sorted({e["ticker"] for e in events if e["size"] == "large_cap"})
    # "small_cap" in the study just means "not a large cap": label it by the companies it holds
    groups = [
        ("all", "All events", sorted({e["ticker"] for e in events})),
        ("ORIG", "Original approvals", sorted({e["ticker"] for e in events if e["kind"] == "ORIG"})),
        ("EFFICACY", "New indications", sorted({e["ticker"] for e in events if e["kind"] == "EFFICACY"})),
        ("large_cap", "Large caps", larges),
        ("small_cap", "Other companies", others),
    ]
    out = []
    for key, label, tickers in groups:
        g = results["groups"][key]["market_model"]
        out.append({"key": key, "label": label, "n": g["n"], "tickers": tickers,
                    "stats": {w: {"n": int(g["windows"][w]["n"]), "mean": _round(g["windows"][w]["mean"]),
                                  "t": _round(g["windows"][w]["t"], 4), "p": _round(g["windows"][w]["p"], 4)}
                              for w in WINDOW_NAMES}})
    return out


def _strategies(analysis: dict) -> list[dict]:
    table = analysis["groups"]["all"]["strategies"]
    out = []
    for key, meta in st.STRATEGIES.items():
        a = table[key]["abnormal"]
        first, last = meta["hold"]
        out.append({
            "key": key, "name": meta["name"], "buy": meta["buy"], "sell": meta["sell"],
            "days_held": last - first + 1, "n": a["n"],
            "abnormal": {"mean": _round(a["mean"]), "lo": _round(a["ci95"][0]), "hi": _round(a["ci95"][1]),
                         "hit_rate": _round(a["hit_rate"], 3), "t": _round(a["t"], 4), "p": _round(a["p"], 4)},
            "raw": _round(table[key]["raw"]["mean"]), "xbi": _round(table[key]["xbi"]["mean"]),
        })
    return out


def build(results: dict, analysis: dict) -> dict:
    groups = results["groups"]
    reg = analysis["groups"]["all"]["regression"]
    return {
        "generated": results["settings"]["run_date"],
        "events": results["data"]["events"],
        "companies": results["data"]["tickers_with_events"],
        "first_event": results["data"]["first_event"],
        "last_event": results["data"]["last_event"],
        "coverage": results["coverage"],
        "settings": {
            "market": es.MARKET, "estimation_window": [es.EST_START, es.EST_END],
            "event_window": [-es.WINDOW, es.WINDOW], "cluster_days": es.CLUSTER_DAYS,
            "years": results["settings"]["years"], "round_trip_cost": st.COST,
        },
        "days": es.DAYS.tolist(),
        "daily_ar": _band(groups["all"]["market_model"], "ar"),
        "car": {
            "all": _band(groups["all"]["market_model"], "car"),
            "ORIG": _band(groups["ORIG"]["market_model"], "car"),
            "EFFICACY": _band(groups["EFFICACY"]["market_model"], "car"),
            "all_market_adjusted": _round(groups["all"]["market_adjusted"]["car"]["mean"]),
        },
        "windows": _window_groups(results),
        "strategies": _strategies(analysis),
        "scatter": {
            "points": [{"ticker": e["ticker"], "kind": e["kind"], "date": e["day0"],
                        "runup": _round(e["runup"]), "after": _round(e["CAR[+2,+10]"])}
                       for e in analysis["events"]],
            "regression": {"n": reg["n"], "slope": _round(reg["slope"], 4), "intercept": _round(reg["intercept"]),
                           "p": _round(reg["p"], 4), "r2": _round(reg["r2"], 5),
                           "clustered_p": _round(reg["clustered"]["p"], 4) if reg["clustered"] else None},
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    es.add_source_args(parser)
    args = parser.parse_args()
    es.setup_logging()

    results = es.compute(args.source, args.years)
    data = build(results, st.analyze(results))
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT_PATH} ({OUT_PATH.stat().st_size / 1024:.1f} KB): {data['events']} events, "
          f"{data['companies']} companies")


if __name__ == "__main__":
    main()
