import os
import csv
import json
import logging
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)

COST_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "costs")
COST_LOG = os.path.join(COST_DIR, "cost_log.csv")
os.makedirs(COST_DIR, exist_ok=True)

GEMINI_PRICING = {
    "gemini-2.5-flash": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
    "gemini-2.5-pro": {"input": 1.25 / 1_000_000, "output": 5.00 / 1_000_000},
}


def _ensure_header():
    if not os.path.exists(COST_LOG) or os.path.getsize(COST_LOG) == 0:
        with open(COST_LOG, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["timestamp", "caller", "input_tokens", "output_tokens", "cost_usd", "model"])


def log_llm_cost(caller: str, input_tokens: int, output_tokens: int, model: str = "gemini-2.5-flash"):
    _ensure_header()
    pricing = GEMINI_PRICING.get(model)
    if pricing is None:
        # Do NOT silently bill an unpriced model at another model's rate — a wrong
        # cost that looks authoritative is worse than an obviously missing one.
        cost = "unknown"
        logger.warning(
            "[CostTracker] No pricing for model %r (caller=%s, %d in / %d out) — "
            "logged as 'unknown' instead of guessing. Add it to GEMINI_PRICING.",
            model, caller, input_tokens, output_tokens,
        )
    else:
        cost = round(input_tokens * pricing["input"] + output_tokens * pricing["output"], 6)
    with open(COST_LOG, "a", newline="") as f:
        w = csv.writer(f)
        w.writerow([datetime.utcnow().isoformat(), caller, input_tokens, output_tokens, cost, model])


def log_stock_call(provider: str):
    _ensure_header()
    with open(COST_LOG, "a", newline="") as f:
        w = csv.writer(f)
        w.writerow([datetime.utcnow().isoformat(), f"stock:{provider}", 0, 0, 0, ""])


def get_cost_summary(days: int = 30) -> dict:
    if not os.path.exists(COST_LOG):
        return {"total_cost": 0, "by_caller": {}, "by_day": {}, "llm_calls": 0, "stock_calls": 0}
    cutoff = (datetime.utcnow().timestamp() - days * 86400)
    total = 0.0
    by_caller = defaultdict(float)
    by_day = defaultdict(float)
    llm_calls = 0
    stock_calls = 0
    unpriced_calls = 0
    with open(COST_LOG) as f:
        for row in csv.DictReader(f):
            ts = row.get("timestamp", "")
            try:
                if datetime.fromisoformat(ts).timestamp() < cutoff:
                    continue
            except Exception:
                continue
            caller = row.get("caller", "unknown")
            raw_cost = row.get("cost_usd", 0)
            try:
                cost = float(raw_cost)
            except (TypeError, ValueError):
                # 'unknown' (unpriced model) or any corrupt row: flag it, don't crash
                # the summary, and don't silently drop it either.
                cost = 0.0
                unpriced_calls += 1
                logger.warning(
                    "[CostTracker] Non-numeric cost_usd %r for caller=%s model=%r at %s "
                    "— counted as 0.0 and excluded from the total. This is unpriced or "
                    "corrupt data; fix GEMINI_PRICING or the writer upstream.",
                    raw_cost, caller, row.get("model", ""), ts,
                )
            total += cost
            by_caller[caller] += cost
            day = ts[:10]
            by_day[day] += cost
            if caller.startswith("stock:"):
                stock_calls += 1
            else:
                llm_calls += 1
    return {
        "total_cost": round(total, 4),
        "by_caller": dict(by_caller),
        "by_day": dict(by_day),
        "llm_calls": llm_calls,
        "stock_calls": stock_calls,
        # >0 means the total above is a floor, not the real spend.
        "unpriced_calls": unpriced_calls,
    }
