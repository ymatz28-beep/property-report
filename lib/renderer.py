"""Jinja2 rendering engine for iUMA dashboards.

Usage:
    from lib.renderer import render

    html = render("pages/stock_report.html", {
        "title": "Portfolio Report",
        "stocks": [...],
    })
"""

from __future__ import annotations

import json
import locale
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from lib.styles.design_tokens import get_base_css, get_css_tokens, get_google_fonts_url

TEMPLATE_DIR = Path(__file__).parent / "templates"

# ---------------------------------------------------------------------------
# Navigation SSoT — all gnav links are defined here, nowhere else
# ---------------------------------------------------------------------------
PUBLIC_NAV = [
    {"href": "https://ymatz28-beep.github.io/report-dashboard/", "label": "Hub", "primary": True},
    {"href": "https://ymatz28-beep.github.io/property-report/", "label": "Property", "primary": True},
    {"href": "https://ymatz28-beep.github.io/trip-planner/", "label": "Travel", "primary": True},
]

PRIVATE_NAV = [
    # Primary: always visible in gnav bar
    {"href": "/stock/portfolio.html", "label": "Stock", "primary": True},
    {"href": "/stock/market-intel.html", "label": "Market Intel", "primary": True},
    {"href": "/cisco/", "label": "Cisco", "primary": True},
    {"href": "/action/", "label": "Action", "primary": True},
    {"href": "https://ymatz28-beep.github.io/property-report/", "label": "Property", "primary": True},
    # Overflow: visible in "⋯" dropdown
    {"href": "/wealth/dashboard.html", "label": "Wealth"},
    {"href": "/intel/", "label": "Insight"},
    {"href": "/health/", "label": "Health"},
    {"href": "/health/medical/", "label": "Medical"},
    {"href": "https://ymatz28-beep.github.io/trip-planner/", "label": "Travel"},
    {"href": "/newsletter/", "label": "Newsletter"},
    {"href": "/bookmarks/", "label": "Bookmarks"},
    {"href": "/sns/", "label": "SNS"},
    {"href": "https://ymatz28-beep.github.io/self-insight/", "label": "Self-Insight"},
]

# ---------------------------------------------------------------------------
# Custom filters
# ---------------------------------------------------------------------------

def _format_number(value: float | int | None, decimals: int = 0) -> str:
    """Format a number with comma separators."""
    if value is None:
        return "N/A"
    if decimals == 0:
        return f"{value:,.0f}"
    return f"{value:,.{decimals}f}"


def _format_currency(value: float | int | None, symbol: str = "\\u00a5", decimals: int = 0) -> str:
    """Format a currency value: \\u00a5123,456 or $1,234.56."""
    if value is None:
        return "N/A"
    formatted = _format_number(abs(value), decimals)
    sign = "+" if value > 0 else ("-" if value < 0 else "")
    return f"{sign}{symbol}{formatted}"


def _format_percent(value: float | None, decimals: int = 1, signed: bool = False) -> str:
    """Format a percentage: +12.3% or 12.3%."""
    if value is None:
        return "N/A"
    if signed:
        return f"{value:+.{decimals}f}%"
    return f"{value:.{decimals}f}%"


def _format_date(value: str | datetime | None, fmt: str = "%Y-%m-%d") -> str:
    """Format a date string or datetime object."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return value.strftime(fmt)


def _pnl_class(value: float | int | None) -> str:
    """Return CSS class based on positive/negative value."""
    if value is None:
        return ""
    return "pnl-positive" if value >= 0 else "pnl-negative"


def _json_safe(value: Any) -> str:
    """Serialize a value to JSON for embedding in templates."""
    return json.dumps(value, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Nav HTML generator — use this instead of hardcoding nav in generators
# ---------------------------------------------------------------------------

_PRIVATE_DOMAIN = "https://iuma-private.pages.dev"


def get_nav_html(
    scope: str = "private",
    current_page: str = "",
    absolute: bool = False,
) -> str:
    """Generate canonical nav HTML from SSoT (Pattern B: primary + overflow).

    Args:
        scope: "private" or "public" — selects nav item list.
        current_page: Label or href of the active page (for aria-current).
        absolute: If True, convert relative hrefs to absolute iuma-private URLs.
                  Use for pages hosted outside iuma-private (e.g., GitHub Pages).
    """
    items = PRIVATE_NAV if scope == "private" else PUBLIC_NAV

    def _link(item: dict) -> str:
        href = item["href"]
        if absolute and href.startswith("/"):
            href = _PRIVATE_DOMAIN + href
        label = item["label"]
        aria = ' aria-current="page"' if label == current_page or href == current_page else ""
        return f'    <a href="{href}"{aria}>{label}</a>'

    primary = [_link(i) for i in items if i.get("primary")]
    overflow = [_link(i) for i in items if not i.get("primary")]

    primary_html = "\n".join(primary)
    overflow_html = ""
    if overflow:
        overflow_links = "\n".join(overflow)
        overflow_html = f"""
    <div class="nav-more">
      <button class="nav-more-btn" aria-label="More pages" onclick="this.parentElement.classList.toggle('open')">⋯</button>
      <div class="nav-more-menu">
{overflow_links}
      </div>
    </div>"""

    return f"""<header class="site-header">
  <input type="checkbox" id="nav-toggle" class="nav-toggle" aria-label="Toggle navigation">
  <label for="nav-toggle" class="nav-toggle-label"><span></span></label>
  <nav class="site-nav">
{primary_html}{overflow_html}
  </nav>
</header>"""


# ---------------------------------------------------------------------------
# Environment factory
# ---------------------------------------------------------------------------

def create_env(extra_dirs: list[Path] | None = None, scope: str = "public") -> Environment:
    """Create a Jinja2 Environment with the shared template directory.

    Args:
        extra_dirs: Additional template directories to search (prepended,
                    so project-local templates override shared ones).
        scope: "public" for GitHub Pages (no private links) or
               "private" for Cloudflare Pages (full nav).
    """
    search_paths = []
    if extra_dirs:
        search_paths.extend(str(d) for d in extra_dirs)
    search_paths.append(str(TEMPLATE_DIR))

    env = Environment(
        loader=FileSystemLoader(search_paths),
        autoescape=False,  # HTML output, we handle escaping manually
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # Register filters
    env.filters["format_number"] = _format_number
    env.filters["format_currency"] = _format_currency
    env.filters["format_percent"] = _format_percent
    env.filters["format_date"] = _format_date
    env.filters["pnl_class"] = _pnl_class
    env.filters["json_safe"] = _json_safe
    env.filters["tojson"] = lambda v: json.dumps(v, ensure_ascii=False)

    # Global variables available in all templates
    env.globals["css_tokens"] = get_css_tokens()
    env.globals["base_css"] = get_base_css()
    env.globals["google_fonts_url"] = get_google_fonts_url()
    env.globals["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Global navigation — public pages must never expose private URLs
    env.globals["nav_items"] = PRIVATE_NAV if scope == "private" else PUBLIC_NAV
    env.globals["site_brand"] = ""
    env.globals["current_page"] = ""

    return env


def render(template_name: str, data: dict, extra_dirs: list[Path] | None = None, scope: str = "public") -> str:
    """Render a template with the given data.

    Args:
        template_name: Template path relative to TEMPLATE_DIR (e.g., "pages/stock_report.html").
        data: Template context variables.
        extra_dirs: Additional template directories (project-local overrides).
        scope: "public" or "private" — controls which nav links appear.

    Returns:
        Rendered HTML string.
    """
    env = create_env(extra_dirs, scope=scope)
    template = env.get_template(template_name)
    return template.render(**data)
