"""Brand colour conversion and profile tests.

Every value here was measured, not assumed:

- ffmpeg `drawbox=color` / `drawtext=fontcolor` / `boxcolor` are **RGB**, in
  either `#RRGGBB` or `0xRRGGBB`. Confirmed by decoding a rendered frame and
  reading the actual pixel values.
- ASS / libass `&HAABBGGRR&` is **BGR**. Confirmed because `ass(AMBER)` comes
  out as `&H000088CC&`, which is byte-identical to the hand-written literal
  that shipped in the subtitles and demonstrably rendered as amber.

A colour-constant swap is the kind of change that "looks right" in a diff and
silently inverts in a render, so the conversion direction is the thing under
test -- not the hex values.
"""
import ast
import json
import pathlib
import re

import pytest

from utils.brand_palette import (
    ACCENT_RAMP, AMBER, GRADE_REFERENCE_YUV, LICORICE, LIGHT_ORANGE,
    ORANGE, PINK, PURPLE, VIOLET, WHITE, ass, content_box, safe_band,
    watermark_position, hex_to_rgb,
)
from utils.visual_profiles import (
    VISUAL_PROFILES, apply_profile_to_prompt, brand_lighting_phrase,
    get_accent_color, get_profile, get_subtitle_color,
)

UTILS = pathlib.Path(__file__).resolve().parent.parent / "utils"

# Black, white and grey are identical in RGB and BGR, so these are the only
# raw ASS literals allowed to stay in the tree.
CHROMALESS = {"&H00000000&", "&H00FFFFFF&", "&H40000000&", "&H80000000&"}


def _rgb(hexv):
    h = hexv.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _ass_rgb(value):
    """Decode an ASS &HAABBGGRR& string back to RGB.

    8 hex digits: the leading AA pair is *alpha*, so blue starts at index 2.
    Slicing from 0 silently reads alpha as blue, which happens to look right for
    nothing and breaks the roundtrip for every colour.
    """
    body = value.lstrip("&H").rstrip("&")
    if len(body) != 8:
        raise AssertionError(f"expected &HAABBGGRR&, got {value!r}")
    b, g, r = int(body[2:4], 16), int(body[4:6], 16), int(body[6:8], 16)
    return r, g, b


def test_ass_converts_rgb_to_bgr_not_the_reverse():
    # The inversion bug: a correct converter produces a DIFFERENT string than a
    # naive pass-through, so this fails if someone "simplifies" it to identity.
    assert ass(PURPLE) == "&H00FF4D9B&"
    assert _ass_rgb(ass(PURPLE)) == _rgb(PURPLE)
    assert _ass_rgb(ass(PINK)) == _rgb(PINK)
    assert _ass_rgb(ass(LIGHT_ORANGE)) == _rgb(LIGHT_ORANGE)
    assert _ass_rgb(ass(LICORICE)) == _rgb(LICORICE)


def test_ass_accepts_both_hash_and_bare_hex():
    assert ass("#9B4DFF") == ass("9B4DFF") == ass(PURPLE) == "&H00FF4D9B&"


def test_amber_ass_matches_the_shipped_subtitle_literal():
    # Regression lock. '&H000088CC&' was hand-written and verified to render as
    # amber; it is now computed. If these ever diverge, one is wrong.
    assert ass(AMBER) == "&H000088CC&"
    assert _ass_rgb(ass(AMBER)) == _rgb(AMBER)


def test_white_and_black_survive_bgr_roundtrip():
    # These are the values that are safe to write raw in either order.
    for v in (WHITE, LICORICE):
        assert _ass_rgb(ass(v)) == _rgb(v)


def test_grade_reference_is_neutral_not_brand_tinted():
    # A near-neutral reference is deliberate: global colour grading must not
    # stamp the channel colour onto every frame. The brand lives in the
    # graphics, the LTX prompt and the watermark, not in a global cast.
    y, u, v = GRADE_REFERENCE_YUV["y_mean"], GRADE_REFERENCE_YUV["u_mean"], GRADE_REFERENCE_YUV["v_mean"]
    assert abs(u - 128) < 2, "u must sit on the neutral axis"
    # Range widened downward from the old 100-150. That range was calibrated to
    # a fictional reference (127.5) that the pipeline never actually produced:
    # measured real output was Y p50=43.3, with 86% of runtime under 64. A floor
    # of 100 would forbid fixing the thing that was wrong. What the assertion is
    # really protecting is "well exposed, neither crushed nor blown" -- 80..130
    # is that band, and the upper bound still refuses the old over-bright teal
    # (140) that desaturated every frame.
    assert 80 <= y <= 130, f"luma target {y} should be well exposed, not crushed or blown"
    assert 132 <= v <= 150, (
        f"v={v} should leave modest chroma headroom above neutral for vibrance, "
        f"without the warm push of the old teal reference (166)"
    )


