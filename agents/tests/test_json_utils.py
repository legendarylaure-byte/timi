from utils.json_utils import extract_json


def test_extract_json_valid():
    result = extract_json('{"a": 1, "b": 2}')
    assert result == {"a": 1, "b": 2}


def test_extract_json_with_surrounding_text():
    result = extract_json('Here is the result: {"key": "value"} and more text')
    assert result == {"key": "value"}


def test_extract_json_control_chars():
    raw = '{"text": "hello\u0000world\u0001test"}'
    result = extract_json(raw)
    assert result == {"text": "hello world test"}


def test_extract_json_no_json_returns_none():
    result = extract_json("This is just plain text without JSON")
    assert result is None


def test_extract_json_nested():
    raw = '{"outer": {"inner": [1, 2, 3]}, "list": ["a", "b"]}'
    result = extract_json(raw)
    assert result == {"outer": {"inner": [1, 2, 3]}, "list": ["a", "b"]}


def test_extract_json_empty_dict():
    result = extract_json("{}")
    assert result == {}


def test_extract_json_markdown_fenced():
    result = extract_json('```json\n{"a": 1}\n```')
    assert result == {"a": 1}


def test_extract_json_escaped_chars():
    raw = '{"path": "C:\\\\Users\\\\test\\\\file.txt"}'
    result = extract_json(raw)
    assert result == {"path": "C:\\Users\\test\\file.txt"}
