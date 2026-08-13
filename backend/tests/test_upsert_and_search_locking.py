from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.earnings_calendar import upsert_earnings_events, search_ticker


def _make_mock_db():
    db = AsyncMock()
    mock_result = MagicMock()
    db.execute = AsyncMock(return_value=mock_result)
    db.commit = AsyncMock()
    return db


class TestUpsertBatching:
    @pytest.mark.asyncio
    async def test_batches_large_inserts(self):
        """Rows should be split into <= 2000-row chunks (matching the
        function's internal _UPSERT_BATCH_SIZE) so a single statement never
        exceeds Postgres/asyncpg's bound-parameter limit."""
        batch_size = 2000
        events_data = [
            {
                "symbol": f"T{i}",
                "companyName": f"Company {i}",
                "date": "2026-02-16",
                "time": "",
                "fiscalDateEnding": None,
                "epsEstimated": None,
            }
            for i in range(batch_size + 10)
        ]

        db = _make_mock_db()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        db.execute.return_value.scalars.return_value = mock_scalars

        await upsert_earnings_events(db, events_data, return_events=False)

        # One execute() call per batch (2 batches), plus commit once.
        assert db.execute.call_count == 2
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_single_batch_for_small_input(self):
        db = _make_mock_db()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        db.execute.return_value.scalars.return_value = mock_scalars

        await upsert_earnings_events(
            db,
            [{"symbol": "AAPL", "companyName": "Apple", "date": "2026-02-16", "time": "", "fiscalDateEnding": None, "epsEstimated": None}],
            return_events=False,
        )

        assert db.execute.call_count == 1
        db.commit.assert_awaited_once()


class TestUpsertMarketCapCoalesce:
    @pytest.mark.asyncio
    async def test_coalesce_used_when_market_cap_present(self):
        """When a re-sync payload includes marketCap, the upsert statement's
        ON CONFLICT SET clause must coalesce it against the existing column
        (not blindly overwrite), so a later sync that omits marketCap
        doesn't null out a previously-enriched value."""
        from sqlalchemy.dialects.postgresql import insert as real_pg_insert

        db = _make_mock_db()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        db.execute.return_value.scalars.return_value = mock_scalars

        captured = {}

        def spy_insert(model):
            stmt = real_pg_insert(model)
            original_on_conflict = stmt.on_conflict_do_update

            def spy_on_conflict(**kwargs):
                captured["set_"] = kwargs.get("set_")
                return original_on_conflict(**kwargs)

            stmt.on_conflict_do_update = spy_on_conflict
            return stmt

        with patch("app.services.earnings_calendar.pg_insert", side_effect=spy_insert):
            await upsert_earnings_events(
                db,
                [{
                    "symbol": "AAPL",
                    "companyName": "Apple",
                    "date": "2026-02-16",
                    "time": "",
                    "fiscalDateEnding": None,
                    "epsEstimated": None,
                    "marketCap": 3_000_000_000_000.0,
                }],
                return_events=False,
            )

        market_cap_expr = str(captured["set_"]["market_cap"])
        assert "coalesce" in market_cap_expr.lower()

    @pytest.mark.asyncio
    async def test_market_cap_omitted_when_not_in_payload(self):
        """When the payload has no marketCap at all, the row dict built for
        the insert shouldn't contain a market_cap key at all, so the
        ON CONFLICT coalesce falls through to the existing DB value
        untouched rather than overwriting it with NULL."""
        from sqlalchemy.dialects.postgresql import insert as real_pg_insert

        db = _make_mock_db()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        db.execute.return_value.scalars.return_value = mock_scalars

        captured = {}

        def spy_insert(model):
            stmt = real_pg_insert(model)
            original_values = stmt.values

            def spy_values(rows):
                captured["rows"] = rows
                return original_values(rows)

            stmt.values = spy_values
            return stmt

        with patch("app.services.earnings_calendar.pg_insert", side_effect=spy_insert):
            await upsert_earnings_events(
                db,
                [{
                    "symbol": "AAPL",
                    "companyName": "Apple",
                    "date": "2026-02-16",
                    "time": "",
                    "fiscalDateEnding": None,
                    "epsEstimated": None,
                }],
                return_events=False,
            )

        assert all("market_cap" not in row for row in captured["rows"])


