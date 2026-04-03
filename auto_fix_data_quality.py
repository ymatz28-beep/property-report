"""Auto-fix data quality issues in raw property data files.

Runs after scraping and before generate_market.py.
Usage: .venv/bin/python auto_fix_data_quality.py [--dry-run] [--city fukuoka|osaka|tokyo]
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"

CITIES = ["fukuoka", "osaka", "tokyo"]

# Building name suffixes/prefixes that indicate a real property name
BUILDING_MARKERS = re.compile(
    r"マンション|ハイツ|プラザ|コート|パレス|ビル|メゾン|ロワール|ピュアドーム"
    r"|エステート|ライオンズ|グランフォーレ|ダイナコート|朝日プラザ|ステイツ"
    r"|ロマネスク|アンピール|スカイ|フォルム|サンシティ|シャトー|トピレック"
    r"|アクロス|クリオ|ネスト|レジデンス|ガーデン|タワー|ドーム|リファレンス"
)

# Ad-copy patterns (not a real building name)
ADCOPY_PATTERNS = re.compile(
    r"^[【▶「]|利回り|徒歩\d+分|！|■"
)


def _parse_line(line: str) -> dict | None:
    if not line or line.startswith("#") or line.startswith("##"):
        return None
    parts = line.split("|")
    if len(parts) < 12:
        return None
    return {
        "source": parts[0],
        "name": parts[1],
        "price": parts[2],
        "location": parts[3],
        "area": parts[4],
        "built": parts[5],
        "station": parts[6],
        "layout": parts[7],
        "pet": parts[8],
        "brokerage": parts[9],
        "maintenance": parts[10],
        "url": parts[11],
        "extra": parts[12:],
    }


def _rebuild_line(p: dict) -> str:
    base = [p["source"], p["name"], p["price"], p["location"], p["area"],
            p["built"], p["station"], p["layout"], p["pet"],
            p["brokerage"], p["maintenance"], p["url"]]
    base.extend(p.get("extra", []))
    return "|".join(base)


def _location_clean(location: str) -> str:
    loc = re.sub(r"^(東京都|大阪府|京都府|北海道|.{2,3}県)", "", location)
    return re.sub(r"[\s\u3000\d丁目番地号−\-]", "", loc)[:10]


def _area_int(area_text: str) -> int | None:
    m = re.search(r"[\d.]+", area_text)
    if not m:
        return None
    try:
        return int(float(m.group()))
    except ValueError:
        return None


def _backup_file(path: Path, backed_up: set) -> None:
    if path not in backed_up:
        shutil.copy2(path, path.with_suffix(".txt.bak"))
        backed_up.add(path)


def fix_yield_consistency(path: Path, dry_run: bool = False) -> int:
    """Fix OC properties where listed yield diverges >20% from annual_income/price."""
    lines = path.read_text(encoding="utf-8").splitlines()
    fixes = 0
    backed_up: set = set()

    for i, line in enumerate(lines):
        p = _parse_line(line)
        if not p:
            continue
        brok = p["brokerage"]
        yield_m = re.search(r"利回り([\d.]+)%", brok)
        income_m = re.search(r"年間収入([\d.]+)万円", brok)
        if not (yield_m and income_m):
            continue

        listed_yield = float(yield_m.group(1))
        annual_income = float(income_m.group(1))

        price_m = re.search(r"[\d.]+", p["price"])
        if not price_m:
            continue
        price_man = float(price_m.group())
        if price_man <= 0:
            continue

        correct_yield = annual_income / price_man * 100
        if correct_yield <= 0:
            continue
        divergence = abs(listed_yield - correct_yield) / correct_yield

        if divergence > 0.20:
            new_brok = re.sub(r"利回り[\d.]+%", f"利回り{correct_yield:.2f}%", brok)
            print(f"  [YIELD] {p['name'][:20]} | 利回り {listed_yield}% → {correct_yield:.2f}% (乖離{divergence:.0%})")
            if not dry_run:
                p["brokerage"] = new_brok
                lines[i] = _rebuild_line(p)
                fixes += 1

    if fixes > 30:
        print(f"  [ABORT] {path.name}: 修正件数{fixes}件が異常値(>30)。スキップ")
        return 0

    if fixes > 0 and not dry_run:
        _backup_file(path, backed_up)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return fixes if not dry_run else 0


def _is_building_name(name: str) -> bool:
    if ADCOPY_PATTERNS.search(name):
        return False
    if len(name) > 25:
        return False
    if BUILDING_MARKERS.search(name):
        return True
    return False


def _is_adcopy_name(name: str) -> bool:
    # Strip leading ad-copy wrappers: 【...】, ▶, 「...」, ■
    stripped = re.sub(r"^[■▶「\s]+", "", name)
    stripped = re.sub(r"^【[^】]*】\s*", "", stripped)
    stripped = re.sub(r"^[■▶「\s]+", "", stripped)  # second pass after bracket removal
    # If the stripped version has a building marker, it's a real name with ad prefix
    # → not ad-copy (fix the prefix instead of replacing the whole name)
    if BUILDING_MARKERS.search(stripped):
        return False
    if ADCOPY_PATTERNS.search(name):
        return True
    if len(name) > 25:
        return True
    if re.search(r"■|の[0-9A-Z]LDK物件|団地", name):
        return True
    return False


def fix_name_cross_reference(city: str, dry_run: bool = False) -> int:
    """Build name registry from all raw files, fix bad names in yield files."""
    registry: dict[tuple, str] = {}

    # Step 1: build registry from reliable source files
    source_globs = [
        f"ftakken_{city}_raw.txt",
        f"suumo_{city}_raw.txt",
        f"multi_site_{city}_raw.txt",
        f"ftakken_{city}_budget_raw.txt",
    ]
    for fname in source_globs:
        fpath = DATA_DIR / fname
        if not fpath.exists():
            continue
        for line in fpath.read_text(encoding="utf-8").splitlines():
            p = _parse_line(line)
            if not p:
                continue
            name = p["name"].strip()
            if not _is_building_name(name):
                continue
            loc_key = _location_clean(p["location"])
            area_key = _area_int(p["area"])
            if area_key is None:
                continue
            key = (loc_key, area_key)
            if key not in registry:
                registry[key] = name

    fixes = 0
    backed_up: set = set()
    yield_path = DATA_DIR / f"yield_{city}_raw.txt"
    if not yield_path.exists():
        return 0

    lines = yield_path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        p = _parse_line(line)
        if not p:
            continue
        name = p["name"]

        # Phase A: Strip ad-copy prefix from names that contain a real building name
        # e.g. "■■■【福岡 投資クリフ】■■■ロマネスク西公園第３" → "ロマネスク西公園第３"
        if ADCOPY_PATTERNS.search(name) or "■" in name:
            stripped = re.sub(r"^[■▶「\s]+", "", name)
            stripped = re.sub(r"^【[^】]*】\s*", "", stripped)
            stripped = re.sub(r"^[■▶「\s]+", "", stripped)
            stripped = re.sub(r"[■▶」\s]+$", "", stripped)
            if stripped != name and BUILDING_MARKERS.search(stripped) and len(stripped) <= 25:
                print(f"  [NAME-CLEAN] {name[:30]} → {stripped}")
                if not dry_run:
                    p["name"] = stripped
                    lines[i] = _rebuild_line(p)
                    fixes += 1
                continue

        # Phase B: Cross-reference replacement for full ad-copy names
        if not _is_adcopy_name(name):
            continue
        loc_key = _location_clean(p["location"])
        area_key = _area_int(p["area"])
        if area_key is None:
            continue
        key = (loc_key, area_key)
        if key in registry:
            new_name = registry[key]
            print(f"  [NAME] {name[:25]} → {new_name}")
            if not dry_run:
                p["name"] = new_name
                lines[i] = _rebuild_line(p)
                fixes += 1

    if fixes > 30:
        print(f"  [ABORT] yield_{city}_raw.txt: 名前修正{fixes}件が異常値(>30)。スキップ")
        return 0

    if fixes > 0 and not dry_run:
        _backup_file(yield_path, backed_up)
        yield_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return fixes if not dry_run else 0


def fix_sublease_mark(path: Path, dry_run: bool = False) -> int:
    """Mark indirect sublease indicators in pet field."""
    SUBLEASE_KEYWORDS = re.compile(r"サブリース|家賃保証|一括借上|借上げ|マスターリース")

    lines = path.read_text(encoding="utf-8").splitlines()
    fixes = 0
    backed_up: set = set()

    for i, line in enumerate(lines):
        p = _parse_line(line)
        if not p:
            continue
        if "サブリース" in p["pet"]:
            continue
        hit = bool(SUBLEASE_KEYWORDS.search(line))
        # Heuristic: メゾン・ド・ + 割安(≤500万) + 楽待 = 高確率サブリース
        if not hit and p["name"].startswith("メゾン・ド・"):
            price_m = re.search(r"[\d.]+", p["price"])
            if price_m and float(price_m.group()) <= 500 and "楽待" in p["source"]:
                hit = True
        if hit:
            print(f"  [SUBLEASE] {p['name'][:25]}: サブリース系キーワード検出")
            if not dry_run:
                p["pet"] = p["pet"].rstrip() + " サブリース"
                lines[i] = _rebuild_line(p)
                fixes += 1

    if fixes > 30:
        print(f"  [ABORT] {path.name}: サブリース修正{fixes}件が異常値(>30)。スキップ")
        return 0

    if fixes > 0 and not dry_run:
        _backup_file(path, backed_up)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return fixes if not dry_run else 0


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Auto-fix data quality in raw property files")
    parser.add_argument("--dry-run", action="store_true", help="Log changes without writing")
    parser.add_argument("--city", choices=CITIES, default=None)
    args = parser.parse_args()

    cities = [args.city] if args.city else CITIES
    total_yield = total_name = total_sublease = 0

    for city in cities:
        yield_path = DATA_DIR / f"yield_{city}_raw.txt"
        if not yield_path.exists():
            continue
        print(f"\n=== {city} ===")
        total_yield += fix_yield_consistency(yield_path, dry_run=args.dry_run)
        total_name += fix_name_cross_reference(city, dry_run=args.dry_run)
        total_sublease += fix_sublease_mark(yield_path, dry_run=args.dry_run)

    tag = " [DRY RUN]" if args.dry_run else ""
    print(f"\n[FIX]{tag} 利回り修正: {total_yield}件, 物件名修正: {total_name}件, サブリース: {total_sublease}件")


if __name__ == "__main__":
    main()
