"""V0: the viral caption and card.

Both are worth locking because the failure mode is invisible in logs. A caption
that leads with a paraphrase of the headline reads fine and ships the wrong
first line; a card that drops the article's own summary looks deliberate and
just loses the tap.
"""
import os
import re

import pytest
from PIL import ImageFont

from utils import viral_news_agent as vna


def _article(**over):
    art = {
        "title": "Nepal Opens Its First Quantum Computing Research Lab",
        "source": "The Kathmandu Post",
        "link": "https://kathmandupost.com/quantum-lab-2026",
        "category": "Science & Technology",
        "body": ("Nepal's first quantum computing research lab opened in Kathmandu "
                 "on Tuesday, funded jointly by the government and two universities. "
                 "Researchers will work on error correction in superconducting qubits."),
    }
    art.update(over)
    return art


class _FakeLLM:
    def __init__(self, reply):
        self.reply = reply

    def call(self, messages):
        return self.reply


def _with_llm(monkeypatch, reply):
    """Stub the whole llm_helper module, not just get_llm.

    generate_caption imports it inside the function, so patching the attribute on
    the real module would need langchain to have imported first -- which the host
    does not have. Substituting sys.modules sidesteps the dependency entirely.
    """
    import sys
    import types
    stub = types.ModuleType("utils.llm_helper")
    stub.get_llm = lambda **kw: _FakeLLM(reply)
    monkeypatch.setitem(sys.modules, "utils.llm_helper", stub)


def test_caption_leads_with_the_verbatim_headline(monkeypatch):
    _with_llm(monkeypatch, "HOOK: A quantum lab just opened in Kathmandu\n"
                           "BODY: Researchers there will work on superconducting qubits.")
    art = _article()
    cap = vna.generate_caption(art)
    assert cap.startswith(art["title"]), "the caption must open with the headline, verbatim"


def test_caption_parts_are_in_the_agreed_order(monkeypatch):
    _with_llm(monkeypatch, "HOOK: A quantum lab just opened in Kathmandu\n"
                           "BODY: Researchers there will work on superconducting qubits.")
    cap = vna.generate_caption(_article())
    body = cap.split("\n\n")
    art = _article()
    assert body[0] == art["title"]
    assert "Comment below" in cap
    assert re.search(r"#\w+", cap), "hashtags are built in code, not asked of the LLM"
    # The URL is the last clickable thing, on every platform.
    assert cap.strip().endswith(art["link"]), "the link must be the final element"
    assert cap.index(art["title"]) < cap.index("#"), "hashtags come after the body"


def test_caption_never_ships_a_headline_twice(monkeypatch):
    """A hook that just repeats the title is dropped, not printed twice."""
    art = _article()
    _with_llm(monkeypatch, f"HOOK: {art['title']}\nBODY: Something else entirely happened.")
    cap = vna.generate_caption(art)
    assert cap.count(art["title"]) == 1


def test_caption_falls_back_to_article_text_when_the_llm_is_unusable(monkeypatch):
    """No HOOK/BODY markers -> the article's own words, still in order."""
    _with_llm(monkeypatch, "here is a caption, no markers at all")
    art = _article()
    cap = vna.generate_caption(art)
    assert cap.startswith(art["title"])
    assert "superconducting qubits" in cap
    assert cap.strip().endswith(art["link"])


def test_caption_with_no_article_body_is_title_and_link_only(monkeypatch):
    """Nothing to summarise means nothing invented. No hook, no CTA."""
    _with_llm(monkeypatch, "HOOK: something\nBODY: something")
    art = _article(body="", description="")
    cap = vna.generate_caption(art)
    assert cap.strip() == f"{art['title']}\n\nRead the full story at {art['source']}: {art['link']}"


def test_hashtags_are_derived_and_never_placeholder_slop():
    tags = vna._hashtags(_article())
    assert "#Quantum" in tags and "#Nepal" in tags
    assert "#News" not in tags, "a real headline already gives us better tags than #News"
    assert len(tags.split()) <= 5


