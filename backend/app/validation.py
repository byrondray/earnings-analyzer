import re

from fastapi import HTTPException

_TICKER_RE = re.compile(r"^(?=.{1,10}$)[A-Z]{1,10}([.\-][A-Z]{1,2})?$")
_QUARTER_RE = re.compile(r"^Q[1-4]-\d{4}$")

MAX_TICKERS_PER_REQUEST = 30


def validate_ticker(ticker: str) -> str:
    upper = ticker.upper().strip()
    if not _TICKER_RE.match(upper):
        raise HTTPException(status_code=422, detail="Invalid ticker format")
    return upper


def validate_quarter(quarter: str) -> str:
    q = quarter.strip()
    if not _QUARTER_RE.match(q):
        raise HTTPException(status_code=422, detail="Invalid quarter format, expected Q1-2025")
    return q
