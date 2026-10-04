"""
test setup: sqlite db + offline fakes for yfinance, openfda, clinicaltrials.gov
and sec edgar — suite never touches the network.
"""
import atexit
import copy
import json
import os
import shutil
import tempfile
import zlib
from pathlib import Path

# must run before any `app` import — settings are read at import time.
# fresh db per run so cached data never bleeds across runs.
_TEST_DB = Path(tempfile.mkdtemp(prefix="pharmasee-tests-")) / "test.db"
atexit.register(shutil.rmtree, _TEST_DB.parent, ignore_errors=True)  # don't leave a folder per run
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB.as_posix()}"
# never send the real contact email / api key; also lets ci run without a .env
os.environ["SEC_CONTACT_EMAIL"] = "tests@example.com"
os.environ["GEMINI_API_KEY"] = "test-key"
os.environ["GEMINI_MIN_INTERVAL_SECONDS"] = "0"
TEST_ADMIN_TOKEN = "test-admin-token"
os.environ["ADMIN_TOKEN"] = TEST_ADMIN_TOKEN

from datetime import date, timedelta  # noqa: E402
from types import SimpleNamespace  # noqa: E402
from urllib.parse import urlparse  # noqa: E402

import httpx  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402
import yfinance  # noqa: E402

from app.config import settings  # noqa: E402

# differs from the .info marketCap so tests can tell which source was used
FAST_INFO_MARKET_CAP = 42_000_000_000


# ── yfinance

def _fake_info(ticker: str) -> dict:
    name = settings.TRACKED_TICKERS[ticker]
    return {
        "shortName": name,
        "longName": f"{name} Inc.",
        "sector": "Healthcare",
        "marketCap": 50_000_000_000,
        "regularMarketPrice": 101.25,
        "previousClose": 100.0,
        "longBusinessSummary": f"{name} is a biotechnology company (test data).",
    }


def _fake_history(start=None, end=None) -> pd.DataFrame:
    if start is None:
        end_d = date.today()
        start_d = end_d - timedelta(days=30)
    else:
        start_d = pd.Timestamp(start).date()
        end_d = pd.Timestamp(end).date() if end else date.today()

    # yfinance end is exclusive
    idx = pd.bdate_range(start_d, end_d - timedelta(days=1), tz="America/New_York", name="Date")
    n = len(idx)
    close = 100 + 10 * np.sin(np.arange(n) / 15)
    return pd.DataFrame(
        {
            "Open": close - 0.5,
            "High": close + 1.0,
            "Low": close - 1.0 ,
            "Close": close,
            "Volume": np.full(n, 1_000_000),
            "Dividends": 0.0,
            "Stock Splits": 0.0,
        },
        index=idx,
    )


class FakeTicker:
    """stand-in for yfinance.Ticker. unknown symbols return no data, like real yfinance."""

    def __init__(self, ticker: str, *args, **kwargs):
        self.ticker=ticker.upper()
        self._known = self.ticker in settings.TRACKED_TICKERS
        self.info = _fake_info(self.ticker) if self._known else {"trailingPegRatio": None}
        # unknown symbols give None here too, like real yfinance
        self.fast_info = SimpleNamespace(
            market_cap=FAST_INFO_MARKET_CAP if self._known else None,
            last_price=101.25 if self._known else None,
            previous_close=100.0 if self._known else None,
        )

    def get_info(self) -> dict:
        return dict(self.info)

    def history(self, period=None, start=None, end=None, **kwargs) -> pd.DataFrame:
        if not self._known:
            return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
        return _fake_history(start=start, end=end)


# ── openfda /clinicaltrials.gov 

FAKE_OPENFDA = {
    "meta": {"results": {"skip": 0, "limit": 50, "total": 1}},
    "results": [
        {
            "application_number": "BLA761339",
            "sponsor_name": "TEST PHARMA",
            "openfda": {
                "brand_name": ["TESTUMAB"],
                "generic_name": ["testumab"],
                "manufacturer_name": ["Test Pharma Inc."],
            },
            "products": [
                {
                    "product_number": "001",
                    "brand_name": "TESTUMAB",
                    "dosage_form": "INJECTION, SOLUTION",
                    "route": "SUBCUTANEOUS",
                    "marketing_status": "Prescription",
                }
            ],
            "submissions": [
                {
                    "submission_type": "ORIG",
                    "submission_number": "1",
                    "submission_status": "AP",
                    "submission_status_date": "20240115",
                    "submission_class_code": "TYPE 1",
                },
                {
                    "submission_type": "SUPPL",
                    "submission_number": "4",
                    "submission_status": "AP",
                    "submission_status_date": "20250610",
                    "submission_class_code": "EFFICACY",
                },
                {
                    "submission_type": "SUPPL",
                    "submission_number":"5",
                    "submission_status": "AP",
                    "submission_status_date": "20250801",
                    "submission_class_code": "LABELING",
                },
            ],
        }
    ],
}

