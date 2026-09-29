"""V0: the viral caption and card.

Both are worth locking because the failure mode is invisible in logs. A caption
that leads with a paraphrase of the headline reads fine and ships the wrong
first line; a card that drops the article's own summary looks deliberate and
just loses the tap.
"""
import os
import re

import pytest

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

    changed = sum(1 for px in diff.get_flattened_data() if px > 12)
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

    Measured on the host render: predicted 337, drawn at rows 336-339 (the rule
    is 4px tall). The real container font wraps the same title differently, so the
    prediction is recomputed from the font actually in use rather than hardcoded.
    """
    from PIL import Image, ImageDraw, ImageFont
    from utils.brand_palette import ORANGE

    size = 1080
    article = _article(body="Nepal opened its first quantum computing research "
                            "laboratory in Kathmandu on Tuesday, funded by the "
                            "government and two universities.")

    probe = ImageDraw.Draw(Image.new("RGB", (size, size)))
    try:
        font = ImageFont.truetype(vna._FONT_PATH, int(size * 0.058))
        font_body = ImageFont.truetype(vna._FONT_PATH, int(size * 0.026))
    except Exception:
        # Host has no container font; the renderer falls back the same way.
        font = font_body = ImageFont.load_default()

    margin = int(size * 0.075)
    max_w = size - margin * 2
    n_headline = len(vna._wrap_text(probe, article["title"], font, max_w))
    n_summary = len(vna._wrap_text(
        probe, vna._caption_body_summary(article, limit=vna._CARD_SUMMARY_CHARS),
        font_body, max_w))
    predicted = vna._card_layout(n_headline, n_summary, size)["div_y"]

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


def test_card_summary_budget_is_what_actually_bounds_the_text(tmp_path, monkeypatch):
    """The 140-char budget is the real constraint on the card, not the 4-line cap.

    Measured, not assumed: at 1080x1080 with the body font, 140 characters wrap to
    3 lines. So the `[:4]` slice in generate_image and `min(n_summary, 4)` in the
    layout are unreachable belt-and-braces -- and untestable, since I removed both
    and the suite stayed green. The binding limit is the character budget, so that
    is what gets tested: a body longer than the budget must render identically to
    the budget-truncated body.
    """
    from PIL import ImageChops
    long_body = ("laboratory research quantum computing superconducting qubits "
                 "calibration dilution " * 20)
    over = _article(body=long_body)
    at_budget = _article(body=vna._trim_to(long_body, vna._CARD_SUMMARY_CHARS))
    assert len(long_body) > vna._CARD_SUMMARY_CHARS, "the body must exceed the budget"
    a = _render(monkeypatch, tmp_path, over, index=0)
    b = _render(monkeypatch, tmp_path, at_budget, index=1)
    assert ImageChops.difference(a, b).getbbox() is None, (
        "an over-budget body renders differently from the truncated one -- the "
        f"{vna._CARD_SUMMARY_CHARS}-char budget is not being applied"
    )


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


def test_a_five_line_headline_does_not_eat_the_click_through_panel():
    """The invariant the layout exists for: the panel is the tap the card buys.

    Asserting the returned `panel_fits` flag is a tautology -- I measured it: it is
    True for every input, because the divider clamp reserves 0.30H and the panel
    only needs 0.21H, so the flag is a dead branch. Two negative tests confirmed it
    (lowering the reserve, and hardcoding the flag True, both stayed green). So
    assert the GEOMETRY the flag is supposed to stand for, and let the clamp be
    what earns it.
    """
    H = 1080
    for n_headline in range(1, 6):
        for n_summary in range(0, 13):
            lay = vna._card_layout(n_headline=n_headline, n_summary=n_summary, H=H)
            where = f"{n_headline}-line headline + {n_summary}-line summary"
            # The panel, the thing that earns the tap, is fully on the card.
            assert lay["panel_y"] + lay["panel_h"] < H - int(H * 0.06), \
                f"{where}: panel falls off the card"
            # Order: headline, then summary, then divider, then panel.
            # With no summary the divider legitimately lands where the summary
            # would have started, so this is >=, not >.
            assert lay["div_y"] >= lay["summary_y"] + lay["body_line_h"] * min(n_summary, 4), \
                f"{where}: divider cuts through the summary"
            assert lay["panel_y"] > lay["div_y"], f"{where}: panel overlaps the divider"


def test_long_headline_still_renders_and_keeps_its_panel(tmp_path, monkeypatch):
    """>5 wrapped lines must not break the card: the tail is dropped, not the panel."""
    long_title = " ".join(["Nepal Opens Its First Quantum Computing Research "
                           "Laboratory In Kathmandu With Government Funding"] * 3)
    out = vna.generate_image(_article(title=long_title), index=0)
    assert out and os.path.exists(out)
    assert os.path.getsize(out) > 5000
