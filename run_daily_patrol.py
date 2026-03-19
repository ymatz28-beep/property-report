#!/usr/bin/env python3
"""
毎朝の物件巡回パトロールスクリプト
- 全サイト×全都市で物件検索
- 既存URLの生死チェック（掲載終了検出）
- レポート再生成 + gh-pagesデプロイ
- 差分サマリー通知

cron設定例:
  0 6 * * * cd ~/Documents/Projects/property-analyzer && python3 run_daily_patrol.py >> data/patrol.log 2>&1
"""

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
STATUS_FILE = DATA_DIR / "property_status.json"
FIRST_SEEN_FILE = DATA_DIR / "first_seen.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run_script(name: str, args: list[str] | None = None, timeout: int = 180) -> bool:
    """Run a Python script and return success status."""
    cmd = [sys.executable, name] + (args or [])
    log(f"  Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(BASE_DIR))
        if result.returncode != 0:
            log(f"  [WARN] {name} exited with code {result.returncode}")
            if result.stderr:
                log(f"  stderr: {result.stderr[:200]}")
        else:
            # Print last few lines of stdout
            lines = result.stdout.strip().split("\n")
            for line in lines[-5:]:
                log(f"  {line}")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        log(f"  [WARN] {name} timed out")
        return False
    except Exception as e:
        log(f"  [ERROR] {name}: {e}")
        return False


def check_url_alive(url: str) -> tuple[bool, int]:
    """Check if a URL is still live. Returns (alive, status_code)."""
    from urllib.parse import quote, urlparse, urlunparse
    try:
        # Percent-encode non-ASCII characters in all URL components
        parsed = urlparse(url)
        safe_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            quote(parsed.path, safe="/:@!$&'()*+,;=-._~"),
            quote(parsed.params, safe="/:@!$&'()*+,;=-._~"),
            quote(parsed.query, safe="/:@!$&'()*+,;=-._~="),
            quote(parsed.fragment, safe=""),
        ))
        req = Request(safe_url, headers=HEADERS, method="HEAD")
        with urlopen(req, timeout=10) as resp:
            return True, resp.status
    except HTTPError as e:
        return e.code not in (404, 410, 403), e.code
    except (URLError, TimeoutError, UnicodeEncodeError, ConnectionResetError, OSError):
        return True, 0  # Network/encoding error = assume still alive


def patrol_dead_urls() -> dict:
    """Check all property URLs in raw data files for dead links."""
    log("=== URLチェック開始 ===")
    raw_files = list(DATA_DIR.glob("*_raw.txt"))
    all_urls: set[str] = set()

    for f in raw_files:
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            # URL is the last field
            if parts:
                url = parts[-1].strip()
                if url.startswith("http"):
                    all_urls.add(url)

    log(f"  合計 {len(all_urls)} URLs をチェック")

    # Load existing status
    status_data = {"properties": {}, "last_check": ""}
    if STATUS_FILE.exists():
        try:
            status_data = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Skip URLs already marked SOLD (persist across CI runs)
    known_sold = {
        u for u, info in status_data.get("properties", {}).items()
        if info.get("status") == "SOLD"
    }
    urls_to_check = sorted(all_urls - known_sold)
    log(f"  スキップ: {len(known_sold)} (既にSOLD), チェック対象: {len(urls_to_check)}")

    dead_urls: list[str] = []
    new_dead: list[str] = []
    checked = 0

    for url in urls_to_check:
        alive, code = check_url_alive(url)
        checked += 1

        if not alive:
            dead_urls.append(url)
            new_dead.append(url)
            status_data.setdefault("properties", {})[url] = {
                "status": "SOLD",
                "detected": datetime.now().isoformat(),
                "http_code": code,
            }
            log(f"  ❌ DEAD ({code}): {url[:80]}")

        if checked % 20 == 0:
            log(f"  ... {checked}/{len(urls_to_check)} checked")
        time.sleep(0.3)  # Rate limiting

    status_data["last_check"] = datetime.now().isoformat()
    STATUS_FILE.write_text(json.dumps(status_data, ensure_ascii=False, indent=2), encoding="utf-8")

    log(f"  完了: {len(dead_urls)} dead / {len(all_urls)} total ({len(new_dead)} new)")
    return {"total": len(all_urls), "dead": len(dead_urls), "new_dead": len(new_dead)}


def parse_raw_files() -> dict[str, dict]:
    """Parse all raw files. Returns {url: {name, price, location, source}}."""
    properties = {}
    for f in DATA_DIR.glob("*_raw.txt"):
        source = f.stem.replace("_raw", "")
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) >= 4:
                url = parts[-1].strip()
                if url.startswith("http"):
                    properties[url] = {
                        "name": parts[1].strip() if len(parts) > 1 else "",
                        "price": parts[2].strip() if len(parts) > 2 else "",
                        "location": parts[3].strip() if len(parts) > 3 else "",
                        "source": source,
                    }
    return properties