FAKE_CLINICAL_TRIALS = {
    "studies": [
        {
            "protocolSection": {
                "identificationModule": {"nctId": "NCT00000001", "briefTitle": "Test Study"},
                "statusModule": {"overallStatus": "RECRUITING"},
                "designModule": {"phases": ["PHASE3"]},
                "conditionsModule": {"conditions": ["Test Condition"]},
            }
        }
    ]
}


def _fake_openfda(params: dict | None) -> dict:
# unique app number per manufacturer so shared-application tests work
    term = str((params or {}).get("search", ""))
    payload = copy.deepcopy(FAKE_OPENFDA)
    payload["results"][0]["application_number"] = f"BLA{800000 + zlib.crc32(term.encode()) % 100000}"
    return payload


# ── sec edgar
# MRNA: one 8-K with an EX-99.1 kept; a 2.02 8-K, a 10-Q and a >180-day-old 8-K are filtered out.
# BNTX: one 6-K with no exhibit, so the primary document is stored.

SEC_CIKS = {"MRNA": 1682852, "BNTX": 1776985}
SEC_REQUESTS: list[str] = []  # urls requested, so tests can check nothing is re-downloaded


def _sec_filings(rows: list[tuple]) -> dict:
    # rows: (accession, form, items, days ago, primary document)
    today = date.today()
    return {"filings": {"recent": {
        "accessionNumber": [r[0] for r in rows],
        "form": [r[1] for r in rows],
        "items": [r[2] for r in rows],
        "filingDate": [(today - timedelta(days=r[3])).isoformat() for r in rows],
        "primaryDocument": [r[4] for r in rows],
    }}}


FAKE_SEC_SUBMISSIONS = {
    SEC_CIKS["MRNA"]: _sec_filings([
        ("0001682852-26-000201", "8-K", "7.01,9.01", 10, "mrna-8k.htm"),
        ("0001682852-26-000202", "8-K", "2.02,9.01", 20, "mrna-earnings.htm"),
        ("0001682852-26-000203", "10-Q", "", 30, "mrna-10q.htm"),
        ("0001682852-25-000204", "8-K", "8.01", 400, "mrna-old.htm"),
    ]),
    SEC_CIKS["BNTX"]: _sec_filings([
        ("0001776985-26-000301", "6-K", "", 5, "form6-k.htm"),
    ]),
}

FAKE_SEC_INDEX = {
    "000168285226000201": ["000168285226000201-index.html", "mrna-8k.htm", "ex99-1.htm"],
    "000177698526000301": ["000177698526000301-index.html", "form6-k.htm"],
}

FAKE_SEC_DOCS = {
    "ex99-1.htm": (
        "<html><head><title>EX-99.1</title><style>p { color: red }</style></head><body>"
        "<p>Moderna announces FDA PDUFA date&nbsp;of December 1.</p>"
        '<div style="display:none"><ix:header>hidden xbrl data</ix:header></div>'
        "</body></html>"
    ),
    "mrna-8k.htm": "<html><body><p>Item 7.01 Regulation FD Disclosure. See Exhibit 99.1.</p></body></html>",
    "form6-k.htm": "<html><body><p>BioNTech announces a Phase 3 trial readout.</p></body></html>",
}


