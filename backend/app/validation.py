import re

from fastapi import HTTPException

_TICKER_RE = re.compile(r"^(?=.{1,10}$)[A-Z]{1,10}([.\-][A-Z]{1,2})?$")

MAX_TICKERS_PER_REQUEST = 30


def validate_ticker(ticker: str) -> str:
    upper = ticker.upper().strip()
    if not _TICKER_RE.match(upper):
        raise HTTPException(status_code=422, detail="Invalid ticker format")
    return upper