def update_first_seen() -> None:
    """Update first_seen.json with any new property URLs from raw data files."""
    today = datetime.now().strftime("%Y-%m-%d")

    # Load existing registry
    registry: dict[str, str] = {}
    if FIRST_SEEN_FILE.exists():
        try:
            registry = json.loads(FIRST_SEEN_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Collect all current URLs from raw files
    new_count = 0
    for f in DATA_DIR.glob("*_raw.txt"):
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            if parts:
                url = parts[-1].strip()
                if url.startswith("http") and url not in registry:
                    registry[url] = today
                    new_count += 1

    FIRST_SEEN_FILE.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log(f"  first_seen.json 更新: {new_count}件追加 (合計{len(registry)}件)")


def diff_properties(before: dict, after: dict) -> dict:
    """Compare before/after snapshots. Returns diff summary."""
    before_urls = set(before.keys())
    after_urls = set(after.keys())
    new_urls = after_urls - before_urls
    removed_urls = before_urls - after_urls

    new_props = [after[u] for u in sorted(new_urls)]
    removed_props = [before[u] for u in sorted(removed_urls)]

    return {
        "new": new_props,
        "removed": removed_props,
        "before_count": len(before_urls),
        "after_count": len(after_urls),
    }


def search_all_sites() -> None:
    """Run all property searches."""
    log("=== 物件検索開始 ===")

    # SUUMO (main source — includes inline management fee enrichment)
    run_script("search_suumo.py", timeout=600)

    # Standard HTTP scrapers (rakumachi, yahoo, athome, cowcamo)
    run_script("search_multi_site.py")

    # R不動産 (BeautifulSoup)
    run_script("search_restate.py")

    # Playwright-based scrapers
    run_script("search_ftakken.py")
    run_script("search_lifull.py", timeout=120)

    # Enrich maintenance fees from detail pages (for non-SUUMO sources)
    log("=== 管理費enrichment ===")
    run_script("enrich_maintenance.py")


def generate_reports() -> None:
    """Generate all city reports."""
    log("=== レポート生成 ===")
    for script in ["generate_osaka_report.py", "generate_fukuoka_report.py", "generate_tokyo_report.py"]:
        run_script(script)
    run_script("generate_inquiry_messages.py")


def deploy() -> None:
    """Deploy to gh-pages."""
    log("=== デプロイ ===")
    from check_property_status import deploy_to_gh_pages
    result = deploy_to_gh_pages()
    if result:
        log("  GitHub Pagesデプロイ完了")
    else:
        log("  デプロイ不要（変更なし）またはエラー")


def save_patrol_summary(start: datetime, elapsed: float, diff: dict, url_report: dict) -> None:
    """Save patrol summary as JSON (structured data for Daily Digest)."""
    new = diff["new"]
    removed = diff["removed"]
    dead_count = url_report.get("new_dead", 0) + len(removed)

    summary = {
        "date": start.strftime("%Y-%m-%d"),
        "total": diff["after_count"],
        "prev_total": diff["before_count"],
        "new_count": len(new),
        "removed_count": dead_count,
        "elapsed_min": round(elapsed / 60),
        "new_items": [
            {"name": p["name"], "price_text": p["price"],
             "price_man": int(p["price"].replace("万円", "").replace(",", "")),
             "source": p["source"]}
            for p in new
        ],
        "report_url": "https://ymatz28-beep.github.io/property-report/",
    }

    summary_file = BASE_DIR / "data" / "patrol_summary.json"
    summary_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"  patrol_summary.json 保存 (total={summary['total']}, +{summary['new_count']}/-{summary['removed_count']})")


def send_line_if_new(diff: dict) -> None:
    """Send LINE push notification only when new properties are found."""
    new_props = diff.get("new", [])
    if not new_props:
        log("  LINE通知スキップ（新規物件なし）")
        return

    # Shared LINE utility (subprocess call — same pattern as other projects)
    line_script = BASE_DIR.parent / "lib" / "line_notify.py"
    if not line_script.exists():
        log(f"  LINE utility not found: {line_script}")
        return

    # Build area string from locations (deduplicated, compact)
    areas: list[str] = []
    for p in new_props:
        loc = p.get("location", "")
        # Extract city/ward level (e.g. "大阪市中央区..." → "大阪市中央区")
        short = loc.split("丁目")[0].split("番")[0][:12] if loc else ""
        if short and short not in areas:
            areas.append(short)
    area_str = ", ".join(areas[:5])
    if len(areas) > 5:
        area_str += f" 他{len(areas) - 5}エリア"

    report_url = "https://ymatz28-beep.github.io/property-report/"
    message = f"[property] 新規{len(new_props)}件検出 ({area_str})\n{report_url}"

    try:
        result = subprocess.run(
            [sys.executable, str(line_script), message],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            log(f"  LINE通知送信: 新規{len(new_props)}件")
        else:
            log(f"  LINE送信失敗: {result.stderr.strip()}")
    except Exception as e:
        log(f"  LINE送信エラー: {e}")


def main():
    start = datetime.now()
    log(f"===== 物件巡回パトロール開始 {start.strftime('%Y-%m-%d %H:%M')} =====")

    # 0. Snapshot before search
    before = parse_raw_files()
    log(f"  スナップショット: {len(before)}件")

    # 1. Search all sites
    search_all_sites()

    # 2. Diff properties
    after = parse_raw_files()
    diff = diff_properties(before, after)
    log(f"  差分: 新規{len(diff['new'])}件, 消失{len(diff['removed'])}件")

    # 3. Update first-seen registry (before reports so they can use it)
    update_first_seen()

    # 4. Check dead URLs
    url_report = patrol_dead_urls()

    # 5. Generate reports
    generate_reports()

    # 5.5. Auto-flag high-score properties for inquiry pipeline
    try:
        from property_pipeline import auto_flag, generate_dashboard
        auto_flag()
        generate_dashboard()
        log("  Pipeline auto-flag 完了")
    except Exception as e:
        log(f"  Pipeline auto-flag skipped: {e}")

    # 6. Deploy
    deploy()

    elapsed = (datetime.now() - start).total_seconds()
    log(f"===== 完了 ({elapsed:.0f}秒) =====")

    # Write structured summary for Daily Digest
    save_patrol_summary(start, elapsed, diff, url_report)

    # 7. LINE notification — disabled (Daily Digestに統合済み。単体通知は形骸化防止のため停止)
    # send_line_if_new(diff)


if __name__ == "__main__":
    main()
