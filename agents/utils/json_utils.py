import json
import re
import ast


def extract_json(response: str) -> dict | None:
    """Extract JSON from LLM response, handling control characters and single-quoted strings."""
    json_start = response.find("{")
    json_end = response.rfind("}") + 1
    if json_start < 0 or json_end <= json_start:
        return None

    raw = response[json_start:json_end]

    for depth in range(3):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        cleaned = ""
        in_string = False
        escaped = False
        for c in raw:
            if escaped:
                cleaned += c
                escaped = False
                continue
            if c == '\\' and in_string:
                cleaned += c
                escaped = True
                continue
            if c == '"':
                in_string = not in_string
                cleaned += c
                continue
            if in_string and ord(c) < 32 and c not in '\n\r\t':
                cleaned += ' '
                continue
            cleaned += c
        raw = cleaned

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        raw = _fix_single_quotes(raw)

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

    try:
        result = ast.literal_eval(raw)
        if isinstance(result, dict):
            return result
    except (ValueError, SyntaxError, MemoryError):
        pass

    return None


def _fix_single_quotes(text: str) -> str:
    """Replace single quotes used as JSON string delimiters with double quotes."""
    result = []
    i = 0
    in_double = False
    in_single = False
    while i < len(text):
        c = text[i]
        if c == '\\':
            result.append(c)
            if i + 1 < len(text):
                i += 1
                result.append(text[i])
            i += 1
            continue
        if c == '"' and not in_single:
            in_double = not in_double
            result.append(c)
            i += 1
            continue
        if c == "'" and not in_double:
            in_single = not in_single
            result.append('"')
            i += 1
            continue
        result.append(c)
        i += 1
    return ''.join(result)
