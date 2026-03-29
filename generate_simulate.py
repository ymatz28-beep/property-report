"""Simulate page generator.

Generates a client-side interactive investment calculator.
No data processing needed — all calculation runs in JavaScript.
"""
from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
_LIB_PARENT = _PROJECT_ROOT.parent
for p in [str(_PROJECT_ROOT), str(_LIB_PARENT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from generate_market import PROPERTY_PAGES, GNAV_PAGES
from lib.renderer import create_env, PUBLIC_NAV
from lib.styles.design_tokens import get_base_css, get_css_tokens, get_google_fonts_url

OUTPUT_DIR = Path("output")


def main() -> Path:
    print("=== Generating Simulate page ===")

    env = create_env(
        extra_dirs=[_PROJECT_ROOT / "lib" / "templates"],
        scope="public",
    )

    template = env.get_template("pages/simulate.html")
    html = template.render(
        property_pages=PROPERTY_PAGES,
        property_current="Simulate",
        gnav_pages=GNAV_PAGES,
        gnav_current="",
        nav_items=PUBLIC_NAV,
        current_page="Property",
        css_tokens=get_css_tokens(),
        base_css=get_base_css(),
        google_fonts_url=get_google_fonts_url(),
    )

    out = OUTPUT_DIR / "simulate.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"Generated: {out} ({len(html) // 1024}KB)")
    return out


if __name__ == "__main__":
    main()