class TestSearchTickerLocking:
    @pytest.mark.asyncio
    async def test_fallback_skips_fetch_when_lock_not_acquired(self):
        """If another request already holds the ticker-search lock, this
        caller should not duplicate the Nasdaq/FMP fetch -- it should poll
        instead, and stop as soon as the holder's data shows up."""
        db = _make_mock_db()
        empty_scalars = MagicMock()
        empty_scalars.all.return_value = []
        found_scalars = MagicMock()
        found_scalars.all.return_value = [MagicMock()]
        # First poll: still empty (holder still fetching). Second poll: data
        # has landed, so the wait loop should stop there.
        db.execute.return_value.scalars.side_effect = [empty_scalars, empty_scalars, found_scalars]

        with patch("app.services.cache.should_search_alpha_vantage", new=AsyncMock(return_value=False)), \
             patch("app.services.cache.acquire_ticker_search_lock", new=AsyncMock(return_value=False)), \
             patch("app.services.cache.release_ticker_search_lock", new=AsyncMock()) as mock_release, \
             patch("app.services.earnings_calendar._fetch_historical_earnings_nasdaq", new=AsyncMock()) as mock_nasdaq, \
             patch("app.services.earnings_calendar._fetch_historical_earnings_fmp", new=AsyncMock()) as mock_fmp, \
             patch("app.services.earnings_calendar.asyncio.sleep", new=AsyncMock()):
            events = await search_ticker(db, "NEWCO")

        mock_nasdaq.assert_not_called()
        mock_fmp.assert_not_called()
        mock_release.assert_not_called()
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_fallback_stops_waiting_once_lock_frees_up_with_no_data(self):
        """If the lock holder finishes (or crashes) without producing data,
        the lock becomes acquirable again -- the waiter should notice that
        and stop polling instead of waiting out the full TTL."""
        db = _make_mock_db()
        empty_scalars = MagicMock()
        empty_scalars.all.return_value = []
        db.execute.return_value.scalars.return_value = empty_scalars

        # First acquire attempt (the real one) fails; the second attempt,
        # made from inside the wait loop once data still hasn't shown up,
        # succeeds -- simulating the original holder having released it.
        acquire_mock = AsyncMock(side_effect=[False, True])

        with patch("app.services.cache.should_search_alpha_vantage", new=AsyncMock(return_value=False)), \
             patch("app.services.cache.acquire_ticker_search_lock", new=acquire_mock), \
             patch("app.services.cache.release_ticker_search_lock", new=AsyncMock()) as mock_release, \
             patch("app.services.earnings_calendar._fetch_historical_earnings_nasdaq", new=AsyncMock()) as mock_nasdaq, \
             patch("app.services.earnings_calendar._fetch_historical_earnings_fmp", new=AsyncMock()) as mock_fmp, \
             patch("app.services.earnings_calendar.asyncio.sleep", new=AsyncMock()):
            events = await search_ticker(db, "NEWCO")

        mock_nasdaq.assert_not_called()
        mock_fmp.assert_not_called()
        assert events == []
        # The lock we re-acquired while polling must be released again,
        # rather than left held.
        mock_release.assert_awaited_once_with("NEWCO")

    @pytest.mark.asyncio
    async def test_fallback_fetches_and_releases_lock_when_acquired(self):
        db = _make_mock_db()
        empty_scalars = MagicMock()
        empty_scalars.all.return_value = []
        db.execute.return_value.scalars.return_value = empty_scalars

        with patch("app.services.cache.should_search_alpha_vantage", new=AsyncMock(return_value=False)), \
             patch("app.services.cache.acquire_ticker_search_lock", new=AsyncMock(return_value=True)), \
             patch("app.services.cache.release_ticker_search_lock", new=AsyncMock()) as mock_release, \
             patch("app.services.earnings_calendar._fetch_historical_earnings_nasdaq", new=AsyncMock(return_value=[])) as mock_nasdaq, \
             patch("app.services.earnings_calendar._fetch_historical_earnings_fmp", new=AsyncMock(return_value=[])) as mock_fmp:
            await search_ticker(db, "NEWCO")

        mock_nasdaq.assert_awaited_once()
        mock_fmp.assert_awaited_once()
        mock_release.assert_awaited_once_with("NEWCO")
