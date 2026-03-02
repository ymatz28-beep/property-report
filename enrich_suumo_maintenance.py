#!/usr/bin/env python3
"""SUUMO物件の管理費+修繕積立金+ペット情報を詳細ページから取得し、rawデータを12列化する。"""

import re
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DATA_DIR = Path("data")
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}


def _parse_suumo_yen(text: str) -> int:
    """SUUMO形式の金額をパース。例: '1万5600円', '8,500円', '1万円'"""
    text = text.replace(",", "").replace("，", "")
    m = re.search(r"(\d+)万(\d+)?円", text)
    if m:
        man = int(m.group(1))
        rest = int(m.group(2)) if m.group(2) else 0
        return man * 10000 + rest
    m2 = re.search(r"(\d+)円", text)
    if m2:
        return int(m2.group(1))
    return 0


def _fetch_suumo_html(url: str) -> str:
    """SUUMOの物件詳細ページHTMLを取得。"""
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError) as e:
        print(f"    Fetch error: {e}")
        return ""


def fetch_maintenance_from_html(html: str) -> int:
    """HTMLから管理費+修繕積立金の合計を取得。"""
    if not html:
        return 0
    total = 0
    m_kanri = re.search(r"管理費.*?<td[^>]*>(.*?)</td>", html, re.DOTALL)
    if m_kanri:
        total += _parse_suumo_yen(m_kanri.group(1))
    m_shuzen = re.search(r"修繕積立金.*?<td[^>]*>(.*?)</td>", html, re.DOTALL)
    if m_shuzen:
        total += _parse_suumo_yen(m_shuzen.group(1))
    return total


def fetch_pet_status_from_html(html: str) -> str:
    """HTMLからペット可否を判定。返り値: '可', '相談可', '不可', '' (不明)"""
    if not html:
        return ""
    # ペット不可を先にチェック（「ペット可」の誤マッチ防止）
    if re.search(r"ペット不可", html):
        return "不可"
    # 「ペット相談」「ペット相談可」
    if re.search(r"ペット相談", html):
        return "相談可"
    # 「ペット可」「ペット飼育可」
    if re.search(r"ペット(飼育)?可", html):
        return "可"
    return ""


def fetch_maintenance_from_suumo(url: str) -> int:
    """後方互換: URLから管理費を取得。"""
    html = _fetch_suumo_html(url)
    return fetch_maintenance_from_html(html)


def enrich_file(filepath: Path) -> int:
    """rawデータファイルを読み、SUUMO URLがある行の管理費を取得して12列化。"""
    lines = filepath.read_text(encoding="utf-8").splitlines()
    updated_lines: list[str] = []
    enriched = 0
    total_data = 0

    for line in lines:
        # Skip headers/comments/empty
        if not line.strip() or line.startswith("#") or line.startswith("##"):
            updated_lines.append(line)
            continue

        parts = line.split("|")

        # Already 12 columns with maintenance data
        if len(parts) == 12 and parts[10].strip():
            updated_lines.append(line)
            total_data += 1
            continue

        # 8-column SUUMO format: name|price|location|area|built|station|layout|url
        if len(parts) == 8:
            url = parts[7].strip()
            total_data += 1
            if "suumo.jp" in url:
                print(f"  Fetching: {parts[0][:20]}...")
                html = _fetch_suumo_html(url)
                maint = fetch_maintenance_from_html(html)
                pet = fetch_pet_status_from_html(html)
                maint_str = str(maint) if maint > 0 else ""
                # Convert to 12-col: source|name|price|location|area|built|station|layout|pet|brokerage|maintenance|url
                new_line = f"SUUMO|{parts[0]}|{parts[1]}|{parts[2]}|{parts[3]}|{parts[4]}|{parts[5]}|{parts[6]}|{pet}||{maint_str}|{url}"
                updated_lines.append(new_line)
                if maint > 0 or pet:
                    enriched += 1
                info_parts = []
                if maint > 0:
                    info_parts.append(f"管理費{maint:,}円/月")
                if pet:
                    info_parts.append(f"ペット{pet}")
                print(f"    → {' / '.join(info_parts) if info_parts else 'データなし'}")
                time.sleep(1.5)  # Rate limiting
            else:
                updated_lines.append(line)
        # 12-column but missing pet info — re-enrich pet only
        elif len(parts) == 12 and not parts[8].strip():
            url = parts[11].strip()
            total_data += 1
            if "suumo.jp" in url:
                print(f"  Re-enriching pet: {parts[1][:20]}...")
                html = _fetch_suumo_html(url)
                pet = fetch_pet_status_from_html(html)
                parts[8] = pet
                updated_lines.append("|".join(parts))
                if pet:
                    enriched += 1
                    print(f"    → ペット{pet}")
                else:
                    print(f"    → ペット情報なし")
                time.sleep(1.5)
            else:
                updated_lines.append(line)
        else:
            updated_lines.append(line)
            total_data += 1

    filepath.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
    return enriched


def main():
    targets = [
        DATA_DIR / "suumo_osaka_v2_raw.txt",
        DATA_DIR / "suumo_fukuoka_raw.txt",
    ]
    for filepath in targets:
        if not filepath.exists():
            print(f"Skip: {filepath} (not found)")
            continue
        print(f"\n=== Enriching {filepath.name} ===")
        count = enrich_file(filepath)
        print(f"  Enriched: {count} properties")


if __name__ == "__main__":
    main()