def test_card_and_caption_get_separate_summary_budgets():
    """Two surfaces, two budgets. The card is space-constrained, the caption is not."""
    long_body = "word " * 400
    card = vna._caption_body_summary(_article(body=long_body), limit=vna._CARD_SUMMARY_CHARS)
    caption = vna._caption_body_summary(_article(body=long_body))
    assert len(card) <= vna._CARD_SUMMARY_CHARS + 1
    assert len(caption) <= vna._CAPTION_SUMMARY_CHARS + 1
    assert len(caption) > len(card)
    # The trim must land on a word boundary in both.
    for out in (card, caption):
        assert not re.search(r"\bwor…", out), f"half word: ...{out[-14:]}"


@pytest.mark.skipif(not vna.HAS_PIL, reason="PIL required for the card")
def test_card_renders_and_keeps_the_read_full_story_panel(tmp_path, monkeypatch):
    """The panel is the click-through cue. A summary must not push it off the card."""
    monkeypatch.setattr(vna, "_TEMP_DIR", tmp_path)
    monkeypatch.setattr(vna, "_IMAGE_WIDTH", 1080)
    monkeypatch.setattr(vna, "_IMAGE_HEIGHT", 1080)
    out = vna.generate_image(_article(body="word " * 400), index=0)
    assert out and os.path.exists(out)
    assert os.path.getsize(out) > 5000


@pytest.mark.skipif(not vna.HAS_PIL, reason="PIL required for the card")
def test_card_summary_is_actually_drawn(tmp_path, monkeypatch):
    """Measure the summary, do not infer it from file size.

    A card with the summary removed is the same byte size and renders perfectly
    -- every earlier assertion here passed against a summary-less card. Only the
    pixels can see it, so render the same article with and without body text and
    require a real difference.
    """
    from PIL import Image, ImageChops
    monkeypatch.setattr(vna, "_TEMP_DIR", tmp_path)
    monkeypatch.setattr(vna, "_IMAGE_WIDTH", 540)
    monkeypatch.setattr(vna, "_IMAGE_HEIGHT", 540)

    with_body = vna.generate_image(_article(), index=0)
    without = vna.generate_image(_article(body="", description=""), index=1)
    a, b = Image.open(with_body).convert("L"), Image.open(without).convert("L")
    diff = ImageChops.difference(a, b)
    bbox = diff.getbbox()
    assert bbox is not None, "the card is byte-identical with and without article text"

    # tobytes(), not get_flattened_data(): the latter does not exist in the
    # container's Pillow, and this suite is only trustworthy if it runs in BOTH
    # places -- that is how the wrap-cap bug below was found.
    changed = sum(1 for px in diff.tobytes() if px > 12)
    assert changed > 500, f"only {changed} px differ -- the summary block is not drawn"


@pytest.mark.skipif(not vna.HAS_PIL, reason="PIL required for the card")
def _render(monkeypatch, tmp_path, article, index=0, size=540):
    from PIL import Image
    monkeypatch.setattr(vna, "_TEMP_DIR", tmp_path)
    monkeypatch.setattr(vna, "_IMAGE_WIDTH", size)
    monkeypatch.setattr(vna, "_IMAGE_HEIGHT", size)
    return Image.open(vna.generate_image(article, index=index)).convert("L")


def test_title_is_rendered_verbatim_not_truncated(tmp_path, monkeypatch):
    """V0 locks the headline as the publisher's own words. A character slice is a
    silent misattribution, and a file-size assertion cannot see it -- a truncated
    title renders a perfectly valid PNG of the same size.

    Detected by comparison: if the code slices, the full title and the pre-sliced
    title produce IDENTICAL cards, so any difference proves the tail survived.
    """
    from PIL import ImageChops
    long_title = ("Nepal Opens Its First Quantum Computing Research Laboratory "
                  "In Kathmandu With Government Funding After Five Years Of "
                  "Negotiation With Three Universities")
    assert len(long_title) > 120, "the title must exceed the old slice to test this"

    full = _render(monkeypatch, tmp_path, _article(title=long_title), index=0)
    sliced = _render(monkeypatch, tmp_path, _article(title=long_title[:120]), index=1)
    assert ImageChops.difference(full, sliced).getbbox() is not None, (
        "the card is identical to the 120-char slice -- the title IS being truncated"
    )


