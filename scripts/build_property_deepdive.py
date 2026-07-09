"""Generic engine for one-off property deep-dive reports.

Usage pattern (see scripts/deepdive_chiyozaki_osaka.py for a worked example):

    from build_property_deepdive import DeepdiveConfig, generate_deepdive

    config = DeepdiveConfig(slug="my-property", title="...", ...)
    generate_deepdive(config)

Renders through lib/renderer.py (pages/property_deepdive.html) — no bespoke
HTML/CSS. Copy the data script for the next property; the template stays fixed.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

PROJECTS_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECTS_ROOT))

from lib.renderer import render  # noqa: E402

PROJECT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_DIR / "output"
TEMPLATE_DIRS = [PROJECT_DIR / "lib" / "templates"]


@dataclass
class DeepdiveConfig:
    slug: str
    title: str
    subtitle: str
    property: dict
    flow_phases: list[dict]
    offer: dict
    renovation: dict
    pnl: dict
    financing: dict
    tax_risk: dict | None = None
    license: dict | None = None
    contractors: list[dict] = field(default_factory=list)
    platforms: list[dict] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)
    dd_sections: list[dict] = field(default_factory=list)


def generate_deepdive(config: DeepdiveConfig) -> Path:
    context = {
        "title": config.title,
        "subtitle": config.subtitle,
        "property": config.property,
        "flow_phases": config.flow_phases,
        "offer": config.offer,
        "renovation": config.renovation,
        "tax_risk": config.tax_risk,
        "license": config.license,
        "pnl": config.pnl,
        "financing": config.financing,
        "contractors": config.contractors,
        "platforms": config.platforms,
        "next_actions": config.next_actions,
        "sources": config.sources,
        "dd_sections": config.dd_sections,
        "current_page": config.title,
    }
    html = render("pages/property_deepdive.html", context, extra_dirs=TEMPLATE_DIRS, scope="private")
    out_path = OUTPUT_DIR / f"{config.slug}.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path


def open_report(path: Path) -> None:
    if sys.stdout.isatty():
        subprocess.run(["open", str(path)])
