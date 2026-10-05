"""Overnight health guards -- the alert path that had never once run.

The guards lived inside a single try/except in daily_analytics_job, and the
staleness timestamp conversion produced a NAIVE datetime while check_staleness
subtracted it from an aware one. The TypeError was raised before the resource
and daily-volume blocks, so both were skipped on every run, and the failure was
logged at "debug" so nobody saw it. Proof from the production log: the string
"Daily volume OK" appears ZERO times, while "can't subtract offset-naive and
offset-aware datetimes" appears 5 times.

There are now two independent defences -- the conversion in main.py and the
naive-input normalisation in check_staleness -- which is exactly the shape that
hides a regression: removing either one alone still leaves the suite green,
because the other covers for it. So each layer gets its own test:

  * test_staleness_accepts_naive_datetime  -> pins the alert_manager layer
  * test_guard_staleness_passes_aware_ts    -> pins the main.py layer

Reverting EITHER one fails exactly one test. Same reasoning as the D46 zoompan
fix, where an output-side -t masked a reverted `d` and four tests stayed green.
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from utils import alert_manager  # noqa: E402
from utils.alert_manager import check_run_produced_today, check_staleness  # noqa: E402


# --------------------------------------------------------------- fake Firestore
class _Doc:
    def __init__(self, data, exists=True):
        self._data = data
        self.exists = exists

    def to_dict(self):
        return self._data


class _Query:
    def __init__(self, docs):
        self._docs = list(docs)

    def order_by(self, *a, **k):
        return self

    def where(self, *a, **k):
        return self

    def limit(self, n):
        return _Query(self._docs[:n])

    def stream(self):
        return iter(self._docs)


class _Collection:
    def __init__(self, docs=()):
        self._docs = list(docs)

    def order_by(self, *a, **k):
        return _Query(self._docs)

    def where(self, *a, **k):
        return _Query(self._docs)

    def limit(self, n):
        return _Query(self._docs[:n])

    def document(self, name):
        return _Doc({})


class _FakeDB:
    def __init__(self, activity_docs=(), video_docs=(), heartbeat=None):
        self._collections = {
            "activity_logs": _Collection(activity_docs),
            "videos": _Collection(video_docs),
            "system": _Collection([heartbeat] if heartbeat else []),
        }

    def collection(self, name):
        return self._collections.get(name, _Collection())


class _FakeTimestamp:
    """Shaped like google.cloud.Timestamp, which is what Firestore returns."""

    def __init__(self, seconds):
        self._seconds = seconds

    def timestamp(self):
        return self._seconds


def _main():
    """Import main, or skip.

    Importing main pulls in crewai -> langchain, which the host does not have
    (the container does). Without this, every test below would be a new HOST
    failure rather than a container pass, which inflates the known 14-failure
    baseline and hides real regressions behind a growing pile. Same pattern as
    test_facebook_resumable.py. The container is the gate; `verify.sh` runs it.
    """
    return pytest.importorskip("main", reason="needs container deps")


# ------------------------------------------------- layer 1: alert_manager side
def test_staleness_accepts_naive_datetime():
    """The exact production crash: a naive datetime must not raise.

    A naive value is what datetime.utcfromtimestamp() produced, so this is the
    input that made every guard after it unreachable. It must RETURN, not raise.
    """
    stale_naive = datetime.utcnow() - timedelta(hours=72)
    result = check_staleness(stale_naive)  # must not raise
    assert result is not None, "72h of silence past a 24h window must alert"
    assert result["type"] == "staleness"


def test_staleness_accepts_aware_datetime():
    assert check_staleness(datetime.now(timezone.utc) - timedelta(hours=72)) is not None


def test_staleness_fresh_activity_does_not_alert():
    assert check_staleness(datetime.now(timezone.utc) - timedelta(minutes=5)) is None


def test_staleness_none_is_none():
    """Unknown activity must not be reported as stale (no data != dead)."""
    assert check_staleness(None) is None


def test_staleness_naive_and_aware_agree():
    """Not just "does not raise" -- the two forms must give the same verdict."""
    stamp = datetime.now(timezone.utc) - timedelta(hours=30)
    assert bool(check_staleness(stamp)) is bool(check_staleness(stamp.replace(tzinfo=None)))


# ------------------------------------------------------- layer 2: main.py side
def _record_last_activity(monkeypatch):
    seen = {}

    def _recorder(last_activity, *a, **k):
        seen["value"] = last_activity
        return None

    monkeypatch.setattr(alert_manager, "check_staleness", _recorder)
    return seen


def test_guard_staleness_passes_aware_timestamp(monkeypatch):
    """main.py must hand check_staleness an AWARE datetime.

    This is the layer check_staleness' own normalisation now hides: with the
    normalisation in place a naive value from main.py would still work, so a test
    that only asserts the alert fires would pass against the bug. Assert the
    value itself.
    """
    _guard_staleness = _main()._guard_staleness

    seen = _record_last_activity(monkeypatch)
    db = _FakeDB(activity_docs=[_Doc({"timestamp": _FakeTimestamp(1_760_000_000.0)})])

    _guard_staleness(db)

    assert "value" in seen, "check_staleness was never called"
    assert seen["value"].tzinfo is not None, (
        "main.py produced a naive datetime; the TypeError returns and every "
        "guard scheduled after it stops running"
    )


def test_guard_staleness_handles_iso_string(monkeypatch):
    """The string branch was already aware and must stay that way."""
    _guard_staleness = _main()._guard_staleness

    seen = _record_last_activity(monkeypatch)
    db = _FakeDB(activity_docs=[_Doc({"timestamp": "2026-10-05T07:00:00Z"})])

    _guard_staleness(db)

    assert seen["value"].tzinfo is not None


def test_guard_staleness_tolerates_null_timestamp(monkeypatch):
    """A doc with no timestamp must not raise."""
    _guard_staleness = _main()._guard_staleness

    monkeypatch.setattr(alert_manager, "check_staleness", lambda la, *a, **k: None)
    _guard_staleness(_FakeDB(activity_docs=[_Doc({})]))


# ------------------------------------------- isolation: one guard cannot disarm
def test_run_guard_reports_failure_without_raising():
    main = _main()

    assert main._run_guard("boom", lambda: 1 / 0) is False


def test_run_guard_reports_success():
    main = _main()

    assert main._run_guard("fine", lambda: None) is True


_GUARDS = (
    ("_guard_staleness", "staleness"),
    ("_guard_system_resources", "resources"),
    ("_guard_daily_volume", "volume"),
    ("_guard_run_produced_today", "produced"),
)


def _stub_guards(monkeypatch, main, ran, boom=None):
    for attr, key in _GUARDS:
        if key == boom:
            def _explode(db=None, _k=key):
                raise RuntimeError("resource probe exploded")
            monkeypatch.setattr(main, attr, _explode)
        else:
            monkeypatch.setattr(
                main, attr, (lambda k: lambda db=None: ran.append(k))(key)
            )
    monkeypatch.setattr("utils.firebase_status.get_firestore_client", lambda: _FakeDB())
    monkeypatch.setattr(main, "log_event", lambda *a, **k: None)


def test_pipeline_guard_isolates_a_failing_guard(monkeypatch):
    """One broken guard must not skip the others. This is the structural fix.

    Reverting _run_guard to a single shared try/except -- the original shape --
    makes the last two assertions fail.
    """
    main = _main()

    ran = []
    _stub_guards(monkeypatch, main, ran, boom="resources")

    main.pipeline_guard_job()

    assert "volume" in ran, "a later guard was skipped by an earlier failure"
    assert "produced" in ran, "a later guard was skipped by an earlier failure"
    assert "staleness" in ran


def test_pipeline_guard_runs_all_four(monkeypatch):
    main = _main()

    ran = []
    _stub_guards(monkeypatch, main, ran)

    main.pipeline_guard_job()

    assert sorted(ran) == ["produced", "resources", "staleness", "volume"], (
        f"unexpected guards ran: {ran}"
    )


def test_daily_analytics_still_calls_the_guards():
    """08:00 must keep running them, or moving them out loses that coverage."""
    import inspect

    main = _main()

    src = inspect.getsource(main.daily_analytics_job)
    assert "pipeline_guard_job()" in src


# ------------------------------------------------------------ run-produced guard
def test_run_produced_today_quiet_before_deadline():
    """At 08:00 the day's run has not been attempted; alerting would be a lie."""
    assert check_run_produced_today(0, deadline_hour=16, now_hour=8) is None
    assert check_run_produced_today(0, deadline_hour=16, now_hour=15) is None


