"""Render the brand logo SVG to the PNG sizes the dashboard/PWA expects.

The SVG is the source of truth. The PNGs are checked in (favicon, PWA icons,
social cards), so a rebrand means re-rendering them or the site keeps serving
the old colours. Chromium does the rasterising; the SVG is drawn at 1024 and
scaled by CSS viewport so the wordmark stays crisp.
"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

SIZES = {
    "logo.png": 1024,
    "logo-vyomai.png": 1024,
    "icon-1024.png": 1024,
    "icon-512.png": 512,
    "icon-192.png": 192,
}


def main(svg_path: str, out_dir: str) -> int:
    svg = Path(svg_path).read_text()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1024, "height": 1024})
        page.set_content(
            '<body style="margin:0;background:transparent">' + svg + "</body>"
        )
        el = page.query_selector("svg")
        if el is None:
            print("FATAL: no <svg> found in the source", file=sys.stderr)
            return 1
        for name, px in SIZES.items():
            # The SVG carries its own width/height, so a bare element screenshot
            # always comes out at the SVG's intrinsic size (200x200) no matter
            # what the viewport is. Override it per size.
            el.evaluate(
                "(node, s) => { node.setAttribute('width', s);"
                " node.setAttribute('height', s); }",
                px,
            )
            dest = out / name
            el.screenshot(path=str(dest), omit_background=True)
            print(f"rendered {name} @ {px}x{px} ({dest.stat().st_size}B)")
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