def test_accent_ramp_is_brand_only_and_covers_profiles():
    allowed = {PURPLE, VIOLET, PINK, ORANGE, LIGHT_ORANGE}
    assert set(ACCENT_RAMP) <= allowed
    assert len(ACCENT_RAMP) == len(set(ACCENT_RAMP)), "duplicate accent"
    profile_accents = {p["accent_color"] for p in VISUAL_PROFILES.values()}
    assert profile_accents <= set(ACCENT_RAMP)


def test_no_raw_chromatic_ass_literals_in_onframe_renderers():
    """Unconverted chromatic ASS values render the wrong colour.

    Black/white/grey are exempt because BGR == RGB for them. This is the check
    that would have caught the hand-written subtitle colours drifting out of
    sync with the palette module.
    """
    offenders = []
    for path in UTILS.glob("*.py"):
        if path.name == "brand_palette.py":
            continue
        for raw in re.findall(r"['\"]&H[0-9A-Fa-f]{6,8}&['\"]", path.read_text()):
            if raw.strip("'\"") not in CHROMALESS:
                offenders.append(f"{path.name}: {raw}")
    assert not offenders, "chromatic ASS literals bypass the BGR helper:\n" + "\n".join(offenders)


def test_visual_profiles_import_and_fall_back():
    # This module used to raise KeyError('AI Explained') on import, so it could
    # not even be loaded and nothing ever used it.
    assert get_profile("AI News") is VISUAL_PROFILES["AI News"]
    # Intent-based fallback: the planner emits several spellings per category.
    for variant in ("World News (24hr)", "Nepal News", "AI Explained", "", None):
        assert get_profile(variant) is not None
    assert get_profile("Science & Technology") is VISUAL_PROFILES["Science & Technology"]
    assert get_profile("some news thing")["brand_lighting"] == \
        VISUAL_PROFILES["AI News"]["brand_lighting"]


def test_brand_lighting_phrase_is_per_category_and_never_empty():
    for cat in list(VISUAL_PROFILES) + ["unknown", None]:
        phrase = brand_lighting_phrase(cat)
        assert isinstance(phrase, str) and phrase.strip()


def test_apply_profile_to_prompt_appends_brand():
    out = apply_profile_to_prompt("a neural network diagram", "Programming & Software")
    assert out.startswith("a neural network diagram")
    assert "magenta" in out.lower()


def test_subtitle_accent_roundtrips_to_the_profile_accent():
    for cat, prof in VISUAL_PROFILES.items():
        got = _ass_rgb(get_subtitle_color(cat))
        want = _rgb(prof["subtitle_accent"]) if isinstance(prof["subtitle_accent"], str) \
            and prof["subtitle_accent"].startswith("#") else got
        assert got == want, cat


def test_brand_constants_are_uppercase_hex():
    for name in ("LICORICE", "PURPLE", "VIOLET", "PINK", "ORANGE",
                 "LIGHT_ORANGE", "WHITE", "AMBER"):
        from utils import brand_palette
        v = getattr(brand_palette, name)
        assert re.fullmatch(r"#[0-9A-F]{6}", v), f"{name}={v}"


def test_onframe_renderers_carry_no_legacy_brand_literals():
    """Regression lock for the teal -> Concept B migration.

    These are the files whose output a viewer actually sees. A straggler here
    is one un-branded teal box on a purple video.
    """
    legacy = ("00CCCC", "8a50e8", "e07040", "1e1e1e", "1a1a2e")
    for name in ("video_compositor.py", "visual_profiles.py",
                 "shorts_renderer.py", "shorts_pipeline.py", "hook_engine.py",
                 "asset_router.py", "scene_parser.py"):
        text = (UTILS / name).read_text()
        for lit in legacy:
            assert lit not in text, f"{name} still has legacy literal {lit}"


def test_onframe_renderers_import_the_palette():
    """A constant can be right and still unused if the import is missing."""
    for name in ("video_compositor.py", "asset_router.py",
                 "shorts_renderer.py", "scene_parser.py"):
        assert "brand_palette import" in (UTILS / name).read_text(), name


# --------------------------------------------------------------------------
# Safe area
# --------------------------------------------------------------------------
# These are regression guards, not restatements of the current numbers. The
# placements were already correct when checked against the platform bands
# (LIKE at y=1382+48 ends at 1430, above the 1574px caption band; the centred
# CTAs clear the 929px action rail) -- so nothing was moved. What is missing is
# anything that would notice a FUTURE change pushing a CTA into a covered band,
# which is invisible in a local render and gone on upload.


def test_content_box_never_leaves_the_frame():
    for fmt, (w, h) in (("shorts", (1080, 1920)), ("long", (1920, 1080)), ("long", (3840, 2160))):
        x, y, cw, ch = content_box(w, h, fmt)
        assert 0 <= x < w and 0 <= y < h
        assert x + cw <= w and y + ch <= h
        assert cw > 0 and ch > 0