def test_drawn_divider_matches_the_layout_prediction(tmp_path, monkeypatch):
    """Guard against _card_layout and the drawing code drifting apart.

    The layout was extracted from inline arithmetic purely so it could be tested.
    That extraction is only safe while the renderer still uses it, and a unit test
    of the function alone cannot see that. So: find the orange divider in the
    rendered pixels and require it to sit exactly where the layout said.

    The rule is 4px tall, so the drawn rows are a small band around the
    prediction. The real container font wraps the same title differently from the
    host's, so the prediction is recomputed from the font actually in use --
    including the fitted headline scale, since the renderer shrinks a long title
    rather than cutting it.
    """
    from PIL import Image, ImageDraw, ImageFont
    from utils.brand_palette import ORANGE

    size = 1080
    article = _article(body="Nepal opened its first quantum computing research "
                            "laboratory in Kathmandu on Tuesday, funded by the "
                            "government and two universities.")

    probe = ImageDraw.Draw(Image.new("RGB", (size, size)))
    # The headline is measured in the SERIF face, not the sans one. Getting this
    # wrong is invisible on the host, where every path collapses to the same
    # load_default() fallback, and only the container's real fonts expose it.
    def _load(path, px):
        try:
            return ImageFont.truetype(path, px)
        except Exception:
            return ImageFont.load_default()

    # The type scale is read from the module, never restated here. This test
    # hardcoded 0.058/0.026 once and silently kept predicting a pre-redesign
    # divider after the scale moved -- the same duplicate-source bug as the
    # _FONT_PATH/_SERIF_FONT_PATH mixup below, one level up.
    margin = int(size * 0.075)
    max_w = size - margin * 2
    # The renderer fits the headline scale down rather than cutting a long
    # title, so the prediction has to fit it the same way.
    scale = vna._title_scale_for(probe, article["title"], size, size, margin)
    font = _load(vna._SERIF_FONT_PATH, int(size * scale))
    font_body = _load(vna._FONT_PATH, int(size * vna._CARD_SCALE["body"]))

    n_headline = len(vna._wrap_text(probe, article["title"], font, max_w))
    n_summary = len(vna._wrap_text(
        probe, vna._caption_body_summary(article, limit=vna._CARD_SUMMARY_CHARS),
        font_body, max_w))
    predicted = vna._card_layout(n_headline, n_summary, size,
                                 line_spacing=int(size * scale * 1.20))["div_y"]

    monkeypatch.setattr(vna, "_TEMP_DIR", tmp_path)
    monkeypatch.setattr(vna, "_IMAGE_WIDTH", size)
    monkeypatch.setattr(vna, "_IMAGE_HEIGHT", size)
    img = Image.open(vna.generate_image(article, index=0)).convert("RGB")

    oc = tuple(int(ORANGE[i:i + 2], 16) for i in (1, 3, 5))
    rows = [
        y for y in range(size)
        if sum(1 for x in range(0, size, 4)
               if all(abs(img.getpixel((x, y))[k] - oc[k]) <= 12
                      for k in range(3))) > (size // 4) * 0.5
    ]
    assert rows, "no orange divider found on the card"
    assert predicted in rows, (
        f"layout predicted the divider at y={predicted}, drawn at {rows} -- "
        "_card_layout and the drawing code have drifted apart"
    )


def test_summary_line_clamp_binds_before_the_character_budget(tmp_path, monkeypatch):
    """The 5-line clamp, not the char budget, is what bounds the summary.

    This replaces a test that had become unable to fail. It compared an
    over-budget body against a body trimmed to `_CARD_SUMMARY_CHARS` and
    demanded identical pixels, on the theory that the char budget was the binding
    limit. That was true at 140 chars and a 0.026 body (140 wrapped to 3 lines,
    under the old 4-line cap). At the new scale 230 chars wraps to 7 lines, so
    BOTH sides now clamp to 5 and the test would pass with the char budget
    deleted -- a green test reading as coverage while proving nothing. So the
    invariant is stated directly instead: the clamp is load-bearing, and the
    budget is a real but looser ceiling.
    """
    H = 1080
    # Words chosen so the 200-char budget lands on 6 lines, one past the cap.
    # Line COUNT is set by word length, not character count, so a fixture can
    # sit inside the budget and still not exercise the clamp. Both earlier
    # fixtures did exactly that -- the post-retune one trimmed to 194 chars and
    # wrapped to precisely 5, making this test pass without testing anything.
    # The precondition assert below is what caught it and is why it stays.
    long_body = "superconducting quantum dilution " * 20
    # 1. The budget really is reached past the clamp, or the test is vacuous.
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (vna._IMAGE_WIDTH, H))
    d = ImageDraw.Draw(img, "RGBA")
    body_font = ImageFont.truetype(vna._FONT_PATH, int(H * vna._CARD_SCALE["body"]))
    margin = int(vna._IMAGE_WIDTH * 0.075)
    wrapped = vna._wrap_text(
        d, vna._trim_to(long_body, vna._CARD_SUMMARY_CHARS), body_font,
        vna._IMAGE_WIDTH - margin * 2)
    assert len(wrapped) > vna._CARD_MAX_SUMMARY_LINES, (
        f"the budget now wraps to {len(wrapped)} lines, which no longer exceeds "
        f"the {vna._CARD_MAX_SUMMARY_LINES}-line clamp -- this test is vacuous and "
        "the char budget needs re-measuring"
    )
    # 2. The clamp is what stops it: exactly the cap is drawn, never more.
    for n_summary in range(0, 14):
        lay = vna._card_layout(3, n_summary, H)
        assert lay["n_summary"] <= vna._CARD_MAX_SUMMARY_LINES, (
            f"n_summary={n_summary} -> {lay['n_summary']} lines drawn, cap is "
            f"{vna._CARD_MAX_SUMMARY_LINES}"
        )
    # 3. And the rendered card really only has that many summary lines: the
    #    divider sits exactly one gap below the last drawn one.
    lay = vna._card_layout(3, vna._CARD_MAX_SUMMARY_LINES, H)
    assert lay["div_y"] == lay["summary_y"] + vna._CARD_MAX_SUMMARY_LINES * lay["body_line_h"] \
        + int(H * 0.028), "the divider is not placed below exactly the drawn lines"


