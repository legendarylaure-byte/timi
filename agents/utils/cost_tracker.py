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
    pricing = GEMINI_PRICING.get(model, GEMINI_PRICING["gemini-2.5-flash"])
    cost = input_tokens * pricing["input"] + output_tokens * pricing["output"]
    with open(COST_LOG, "a", newline="") as f:
        w = csv.writer(f)
        w.writerow([datetime.utcnow().isoformat(), caller, input_tokens, output_tokens, round(cost, 6), model])


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
    with open(COST_LOG) as f:
        for row in csv.DictReader(f):
            ts = row.get("timestamp", "")
            try:
                if datetime.fromisoformat(ts).timestamp() < cutoff:
                    continue
            except Exception:
                continue
            caller = row.get("caller", "unknown")
            cost = float(row.get("cost_usd", 0))
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
    }
