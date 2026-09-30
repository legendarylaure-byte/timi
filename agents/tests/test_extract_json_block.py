"""_extract_json must BLOCK on unparseable crew output, never raise.

The no-brace branch used to fabricate `{...}` and call json.loads() with no
guard. Crew output that is prose containing a quote raised JSONDecodeError,
the caller caught it, logged "CRASHED" and continued — so the virality gate
was SKIPPED instead of blocking. Mutation-confirmed: restoring the bare
`return json.loads(text)` fails both tests below.
"""


def test_prose_with_quote_blocks_instead_of_raising():
    import main

    raw = (
        'Here is my virality analysis of the script.\n'
        'The hook is described as "strong" and I recommend "approve" it.\n'
        'Overall this is a strong video.'
    )
    assert '{' not in raw  # this is the path that used to raise

    result = main._extract_json(raw)

    assert result["decision"] == "block"
    assert result["score"] == 0


def test_prose_without_any_quote_blocks():
    import main

    result = main._extract_json("plain prose with no quotes at all")

    assert result["decision"] == "block"
    assert result["score"] == 0


def test_parse_failure_default_is_not_shared_between_calls():
    import main

    first = main._extract_json("prose with a \"quote\" in it")
    first["breakdown"]["engagement"] = 99
    first["issues"][0]["detail"] = "mutated"

    second = main._extract_json("more prose with a \"quote\"")

    assert second["breakdown"]["engagement"] == 0
    assert second["issues"][0]["detail"] == "Crew output parse failed"


def test_valid_json_still_parses():
    import main

    assert main._extract_json('{"decision": "approve", "score": 91}') == {
        "decision": "approve",
        "score": 91,
    }
