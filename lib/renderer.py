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
    _public_nav = [
        {"href": "https://ymatz28-beep.github.io/report-dashboard/", "label": "Hub"},
        {"href": "https://ymatz28-beep.github.io/property-report/", "label": "Property"},
        {"href": "https://ymatz28-beep.github.io/trip-planner/", "label": "Travel"},
    ]
    # Private first (investment → ops), then Public (property → travel)
    _private_nav = [
        {"href": "https://iuma-private.pages.dev/stock/portfolio.html", "label": "Stock"},
        {"href": "https://iuma-private.pages.dev/stock/market-intel.html", "label": "Market Intel"},
        {"href": "https://iuma-private.pages.dev/intel/", "label": "Insight"},
        {"href": "https://iuma-private.pages.dev/wealth/dashboard.html", "label": "Wealth"},
        {"href": "https://iuma-private.pages.dev/action/", "label": "Action"},
        {"href": "https://iuma-private.pages.dev/health/", "label": "Health"},
        {"href": "https://ymatz28-beep.github.io/property-report/", "label": "Property"},
        {"href": "https://ymatz28-beep.github.io/trip-planner/", "label": "Travel"},
    ]
    env.globals["nav_items"] = _private_nav if scope == "private" else _public_nav
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
