from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.analysis import run_analysis_streaming


class _FakeSession:
    """Minimal async-context-manager session double. `commit_should_fail`
    lets the second `async with factory() as db` block (the persistence
    block) raise on commit while the first (read-only candidates lookup)
    succeeds normally."""

    def __init__(self, commit_should_fail=False):
        self.commit_should_fail = commit_should_fail
        self.added = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, *args, **kwargs):
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        return result

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        if self.commit_should_fail:
            raise RuntimeError("connection reset")

    async def refresh(self, obj):
        obj.id = 1


class _FakeSessionFactory:
    """Mimics get_session_factory()'s callable-returns-session-cm shape,
    handing out a fresh session per `async with factory() as db`, with the
    persistence-block (2nd) session configured to fail on commit."""

    def __init__(self):
        self.call_count = 0

    def __call__(self):
        self.call_count += 1
        # 1st call = read-only candidates lookup, 2nd = persistence block
        commit_should_fail = self.call_count >= 2
        return _FakeSession(commit_should_fail=commit_should_fail)


@pytest.mark.asyncio
async def test_commit_failure_yields_error_and_lock_still_released(sample_analysis_result):
    fake_factory = _FakeSessionFactory()

    lock_acquired = AsyncMock(return_value=True)
    lock_released = AsyncMock()

    with patch("app.services.cache.get_cached_analysis_redis", new=AsyncMock(return_value=None)), \
         patch("app.services.cache.acquire_analysis_lock", new=lock_acquired), \
         patch("app.services.cache.release_analysis_lock", new=lock_released), \
         patch("app.services.cache.set_cached_analysis_redis", new=AsyncMock()), \
         patch("app.db.database.get_session_factory", return_value=fake_factory), \
         patch("app.services.analysis.search_earnings_report", new=AsyncMock(return_value="some search text")), \
         patch("app.services.analysis.analyze_earnings", new=AsyncMock(return_value=dict(sample_analysis_result))):
        events = []
        async for event_type, payload in run_analysis_streaming("AAPL", "Q4-2025"):
            events.append((event_type, payload))

    error_events = [e for e in events if e[0] == "error"]
    assert len(error_events) == 1
    assert error_events[0][1] == {"error": "Failed to save analysis results"}

    # No "result" event should have been yielded since persistence failed.
    assert not any(e[0] == "result" for e in events)

    # The lock must still be released via the caller's `finally`, even
    # though the persistence block raised.
    lock_acquired.assert_awaited_once()
    lock_released.assert_awaited_once_with("AAPL", "Q4-2025")


@pytest.mark.asyncio
async def test_successful_commit_yields_result_and_releases_lock(sample_analysis_result):
    class _AlwaysSucceedFactory:
        def __call__(self):
            return _FakeSession(commit_should_fail=False)

    lock_acquired = AsyncMock(return_value=True)
    lock_released = AsyncMock()

    with patch("app.services.cache.get_cached_analysis_redis", new=AsyncMock(return_value=None)), \
         patch("app.services.cache.acquire_analysis_lock", new=lock_acquired), \
         patch("app.services.cache.release_analysis_lock", new=lock_released), \
         patch("app.services.cache.set_cached_analysis_redis", new=AsyncMock()), \
         patch("app.db.database.get_session_factory", return_value=_AlwaysSucceedFactory()), \
         patch("app.services.analysis.search_earnings_report", new=AsyncMock(return_value="some search text")), \
         patch("app.services.analysis.analyze_earnings", new=AsyncMock(return_value=dict(sample_analysis_result))):
        events = []
        async for event_type, payload in run_analysis_streaming("AAPL", "Q4-2025"):
            events.append((event_type, payload))

    result_events = [e for e in events if e[0] == "result"]
    assert len(result_events) == 1
    assert not any(e[0] == "error" for e in events)

    lock_released.assert_awaited_once_with("AAPL", "Q4-2025")
