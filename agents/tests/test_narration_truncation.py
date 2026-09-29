"""Guard: a truncated TTS segment must be detected, retried, and RECORDED.

Measured on 2026-09-29 during a verify.sh run: Edge TTS returned 1.26s of audio
for a ~10s Hindi sentence, then 5 consecutive re-runs came back clean at 9.97s.
1.26s is ~10KB, so the only size guard on the whole narration path
(`getsize > 100` in voice_provider.EdgeTTSProvider.generate) waves it through.

The dub path caught it -- its 25% drift ladder measured 691% and refused to
publish. The MAIN pipeline had no such ladder, so a truncated segment was
composited and uploaded as a normal video. That is the gap this pins.

The thresholds are pinned to the real observed pair (1.26s vs 9.97s) rather than
to tidy round numbers, because a tidy number is not the thing that was measured.
"""
import pytest

from utils.voice_gen import (
    MIN_WORDS_PER_SECOND_FLOOR,
    NARRATION_TRUNCATION_RATIO,
    narration_floor_ms,
    narration_is_truncated,
)

# The actual Hindi sentence that produced the 1.26s glitch, trimmed to a
# representative length. ~10s of speech at Edge's normal rate.
HINDI_WORDS = "भारत में आज एक बड़ा ऐतिहासिक बदलाव आया है जिसने लोगों को हैरान कर दिया और आगे की दिशा तय कर दी।"
OBSERVED_CLEAN_MS = 9970.0   # 5/5 re-runs
OBSERVED_TRUNCATED_MS = 1260.0  # 1-in-7


def _boundaries(end_ms):
    """Edge boundary metadata claiming the speech ended at `end_ms`."""
    return [{"type": "WordBoundary", "offset_ms": 0, "duration_ms": 10},
            {"type": "SentenceBoundary", "offset_ms": 0, "duration_ms": end_ms}]


def test_the_measured_clean_run_is_not_flagged():
    floor = narration_floor_ms(HINDI_WORDS, _boundaries(OBSERVED_CLEAN_MS))
    assert not narration_is_truncated(OBSERVED_CLEAN_MS, floor), (
        f"a full {OBSERVED_CLEAN_MS}ms read must never be flagged (floor={floor}ms)"
    )


def test_the_measured_truncated_run_is_flagged():
    floor = narration_floor_ms(HINDI_WORDS, _boundaries(OBSERVED_TRUNCATED_MS))
    assert narration_is_truncated(OBSERVED_TRUNCATED_MS, floor), (
        f"the real 1.26s glitch must be caught (floor={floor}ms)"
    )


def test_truncation_is_caught_even_when_the_provider_lies_about_it():
    """The whole reason there are two signals.

    If Edge truncated the response, the boundaries it reports for that same
    response may be truncated too -- the audio then looks perfectly
    self-consistent at 1.26s and a boundary-only check sees nothing wrong. The
    word-count floor is independent of the provider, so the pair covers each
    other. This is the case that a single-signal implementation misses.
    """
    floor = narration_floor_ms(HINDI_WORDS, _boundaries(OBSERVED_TRUNCATED_MS))
    word_only = floor
    assert word_only > OBSERVED_TRUNCATED_MS * NARRATION_TRUNCATION_RATIO, (
        "word-count floor alone must already condemn the 1.26s response"
    )
    assert narration_is_truncated(OBSERVED_TRUNCATED_MS, floor)


def test_a_deliberately_slow_read_is_not_flagged():
    """A 2x-slower-than-typical delivery is normal pacing, not truncation."""
    slow = OBSERVED_CLEAN_MS * 2
    assert not narration_is_truncated(slow, narration_floor_ms(HINDI_WORDS, _boundaries(OBSERVED_CLEAN_MS)))


def test_no_timing_metadata_falls_back_to_word_count():
    floor = narration_floor_ms(HINDI_WORDS, None)
    assert floor == pytest.approx(len(HINDI_WORDS.split()) / MIN_WORDS_PER_SECOND_FLOOR * 1000)
    assert not narration_is_truncated(OBSERVED_CLEAN_MS, floor), (
        "the word-count floor must be loose enough to pass a full read"
    )


def test_no_signal_means_no_verdict_rather_than_a_false_accusation():
    """Empty text and empty timing must NOT be reported as truncated.

    Defaulting to 'truncated' when there is nothing to measure would flag every
    segment with no boundaries, and a guard that cries wolf is a guard that gets
    switched off.
    """
    assert narration_floor_ms("", None) == 0.0
    assert not narration_is_truncated(0.0, 0.0)
    assert not narration_is_truncated(1000.0, 0.0)


def test_the_floor_takes_the_more_demanding_of_the_two_signals():
    """A dishonest provider must not be able to LOWER the bar.

    The word-count signal is the floor of last resort: a provider that reports a
    200ms boundary can never pull the expectation below what the text itself
    implies, it can only ever make the check *stricter*.
    """
    word_floor = narration_floor_ms(HINDI_WORDS, None)
    honest = narration_floor_ms(HINDI_WORDS, _boundaries(OBSERVED_CLEAN_MS))
    lying = narration_floor_ms(HINDI_WORDS, _boundaries(200.0))

    assert lying == pytest.approx(word_floor), (
        "a boundary signal below the word floor must not lower the floor"
    )
    assert honest > lying, "an honest, longer boundary signal must dominate"
    assert narration_floor_ms(HINDI_WORDS, _boundaries(OBSERVED_CLEAN_MS)) == max(honest, word_floor)


def test_generated_voiceover_result_carries_a_count_not_just_a_bool():
    """A bool would collapse '1 bad segment' and '3 bad segments' into one value.

    The count is the thing worth watching across runs; the bool is only a
    convenience for dashboards.
    """
    from utils.voice_gen import generate_voiceover
    import inspect
    src = inspect.getsource(generate_voiceover)
    assert '"truncated_segments": truncated_segments' in src
    assert '"narration_truncated": truncated_segments > 0' in src
    assert '"truncated_detail": truncated_detail' in src
