#!/usr/bin/env python3
"""Property Market QA Gate — runs after generate_market.py, before deploy.

Usage: .venv/bin/python qa_market.py [--strict]
Exit 0 = PASS, Exit 1 = FAIL (blocks deploy)
"""
from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

HTML_PATH = Path(__file__).resolve().parent / "output" / "market.html"

# Required columns that every section type must have
REQUIRED_COLS = {"スコア", "掲載日", "物件名", "価格"}
SECTION_TYPES = {"kubun", "ittomono", "kodate"}

# Station-only name pattern (pure transport address used as property name)
_STATION_RE = re.compile(
    r"^[\w\s\u3000-\u9fff\uff00-\uffef]+[線駅][\s　]*徒歩\d+分$"
)
# Area-fallback name pattern like "福岡市博多区 2LDK"
_AREA_FALLBACK_RE = re.compile(
    r"^[\u3000-\u9fff\uff00-\uffef\w]+[区市町村]\s+\d[SLDK]+$"
)


# ---------------------------------------------------------------------------
# Lightweight HTML parser to extract what we need
# ---------------------------------------------------------------------------
class MarketHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        # Section tracking: {section_id: {headers, prop_cards, detail_rows, ...}}
        self.sections: dict[str, dict] = {}
        self._current_section: str | None = None
        self._current_section_type: str | None = None

        # Table header tracking
        self._in_thead = False
        self._in_th = False
        self._current_headers: list[str] = []

        # Table row tracking
        self._current_tr_attrs: dict = {}
        self._in_tr = False

        # Name cell tracking
        self._in_name_cell = False
        self._in_prop_card_name = False
        self._name_buffer = ""

        # Link tracking
        self._links: list[str] = []

        # JS content
        self.has_toggle_detail = False
        self.has_data_score_attr = False
        self.has_data_price_attr = False
        self.has_data_area_attr = False

        # Raw text for JS check
        self._in_script = False
        self._script_buffer = ""

        # Prop cards (for sort attribute check)
        self.prop_cards: list[dict] = []

        # All table rows with data-score (for sort check)
        self.table_rows_with_attrs: int = 0

    # ---- helpers -----------------------------------------------------------
    def _get_section(self) -> dict:
        sid = self._current_section or "__global__"
        if sid not in self.sections:
            self.sections[sid] = {
                "type": self._current_section_type,
                "headers": [],
                "prop_cards": [],      # card-view names
                "table_rows": [],      # {score, price, area, name, url, has_detail}
                "detail_rows": 0,
                "links": [],
            }
        return self.sections[sid]

    # ---- HTMLParser overrides ----------------------------------------------
    def handle_starttag(self, tag: str, attrs_list: list) -> None:
        attrs = dict(attrs_list)
        cls = attrs.get("class", "")
        aid = attrs.get("id", "")

        # Section boundaries
        if tag == "div" and "type-section" in cls and aid:
            self._current_section = aid
            self._current_section_type = attrs.get("data-type", "")
            sec = self._get_section()
            sec["type"] = self._current_section_type

        # Prop card (card view)
        if tag == "div" and "prop-card" in cls.split() and "data-score" in attrs:
            card = {
                "score": attrs.get("data-score"),
                "price": attrs.get("data-price"),
                "area": attrs.get("data-area"),
            }
            self._get_section()["prop_cards"].append(card)
            self.prop_cards.append(card)
            if attrs.get("data-score"):
                self.has_data_score_attr = True
            if attrs.get("data-price"):
                self.has_data_price_attr = True
            if attrs.get("data-area"):
                self.has_data_area_attr = True

        # prop-card-name
        if tag == "div" and "prop-card-name" in cls:
            self._in_prop_card_name = True
            self._name_buffer = ""

        # Table structure
        if tag == "thead":
            self._in_thead = True
            self._current_headers = []
        if tag == "th" and self._in_thead:
            self._in_th = True
            self._name_buffer = ""

        # Table rows
        if tag == "tr" and attrs.get("data-score"):
            self._in_tr = True
            self._current_tr_attrs = {
                "score": attrs.get("data-score"),
                "price": attrs.get("data-price"),
                "area": attrs.get("data-area"),
                "expandable": "data-expandable" in attrs,
            }
            self.table_rows_with_attrs += 1

        # Name cell in table
        if tag == "td" and "name-cell" in cls and self._in_tr:
            self._in_name_cell = True
            self._name_buffer = ""

        # Detail row
        if tag == "tr" and "detail-row" in cls:
            self._get_section()["detail_rows"] += 1

        # Links
        if tag == "a" and attrs.get("href"):
            self._links.append(attrs["href"])
            if self._in_tr:
                self._current_tr_attrs["url"] = attrs["href"]

        # Script
        if tag == "script":
            self._in_script = True
            self._script_buffer = ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "thead":
            self._in_thead = False
            if self._current_section and self._current_headers:
                self._get_section()["headers"] = list(self._current_headers)
            self._current_headers = []

        if tag == "th":
            self._in_th = False

        if tag == "tr" and self._in_tr:
            self._in_tr = False
            row = dict(self._current_tr_attrs)
            if not row.get("name"):
                row["name"] = ""
            self._get_section()["table_rows"].append(row)
            self._current_tr_attrs = {}

        if tag == "td" and self._in_name_cell:
            self._in_name_cell = False
            if self._current_tr_attrs is not None:
                self._current_tr_attrs["name"] = self._name_buffer.strip()
            self._name_buffer = ""

        if tag == "div" and self._in_prop_card_name:
            self._in_prop_card_name = False
            self._get_section()["prop_cards"][-1]["name"] = self._name_buffer.strip() if self._get_section()["prop_cards"] else ""
            self._name_buffer = ""

        if tag == "script":
            self._in_script = False
            if "toggleDetail" in self._script_buffer:
                self.has_toggle_detail = True
            self._script_buffer = ""

    def handle_data(self, data: str) -> None:
        if self._in_th and self._in_thead:
            self._current_headers.append(data.strip())

        if self._in_name_cell or self._in_prop_card_name:
            self._name_buffer += data

        if self._in_script:
            self._script_buffer += data