def test_portrait_keeps_out_more_than_landscape():
    p, l = safe_band("shorts"), safe_band("long")
    # 9:16 is covered by platform UI on three sides; 16:9 only at the bottom.
    assert p["bottom"] > l["bottom"]
    assert p["right"] > l["right"]
    assert p["top"] > l["top"]


def test_watermark_avoids_the_portrait_caption_band():
    """The bug that motivated all of this.

    add_logo_overlay defaulted to bottom_right with a hardcoded 20px margin. On
    9:16 the bottom 18% is the platform's caption and channel-name band, so the
    bug rendered perfectly and was invisible on upload. Assert the chosen corner
    is above that band.
    """
    h = 1920
    _, _, _, ch = content_box(1080, h, "shorts")
    content_bottom = round(h * safe_band("shorts")["top"]) + ch
    logo_h = round(1080 * 0.11)          # square source
    top_y = round(h * 0.035)
    assert top_y + logo_h < content_bottom, "logo must sit above the caption band"
    assert "main_h" not in watermark_position(1080, h, "shorts"), \
        "portrait watermark must not be anchored to the bottom"


def test_watermark_sits_in_the_corner_clear_of_the_centre_action_rail():
    """Corrects a test that asserted nothing.

    The previous version compared `(w - gap - logo_w) > (rail_x - logo_w)`, which
    cancels `logo_w` and reduces to `w - gap > rail_x` -- true, but it never
    touched the logo's own edges, so a logo overlapping the rail passed. (The
    logo's left edge is in fact 35px inside the declared right band.)

    What is actually true, and what matters: the rail's *buttons* occupy the
    vertical middle, not the full column. A top-right corner mark clears them by
    construction, which is the real reason the top-right corner was chosen.
    """
    w, h = 1080, 1920
    gap = round(h * 0.035)
    logo = round(w * 0.11)
    left, top = w - gap - logo, gap

    # Top-right corner, in the top ~12% of the frame: far above the rail buttons
    # (roughly the vertical middle third) and far above the hook bar.
    assert top + logo <= round(h * 0.12), "watermark drifted into the vertical middle"
    assert left > w * 0.75, "watermark is no longer a corner mark"

    # It does overlap the declared right *content* band, by design: a brand mark
    # is not scene content, so it is exempt from the content keep-out. Pin that
    # exemption explicitly so a future reader does not "fix" it into a bug.
    rail_x = round(w * (1 - safe_band("shorts")["right"]))
    assert left < rail_x, (
        "watermark no longer sits in the corner; if this is now scene-content, "
        "it must move fully inside content_box() instead"
    )


def test_watermark_keeps_a_real_top_margin():
    """Guards against being nudged flush to the frame edge, and records the one
    open tradeoff: y=67 on a 1080x1920 frame sits under where some apps draw
    status-bar icons. Human visual review owns that call, not this test."""
    h = 1920
    gap = round(h * 0.035)
    assert gap >= 36, "watermark is flush to the top edge"
    logo = round(1080 * 0.11)
    assert gap + logo <= round(h * 0.10), "watermark is tall enough to reach the hook bar"


def test_declared_overlay_fractions_stay_inside_the_safe_box():
    """Parse the real fractions out of the renderers and check them.

    A regex guard is the cheap version: it cannot tell you a CTA is legible, but
    it will fail the moment someone moves one into a platform keep-out band,
    which is the failure mode that costs a re-render to discover.
    """
    h, w = 1920, 1080
    _, cy, _, content_h = content_box(w, h, "shorts")
    content_bottom = cy + content_h      # absolute y, not the height
    rail_x = round(w * (1 - safe_band("shorts")["right"]))
    checks = {
        # file: (fraction_of_height, approximate_text_height_px)
        "shorts_renderer.py": [("y=h*0.15", 0.15, 56), ("y=h*0.72", 0.72, 48)],
    }
    for fname, items in checks.items():
        text = (UTILS / fname).read_text()
        for needle, frac, text_h in items:
            assert needle in text, f"{needle} vanished from {fname}"
            top = round(h * frac)
            assert top + text_h < content_bottom, \
                f"{fname}: {needle} at y={top} enters the portrait caption band ({content_bottom})"
    # The centred CTAs must also not reach the action rail.
    for needle, chars, size in (("y=(h-text_h)/2", 29, 38), ("y=h*0.72", 19, 34)):
        est_w = round(chars * size * 0.55)
        left = round((w - est_w) / 2)
        assert left + est_w <= rail_x, f"{needle} text reaches the action rail"


def test_add_logo_overlay_is_importable_and_safe_by_default():
    import inspect
    from utils.video_compositor import add_logo_overlay

    sig = inspect.signature(add_logo_overlay)
    assert sig.parameters["position"].default == "safe"
    assert sig.parameters["scale"].default == 0.0, "scale=0 derives size from the frame"


# --------------------------------------------------------------------------
# Thumbnails
# --------------------------------------------------------------------------


