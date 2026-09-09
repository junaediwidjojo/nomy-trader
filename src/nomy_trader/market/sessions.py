"""Completed U.S. equity sessions, including holidays and early closes."""

from datetime import UTC, date, datetime, timedelta

import exchange_calendars as xcals  # type: ignore[import-untyped]


def completed_session(now: datetime) -> tuple[date, datetime]:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("session clock must be aware")
    now = now.astimezone(UTC)
    calendar = xcals.get_calendar(
        "XNYS",
        start=now.date() - timedelta(days=40),
        end=now.date() + timedelta(days=14),
    )
    schedule = calendar.schedule
    completed = schedule[schedule["close"] < now]
    label = completed.index[-1]
    future = schedule[schedule["close"] >= now]
    return label.date(), future.iloc[0]["close"].to_pydatetime()