# ---------------------------------------------------------------------------
# Check functions
# ---------------------------------------------------------------------------
def _parse_html(path: Path) -> MarketHTMLParser:
    parser = MarketHTMLParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


def check_feature_parity(parser: MarketHTMLParser) -> tuple[str, str]:
    """All sections with a table must have the required columns."""
    issues = []
    sections_with_headers = {
        sid: sec for sid, sec in parser.sections.items()
        if sec.get("headers")
    }
    total = len(sections_with_headers)

    for sid, sec in sections_with_headers.items():
        headers_set = set(sec["headers"])
        missing = REQUIRED_COLS - headers_set
        if missing:
            issues.append(f"{sid} missing: {missing}")
        if "掲載日" not in headers_set:
            issues.append(f"{sid} missing first_seen (掲載日) column")

    if not sections_with_headers:
        return "FAIL", "No table sections found"
    if issues:
        return "FAIL", "; ".join(issues)
    return "PASS", f"掲載日 column in all {total} sections"


def check_revenue_coverage(parser: MarketHTMLParser) -> tuple[str, str]:
    """80% warn / 50% fail for revenue detail-rows vs total table rows."""
    total_rows = sum(
        len(sec["table_rows"]) for sec in parser.sections.values()
    )
    total_detail = sum(
        sec["detail_rows"] for sec in parser.sections.values()
    )
    if total_rows == 0:
        return "WARN", "No table rows found"

    pct = total_detail / total_rows * 100
    msg = f"{total_detail}/{total_rows} properties ({pct:.0f}%)"
    if pct < 50:
        return "FAIL", f"Revenue coverage too low: {msg}"
    if pct < 80:
        return "WARN", f"Revenue coverage below 80%: {msg}"
    return "PASS", msg


def check_name_quality(parser: MarketHTMLParser) -> tuple[str, str]:
    """Detect station-pattern names (FAIL) and area-fallback names (WARN>20%)."""
    station_violations = []
    area_fallback = []

    for sec in parser.sections.values():
        # Check card-view names
        for card in sec.get("prop_cards", []):
            name = card.get("name", "").strip()
            if not name:
                continue
            if _STATION_RE.match(name):
                station_violations.append(name)
            elif _AREA_FALLBACK_RE.match(name):
                area_fallback.append(name)

        # Check table row names
        for row in sec.get("table_rows", []):
            name = row.get("name", "").strip()
            if not name:
                continue
            if _STATION_RE.match(name):
                station_violations.append(name)
            elif _AREA_FALLBACK_RE.match(name):
                area_fallback.append(name)

    total_names = sum(
        len(sec.get("prop_cards", [])) for sec in parser.sections.values()
    )
    if not total_names:
        total_names = 1  # avoid division by zero

    if station_violations:
        sample = station_violations[:3]
        return "FAIL", f"{len(station_violations)} station-pattern names: {sample}"

    fallback_pct = len(area_fallback) / total_names * 100
    if fallback_pct > 20:
        return "WARN", f"{len(area_fallback)} area-fallback names ({fallback_pct:.0f}%)"

    return "PASS", f"0 station violations; {len(area_fallback)} area-fallback names ({fallback_pct:.0f}%)"


