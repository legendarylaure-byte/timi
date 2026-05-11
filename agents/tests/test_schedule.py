from datetime import datetime


def _next_schedule_time(hour: int) -> str:
    now = datetime.utcnow()
    scheduled = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if scheduled <= now:
        scheduled = scheduled.replace(day=scheduled.day + 1)
    return scheduled.strftime("%Y-%m-%dT%H:%M:%SZ")


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