def _fake_sec(url: str) -> httpx.Response:
    SEC_REQUESTS.append(url)
    path = urlparse(url).path
    request = httpx.Request("GET", url)
    if path == "/files/company_tickers.json":
        rows = {str(i): {"cik_str": cik, "ticker": t, "title": t} for i, (t, cik) in enumerate(SEC_CIKS.items())}
        return httpx.Response(200, json=rows, request=request)
    if path.startswith("/submissions/CIK"):
        cik = int(path.removeprefix("/submissions/CIK").removesuffix(".json"))
        if cik not in FAKE_SEC_SUBMISSIONS:
            return httpx.Response(404, request=request)
        return httpx.Response(200, json=FAKE_SEC_SUBMISSIONS[cik], request=request)
    if path.endswith("/index.json"):
        acc = path.split("/")[-2]
        items = [{"name": n, "type": "text.gif"} for n in FAKE_SEC_INDEX.get(acc, [])]
        return httpx.Response(200, json={"directory": {"item": items}}, request=request)
    name = path.rsplit("/", 1)[-1]
    if name in FAKE_SEC_DOCS:
        return httpx.Response(200, text=FAKE_SEC_DOCS[name], request=request)
    return httpx.Response(404, request=request)


# ── gemini
# tests queue replies: a list of catalysts, or an http status code (e.g. 429) for an error.
# an empty queue answers with no catalysts.

GEMINI_QUEUE: list = []
GEMINI_CALLS: list[dict] = []  # request bodies sent to gemini


def _fake_gemini(url: str, body: dict) -> httpx.Response:
    GEMINI_CALLS.append(body)
    request = httpx.Request("POST", url)
    reply = GEMINI_QUEUE.pop(0) if GEMINI_QUEUE else []
    if isinstance(reply, int):
        error = {"code": reply, "status": "RESOURCE_EXHAUSTED" if reply == 429 else "INTERNAL", "message": "fake"}
        return httpx.Response(reply, json={"error": error}, request=request)
    text = json.dumps({"catalysts": reply})
    return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": text}]}}]}, request=request)


# ── second voter: fake openai-compatible provider that voting tests add to PROVIDERS
# same queue format as gemini, plus a str for a raw reply (e.g. invalid json)

SECOND_LLM_HOST = "second-llm.test"
SECOND_QUEUE: list = []
SECOND_CALLS: list[dict] = []


def _fake_openai_compatible(url: str, body: dict) -> httpx.Response:
    SECOND_CALLS.append(body)
    request = httpx.Request("POST", url)
    reply = SECOND_QUEUE.pop(0) if SECOND_QUEUE else []
    if isinstance(reply, int):
        return httpx.Response(reply, json={"error": {"message": "fake", "type": "fake"}}, request=request)
    content = reply if isinstance(reply, str) else json.dumps({"catalysts": reply})
    return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": content}}]},
                          request=request)


def _json_response(payload):
    return lambda url, params: httpx.Response(200, json=payload(params), request=httpx.Request("GET", url))


_FAKE_RESPONSES = {
    "api.fda.gov": _json_response(_fake_openfda),
    "clinicaltrials.gov": _json_response(lambda params: FAKE_CLINICAL_TRIALS),
    "www.sec.gov": lambda url, params: _fake_sec(url),
    "data.sec.gov": lambda url, params: _fake_sec(url),
}

_real_async_get = httpx.AsyncClient.get


async def _fake_async_get(self, url, *args, **kwargs):
    host = urlparse(str(url)).hostname
    if host in _FAKE_RESPONSES:
        return _FAKE_RESPONSES[host](str(url), kwargs.get("params"))
    if host is None or host == "test":
# test client talking to the app via ASGITransport
        return await _real_async_get(self, url, *args, **kwargs)
    raise RuntimeError(f"unexpected network call in tests: {url}")


_real_async_post = httpx.AsyncClient.post


async def _fake_async_post(self, url, *args, **kwargs):
    host = urlparse(str(url)).hostname
    if host == "generativelanguage.googleapis.com":
        return _fake_gemini(str(url), kwargs.get("json") or {})
    if host == SECOND_LLM_HOST:
        return _fake_openai_compatible(str(url), kwargs.get("json") or {})
    if host is None or host == "test":
        return await _real_async_post(self, url, *args, **kwargs)
    raise RuntimeError(f"unexpected network call in tests: POST {url}")


@pytest.fixture(autouse=True)
def offline_apis(monkeypatch):
    monkeypatch.setattr(yfinance, "Ticker", FakeTicker)
    monkeypatch.setattr(httpx.AsyncClient, "get", _fake_async_get)
    monkeypatch.setattr(httpx.AsyncClient, "post", _fake_async_post)
    GEMINI_QUEUE.clear()
    GEMINI_CALLS.clear()
    SECOND_QUEUE.clear()
    SECOND_CALLS.clear()
    yield