def test_run_produced_today_alerts_after_deadline_with_nothing():
    alert = check_run_produced_today(0, deadline_hour=16, now_hour=16)
    assert alert is not None
    assert alert["type"] == "run_produced_nothing"
    assert alert["severity"] == "error"


def test_run_produced_today_quiet_when_something_was_produced():
    assert check_run_produced_today(1, deadline_hour=16, now_hour=20) is None


def test_run_produced_today_defaults_to_real_utc():
    """With no now_hour it reads the wall clock; must not raise."""
    assert check_run_produced_today(1) is None


# ------------------------------------------------- no-db must not fake a fault
def test_run_produced_guard_stays_quiet_without_firestore(monkeypatch):
    """A Firestore outage must not be reported as 'the pipeline produced nothing'.

    This is the same family as the 401-rendered-as-offline bug: a failure to
    READ state is not a state that was read. Distinguishing them needs an
    explicit return, because an unqueryable collection looks identical to an
    empty one.
    """
    main = _main()

    sent = []
    monkeypatch.setattr("utils.firebase_status.get_firestore_client", lambda: None)
    monkeypatch.setattr(main, "send_alert", lambda *a, **k: sent.append(a))
    monkeypatch.setattr(main, "log_event", lambda *a, **k: None)

    main._guard_run_produced_today(None)

    assert sent == [], "alerted on an unreachable Firestore instead of on the real signal"


