import os
from PIL import Image, ImageDraw, ImageFont
import logging

logger = logging.getLogger(__name__)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tmp", "screencaps")
os.makedirs(OUTPUT_DIR, exist_ok=True)

MONO_FONT_PATH = None
UI_FONT_PATH = None

_candidates_mono = [
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/SFNSMono.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
]
_candidates_ui = [
    "/System/Library/Fonts/SFNSDisplay.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

for p in _candidates_mono:
    if os.path.exists(p):
        MONO_FONT_PATH = p
        break
for p in _candidates_ui:
    if os.path.exists(p):
        UI_FONT_PATH = p
        break

FALLBACK_FONT_SIZE = 14

# Color palette
BG_DARK = "#1E1E2E"
BG_TERMINAL = "#0D0D0D"
BG_IDE = "#1E1E2E"
ACCENT_CYAN = "#89B4FA"
ACCENT_GREEN = "#A6E3A1"
ACCENT_YELLOW = "#F9E2AF"
ACCENT_RED = "#F38BA8"
TEXT_COLOR = "#CDD6F4"


def _load_font(path: str | None, size: int = 14):
    if path and os.path.exists(path):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def render_terminal(code_lines: list[str], title: str = "terminal.py", width: int = 960, height: int = 540) -> str:
    img = Image.new("RGB", (width, height), BG_TERMINAL)
    draw = ImageDraw.Draw(img)
    font = _load_font(MONO_FONT_PATH, FALLBACK_FONT_SIZE)
    font_small = _load_font(MONO_FONT_PATH, 11)

    title_bar_h = 36
    draw.rectangle([(0, 0), (width, title_bar_h)], fill="#1A1A1A")

    dot_colors = ["#FF5F56", "#FFBD2E", "#27C93F"]
    for i, dc in enumerate(dot_colors):
        cx, cy = 18 + i * 24, title_bar_h // 2
        draw.ellipse([(cx - 6, cy - 6), (cx + 6, cy + 6)], fill=dc)

    if title:
        draw.text((width // 2 - 40, 10), title, fill="#888888", font=font_small)

    y = title_bar_h + 16
    line_h = font.size + 4
    for line in code_lines[:max(1, (height - title_bar_h) // line_h - 1)]:
        if line.startswith("#"):
            draw.text((16, y), line, fill="#6C7086", font=font)
        elif line.startswith("$"):
            draw.text((16, y), line, fill=ACCENT_GREEN, font=font)
        elif "def " in line or "class " in line:
            draw.text((16, y), line, fill=ACCENT_YELLOW, font=font)
        elif "import" in line or "from" in line:
            draw.text((16, y), line, fill=ACCENT_CYAN, font=font)
        else:
            draw.text((16, y), line, fill=TEXT_COLOR, font=font)
        y += line_h

    path = os.path.join(OUTPUT_DIR, f"terminal_{title}_{hash(tuple(code_lines)) % 10000:04d}.png")
    img.save(path)
    return path


def render_ide(code_lines: list[str], title: str = "main.py", width: int = 960, height: int = 540) -> str:
    img = Image.new("RGB", (width, height), BG_IDE)
    draw = ImageDraw.Draw(img)
    font = _load_font(MONO_FONT_PATH, FALLBACK_FONT_SIZE)
    font_small = _load_font(MONO_FONT_PATH, 11)

    sidebar_w = 50
    draw.rectangle([(0, 0), (sidebar_w, height)], fill="#181825")
    tab_h = 36
    draw.rectangle([(sidebar_w, 0), (width, tab_h)], fill="#181825")
    tab_w = min(len(title) * 8 + 40, 200)
    draw.rectangle([(sidebar_w, 0), (sidebar_w + tab_w, tab_h)], fill="#1E1E2E")
    draw.text((sidebar_w + 12, 10), title, fill=TEXT_COLOR, font=font_small)

    line_numbers_w = 48
    draw.rectangle([(sidebar_w, tab_h), (sidebar_w + line_numbers_w, height)], fill="#181825")

    content_x = sidebar_w + line_numbers_w + 12
    y = tab_h + 8
    font_editor = _load_font(MONO_FONT_PATH, 13)
    line_h = font_editor.size + 3
    for i, line in enumerate(code_lines[:max(1, (height - tab_h) // line_h - 1)]):
        ln = i + 1
        draw.text((sidebar_w + 8, y + 1), str(ln), fill="#6C7086", font=font_small)
        if line.strip().startswith("#"):
            draw.text((content_x, y), line, fill="#6C7086", font=font_editor)
        elif line.strip().startswith("def ") or line.strip().startswith("class "):
            draw.text((content_x, y), line, fill=ACCENT_YELLOW, font=font_editor)
        elif "import" in line or "from" in line:
            draw.text((content_x, y), line, fill=ACCENT_CYAN, font=font_editor)
        elif "return" in line:
            draw.text((content_x, y), line, fill=ACCENT_GREEN, font=font_editor)
        else:
            draw.text((content_x, y), line, fill=TEXT_COLOR, font=font_editor)
        y += line_h

    path = os.path.join(OUTPUT_DIR, f"ide_{title}_{hash(tuple(code_lines)) % 10000:04d}.png")
    img.save(path)
    return path


def render_browser(url: str = "https://example.com", width: int = 960, height: int = 540) -> str:
    img = Image.new("RGB", (width, height), "#FFFFFF")
    draw = ImageDraw.Draw(img)
    font_ui = _load_font(UI_FONT_PATH, 13)
    font_small = _load_font(UI_FONT_PATH, 11)

    title_bar_h = 40
    draw.rectangle([(0, 0), (width, title_bar_h)], fill="#DEE1E6")
    nav_h = 36
    draw.rectangle([(0, title_bar_h), (width, title_bar_h + nav_h)], fill="#E8EAED")

    dot_colors = ["#FF5F56", "#FFBD2E", "#27C93F"]
    for i, dc in enumerate(dot_colors):
        cx, cy = 16 + i * 20, title_bar_h // 2
        draw.ellipse([(cx - 5, cy - 5), (cx + 5, cy + 5)], fill=dc)

    addr_x = 120
    addr_w = width - addr_x - 16
    draw.rounded_rectangle([(addr_x, title_bar_h + 6), (addr_x + addr_w, title_bar_h + nav_h - 6)], radius=4, fill="#FFFFFF")
    draw.text((addr_x + 12, title_bar_h + 10), url, fill="#5F6368", font=font_ui)

    content_y = title_bar_h + nav_h + 20
    draw.text((width // 2 - 60, content_y), "Page content area", fill="#888888", font=font_small)

    lock_x = addr_x + addr_w - 30
    draw.text((lock_x, title_bar_h + 10), "🔒", fill="#34A853", font=font_ui)

    path = os.path.join(OUTPUT_DIR, f"browser_{hash(url) % 10000:04d}.png")
    img.save(path)
    return path


def render_code_snippet(code_lines: list[str], width: int = 960, height: int = 540) -> str:
    return render_ide(code_lines, title="snippet.py", width=width, height=height)
