import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, mock_open

sys.path.insert(0, str(Path(__file__).parent.parent))

from crew.analyst import load_recent_performance


def test_load_recent_performance_no_file():
    with patch("os.path.exists", return_value=False):
        result = load_recent_performance(days=7)
        assert result == "No analytics data available."


def test_load_recent_performance_bad_json():
    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data="not json")):
            result = load_recent_performance(days=7)
            assert result == "Failed to load analytics data."


def test_load_recent_performance_empty():
    data = json.dumps({"videos": {}, "daily_stats": {}})
    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=data)):
            result = load_recent_performance(days=7)
            assert "Total videos analyzed: 0" in result
            assert "Shorts: 0" in result
            assert "Longs: 0" in result


def test_load_recent_performance_with_videos():
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    old = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    data = json.dumps({
        "videos": {
            "vid1": {
                "type": "shorts",
                "created_at": today,
                "metrics": {"views": 150}, "score": 85,
            },
            "vid2": {
                "type": "long",
                "created_at": yesterday,
                "metrics": {"views": 300}, "score": 92,
            },
            "vid3": {
                "type": "shorts",
                "created_at": old,
                "metrics": {"views": 50}, "score": 60,
            },
        },
        "daily_stats": {
            today: {"videos_created": 1, "total_views": 150},
            yesterday: {"videos_created": 1, "total_views": 300},
        },
    })

    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=data)):
            result = load_recent_performance(days=7)
            assert "Total videos analyzed: 2" in result
            assert "Shorts: 1" in result
            assert "Longs: 1" in result
            assert "Total views: 450" in result
            assert "Avg quality score: 88.5" in result
            assert "Best score: 92" in result


def test_load_recent_performance_long_key_fix():
    today = datetime.now().strftime("%Y-%m-%d")
    data = json.dumps({
        "videos": {
            "vid1": {"type": "long", "created_at": today, "metrics": {"views": 100}, "score": 80},
        },
        "daily_stats": {},
    })
    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=data)):
            result = load_recent_performance(days=7)
            assert "Longs: 1" in result
