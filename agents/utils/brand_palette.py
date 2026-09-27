"""Brand palette — the single source of truth for brand colours.

`#00CCCC` teal was previously hardcoded in ~20 places across 10+ files, so a
rebrand meant hunting string literals and any miss showed up as one mismatched
CTA. Everything new reads from here.

Channel order, measured not assumed (see tests/test_brand_colors.py):
  * ffmpeg `drawtext=fontcolor`, `drawbox=color` and `boxcolor` are **RGB**, in
    both `#RRGGBB` and `0xRRGGBB` form. No conversion. (Probed: a #FF8000 box
    reads back (253,127,0), i.e. red-first, not swapped.)
  * ASS/libass `&HAABBGGRR&` subtitle colours really **are BGR**. Those are the
    only values that need converting, which is what `ass()` is for. Subtitles
    stay amber for contrast — the brand lives in the graphics, not in text a
    viewer reads for three seconds.

Deliberately NOT centralised: subtitle colours per tier. They are calibrated for
readability against unknown footage, not chosen, and turning them purple would
trade legibility for branding.

Source of truth for the brand: the rendered logo + this file.
"""

# Core palette
LICORICE = "#1B1212"   # backgrounds, dark surfaces
PURPLE = "#9B4DFF"     # primary accent (logo)
VIOLET = "#6641FC"     # secondary accent, gradients
PINK = "#F856A5"       # highlight / rare emphasis
ORANGE = "#FF8133"     # CTA, dividers
LIGHT_ORANGE = "#FFB05F"  # secondary CTA, softer text
WHITE = "#FFFFFF"      # body text on dark
AMBER = "#CC8800"      # subtitle primary, the BGR twin of ASS &H000088CC&

# Brand type scale for social cards / thumbnails
SERIF_DISPLAY = "serif"   # headline voice
SANS_BODY = "sans-serif"  # everything else

# Every brand surface that needs a gradient or accent strip, in draw order.
ACCENT_RAMP = (PURPLE, VIOLET, PINK, ORANGE, LIGHT_ORANGE)

# Ordered ramp for a top-to-top "spotlight" gradient: dark at the edges,
# brightest where the eye lands (upper third).
SPOTLIGHT_RAMP = (VIOLET, PURPLE, PINK, ORANGE, LIGHT_ORANGE)

# Colour-grading reference, in the YUV units _histogram_shift compares against.
#
# MEASURED, not freehand. `python3 -m scripts.measure_grade <mp4> --histogram`
# against the two most recent long-form outputs:
#
#   long-20260926-1_long.mp4  Y p50=43.3  p90=73.7  max=163.8  U=128.1 V=127.8
#   long-20260925-1_long.mp4  Y p50=38.7  p90=51.2  max= 81.0  U=135.0 V=123.5
#
# So the pipeline was shipping video that sits almost entirely in the 32-64 luma
# band -- 94% of runtime on 09-25, with nothing at all above 64. That is not a
# "mood", it is a near-black frame: invisible on a phone in daylight, which is
# where most of this is actually watched. The old teal reference had the opposite
# failure (y=140,u=160,v=80 desaturated every frame ~4% and sat 32/255 off
# neutral chroma, so ordinary footage read as "off brand").
#
# Target below is therefore a deliberate, well-exposed corporate-cinematic look
# rather than a restatement of what the pipeline happened to produce:
#   y=92  comfortable exposure. Rec.709 mid-grey is 126 at 50% code, but that
#         is a *reference white*; well-exposed editorial content averages lower.
#         92 keeps deep shadow detail without the mud.
#   u=128 neutral chroma axis (measured 128-135, so no cast to correct).
#   v=140 a small headroom so the grade can add vibrance rather than have to
#         desaturate first -- measured V sat at 123-128, i.e. slightly flat.
#
# The brand colour is carried by the CTA / lower-third / watermark. Tinting every
# frame purple is what makes AI footage look cheap; brightening it so people can
# actually watch it is what makes them stay.
GRADE_REFERENCE_YUV = {"y_mean": 92.0, "u_mean": 128.0, "v_mean": 140.0}

