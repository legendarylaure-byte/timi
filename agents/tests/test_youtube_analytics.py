from unittest.mock import patch, MagicMock

from utils.youtube_analytics import _extract_youtube_id


def test_extract_youtube_id_from_youtube_id_field():
    data = {"youtube_id": "dQw4w9WgXcQ"}
    assert _extract_youtube_id(data) == "dQw4w9WgXcQ"


def test_extract_youtube_id_from_yt_video_id_field():
    data = {"yt_video_id": "dQw4w9WgXcQ"}
    assert _extract_youtube_id(data) == "dQw4w9WgXcQ"


def test_extract_youtube_id_youtube_id_preferred():
    data = {"youtube_id": "aaaaaaaaaaa", "yt_video_id": "bbbbbbbbbbb"}
    assert _extract_youtube_id(data) == "aaaaaaaaaaa"


def test_extract_youtube_id_from_publish_urls():
    data = {"publish_urls": {"youtube": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}}
    assert _extract_youtube_id(data) == "dQw4w9WgXcQ"


def test_extract_youtube_id_from_shorts_url():
    data = {"publish_urls": {"youtube": "https://www.youtube.com/shorts/dQw4w9WgXcQ"}}
    assert _extract_youtube_id(data) == "dQw4w9WgXcQ"


def test_extract_youtube_id_from_video_url():
    data = {"video_url": "https://youtu.be/dQw4w9WgXcQ"}
    assert _extract_youtube_id(data) == "dQw4w9WgXcQ"


def test_extract_youtube_id_returns_none_for_missing():
    assert _extract_youtube_id({}) is None


def test_extract_youtube_id_returns_none_for_invalid_length():
    data = {"youtube_id": "toolongyoutubeid"}
    assert _extract_youtube_id(data) is None


def test_extract_youtube_id_skips_non_11_char_values():
    data = {"youtube_id": "short", "yt_video_id": "dQw4w9WgXcQ"}
    assert _extract_youtube_id(data) == "dQw4w9WgXcQ"


def test_extract_youtube_id_from_youtube_url_in_video_url():
    data = {"video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
    assert _extract_youtube_id(data) == "dQw4w9WgXcQ"


def test_extract_youtube_id_prefers_youtube_id_over_url():
    data = {
        "youtube_id": "aaaaaaaaaaa",
        "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    }
    assert _extract_youtube_id(data) == "aaaaaaaaaaa"


@patch("utils.youtube_analytics.get_youtube_credentials")
@patch("utils.youtube_analytics.fetch_video_stats")
@patch("utils.youtube_analytics.get_firestore_client")
def test_pull_all_video_analytics_skips_non_uploaded(
    mock_get_firestore, mock_fetch_stats, mock_get_creds
):
    mock_get_creds.return_value = MagicMock()
    docs = [
        MagicMock(to_dict=lambda: {"status": "generating", "video_id": "v1"}),
        MagicMock(to_dict=lambda: {"status": "failed", "video_id": "v2"}),
    ]
    mock_get_firestore.return_value.collection.return_value.order_by.return_value.limit.return_value.stream.return_value = docs
    from utils.youtube_analytics import pull_all_video_analytics
    result = pull_all_video_analytics()
    assert result == {"processed": 0, "failed": 0}
    mock_fetch_stats.assert_not_called()


@patch("utils.youtube_analytics.get_youtube_credentials")
@patch("utils.youtube_analytics.fetch_video_stats")
@patch("utils.youtube_analytics.get_firestore_client")
@patch("utils.youtube_analytics.update_video_analytics")
@patch("utils.youtube_analytics.log_activity")
def test_pull_all_video_analytics_processes_uploaded(
    mock_log, mock_update, mock_get_firestore, mock_fetch_stats, mock_get_creds
):
    mock_get_creds.return_value = MagicMock()
    doc = MagicMock()
    doc.to_dict.return_value = {
        "status": "published",
        "video_id": "v1",
        "youtube_id": "dQw4w9WgXcQ",
    }
    mock_get_firestore.return_value.collection.return_value.order_by.return_value.limit.return_value.stream.return_value = [doc]
    mock_fetch_stats.return_value = {"views": 100, "likes": 5, "comments": 2, "favorites": 0}
    from utils.youtube_analytics import pull_all_video_analytics
    result = pull_all_video_analytics()
    assert result == {"processed": 1, "failed": 0}
    mock_fetch_stats.assert_called_once_with("dQw4w9WgXcQ")
    mock_update.assert_called_once_with("v1", {"views": 100, "likes": 5, "comments": 2, "favorites": 0})


@patch("utils.youtube_analytics.get_youtube_credentials")
@patch("utils.youtube_analytics.fetch_video_stats")
@patch("utils.youtube_analytics.get_firestore_client")
@patch("utils.youtube_analytics.log_activity")
def test_pull_all_video_analytics_no_credentials(
    mock_log, mock_get_firestore, mock_fetch_stats, mock_get_creds
):
    mock_get_creds.return_value = None
    from utils.youtube_analytics import pull_all_video_analytics
    result = pull_all_video_analytics()
    assert result == {"processed": 0, "failed": 0}
    mock_get_firestore.assert_not_called()


@patch("utils.youtube_upload.get_youtube_credentials")
@patch("utils.youtube_upload.build")
def test_fetch_video_stats_success(mock_build, mock_get_creds):
    mock_get_creds.return_value = MagicMock()
    mock_execute = MagicMock(return_value={
        "items": [{
            "statistics": {
                "viewCount": "500",
                "likeCount": "25",
                "commentCount": "10",
                "favoriteCount": "0",
            },
            "contentDetails": {
                "duration": "PT5M30S",
            }
        }]
    })
    mock_build.return_value.videos.return_value.list.return_value.execute = mock_execute
    from utils.youtube_upload import fetch_video_stats
    result = fetch_video_stats("dQw4w9WgXcQ")
    assert result == {"views": 500, "likes": 25, "comments": 10, "favorites": 0, "duration_seconds": 330}
    mock_build.return_value.videos.return_value.list.assert_called_once_with(
        part="statistics,contentDetails", id="dQw4w9WgXcQ"
    )


@patch("utils.youtube_upload.get_youtube_credentials")
@patch("utils.youtube_upload.build")
def test_fetch_video_stats_not_found(mock_build, mock_get_creds):
    mock_get_creds.return_value = MagicMock()
    mock_execute = MagicMock(return_value={"items": []})
    mock_build.return_value.videos.return_value.list.return_value.execute = mock_execute
    from utils.youtube_upload import fetch_video_stats
    result = fetch_video_stats("nonexistent")
    assert "error" in result
    assert "not found" in result["error"]