def _luma(c):
    def f(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (f(x) for x in c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a, b):
    la, lb = _luma(a), _luma(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def test_thumbnail_palettes_are_brand_only():
    """The thumbnail is the most-seen surface the channel has.

    It was eight unrelated schemes (teal, green, red, orange) and the one place
    carrying no brand at all.
    """
    from utils.thumbnail_gen import COLOR_SCHEMES

    brand = {hex_to_rgb(c) for c in (PURPLE, VIOLET, PINK, ORANGE, LIGHT_ORANGE, LICORICE, WHITE)}
    lic = hex_to_rgb(LICORICE)
    for i, s in enumerate(COLOR_SCHEMES):
        for key in ("bg1", "accent", "text"):
            assert tuple(s[key]) in brand, f"scheme {i} {key}={s[key]} is off-brand"
        # bg2 is deliberately a 50% blend of the accent into Licorice (contrast
        # fix), so assert the derivation rather than membership.
        for ch in range(3):
            expected = round((s["accent"][ch] + lic[ch]) / 2)
            assert s["bg2"][ch] == expected, (
                f"scheme {i} bg2 channel {ch}={s['bg2'][ch]} is not accent/licorice midpoint {expected}"
            )


def test_thumbnail_text_clears_wcag_aa_on_every_scheme():
    """Regression lock for a measured defect.

    White on the full-brightness accents measured 3.06:1 (pink) and 2.49:1
    (orange) -- below AA, i.e. unreadable at thumbnail size. The gradient end is
    now blended toward Licorice, putting the worst case at ~6.7:1. If someone
    raises the blend toward the raw accent again, this fails.
    """
    from utils.thumbnail_gen import COLOR_SCHEMES

    for i, s in enumerate(COLOR_SCHEMES):
        for key in ("bg1", "bg2"):
            r = _contrast(tuple(s["text"]), tuple(s[key]))
            assert r >= 4.5, f"scheme {i} text on {key} is {r:.2f}:1, below WCAG AA"


def test_thumbnail_palette_selection_is_deterministic():
    """hash() on a str is salted per process, so the same topic used to render a
    different palette after every container restart."""
    import subprocess
    import sys

    code = (
        "import sys; sys.path.insert(0,'/app')\n"
        "from utils.thumbnail_gen import COLOR_SCHEMES\n"
        "import zlib\n"
        "t='How Transformers Actually Work'\n"
        "print(zlib.crc32(t.encode()) % len(COLOR_SCHEMES))\n"
    )
    runs = set()
    for seed in ("1", "2", "3"):
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                             env={"PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin"})
        runs.add(out.stdout.strip())
    assert len(runs) == 1, f"palette index varies with PYTHONHASHSEED: {runs}"


def test_thumbnail_renderer_never_calls_the_salted_hash():
    """ast, not a string search: comments and docstrings legitimately quote
    `hash(loop_index)` and `hash(topic)`, so a text match either false-positives
    on the explanation or has to be weakened until it catches nothing."""
    import ast as _ast
    from utils import thumbnail_gen

    tree = _ast.parse(pathlib.Path(thumbnail_gen.__file__).read_text())
    calls = [
        n.func.id for n in _ast.walk(tree)
        if isinstance(n, _ast.Call) and isinstance(n.func, _ast.Name) and n.func.id == "hash"
    ]
    assert not calls, (
        f"bare hash() called {len(calls)}x: str hashes are salted per process, so "
        "palette choice and output filenames change on every restart"
    )






def test_dashboard_favicon_is_brand_purple():
    """favicon.svg/png are live: dashboard/src/app/layout.tsx serves both as the
    app icon and the Apple touch icon. They were still on the pre-rebrand
    #9040F0/#7030C0/#F07030 gradient, so the browser chrome and the installed PWA
    kept the old brand no matter what logo.svg said."""
    from PIL import Image
    import numpy as np
    from collections import Counter

    pub = pathlib.Path(__file__).resolve().parents[2] / "dashboard" / "public"
    if not pub.is_dir():
        # The image ships agents/ as /app only, so the dashboard is a host-only
        # checkout. This guard is still worth having on the host/CI.
        pytest.skip(f"dashboard assets not present at {pub}")
    svg = (pub / "favicon.svg").read_text()
    for old in ("#9040F0", "#7030C0", "#F07030"):
        assert old not in svg, f"favicon.svg still carries legacy {old}"
    for c in (PURPLE, VIOLET, ORANGE):
        assert f"#{c.lstrip('#')}" in svg, f"favicon.svg missing brand stop {c}"

    # 32x32 of a gradient: the modal pixel lands between stops, so check it is
    # within a short distance of a brand colour rather than exactly equal.
    # int() matters: numpy uint8 would wrap the subtraction around instead.
    a = np.array(Image.open(pub / "favicon.png").convert("RGB")).reshape(-1, 3).astype(int)
    brand = {tuple(hex_to_rgb(c)) for c in (PURPLE, VIOLET, ORANGE, WHITE, LICORICE)}
    top = Counter(map(tuple, a)).most_common(1)[0][0]
    assert min(sum(abs(x - y) for x, y in zip(top, b)) for b in brand) < 40, (
        f"favicon.png modal colour {top} is not brand-adjacent"
    )


def test_no_unreferenced_offbrand_logo_asset_is_left_behind():
    """utils/assets/logo.png was the old teal wordmark. Once add_logo_overlay
    switched to channel_logo.png nothing referenced it any more, so it is dead
    weight a future change could plausibly reach for. Deleting beats recolouring
    something no code path can see."""
    assets = pathlib.Path(__file__).resolve().parents[1] / "utils" / "assets"
    assert not (assets / "logo.png").exists(), (
        "unreferenced legacy logo.png is back; delete it or point the watermark at it"
    )
    assert (assets / "channel_logo.png").exists(), "the watermark source is missing"


# The dirs Dockerfile.overlay COPYs into the image. Anything the runtime needs
# from these trees has to be in git: the image is built from the working tree, so
# a gitignored file here means a clean clone silently produces a different image.
_IMAGE_COPY_DIRS = ("utils", "crew", "models", "scripts")


def _git(*args):
    import subprocess
    return subprocess.run(
        ["git", "-C", str(pathlib.Path(__file__).resolve().parents[2]), *args],
        capture_output=True, text=True, check=True,
    ).stdout


def test_image_build_inputs_are_tracked_by_git():
    """channel_logo.png was gitignored by a blanket `*.png` rule. The image bakes
    it in from the working tree, so a clean clone built a container that rendered
    every video with no watermark, and the test suite was green throughout.

    A test that reads the *working tree* cannot see that class of bug at all --
    the file is present locally and absent from the clone. This asks git
    directly, which is the only place the difference is visible."""
    root = pathlib.Path(__file__).resolve().parents[2]
    if not (root / ".git").exists():
        pytest.skip("no .git here (container); the image ships the files, not the history")

    untracked = _git(
        "ls-files", "--others", "--exclude-standard", "--",
        *[f"agents/{d}" for d in _IMAGE_COPY_DIRS],
    ).split()
    stray = [
        f for f in untracked
        if "__pycache__" not in f and not f.endswith((".pyc", ".pyo"))
    ]
    assert not stray, (
        "present in the tree but untracked, so a clean clone would not build them: "
        + ", ".join(stray[:8])
    )


def test_watermark_source_is_committed_not_just_present():
    """The specific instance of the above, kept explicit because it is the one
    that shipped: the watermark is the only binary asset the render path needs."""
    root = pathlib.Path(__file__).resolve().parents[2]
    if not (root / ".git").exists():
        pytest.skip("no .git here (container)")
    tracked = _git("ls-files", "--", "agents/utils/assets/channel_logo.png").split()
    assert tracked == ["agents/utils/assets/channel_logo.png"], (
        "the watermark source is not committed; the image bakes it in from the "
        "working tree, so a clean clone would render with no watermark"
    )


def _runtime_style_guide():
    """`data/brand/` is gitignored runtime state (see .gitignore), so a bare CI
    checkout has no file. Return None rather than failing: the invariant that
    matters in CI is the one against source, which these tests still assert."""
    p = pathlib.Path(__file__).resolve().parents[1] / "data" / "brand" / "style_guide.json"
    return json.loads(p.read_text()) if p.exists() else None


def _colour_forms(token):
    """Every spelling a config colour could be hiding behind.

    An ASS colour is `&HAABBGGRR&` -- BGR, the reverse of CSS `#RRGGBB`. Hand
    editing a CSS hex into that field without swapping the pairs is exactly how
    the style guide ended up holding `&HFF00CCCC&`: read as CSS that is the
    retired teal `#00CCCC`, so the value is a mangled teal whichever way you
    read it, and a guard that only searched for `#00CCCC` never saw it. Return
    both orderings and the bare digits so none of them can hide.
    """
    text = token.strip()
    forms = {text.upper()}
    m = re.fullmatch(r"&H([0-9A-F]{2})([0-9A-F]{6})&", text.upper())
    if m:
        bgr, g, r = m.group(2)[0:2], m.group(2)[2:4], m.group(2)[4:6]
        forms.add("#" + r + g + bgr)   # what a viewer actually sees
        forms.add("#" + bgr + g + r)   # what the editor assumed they had typed
    bare = re.sub(r"[^0-9A-Fa-f]", "", text)
    if len(bare) == 6:
        forms.add("#" + bare.upper())
    return forms


def _compositor_subtitle_sizes():
    """Read the font sizes video_compositor actually burns, out of its source.

    Parsed rather than hardcoded so the guard follows the renderer: if a tier
    is retuned, the style guide's admissible range moves with it instead of
    silently going stale in the other direction.
    """
    import utils.video_compositor as vc

    src = pathlib.Path(vc.__file__).read_text()
    return {int(n) for n in re.findall(r"sub_fs\s*=\s*(\d+)", src)}


def test_stored_brand_config_agrees_with_the_palette():
    """Two live pre-publish config sources used to carry two *different* stale
    palettes while the renderers used a third.

    - data/brand/style_guide.json said primary #00CCCC, the retired teal
    - utils/brand_manager.py DEFAULT_STYLE_GUIDE said #8a50e8
    - video_compositor/visual_profiles render the brand_palette values

    run_consistency_audit is live (main.py calls it on the shorts path), so this
    is not inert data: a reader had no way to tell which set was authoritative.
    """
    import json  # noqa: F401  (used via _runtime_style_guide)
    from utils.brand_manager import DEFAULT_STYLE_GUIDE

    expect = {"primary": PURPLE, "secondary": LICORICE, "accent": ORANGE, "text": WHITE}

    guide = _runtime_style_guide()
    for k, v in expect.items():
        if guide is not None:
            assert guide["colors"][k].upper() == v.upper(), (
                f"style_guide.json colors.{k}={guide['colors'][k]} != {v}"
            )
        assert DEFAULT_STYLE_GUIDE["colors"][k].upper() == v.upper(), (
            f"brand_manager DEFAULT colors.{k}={DEFAULT_STYLE_GUIDE['colors'][k]} != {v}"
        )


def test_stored_subtitle_colour_matches_what_the_compositor_burns():
    """brand_manager advertised white subtitles while the compositor burns
    amber, so a future editor reading the style guide would have 'corrected'
    working code back to unreadable-on-bright-footage white."""
    from utils.brand_manager import DEFAULT_STYLE_GUIDE
    from utils.video_compositor import SUBTITLE_ASS

    stored = DEFAULT_STYLE_GUIDE["visual"]["subtitle_color"].upper()
    assert stored == SUBTITLE_ASS.upper(), (
        f"brand_manager says {stored}, compositor burns {SUBTITLE_ASS}"
    )
    assert stored == "&H000088CC&", "amber is BGR 00 00 88 CC"

    # The code default is only half the story: data/brand/style_guide.json is the
    # copy a human actually opens, and it said the retired teal at size 14 while
    # the default said amber at 24 and the compositor burned amber at 24/26/28/34
    # depending on tier. Reading the default alone is what let that stand.
    #
    # The size check is "one of the sizes the compositor really burns", not
    # "equal to the default": the guide has a single un-per-tier slot while
    # video_compositor picks 24/26/28/34 by tier, so demanding equality with one
    # branch would be inventing an invariant the renderers do not have. What it
    # must never do is advertise a size nothing uses -- 14 was that.
    guide = _runtime_style_guide()
    if guide is not None:
        assert guide["visual"]["subtitle_color"].upper() == SUBTITLE_ASS.upper(), (
            f"style_guide.json says {guide['visual']['subtitle_color']}, "
            f"compositor burns {SUBTITLE_ASS}"
        )
        burned = _compositor_subtitle_sizes()
        assert guide["visual"]["subtitle_font_size"] in burned, (
            f"style_guide.json advertises subtitle_font_size="
            f"{guide['visual']['subtitle_font_size']}, which the compositor "
            f"never burns; it uses {sorted(burned)}"
        )


def test_legacy_teal_is_gone_from_stored_config():
    """#00CCCC is the pre-D35 teal. It is not a brand colour any more; if it
    reappears in stored config, the teal rebrand is half-undone."""
    import json
    from utils.brand_manager import DEFAULT_STYLE_GUIDE

    guide = _runtime_style_guide()
    blob = (json.dumps(guide) if guide is not None else "") + json.dumps(
        DEFAULT_STYLE_GUIDE
    )
    present = set()
    for token in re.findall(r"&H[0-9A-Fa-f]{8}&|#[0-9A-Fa-f]{6}", blob):
        present |= _colour_forms(token)
    present = {p.lower() for p in present}
    for old in LEGACY_HEXES:
        assert old.lower() not in present, f"legacy colour {old} is back in stored config"


LEGACY_HEXES = ("#00cccc", "#8a50e8", "#c060d0", "#e07040", "#9040f0", "#7030c0",
                "#ff6b35", "#1e1e1e")

# The files whose colour literals actually reach a rendered frame or a social
# card. This is an explicit list on purpose: the dashboard/backend agent-chip
# palette is a *categorical* multi-hue scale, not a brand claim, and it sits
# inside a dashboard that still carries an older theme wholesale. Repainting
# that needs visual review, so it is tracked separately rather than smuggled in
# here -- and a broad tree walk would only have forced that change prematurely.
_RENDER_SURFACE_FILES = (
    "utils/brand_palette.py",
    "utils/annotation_renderer.py",
    "utils/video_compositor.py",
    "utils/shorts_renderer.py",
    "utils/scene_parser.py",
    "utils/asset_router.py",
    "utils/dub_pipeline.py",
    "utils/thumbnail_gen.py",
)


def _string_literals_without_docstrings(source: str) -> list[str]:
    """Every string constant in `source` except module/class/function docstrings.

    Comments are absent from the AST entirely, and docstrings are the one place
    the codebase is *meant* to name a retired colour (to explain what was
    replaced). Both are excluded so this test flags real code -- a colour
    assigned to a constant or interpolated into a filter -- and not the history.
    """
    import ast

    tree = ast.parse(source)
    docstring_nodes = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                if isinstance(body[0].value.value, str):
                    docstring_nodes.add(id(body[0].value))
    return [
        n.value for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstring_nodes
    ]


def _rgb_tuple_literals(source: str) -> list[tuple]:
    """Every ``(r, g, b)`` integer tuple written literally in `source`.

    The hex walk above cannot see these: ``(0, 204, 204)`` *is* `#00CCCC`, but it
    is a tuple of int constants, not a string, so it never matches `LEGACY_HEXES`.
    That is how the retired teal stayed live in `asset_router.py` (the accent
    stripe and corner dots on the branded card in the first and last frame of
    every video) and in `dub_pipeline.py` (which was entirely pre-rebrand: #1E1E1E,
    #00CCCC and #FF6B35) while the hex test stayed green. Black, white and grey
    triples are simply not in `LEGACY_HEXES`, so they need no exemption.
    """
    import ast

    out = []
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Tuple)
            and len(node.elts) == 3
            and all(
                isinstance(e, ast.Constant) and isinstance(e.value, int)
                and 0 <= e.value <= 255
                for e in node.elts
            )
        ):
            out.append(tuple(e.value for e in node.elts))
    return out


