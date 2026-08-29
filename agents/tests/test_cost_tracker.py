"""ponytail: smoke tests for cost_tracker."""
import os
import sys
import json
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils import cost_tracker

# ponytail: temp dir isolation
_tmp = tempfile.mkdtemp()
_cost_log = os.path.join(_tmp, 'cost_log.csv')


def _reset():
    cost_tracker.COST_LOG = _cost_log
    if os.path.exists(_cost_log):
        os.remove(_cost_log)


def test_log_llm_cost_creates_csv():
    _reset()
    cost_tracker.log_llm_cost('gemini_flash', 100, 50)
    assert os.path.exists(_cost_log)
    with open(_cost_log) as f:
        lines = f.read().strip().split('\n')
    assert len(lines) == 2  # header + row
    assert 'gemini_flash' in lines[1]


def test_log_stock_call():
    _reset()
    cost_tracker.log_stock_call('pexels')
    cost_tracker.log_stock_call('pixabay')
    with open(_cost_log) as f:
        lines = f.read().strip().split('\n')
    assert len(lines) == 3  # header + 2 rows


def test_get_cost_summary():
    _reset()
    cost_tracker.log_llm_cost('gemini_flash', 1000, 200)
    summary = cost_tracker.get_cost_summary()
    assert summary['llm_calls'] == 1
    assert summary['total_cost'] > 0
    assert 'gemini_flash' in summary['by_caller']


def test_multiple_calls_sum():
    _reset()
    cost_tracker.log_llm_cost('gemini_flash', 1_000_000, 200)
    cost_tracker.log_llm_cost('gemini_flash', 500_000, 100)
    summary = cost_tracker.get_cost_summary()
    assert summary['llm_calls'] == 2
    assert summary['total_cost'] > 0.001


def test_stock_calls_separate():
    _reset()
    cost_tracker.log_llm_cost('gemini_flash', 1000, 200)
    cost_tracker.log_stock_call('pexels')
    summary = cost_tracker.get_cost_summary()
    assert summary['llm_calls'] == 1
    assert summary['stock_calls'] == 1
    assert 'gemini_flash' in summary['by_caller']
    assert summary['by_caller'].get('pexels') is None or 'pexels' not in summary['by_caller']


def test_empty_log():
    _reset()
    summary = cost_tracker.get_cost_summary()
    assert summary['llm_calls'] == 0
    assert summary['total_cost'] == 0
    assert summary['stock_calls'] == 0


def test_no_csv_file():
    _reset()
    if os.path.exists(_cost_log):
        os.remove(_cost_log)
    summary = cost_tracker.get_cost_summary()
    assert summary['llm_calls'] == 0
