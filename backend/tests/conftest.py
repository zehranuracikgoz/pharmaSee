"""
test setup: sqlite db + offline fakes for yfinance, openfda and
clinicaltrials.gov — suite never touches the network.
"""
import copy
import os
import tempfile
import zlib
from pathlib import Path

# must run before any `app` import — settings are read at import time.
# fresh db per run so cached data never bleeds across runs.
_TEST_DB = Path(tempfile.mkdtemp(prefix="pharmasee-tests-")) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB.as_posix()}"

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


_FAKE_RESPONSES = {
    "api.fda.gov": _fake_openfda,
    "clinicaltrials.gov": lambda params: FAKE_CLINICAL_TRIALS,
}

_real_async_get = httpx.AsyncClient.get


async def _fake_async_get(self, url, *args, **kwargs):
    host = urlparse(str(url)).hostname
    if host in _FAKE_RESPONSES:
        payload = _FAKE_RESPONSES[host](kwargs.get("params"))
        return httpx.Response(200, json=payload, request=httpx.Request("GET", str(url)))
    if host is None or host == "test":
# test client talking to the app via ASGITransport
        return await _real_async_get(self, url, *args, **kwargs)
    raise RuntimeError(f"unexpected network call in tests: {url}")


@pytest.fixture(autouse=True)
def offline_apis(monkeypatch):
    monkeypatch.setattr(yfinance, "Ticker", FakeTicker)
    monkeypatch.setattr(httpx.AsyncClient, "get", _fake_async_get)
    yield