import json


def extract_json(response: str) -> dict | None:
    """Extract JSON from LLM response, handling control characters."""
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

    return None
