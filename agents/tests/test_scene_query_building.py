"""WS2 guards: the stock query must be the scene's own concrete words.

Root cause fixed 2026-10: `_infer_keywords` prepended the *video title* into
every scene's `asset_keywords[0]`, and folded an abstract `visual_map`
("glowing neural pathways") into the rest. So every scene in a video searched
the same phrase and Pexels returned near-identical abstract footage. Measured
in python.log: ~26 scenes, all `query="new features in python 3.11"`.
"""


def test_scene_words_lead_not_the_title():
    from utils.scene_parser import _infer_keywords

    kws = _infer_keywords(
        "A Python list stores many values and you can index any element by its position.",
        title="New Features in Python 3.11",
    )
    assert kws, kws
    joined = " ".join(kws).lower()
    # The title phrase must not be the query; the scene's own words lead.
    assert "new features" not in joined, kws
    assert kws[0].lower() != "new features in python 3.11", kws


def test_keywords_never_contain_abstract_vocabulary():
    from utils.scene_parser import _infer_keywords

    kws = _infer_keywords(
        "The attention mechanism in a transformer computes weighted relationships "
        "between the tokens in the input sequence."
    )
    joined = " ".join(kws).lower()
    for term in ("abstract", "neon", "holographic", "glowing", "3d", "cgi", "neural"):
        assert term not in joined, (term, kws)


def test_title_is_a_last_resort_fallback_only():
    from utils.scene_parser import _infer_keywords

    # A scene with no usable words falls back to the title rather than nothing.
    kws = _infer_keywords("Go, be, to a.", title="Quantum Error Correction Explained")
    assert kws, kws
    assert "quantum" in " ".join(kws).lower(), kws


def test_keyword_expand_sinks_abstract_queries_to_the_end():
    from utils.stock_video import _keyword_expand

    qs = _keyword_expand("embedding")
    # "3d visualization" is an abstract alias in PEXELS_KEYWORD_MAP; "vector space"
    # is concrete. Concrete must be tried first, abstract last.
    assert "3d visualization" in qs, qs
    assert qs.index("3d visualization") > qs.index("vector space"), qs
    assert qs[-1] == "3d visualization", qs