def test_legacy_hexes_are_gone_from_runtime_source():
    """The stored-config test above cannot see this bug class.

    It read `style_guide.json` + `DEFAULT_STYLE_GUIDE` and stayed green while
    `annotation_renderer.py` still hardcoded the retired palette -- it painted
    the callout text on every composite. A test that reads config cannot see a
    constant in source, so this one walks the AST of the trees that reach a
    rendered frame.
    """
    import ast

    root = pathlib.Path(__file__).resolve().parents[1]
    checked = 0
    for rel in _RENDER_SURFACE_FILES:
        path = root / rel
        assert path.is_file(), f"render-surface file missing, update the list: {rel}"
        src = path.read_text(encoding="utf-8", errors="ignore")
        try:
            literals = _string_literals_without_docstrings(src)
            triples = _rgb_tuple_literals(src)
        except SyntaxError:
            continue
        checked += 1
        for lit in literals:
            low = lit.lower()
            for old in LEGACY_HEXES:
                assert old not in low, (
                    f"{rel} still hardcodes legacy colour {old} "
                    f"in a runtime string literal -- read it from "
                    f"utils.brand_palette instead"
                )
        for triple in triples:
            as_hex = "#%02x%02x%02x" % triple
            assert as_hex not in LEGACY_HEXES, (
                f"{rel} still hardcodes legacy colour {as_hex.upper()} as the RGB "
                f"tuple {triple} -- a hex grep cannot see this form, so read it "
                f"from utils.brand_palette instead"
            )
    # Sanity: the walk must actually cover the files that burned teal. The floor
    # dropped from 13 to 8 when the manim/blender/diagram renderers were deleted.
    assert checked >= 8, f"source walk only covered {checked} files - is the list wrong?"


