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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def run_script(name: str, args: list[str] | None = None) -> bool:
    """Run a Python script and return success status."""
    cmd = [sys.executable, name] + (args or [])
    log(f"  Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=str(BASE_DIR))
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
    try:
        req = Request(url, headers=HEADERS, method="HEAD")
        with urlopen(req, timeout=10) as resp:
            return True, resp.status
    except HTTPError as e:
        return e.code not in (404, 410, 403), e.code
    except (URLError, TimeoutError):
        return True, 0  # Network error = assume still alive


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


def search_all_sites() -> None:
    """Run all property searches."""
    log("=== 物件検索開始 ===")

    # Standard HTTP scrapers (rakumachi, yahoo, athome, cowcamo)
    run_script("search_multi_site.py")

    # R不動産 (BeautifulSoup)
    run_script("search_restate.py")

    # Playwright-based scrapers
    run_script("search_ftakken.py")
    run_script("search_lifull.py")

    # Enrich maintenance fees from detail pages
    log("=== 管理費enrichment ===")
    run_script("enrich_maintenance.py")


def generate_reports() -> None:
    """Generate all city reports."""
    log("=== レポート生成 ===")
    for script in ["generate_osaka_report.py", "generate_fukuoka_report.py", "generate_tokyo_report.py"]:
        run_script(script)


def deploy() -> None:
    """Deploy to gh-pages."""
    log("=== デプロイ ===")
    from check_property_status import deploy_to_gh_pages
    result = deploy_to_gh_pages()
    if result:
        log("  GitHub Pagesデプロイ完了")
    else:
        log("  デプロイ不要（変更なし）またはエラー")


def main():
    start = datetime.now()
    log(f"===== 物件巡回パトロール開始 {start.strftime('%Y-%m-%d %H:%M')} =====")

    # 1. Search all sites
    search_all_sites()

    # 2. Check dead URLs
    url_report = patrol_dead_urls()

    # 3. Generate reports
    generate_reports()

    # 4. Deploy
    deploy()

    elapsed = (datetime.now() - start).total_seconds()
    log(f"===== 完了 ({elapsed:.0f}秒) =====")
    log(f"  URL: {url_report['total']}件チェック, {url_report['new_dead']}件新規DEAD")


if __name__ == "__main__":
    main()