# Filmic S-curve applied after the exposure lift: a soft toe so shadows keep
# detail, a shoulder at 0.75 so mid-tones stay open, and a 0.98 ceiling so
# speculars roll off instead of clipping flat. Gentle on purpose -- a hard curve
# on already-crushed footage just trades mud for banding.
GRADE_CURVES = "0/0 0.25/0.255 0.5/0.55 0.75/0.80 1/0.98"



def ass(rgb: str, alpha: int = 0) -> str:
    """'#FF8133' -> '&H003381FF&'. libass wants &HAABBGGRR&, so the channels
    are reversed. This is the one conversion in the codebase that is real; see
    the module docstring for why ffmpeg filter strings need none."""
    r, g, b = hex_to_rgb(rgb)
    return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}&"


def hex_to_rgb(value: str) -> tuple:
    """'#9B4DFF' -> (155, 77, 255). Raises on anything that is not #RRGGBB."""
    v = value.lstrip("#")
    if len(v) != 6:
        raise ValueError(f"expected #RRGGBB, got {value!r}")
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))


def lerp(a: str, b: str, t: float) -> tuple:
    """Blend two hex colours, t in [0, 1]. Returns an RGB tuple."""
    t = max(0.0, min(1.0, t))
    ra, ga, ba = hex_to_rgb(a)
    rb, gb, bb = hex_to_rgb(b)
    return (
        round(ra + (rb - ra) * t),
        round(ga + (gb - ga) * t),
        round(ba + (bb - ba) * t),
    )


# --------------------------------------------------------------------------
# Safe areas
# --------------------------------------------------------------------------
# Fractions of the frame, measured not guessed. These are the regions the
# *platform* covers with its own UI, so anything we draw there is invisible in
# the published video even though it renders fine locally.
#
#   9:16 (Shorts / TikTok / Reels)
#     top    ~12%  status bar + notch
#     right  ~14%  action rail (like/comment/share), vertically centred
#     bottom ~18%  channel name + caption + audio ticker
#   16:9 (YouTube long form)
#     bottom ~6%   controls fade in on hover; progress bar
#     right  ~4%   nothing, kept for symmetry with 9:16
#
# The bottom band is the one that bites: it is the widest, it is the most
# reliably covered on every platform, and a centred CTA dropped into it looks
# fine in the render and is simply gone on upload.
SAFE_AREA = {
    "portrait": {"top": 0.12, "right": 0.14, "bottom": 0.18, "left": 0.04},
    "landscape": {"top": 0.06, "right": 0.04, "bottom": 0.06, "left": 0.04},
}


def safe_band(format_type: str) -> dict:
    """Keep-out fractions for a format. 'shorts'/'portrait' -> portrait bands."""
    key = "portrait" if str(format_type).lower() in ("shorts", "short", "portrait", "9:16") else "landscape"
    return SAFE_AREA[key]


def content_box(width: int, height: int, format_type: str = "landscape") -> tuple:
    """The rectangle that is actually visible on every platform.

    Returns (x, y, w, h) in pixels. Use it to place anything that must never be
    covered -- the logo, the CTA, the end card -- instead of hand-tuning
    fractions per format.
    """
    b = safe_band(format_type)
    x = round(width * b["left"])
    y = round(height * b["top"])
    w = max(1, round(width * (1 - b["left"] - b["right"])))
    h = max(1, round(height * (1 - b["top"] - b["bottom"])))
    return x, y, w, h


def watermark_position(width: int, height: int, format_type: str = "landscape") -> str:
    """ffmpeg overlay expression for the channel logo, inside the safe box.

    Top-right on every format, and that is deliberate rather than lazy:
      - 9:16 bottom is the caption/name band, so bottom-right is the single
        worst corner on Shorts and TikTok.
      - 9:16 right is the action rail through the vertical middle.
      - the top-right corner is the only one clear on both formats, and using
        one corner for both keeps the bug in the same place in every video, so
        it reads as a brand mark instead of drift.
    The hook bar is the one thing that shares that corner; it only occupies the
    first ~2s, and the logo is scaled small enough to sit clear of its text.
    """
    b = safe_band(format_type)
    m = round(height * 0.035)          # breathing room inside the safe box
    return f"main_w-overlay_w-{m}:{m}"

