"""Self-check for P4 stock-footage variety.

Run: python -m utils.stock_selfcheck

Three separate causes of "every video looks the same":
  1. _keyword_expand threw away the scene's own words on any keyword-map hit.
  2. Sorting was by query relevance only, so candidates from one query tied and the
     stable sort always returned the provider's first result.
  3. The download filename was keyed by scene_idx only, so a clip fetched for one
     video was silently reused by the next video.
"""
import utils.stock_video as sv


def test_scene_words_survive_expansion():
    q = sv._keyword_expand("quantum qubit superposition")
    assert q[0] == "quantum qubit superposition", f"scene words not leading: {q}"
    assert any("quantum" in x for x in q), f"scene words lost entirely: {q}"


def test_expansion_is_not_the_generic_fallback():
    a = sv._keyword_expand("transformer attention mechanism")
    b = sv._keyword_expand("nepal earthquake reconstruction")
    assert a != b, f"two unrelated scenes expanded to the same list: {a}"
    assert "transformer" in " ".join(a) and "earthquake" in " ".join(b), (a, b)


def test_expansion_handles_empty():
    assert sv._keyword_expand("") and sv._keyword_expand(None), "empty keyword crashed or returned nothing"


def test_jitter_varies_by_video_but_is_stable():
    cid = "pexels_123"
    a = sv._stable_jitter("video-aaa", 0, cid)
    b = sv._stable_jitter("video-bbb", 0, cid)
    assert a != b, "two different videos got identical jitter"
    assert a == sv._stable_jitter("video-aaa", 0, cid), "jitter not deterministic for a re-run"
    assert sv._stable_jitter("video-aaa", 0, cid) != sv._stable_jitter("video-aaa", 1, cid), \
        "different scenes got identical jitter"


def test_repeat_penalty_penalises_recent_use():
    sv._mark_used("pexels_selftest_clip")
    assert sv._repeat_penalty("pexels_selftest_clip") > 1.0, "just-used clip not penalised"
    assert sv._repeat_penalty("pexels_never_seen") == 0.0, "unused clip penalised"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"  PASS {name}")
    print("stock selfcheck OK")