def test_keyterm_text_overlays_are_gone_from_source():
    """Key terms were burned onto every frame twice, on top of the subtitles.

    `_build_keyterm_filters` painted up to three of them large at the top of the
    frame, and `enrich_scenes_with_annotations` painted the same words again as
    small teal callouts at the bottom-left, directly under the amber subtitle
    track. Both were removed after the owner reviewed real output. This asserts
    the call sites and generators stay gone rather than drifting back.
    """
    import ast

    root = pathlib.Path(__file__).resolve().parents[1]
    for rel in _RENDER_SURFACE_FILES:
        path = root / rel
        if not path.is_file():
            continue
        src = path.read_text(encoding="utf-8", errors="ignore")
        assert "_build_keyterm_filters" not in src, (
            f"{rel} references _build_keyterm_filters; the body key-term overlay "
            f"was removed 09-28"
        )
        assert '"type": "callout"' not in src, (
            f"{rel} re-generates callout annotations; they duplicated the burned "
            f"subtitles and were removed 09-28"
        )


# ---------------------------------------------------------------------------
# Colour grading: the exposure lift
# ---------------------------------------------------------------------------
# Measured with `python3 -m scripts.measure_grade --histogram` against the two
# most recent long-form outputs. Both sat almost entirely in the 32-64 luma
# band (94% of runtime on 09-25, nothing above 64) -- near-black video, which
# is invisible on a phone in daylight. The grader could not fix it: brightness
# was `(target_y - 0.5) * 0.3`, which pins neutral at 0.5 and derived exactly
# +0.000 against measured Y=43. A grader that structurally cannot say "make
# this brighter" cannot fix video that is too dark.

