from datetime import datetime

# Import the real function instead of copying it. This file used to carry its own
# copy of _next_schedule_time with the pre-D27-2 `replace(day=day+1)` bug, so
# production was correct while the test was wrong — and the test only failed on
# the 30th of a 30-day month (2026-09-30 in CI), passing every other day.
from main import _add_days, _next_schedule_time


def test_month_end_rollover_does_not_overflow():
    """A 30-day month plus one day is a real date; replace(day=31) was not.

    Pins the exact failure CI hit on 2026-09-30, plus the other short months
    and a leap day, so this cannot silently regress back to replace(day=...).
    """
    for last_day, expected in (
        (datetime(2026, 9, 30), datetime(2026, 10, 1)),
        (datetime(2026, 4, 30), datetime(2026, 5, 1)),
        (datetime(2026, 6, 30), datetime(2026, 7, 1)),
        (datetime(2024, 2, 29), datetime(2024, 3, 1)),
    ):
        assert _add_days(last_day, 1) == expected


def test_slot_already_past_returns_tomorrow():
    result = _next_schedule_time(6)
    now = datetime.utcnow()
    if now.hour >= 6 and (now.hour > 6 or now.minute > 0 or now.second > 0):
        assert result > now.strftime("%Y-%m-%dT%H:%M:%SZ")
        assert "T06:00:00Z" in result
    else:
        assert result == now.strftime("%Y-%m-%d") + "T06:00:00Z"


def test_slot_format():
    result = _next_schedule_time(14)
    parts = result.split("T")
    assert len(parts) == 2
    date_part, time_part = parts
    assert time_part == "14:00:00Z"
    assert len(date_part) == 10


def test_two_slots_different():
    r1 = _next_schedule_time(6)
    r2 = _next_schedule_time(8)
    assert r1 != r2
    assert "T06:00:00Z" in r1
    assert "T08:00:00Z" in r2


def test_returns_utc_iso_format():
    result = _next_schedule_time(10)
    assert result.endswith("Z")
    datetime.strptime(result.replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