def test_run_produced_guard_alerts_on_real_zero(monkeypatch):
    """And the inverse: an EMPTY collection after the deadline must alert."""
    main = _main()

    sent = []
    monkeypatch.setattr(main, "send_alert", lambda *a, **k: sent.append(a))
    monkeypatch.setattr(main, "log_event", lambda *a, **k: None)
    monkeypatch.setenv("RUN_DEADLINE_UTC_HOUR", "0")

    main._guard_run_produced_today(_FakeDB(video_docs=[]))

    assert len(sent) == 1, f"expected exactly one alert, got {sent}"


def test_run_produced_guard_quiet_when_videos_exist(monkeypatch):
    """Any video doc today counts -- the question is whether the run happened."""
    main = _main()

    sent = []
    monkeypatch.setattr(main, "send_alert", lambda *a, **k: sent.append(a))
    monkeypatch.setattr(main, "log_event", lambda *a, **k: None)

    main._guard_run_produced_today(
        _FakeDB(video_docs=[_Doc({"created_at": datetime.now(timezone.utc)})])
    )

    assert sent == []


# ------------------------------------------- daily volume: the CALL SITE target
def test_daily_volume_guard_passes_the_planners_slate(monkeypatch):
    """The guard must pass daily_slate() (5/day), not SCHEDULE_* sum (3/day).

    This test exists because mutation M7 SURVIVED the first run of the suite:
    test_daily_volume.py pins check_daily_volume and daily_slate separately, and
    neither can see which one the CALLER hands over. Reverting the guard to the
    old SCHEDULE_* sum -- the exact defect that made the guard pass on a day
    that shipped 3 of 5 -- left every test green.

    Same gap as the `.get(key, unbound_local)` incident, where 299 green helper
    tests coexisted with a broken call site. A test on the helper cannot see a
    bug in the caller.
    """
    main = _main()
    import utils.scheduler_planner as sp

    seen = {}
    monkeypatch.setattr(
        alert_manager,
        "check_daily_volume",
        lambda docs, slate: seen.update(slate=slate, docs=docs) or None,
    )
    monkeypatch.setattr(main, "send_alert", lambda *a, **k: None)
    monkeypatch.setattr(main, "log_event", lambda *a, **k: None)

    main._guard_daily_volume(_FakeDB(video_docs=[]))

    assert seen.get("slate") == sp.daily_slate(), (
        "guard used a different target than the planner; the SCHEDULE_* sum is "
        f"{int(os.environ.get('SCHEDULE_SHORTS_PER_DAY', '1')) + int(os.environ.get('SCHEDULE_LONG_PER_DAY', '2'))} "
        f"but real daily volume is {sp.daily_slate()['total']}"
    )


def test_daily_volume_guard_logs_the_ok_line(monkeypatch):
    """'Daily volume OK' appears ZERO times in the production log. It must appear now.

    A guard that runs but says nothing on success is indistinguishable from the
    guard that never ran -- which is exactly the failure being fixed.
    """
    main = _main()
    events = []
    monkeypatch.setattr(alert_manager, "check_daily_volume", lambda docs, slate: None)
    monkeypatch.setattr(main, "send_alert", lambda *a, **k: None)
    monkeypatch.setattr(main, "log_event", lambda tag, msg, *a, **k: events.append(msg))

    main._guard_daily_volume(_FakeDB(video_docs=[]))

    assert any("Daily volume OK" in m for m in events), f"no OK line logged: {events}"


def test_daily_volume_guard_alerts_on_short_slate(monkeypatch):
    """And it must actually send when the alert comes back."""
    main = _main()
    sent = []
    monkeypatch.setattr(
        alert_manager,
        "check_daily_volume",
        lambda docs, slate: {"message": "0/5 videos", "severity": "error"},
    )
    monkeypatch.setattr(main, "send_alert", lambda *a, **k: sent.append(a))
    monkeypatch.setattr(main, "log_event", lambda *a, **k: None)

    main._guard_daily_volume(_FakeDB(video_docs=[]))

    assert len(sent) == 1, f"expected an alert, got {sent}"