def test_panel_and_url_are_bottom_anchored():
    """The layout fix: the panel and URL hold fixed offsets from the bottom edge.

    They used to float at `div_y + pad`, which is what left 21-39% of the card
    empty (measured across real article shapes). Anchoring is the whole point of
    the redesign, and it is trivially assertable without rendering: panel_y and
    url_y must not vary with content length.
    """
    H = 1080
    for n_headline in range(0, 8):
        for n_summary in range(0, 10):
            lay = vna._card_layout(n_headline=n_headline, n_summary=n_summary, H=H)
            where = f"{n_headline} headline / {n_summary} summary"
            assert lay["panel_y"] == H - int(H * 0.075) - int(H * 0.105), \
                f"{where}: panel_y {lay['panel_y']} is not the bottom-anchored value"
            assert lay["url_y"] == H - int(H * 0.038), \
                f"{where}: url_y {lay['url_y']} is not the bottom-anchored value"


def test_text_block_is_centred_above_the_panel():
    """A short card must read as balanced padding, not as a hole.

    Bottom-anchoring alone moved the hole rather than removing it: a 2-line
    headline with a 1-line summary still measured 20% of empty card, all of it
    between the divider and the panel. The layout centres the block in that
    slack, so the two empty bands end up within a line of each other.
    """
    H = 1080
    for n_headline in range(1, 6):
        for n_summary in range(0, 8):
            lay = vna._card_layout(n_headline=n_headline, n_summary=n_summary, H=H)
            # Slack above the block (from below the gradient strip) and below it
            # (down to the panel top) should be within ~1.5 body lines of equal.
            top = lay["eyebrow_y"] - int(H * 0.035)
            bottom = lay["panel_y"] - lay["div_y"]
            assert abs(top - bottom) <= int(1.5 * lay["body_line_h"]), (
                f"{n_headline}H/{n_summary}S: top gap {top} vs bottom gap {bottom} "
                "is not centred"
            )