DARK_SCENE = {"y_mean": 43.3, "u_mean": 128.1, "v_mean": 127.9}   # measured 09-26
ON_TARGET = {"y_mean": 92.0, "u_mean": 128.0, "v_mean": 140.0}    # the reference


def _brightness_of(vf: str) -> float:
    m = re.search(r"brightness=([+-][0-9.]+)", vf)
    assert m, f"no brightness in filter: {vf}"
    return float(m.group(1))


def test_grade_lifts_a_scene_that_is_measurably_too_dark():
    """The regression that mattered: dark in, positive brightness out."""
    from utils.video_compositor import BRAND_YUV, _grade_filter

    vf = _grade_filter(DARK_SCENE, BRAND_YUV, 1.0)
    assert _brightness_of(vf) > 0.05, (
        f"dark scene got {vf} -- the grade would be a no-op on exactly the "
        f"footage that needs it"
    )


def test_grade_is_a_no_op_on_a_scene_already_on_target():
    """Converges rather than oscillating: once a scene hits the target it stops."""
    from utils.video_compositor import BRAND_YUV, _grade_filter

    vf = _grade_filter(ON_TARGET, BRAND_YUV, 1.0)
    assert abs(_brightness_of(vf)) < 0.01, f"would keep pushing: {vf}"


