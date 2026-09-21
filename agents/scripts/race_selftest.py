"""Deterministic concurrent race selftest for the shared temp-file fix.

Spawns 2 threads mimicking short+long pipelines writing phrase_timing /
subtitles / background music, asserts each gets its own vid-scoped path and
both files are complete/valid afterward (no cross-clobber).
"""
import io
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, ".")

from utils.voice_gen import generate_voiceover
from utils.subtitle_gen import generate_subtitles_for_video
from utils.music_gen import generate_background_music
from utils.voice_gen import VOICE_DIR
from utils.subtitle_gen import SUBTITLE_DIR
from utils.music_gen import MUSIC_DIR


def run_pipeline(video_id: str, n_segments: int):
    script = "\n".join(f"Segment {i} of {video_id} with some narration text to speak." for i in range(1, n_segments + 1))
    import asyncio
    loop = asyncio.new_event_loop()
    vr = loop.run_until_complete(generate_voiceover(script, output_filename=f"voiceover_{video_id}.wav", video_id=video_id))
    timing = vr.get("timing_file")
    assert timing and video_id in str(timing), f"timing not vid-scoped: {timing}"
    sr = generate_subtitles_for_video(timing_file=timing, full_text=script, video_id=video_id)
    srt = sr.get("srt")
    assert srt and video_id in srt, f"srt not vid-scoped: {srt}"
    m = generate_background_music("Science & Technology", duration=3, video_id=video_id)
    mp = m.get("path")
    assert mp and video_id in mp, f"music not vid-scoped: {mp}"
    return timing, srt, mp


def main():
    threads = 2
    results = [None] * threads
    with ThreadPoolExecutor(max_workers=threads) as ex:
        futs = [ex.submit(run_pipeline, f"test-short-{i}", 3 if i == 0 else 8) for i in range(threads)]
        for i, f in enumerate(futs):
            results[i] = f.result()

    (t0, s0, m0), (t1, s1, m1) = results
    # paths must all be distinct
    distinct = {t0, s0, m0, t1, s1, m1}
    assert len(distinct) == 6, f"path clobber: {distinct}"
    # generated files must be complete/valid
    for ti in (t0, t1):
        data = json.load(open(ti))
        assert isinstance(data, list) and len(data) > 0, f"empty timing: {ti}"
    for si in (s0, s1):
        content = open(si, encoding="utf-8").read()
        assert content.count("-->") > 0, f"empty/truncated srt: {si}"
    for mi in (m0, m1):
        sz = open(mi, "rb").read(4)
        assert sz[:4] == b"RIFF", f"corrupt wav (not RIFF header): {mi} ({open(mi,'rb').read()})"
    print("RACE SELFTEST PASSED")
    print("  short:", t0, s0, m0)
    print("  long :", t1, s1, m1)
    return 0


if __name__ == "__main__":
    sys.exit(main())