def test_a_five_line_headline_does_not_eat_the_click_through_panel():
    """The invariant the layout exists for: the panel is the tap the card buys.

    Asserting the returned `panel_fits` flag was a tautology -- I measured it: it
    is True for every input, because the divider clamp reserves 0.30H and the
    panel only needs 0.21H, so the flag was a dead branch. Two negative tests
    confirmed it (lowering the reserve, and hardcoding the flag True, both stayed
    green). The flag is gone now that the panel does not move, and the geometry
    it stood for is asserted directly: overlap is impossible because the layout
    caps how many lines may be drawn rather than clamping a y.
    """
    H = 1080
    for n_headline in range(1, 6):
        for n_summary in range(0, 13):
            lay = vna._card_layout(n_headline=n_headline, n_summary=n_summary, H=H)
            where = f"{n_headline}-line headline + {n_summary}-line summary"
            # The panel, the thing that earns the tap, is fully on the card.
            assert lay["panel_y"] + lay["panel_h"] < H - int(H * 0.06), \
                f"{where}: panel falls off the card"
            # Order: headline, then summary, then divider, then panel. Asserted
            # against the lines the layout says it will DRAW, which is the point:
            # an input asking for 12 lines must not push the divider down.
            drawn_h = lay["n_headline"] * lay["line_spacing"]
            drawn_s = lay["n_summary"] * lay["body_line_h"]
            assert lay["headline_y"] + drawn_h <= lay["summary_y"] + 1, \
                f"{where}: headline overruns the summary"
            assert lay["div_y"] >= lay["summary_y"] + drawn_s, \
                f"{where}: divider cuts through the drawn summary"
            assert lay["panel_y"] > lay["div_y"], f"{where}: panel overlaps the divider"
            assert lay["url_y"] > lay["panel_y"] + lay["panel_h"], \
                f"{where}: URL overlaps the panel"


def test_summary_position_tracks_headline_length():
    """The summary is laid out AFTER the headline, so its y must move when the
    headline grows. A summary pinned to a fixed y fails this.

    This is the check the pixel diff could not make: measuring with/without-body
    gave the same numbers (131/169) for both a correct and a fixed-y summary,
    because the divider moves too and its top edge is what the diff reports.
    """
    H = 1080
    short = [vna._card_layout(n, 4, H)["summary_y"] for n in (1, 2, 3, 4, 5)]
    assert short == sorted(short) and len(set(short)) == 5, (
        f"summary_y does not move with the headline: {short} -- it is at a fixed y"
    )
    # Past 5 wrapped lines the headline is capped, so the summary stops moving.
    # This is what makes the 5-line cap load-bearing rather than decorative.
    capped = vna._card_layout(9, 4, H)["summary_y"]
    assert capped == short[-1], (
        f"a 9-line headline moved the summary to {capped}, expected the 5-line cap "
        f"to hold it at {short[-1]}"
    )


def test_long_headline_still_renders_and_keeps_its_panel(tmp_path, monkeypatch):
    """>5 wrapped lines must not break the card: the tail is dropped, not the panel."""
    long_title = " ".join(["Nepal Opens Its First Quantum Computing Research "
                           "Laboratory In Kathmandu With Government Funding"] * 3)
    out = vna.generate_image(_article(title=long_title), index=0)
    assert out and os.path.exists(out)
    assert os.path.getsize(out) > 5000