# ------------------------------------------------------------------ cooldown
def _slack_recorder(monkeypatch):
    calls = []
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.example/xyz")
    monkeypatch.setattr(
        "utils.slack_notifier.send_alert_slack",
        lambda msg, *a, **k: calls.append(msg) or True,
    )
    return calls


def test_send_alert_cooldown_suppresses_a_repeat(monkeypatch):
    """A 15-min poll must not become ~52 identical Slack messages a night."""
    import utils.slack_notifier as slack

    calls = _slack_recorder(monkeypatch)
    monkeypatch.setattr(alert_manager, "_alert_last_sent", {})

    assert alert_manager.send_alert("disk is full", "warning", alert_type="system_resources") is True
    assert alert_manager.send_alert("disk is full", "warning", alert_type="system_resources") is False

    assert len(calls) == 1, f"cooldown did not suppress the repeat: {calls}"


def test_send_alert_cooldown_is_per_type(monkeypatch):
    """A real disk fault must not mask a real staleness fault."""
    calls = _slack_recorder(monkeypatch)
    monkeypatch.setattr(alert_manager, "_alert_last_sent", {})

    alert_manager.send_alert("disk", "warning", alert_type="system_resources")
    alert_manager.send_alert("stale", "warning", alert_type="staleness")

    assert len(calls) == 2, f"one type suppressed another: {calls}"


def test_send_alert_still_suppressed_inside_the_window(monkeypatch):
    """The control for the expiry test: 1h into a 6h window is still suppressed.

    Written after the expiry test failed for the wrong reason -- I advanced the
    clock 1h against a 6h cooldown and asserted a resend. The guard was right and
    the assertion was wrong, which is the same shape as the D45 check that
    'passed' an invisible logo.
    """
    calls = _slack_recorder(monkeypatch)
    monkeypatch.setattr(alert_manager, "_alert_last_sent", {})
    monkeypatch.setattr(alert_manager, "ALERT_COOLDOWN_HOURS", 6)
    monkeypatch.setattr(alert_manager.time, "time", lambda: 0.0)

    alert_manager.send_alert("disk", "warning", alert_type="system_resources")
    monkeypatch.setattr(alert_manager.time, "time", lambda: 3601.0)

    assert alert_manager.send_alert("disk", "warning", alert_type="system_resources") is False
    assert len(calls) == 1


def test_send_alert_resends_after_the_cooldown(monkeypatch):
    """Suppression must expire, or a long outage goes unreported for good."""
    calls = _slack_recorder(monkeypatch)
    monkeypatch.setattr(alert_manager, "_alert_last_sent", {})
    monkeypatch.setattr(alert_manager, "ALERT_COOLDOWN_HOURS", 6)
    monkeypatch.setattr(alert_manager.time, "time", lambda: 0.0)

    alert_manager.send_alert("disk", "warning", alert_type="system_resources")
    # 6h + 60s: strictly past the window, not "about an hour later".
    monkeypatch.setattr(alert_manager.time, "time", lambda: 6 * 3600 + 60)

    assert alert_manager.send_alert("disk", "warning", alert_type="system_resources") is True
    assert len(calls) == 2


def test_send_alert_without_a_type_always_sends(monkeypatch):
    """Back-compat: every existing caller passes no alert_type.

    Keying the cooldown on a default bucket would make those callers suppress
    each other, which is a silent new failure mode rather than a fix.
    """
    calls = _slack_recorder(monkeypatch)
    monkeypatch.setattr(alert_manager, "_alert_last_sent", {})

    alert_manager.send_alert("legacy one", "warning")
    alert_manager.send_alert("legacy two", "warning")

    assert len(calls) == 2, "untyped alerts must not share a cooldown bucket"


# ------------------------------------------------------------- registration
def test_guard_job_is_registered_every_15_minutes():
    """Overnight coverage is the whole point; the registration is the feature.

    A 15-min poll with no cooldown would be ~52 messages, and without the
    registration the guards would run 08:00 only -- the 6h gap this fixes.
    """
    import inspect

    main = _main()

    src = inspect.getsource(main.start_scheduler) if hasattr(main, "start_scheduler") else ""
    if not src:
        import re

        raw = Path(main.__file__).read_text()
        m = re.search(r"add_job\(pipeline_guard_job[^\n]*", raw)
        assert m, "pipeline_guard_job is never registered with the scheduler"
        src = m.group(0)
    else:
        assert "pipeline_guard_job" in src

    assert 'minutes=15' in src
    assert "misfire_grace_time=120" in src
