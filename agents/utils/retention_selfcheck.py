"""Self-check for the retention unit fix (P1).

Run: python -m utils.retention_selfcheck

Fails if the analyzer indexes a curve as seconds when it was handed one value per
ratio-bucket — the bug that made hook_retention read t=6% of the video and labelled
drop-offs with bucket indexes instead of timestamps.
"""
from utils.retention_analyzer import analyze_retention


def _bucketed_curve(n_buckets: int, duration: int) -> list[float]:
    """What YouTube actually returns: 1.0 decaying to 0.4, one value per bucket."""
    return [1.0 - 0.6 * (i / max(1, n_buckets - 1)) for i in range(n_buckets)]


def test_hook_retention_is_read_at_five_seconds():
    # 100 buckets for a 300s video == one bucket per 3s. At t=5s the true value is
    # ~0.99. Reading index 5 (the 6th bucket) gives 0.970, so the bound has to be
    # tight enough to tell the two apart.
    curve = _bucketed_curve(100, 300)
    res = analyze_retention("t_hook", "unit", curve, 300, persist=False)
    assert res["hook_retention"] >= 0.98, res["hook_retention"]


def test_drop_offs_are_real_seconds():
    # A cliff at bucket 50/100 of a 300s video is t=150s, and the reported
    # timestamp must be 150, not 50.
    curve = _bucketed_curve(100, 300)
    curve[50] -= 0.30
    res = analyze_retention("t_drop", "unit", curve, 300, persist=False)
    stamps = [ts for ts, _ in res["drop_off_points"]]
    assert stamps, "no drop-off detected"
    worst = max(res["drop_off_points"], key=lambda x: x[1])[0]
    assert abs(worst - 150) <= 5, f"drop-off reported at t={worst}s, expected ~150s"


def test_per_second_curve_is_not_mangled():
    # Already-correct input (one value per second) must pass through unchanged.
    curve = _bucketed_curve(300, 300)
    res = analyze_retention("t_perfect", "unit", curve, 300, persist=False)
    assert 0.95 <= res["hook_retention"] <= 1.0, res["hook_retention"]


def test_empty_input_is_safe():
    assert analyze_retention("t_empty", "unit", [], 100, persist=False)["hook_retention"] == 0


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"  PASS {name}")
    print("retention selfcheck OK")
