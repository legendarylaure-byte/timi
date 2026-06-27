import re


SENSITIVE_PATTERNS = [
    (re.compile(r'(?i)(access_token|api_key|secret|password|token|bearer)\s*[=:]\s*[\'"]?\w+'), r'\1=REDACTED'),
    (re.compile(r'(?i)(Authorization:\s*Bearer\s+)\w+'), r'\1REDACTED'),
    (re.compile(r'(?i)(bot\d+:)[\w-]+'), r'\1REDACTED'),
]


def redact(value: str) -> str:
    if not isinstance(value, str):
        return str(value)
    result = value
    for pattern, replacement in SENSITIVE_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def safe_log(msg: str) -> str:
    return redact(msg)