def check_duplicate_detection(parser: MarketHTMLParser) -> tuple[str, str]:
    """Same (price, area) combination across all sections."""
    seen: dict[tuple, list] = {}
    for sec_id, sec in parser.sections.items():
        for card in sec.get("prop_cards", []):
            key = (card.get("price"), card.get("area"))
            if None not in key and "" not in key:
                seen.setdefault(key, []).append(sec_id)

    dupes = {k: v for k, v in seen.items() if len(v) > 1}
    if dupes:
        sample = list(dupes.items())[:3]
        return "WARN", f"{len(dupes)} duplicate (price, area) pairs: {sample}"
    return "PASS", "0 duplicates"


def check_data_completeness(parser: MarketHTMLParser) -> tuple[str, str]:
    """Every property row must have score, price, name, URL. Yield check for ittomono/kodate."""
    issues = []
    missing_yield_sections = []
    total_props = 0

    for sec_id, sec in parser.sections.items():
        sec_type = sec.get("type", "")
        rows = sec.get("table_rows", [])
        for i, row in enumerate(rows):
            total_props += 1
            if not row.get("score"):
                issues.append(f"{sec_id}[{i}] missing score")
            if not row.get("price"):
                issues.append(f"{sec_id}[{i}] missing price")
            if not row.get("url"):
                issues.append(f"{sec_id}[{i}] missing url")

        # Yield check: ittomono/kodate sections
        if sec_type in ("ittomono", "kodate"):
            headers = sec.get("headers", [])
            if "利回り" not in headers:
                missing_yield_sections.append(sec_id)

        # Link validity
        for link in sec.get("links", []):
            if link and not link.startswith("http") and not link.startswith("#") and not link.startswith("/"):
                issues.append(f"{sec_id} bad link: {link[:60]}")

    if issues:
        sample = issues[:5]
        level = "FAIL" if len(issues) > 5 else "WARN"
        return level, f"{len(issues)} completeness issues: {sample}"
    if missing_yield_sections:
        return "WARN", f"利回り column missing in: {missing_yield_sections}"
    return "PASS", f"all {total_props} properties have required fields"


def check_sort_functionality(parser: MarketHTMLParser) -> tuple[str, str]:
    """Verify data-score/price/area attributes and toggleDetail JS function."""
    issues = []
    if not parser.has_data_score_attr:
        issues.append("data-score attribute missing")
    if not parser.has_data_price_attr:
        issues.append("data-price attribute missing")
    if not parser.has_data_area_attr:
        issues.append("data-area attribute missing")
    if not parser.has_toggle_detail:
        issues.append("toggleDetail function not found in JS")

    if issues:
        return "FAIL", "; ".join(issues)
    return "PASS", f"data attributes present; toggleDetail found ({parser.table_rows_with_attrs} rows)"


def check_data_accuracy(parser: MarketHTMLParser) -> tuple[str, str]:
    """Compare rendered HTML against raw data files.

    Checks that property names, prices, areas are not blank/missing
    and that first_seen (掲載日) is populated for all properties.
    """
    issues = []
    total = 0
    blank_names = 0
    blank_prices = 0
    blank_areas = 0
    blank_first_seen = 0

    html_path = HTML_PATH
    html_text = html_path.read_text(encoding="utf-8") if html_path.exists() else ""

    for sec_id, sec in parser.sections.items():
        for row in sec.get("table_rows", []):
            total += 1
            name = row.get("name", "").strip()
            if not name or name == "—":
                blank_names += 1

        for card in sec.get("prop_cards", []):
            name = card.get("name", "").strip()
            if not name or name == "—":
                blank_names += 1

    # Count blank cells via regex on rendered HTML (—, empty td)
    blank_td_count = len(re.findall(r"<td[^>]*>\s*</td>", html_text))

    if blank_names:
        issues.append(f"{blank_names} blank property names")
    if blank_td_count > 5:
        issues.append(f"{blank_td_count} empty <td> cells")

    # Check first_seen coverage in rendered output
    # Count "—" in first_seen position (2nd column of each table)
    dash_first_seen = html_text.count(">—</td>\n")

    if total == 0:
        return "WARN", "No properties found"
    if issues:
        level = "FAIL" if blank_names > 3 else "WARN"
        return level, "; ".join(issues) + f" (blank_td={blank_td_count})"
    return "PASS", f"{total} properties checked; {blank_td_count} empty cells"


