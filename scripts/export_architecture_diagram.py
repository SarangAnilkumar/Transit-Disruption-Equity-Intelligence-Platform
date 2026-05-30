#!/usr/bin/env python3
"""Export architecture diagram PNGs from docs/architecture_diagram.html."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "docs" / "architecture_diagram.html"
OUTPUT_COMPACT = ROOT / "docs" / "assets" / "architecture_diagram.png"
OUTPUT_FULL = ROOT / "docs" / "assets" / "architecture_diagram_full.png"

EXPORT_CSS = """
body { padding: 16px !important; }
.toolbar { display: none !important; }
#report-container {
  max-width: none !important;
  width: max-content !important;
}
#architecture-export {
  display: block !important;
  width: max-content !important;
  max-width: none !important;
  overflow: visible !important;
}
#architecture-export .diagram-container {
  overflow: visible !important;
}
#architecture-export .diagram-svg {
  width: 1320px !important;
  min-width: 1320px !important;
  max-width: none !important;
  display: block !important;
}
.page-supplement {
  display: block !important;
  visibility: visible !important;
  width: 1320px !important;
  max-width: 1320px !important;
  margin-top: 2rem !important;
  clear: both !important;
}
"""


def _measure(page, selector: str) -> dict[str, int]:
    return page.evaluate(
        """(selector) => {
          const el = document.querySelector(selector);
          if (!el) throw new Error('Missing element: ' + selector);
          const rect = el.getBoundingClientRect();
          return {
            scrollWidth: Math.ceil(el.scrollWidth),
            scrollHeight: Math.ceil(el.scrollHeight),
            width: Math.ceil(rect.width),
            height: Math.ceil(rect.height),
          };
        }""",
        selector,
    )


def _viewport_for(dims: dict[str, int], *, min_w: int = 1600, min_h: int = 700) -> dict[str, int]:
    return {
        "width": max(dims["scrollWidth"], dims["width"], min_w) + 48,
        "height": max(dims["scrollHeight"], dims["height"], min_h) + 48,
    }


def _screenshot_element(
    page,
    selector: str,
    output: Path,
    *,
    min_h: int = 700,
) -> dict[str, int]:
    dims = _measure(page, selector)
    viewport = _viewport_for(dims, min_h=min_h)
    page.set_viewport_size(viewport)
    page.wait_for_timeout(300)
    page.locator(selector).screenshot(path=str(output), type="png")
    return viewport


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "Playwright is required. Install with:\n"
            "  pip install playwright\n"
            "  playwright install chromium",
            file=sys.stderr,
        )
        return 1

    if not HTML.is_file():
        print(f"Missing HTML: {HTML}", file=sys.stderr)
        return 1

    OUTPUT_COMPACT.parent.mkdir(parents=True, exist_ok=True)
    url = HTML.resolve().as_uri()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(device_scale_factor=2)
        page.set_viewport_size({"width": 2100, "height": 1200})
        page.goto(url, wait_until="networkidle")
        page.add_style_tag(content=EXPORT_CSS)
        page.wait_for_timeout(1200)

        compact_vp = _screenshot_element(page, "#architecture-export", OUTPUT_COMPACT)
        full_vp = _screenshot_element(
            page,
            "#report-container",
            OUTPUT_FULL,
            min_h=1100,
        )
        browser.close()

    print(f"Wrote {OUTPUT_COMPACT}")
    print(f"  target: #architecture-export (README compact)")
    print(f"  viewport: {compact_vp['width']}x{compact_vp['height']} (device scale 2x)")
    print(f"Wrote {OUTPUT_FULL}")
    print(f"  target: #report-container (full page with cards)")
    print(f"  viewport: {full_vp['width']}x{full_vp['height']} (device scale 2x)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
