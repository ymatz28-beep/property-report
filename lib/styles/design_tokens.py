"""Unified design tokens for all iUMA dashboards.

Consolidated from:
- iuma-hub.html (master reference — Cormorant Garamond, gold accent)
- stock-analyzer/report.html (Inter + Noto Sans JP, purple accent)
- property-analyzer (Inter + Noto Sans JP, blue accent)
- kaizen-agent/action_tracker.py (system fonts, minimal dark)

The unified palette keeps stock-analyzer's practical dark scheme as the base
(it covers the most surface types), enhanced with iuma-hub's gold accent for
branding elements.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Token dictionary — single source of truth
# ---------------------------------------------------------------------------

TOKENS: dict[str, str] = {
    # Backgrounds
    "bg": "#0f1117",
    "surface": "#1a1d27",
    "surface2": "#242836",
    "card": "#1a1d27",
    "card-hover": "#242836",

    # Borders
    "border": "#2d3348",
    "border-light": "#3d4460",

    # Brand
    "gold": "#c9a84c",
    "gold-dim": "rgba(201,168,76,0.12)",

    # Accents
    "accent": "#6366f1",
    "accent2": "#8b5cf6",
    "blue": "#3b82f6",
    "purple": "#6366f1",
    "orange": "#ff6b35",
    "green": "#22c55e",
    "green-light": "#4ade80",
    "red": "#ef4444",
    "red-light": "#f87171",
    "yellow": "#eab308",

    # Text
    "text": "#e4e4e7",
    "text-secondary": "#9ca3af",
    "text-muted": "#7c8293",
    "text-decorative": "#5f6678",

    # Typography
    "font-display": "'Inter', 'Noto Sans JP', sans-serif",
    "font-body": "'Inter', 'Noto Sans JP', sans-serif",
    "font-mono": "'JetBrains Mono', monospace",

    # Spacing scale (4px base)
    "space-1": "4px",
    "space-2": "8px",
    "space-3": "12px",
    "space-4": "16px",
    "space-5": "20px",
    "space-6": "24px",
    "space-8": "32px",
    "space-10": "40px",
    "space-12": "48px",
    "space-16": "64px",

    # Border radius
    "radius-sm": "6px",
    "radius-md": "10px",
    "radius-lg": "14px",
    "radius-xl": "16px",

    # Breakpoints (as reference values — not usable in :root but documented)
    "bp-mobile": "640px",
    "bp-tablet": "768px",
    "bp-desktop": "1200px",

    # Shadows
    "shadow-card": "0 4px 16px rgba(0,0,0,0.2)",
    "shadow-hover": "0 8px 32px rgba(0,0,0,0.3)",

    # Layout
    "gnav-height": "52px",

    # Z-index scale
    "z-nav": "100",
    "z-subnav": "90",
    "z-modal": "200",
    "z-toast": "300",

    # Fluid typography (clamp-based)
    "fs-display": "clamp(22px, 4vw, 36px)",
    "fs-h1": "clamp(20px, 2.5vw, 26px)",
    "fs-h2": "clamp(16px, 2vw, 22px)",
    "fs-h3": "clamp(14px, 1.8vw, 18px)",
    "fs-body": "14px",
    "fs-small": "12px",
    "fs-xs": "10px",
}


# ---------------------------------------------------------------------------
# CSS generator
# ---------------------------------------------------------------------------

def get_css_tokens() -> str:
    """Return the full :root CSS block with all design tokens.

    Returns a string like:
        :root {
          --bg: #0f1117;
          --surface: #1a1d27;
          ...
        }
    """
    lines = [":root {"]
    for key, value in TOKENS.items():
        lines.append(f"  --{key}: {value};")
    lines.append("}")
    return "\n".join(lines)


def get_google_fonts_url() -> str:
    """Return the Google Fonts URL for all required font families."""
    return (
        "https://fonts.googleapis.com/css2?"
        "family=Inter:wght@400;500;600;700"
        "&family=JetBrains+Mono:wght@400;500;600"
        "&family=Noto+Sans+JP:wght@300;400;500;600;700"
        "&display=swap"
    )


def get_base_css() -> str:
    """Return base CSS reset + responsive utilities used across all pages.

    This is injected into base.html alongside the tokens.
    """
    return """
/* === Reset === */
*, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
html { font-size: 16px; scroll-behavior: smooth; scroll-padding-top: calc(var(--gnav-height, 52px) + 60px); }
body {
  font-family: var(--font-body);
  background: var(--bg);
  color: var(--text);
  line-height: 1.6;
  min-height: 100vh;
}

/* === Utilities === */
.container { max-width: 1100px; margin: 0 auto; padding: 24px; }
.container-narrow { max-width: 720px; margin: 0 auto; padding: 24px; }
.container-wide { max-width: 1280px; margin: 0 auto; padding: 24px; }
.hide-mobile { }  /* overridden at 640px */
.show-mobile { display: none; }
.pnl-positive { color: var(--green); }
.pnl-negative { color: var(--red); }

/* === Fluid Typography === */
.text-display { font-size: var(--fs-display); font-weight: 700; font-family: var(--font-display); line-height: 1.1; }
.text-h1 { font-size: var(--fs-h1); font-weight: 700; line-height: 1.2; }
.text-h2 { font-size: var(--fs-h2); font-weight: 700; line-height: 1.3; }
.text-h3 { font-size: var(--fs-h3); font-weight: 600; line-height: 1.4; }
.text-body { font-size: var(--fs-body); }
.text-small { font-size: var(--fs-small); }
.text-xs { font-size: var(--fs-xs); }
.text-mono { font-family: var(--font-mono); }

/* === Stat Grid (responsive auto-fit) === */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: var(--space-4);
}

/* === Section Spacing === */
.section { padding: var(--space-8) 0; }
.section + .section { border-top: 1px solid var(--border); }

/* === Responsive grid === */
.responsive-grid { display: grid; gap: 16px; }
.responsive-grid.cols-2 { grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); }
.responsive-grid.cols-3 { grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }

/* === Table Scroll Indicator === */
.table-scroll-wrap {
  position: relative;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}
.table-scroll-wrap::after {
  content: '→ scroll';
  position: absolute;
  right: 8px;
  top: 8px;
  font-size: 9px;
  color: var(--text-muted);
  background: var(--surface);
  padding: 2px 6px;
  border-radius: 4px;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.3s;
}
.table-scroll-wrap.has-scroll::after { opacity: 1; }

/* === Animations === */
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}

/* ===== Tablet (768px) ===== */
@media (max-width: 768px) {
  .responsive-grid.cols-2,
  .responsive-grid.cols-3 { grid-template-columns: 1fr; }
}

/* ===== Mobile (640px) ===== */
@media (max-width: 640px) {
  .container { padding: 12px; }
  .hide-mobile { display: none; }
  .show-mobile { display: block; }
  .stat-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: var(--space-2);
  }
  .section { padding: var(--space-4) 0; }
}

/* ===== Extra small (380px) ===== */
@media (max-width: 380px) {
  .container { padding: 8px; }
  .stat-grid { grid-template-columns: 1fr; }
}
"""