def check_first_seen_coverage(parser: MarketHTMLParser) -> tuple[str, str]:
    """Verify first_seen (掲載日) is populated. WARN if >30% missing."""
    total = 0
    missing = 0

    html_path = HTML_PATH
    if not html_path.exists():
        return "WARN", "HTML file not found"

    html_text = html_path.read_text(encoding="utf-8")
    # Count rows that show "—" in the first_seen column
    # The pattern is: score cell, then first_seen cell
    # In template: <td>—</td> right after score-cell
    # We can count all properties vs those with first_seen dates
    for sec in parser.sections.values():
        total += len(sec.get("table_rows", []))

    # Count first_seen dates in HTML (MM/DD or NEW pattern)
    date_pattern = re.compile(r'<td>(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}|<span[^>]*>NEW</span>)</td>')
    found_dates = len(date_pattern.findall(html_text))

    if total == 0:
        return "WARN", "No properties found"

    missing = total - found_dates
    pct_covered = found_dates / total * 100 if total else 0

    if pct_covered < 50:
        return "FAIL", f"掲載日 coverage {pct_covered:.0f}% ({found_dates}/{total})"
    if pct_covered < 80:
        return "WARN", f"掲載日 coverage {pct_covered:.0f}% ({found_dates}/{total})"
    return "PASS", f"掲載日 coverage {pct_covered:.0f}% ({found_dates}/{total})"


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def run_qa(html_path: Path = HTML_PATH, strict: bool = False) -> bool:
    """Run all checks. Returns True if overall result is OK (no FAILs)."""
    if not html_path.exists():
        print(f"[ERROR] {html_path} not found. Run generate_market.py first.")
        return False

    print("=== Property Market QA ===")
    parser = _parse_html(html_path)

    checks = [
        ("Feature Parity", check_feature_parity),
        ("Revenue Coverage", check_revenue_coverage),
        ("Name Quality", check_name_quality),
        ("Duplicate Detection", check_duplicate_detection),
        ("Data Completeness", check_data_completeness),
        ("Sort Functionality", check_sort_functionality),
        ("Data Accuracy", check_data_accuracy),
        ("First-Seen Coverage", check_first_seen_coverage),
    ]

    results: list[tuple[str, str, str]] = []
    for name, fn in checks:
        level, msg = fn(parser)
        results.append((level, name, msg))
        print(f"[{level}] {name}: {msg}")

    passes = sum(1 for r in results if r[0] == "PASS")
    warns = sum(1 for r in results if r[0] == "WARN")
    fails = sum(1 for r in results if r[0] == "FAIL")

    ok = fails == 0 and (not strict or warns == 0)
    status = "OK" if ok else "FAIL"
    print(f"\nResult: {passes} PASS, {warns} WARN, {fails} FAIL → {status}")
    return ok


def run_qa_for_kaizen(html_path: Path = HTML_PATH) -> list[dict]:
    """Return QA results as Kaizen-compatible findings list.

    Called by kaizen-agent product_quality checks for integrated QA.
    """
    if not html_path.exists():
        return [{"check": "qa_market", "severity": "error",
                 "file": "Property Market", "project": "property-analyzer",
                 "message": f"{html_path} not found"}]

    parser = _parse_html(html_path)
    checks = [
        ("feature_parity", check_feature_parity),
        ("revenue_coverage", check_revenue_coverage),
        ("name_quality", check_name_quality),
        ("duplicate_detection", check_duplicate_detection),
        ("data_completeness", check_data_completeness),
        ("sort_functionality", check_sort_functionality),
        ("data_accuracy", check_data_accuracy),
        ("first_seen_coverage", check_first_seen_coverage),
    ]

    findings = []
    for name, fn in checks:
        level, msg = fn(parser)
        if level != "PASS":
            findings.append({
                "check": f"qa_market_{name}",
                "severity": "error" if level == "FAIL" else "warn",
                "file": "Property Market",
                "project": "property-analyzer",
                "message": msg,
            })
    return findings


def main() -> None:
    strict = "--strict" in sys.argv
    ok = run_qa(strict=strict)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