def test_brightness_is_clamped_both_ways():
    """`eq` brightness is asymmetric: a big negative is a *cut*. An unbounded
    delta would blow out a bright scene trying to match a dark target."""
    from utils.video_compositor import BRAND_YUV, _grade_filter

    lift = _grade_filter({"y_mean": 5.0}, BRAND_YUV, 1.0)
    cut = _grade_filter({"y_mean": 250.0}, BRAND_YUV, 1.0)
    assert _brightness_of(lift) <= 0.22 + 1e-9, f"lift unclamped: {lift}"
    assert _brightness_of(cut) >= -0.12 - 1e-9, f"cut unclamped: {cut}"


def test_strength_zero_is_an_honest_no_op():
    """The dial claims 0 disables grading. If it still emitted `curves` the
    claim would be false and 'off' would still cost a re-encode."""
    from utils.video_compositor import BRAND_YUV, _grade_filter

    assert _grade_filter(DARK_SCENE, BRAND_YUV, 0.0) == "null"


def test_grade_carries_the_cinematic_look():
    """vibrance instead of eq=saturation (preserves skin tone), a filmic toe
    and shoulder, and no forced brand tint on U/V."""
    from utils.video_compositor import BRAND_YUV, _grade_filter

    vf = _grade_filter(DARK_SCENE, BRAND_YUV, 1.0)
    assert "curves=all=" in vf, f"no filmic curve: {vf}"
    assert "vibrance=" in vf, f"vibrance missing: {vf}"
    assert "saturation=" not in vf, (
        "flat eq=saturation oversaturates skin; vibrance is the correct knob"
    )


def test_grade_threshold_can_actually_see_the_darkness():
    """The threshold is a deadband. At the old 0.15 a dark scene shifted only
    0.080 from the target, so grading silently did almost nothing."""
    from utils.video_compositor import COLOR_GRADING_THRESHOLD, _histogram_shift

    shift = _histogram_shift(GRADE_REFERENCE_YUV, DARK_SCENE)
    assert shift > COLOR_GRADING_THRESHOLD, (
        f"measured dark scene shifts {shift:.4f}, threshold is "
        f"{COLOR_GRADING_THRESHOLD} -- it would never be graded"
    )


def test_env_threshold_matches_the_measured_requirement():
    """D36 rule: code default, .env and Firestore must agree, because a stale
    .env silently overrides the code default and makes the fix inert."""
    import os
    import pathlib

    from utils.video_compositor import COLOR_GRADING_THRESHOLD

    # The value that actually applies, env beating the code default.
    effective = float(os.getenv("COLOR_GRADING_THRESHOLD", COLOR_GRADING_THRESHOLD))
    assert effective <= 0.05, (
        f"effective threshold {effective} is too loose to catch the darkness "
        f"we ship; the grade would silently do nothing"
    )
    here = pathlib.Path(__file__).resolve().parents[1]
    env = here / ".env"
    if env.exists():
        m = re.search(r"^COLOR_GRADING_THRESHOLD=([0-9.]+)", env.read_text(), re.M)
        assert m, "COLOR_GRADING_THRESHOLD missing from .env"
        assert float(m.group(1)) <= 0.05, (
            f".env has {m.group(1)} which would override the code default and "
            f"stop the exposure lift entirely"
        )
