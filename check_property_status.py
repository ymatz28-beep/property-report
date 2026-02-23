#!/usr/bin/env python3
"""
物件ステータスチェッカー
SUUMOの掲載終了を検出し、レポートを自動更新する。
launchdで毎日自動実行。
"""

import json
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
STATUS_FILE = DATA_DIR / "property_status.json"

# SUUMOの掲載終了パターン
REMOVED_PATTERNS = [
    "ochi_error",
    "掲載終了",
    "売約済",
    "この物件の掲載は終了",
    "お探しの物件は見つかりません",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}


def load_status() -> dict:
    """前回のステータスを読み込み"""
    if STATUS_FILE.exists():
        with open(STATUS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"last_check": None, "properties": {}}


def save_status(status: dict):
    """ステータスを保存"""
    DATA_DIR.mkdir(exist_ok=True)
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)


def extract_urls_from_data(data_path: Path) -> list[dict]:
    """データファイルからURL一覧を抽出"""
    properties = []
    if not data_path.exists():
        return properties

    with open(data_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # SUUMO URL抽出
            urls = re.findall(r"https://suumo\.jp/ms/chuko/[^\s|\"'<>]+", line)
            for url in urls:
                url = url.rstrip("/") + "/"
                # 物件名を行の先頭から取得
                name = line.split("|")[0].strip() if "|" in line else url
                properties.append({"name": name, "url": url, "source": data_path.name})
    return properties


def extract_urls_from_html(html_path: Path) -> list[dict]:
    """HTMLレポートからURL一覧を抽出"""
    properties = []
    if not html_path.exists():
        return properties

    with open(html_path, encoding="utf-8") as f:
        content = f.read()

    # href属性からSUUMO URLを抽出
    urls = re.findall(r'href="(https://suumo\.jp/ms/chuko/[^"]+)"', content)
    # 大阪R不動産URLも
    urls += re.findall(r'href="(https://www\.realosaka\.jp/estate/[^"]+)"', content)
    # 楽待URLも
    urls += re.findall(r'href="(https://www\.rakumachi\.jp/syuuekibukken/[^"]+)"', content)

    for url in urls:
        url = url.rstrip("/") + "/"
        properties.append({"name": "", "url": url, "source": html_path.name})

    # 重複排除
    seen = set()
    unique = []
    for p in properties:
        if p["url"] not in seen:
            seen.add(p["url"])
            unique.append(p)
    return unique


def check_suumo_url(url: str) -> str:
    """SUUMOのURLが有効か確認"""
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
            for pattern in REMOVED_PATTERNS:
                if pattern in content:
                    return "SOLD"
            if "中古マンション物件情報" in content or "販売価格" in content:
                return "ACTIVE"
            return "UNKNOWN"
    except HTTPError as e:
        if e.code == 404:
            return "SOLD"
        return f"ERROR_{e.code}"
    except (URLError, TimeoutError):
        return "ERROR_TIMEOUT"
    except Exception as e:
        return f"ERROR_{type(e).__name__}"


def check_realosaka_url(url: str) -> str:
    """大阪R不動産のURLが有効か確認"""
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
            if "売約済" in content or "SOLD" in content:
                return "SOLD"
            if "物件情報" in content or "価格" in content:
                return "ACTIVE"
            return "UNKNOWN"
    except HTTPError as e:
        if e.code == 404:
            return "SOLD"
        return f"ERROR_{e.code}"
    except (URLError, TimeoutError):
        return "ERROR_TIMEOUT"
    except Exception as e:
        return f"ERROR_{type(e).__name__}"


def check_rakumachi_url(url: str) -> str:
    """楽待のURLが有効か確認"""
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
            if "この物件は掲載が終了" in content or "掲載終了" in content:
                return "SOLD"
            if "物件詳細" in content or "万円" in content:
                return "ACTIVE"
            return "UNKNOWN"
    except HTTPError as e:
        if e.code == 404:
            return "SOLD"
        return f"ERROR_{e.code}"
    except (URLError, TimeoutError):
        return "ERROR_TIMEOUT"
    except Exception as e:
        return f"ERROR_{type(e).__name__}"


def check_url(url: str) -> str:
    """URLの種類に応じてチェック"""
    if "suumo.jp" in url:
        return check_suumo_url(url)
    elif "realosaka.jp" in url:
        return check_realosaka_url(url)
    elif "rakumachi.jp" in url:
        return check_rakumachi_url(url)
    return "UNKNOWN"


def extract_urls_from_multi_site(data_path: Path) -> list[dict]:
    """マルチサイトデータファイルからURL一覧を抽出"""
    properties = []
    if not data_path.exists():
        return properties

    with open(data_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            # Extended format: source|name|price|location|area|built|station|layout|pet|brokerage|url
            if len(parts) >= 10:
                url = parts[-1]
                name = parts[1]
                source = parts[0]
                if url.startswith("http"):
                    properties.append({"name": name, "url": url, "source": f"{source}/{data_path.name}"})
    return properties


def collect_all_properties() -> list[dict]:
    """全物件URLを収集"""
    all_props = []

    # SUUMOデータファイルから
    for data_file in DATA_DIR.glob("suumo_*.txt"):
        all_props.extend(extract_urls_from_data(data_file))

    # マルチサイトデータファイルから
    for data_file in DATA_DIR.glob("multi_site_*.txt"):
        all_props.extend(extract_urls_from_multi_site(data_file))

    # HTMLレポートから
    for html_file in OUTPUT_DIR.glob("*_search_report.html"):
        all_props.extend(extract_urls_from_html(html_file))

    # 重複排除
    seen = set()
    unique = []
    for p in all_props:
        if p["url"] not in seen:
            seen.add(p["url"])
            unique.append(p)

    return unique


REPORT_URLS = {
    "fukuoka": "https://ymatz28-beep.github.io/property-report/fukuoka_search_report.html",
    "osaka": "https://ymatz28-beep.github.io/property-report/osaka_search_report.html",
}


def send_reminder(message: str, notes: str = ""):
    """リマインダーに通知（本文 + notes）"""
    escaped = message.replace('"', '\\"').replace("'", "'\\''")
    notes_escaped = notes.replace('"', '\\"').replace("'", "'\\''")
    script = f'''
    tell application "Reminders"
        set targetList to list "リマインダー"
        set newReminder to make new reminder at end of reminders of targetList
        set name of newReminder to "{escaped}"
        set body of newReminder to "{notes_escaped}"
        set remind me date of newReminder to (current date) + 1 * minutes
    end tell
    '''
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=10)
    except Exception:
        pass


def run_multi_site_search():
    """マルチサイト検索を実行（レート制限に注意）"""
    try:
        from search_multi_site import search_city
        print("\n--- マルチサイト検索 ---")
        for city_key in ["osaka", "fukuoka"]:
            try:
                search_city(city_key)
            except Exception as e:
                print(f"  [ERROR] {city_key}: {e}")
    except ImportError:
        print("  [SKIP] search_multi_site.py not found")


def run_ftakken_search():
    """ふれんず検索を実行"""
    try:
        from search_ftakken import search_ftakken, save_results
        print("\n--- ふれんず検索 ---")
        props = search_ftakken("fukuoka")
        if props:
            save_results(props, "fukuoka")
            print(f"  ふれんず: {len(props)}件")
        else:
            print("  ふれんず: 0件")
    except ImportError:
        print("  [SKIP] search_ftakken.py not found")
    except Exception as e:
        print(f"  [ERROR] ふれんず: {e}")


def deploy_to_gh_pages():
    """レポートをGitHub Pagesにデプロイ"""
    import tempfile
    deploy_dir = Path(tempfile.mkdtemp(prefix="property-deploy-"))
    try:
        # Clone gh-pages branch
        subprocess.run(
            ["git", "clone", "--branch", "gh-pages", "--single-branch", "--depth", "1",
             "https://github.com/ymatz28-beep/property-report.git", str(deploy_dir)],
            capture_output=True, timeout=30,
        )

        # Copy updated reports
        updated = False
        for report in OUTPUT_DIR.glob("*_search_report.html"):
            dest = deploy_dir / report.name
            dest.write_text(report.read_text(encoding="utf-8"), encoding="utf-8")
            updated = True

        if not updated:
            print("  デプロイ対象なし")
            return False

        # Commit and push
        subprocess.run(["git", "add", "-A"], cwd=deploy_dir, capture_output=True)
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"], cwd=deploy_dir, capture_output=True
        )
        if result.returncode == 0:
            print("  変更なし（デプロイ不要）")
            return False

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        subprocess.run(
            ["git", "commit", "-m", f"Auto-update reports {now}"],
            cwd=deploy_dir, capture_output=True, timeout=10,
        )
        push_result = subprocess.run(
            ["git", "push", "origin", "gh-pages"],
            cwd=deploy_dir, capture_output=True, timeout=30,
        )
        if push_result.returncode == 0:
            print("  GitHub Pagesデプロイ完了")
            return True
        else:
            print(f"  デプロイエラー: {push_result.stderr.decode()[:200]}")
            return False
    except Exception as e:
        print(f"  デプロイエラー: {e}")
        return False
    finally:
        import shutil
        shutil.rmtree(deploy_dir, ignore_errors=True)


def regenerate_reports() -> bool:
    """レポート再生成"""
    print("\n--- レポート再生成 ---")
    try:
        from generate_osaka_report import main as gen_osaka
        from generate_fukuoka_report import main as gen_fukuoka
        gen_osaka()
        gen_fukuoka()
        print("  レポート更新完了")
        return True
    except Exception as e:
        print(f"  レポート更新エラー: {e}")
        return False


def main():
    print(f"=== 物件自動パイプライン {datetime.now().strftime('%Y-%m-%d %H:%M')} ===")

    # --- Step 1: 全ソースから物件データ更新 ---
    print("\n[1/5] マルチサイト検索")
    run_multi_site_search()

    print("\n[2/5] ふれんず検索")
    run_ftakken_search()

    # --- Step 2: 物件ステータスチェック ---
    print("\n[3/5] 物件ステータスチェック")
    status = load_status()
    prev_props = status.get("properties", {})
    properties = collect_all_properties()

    print(f"  チェック対象: {len(properties)}件")

    newly_sold = []
    results = {}

    for i, prop in enumerate(properties):
        url = prop["url"]
        current = check_url(url)
        prev = prev_props.get(url, {}).get("status", "UNKNOWN")

        results[url] = {
            "name": prop["name"],
            "source": prop["source"],
            "status": current,
            "last_check": datetime.now().isoformat(),
            "prev_status": prev,
        }

        if current == "SOLD" and prev != "SOLD":
            newly_sold.append(prop)
            print(f"  [{i+1}/{len(properties)}] SOLD: {prop['name'] or url}")
        elif current == "ACTIVE":
            print(f"  [{i+1}/{len(properties)}] OK: {prop['name'] or url}")
        else:
            print(f"  [{i+1}/{len(properties)}] {current}: {prop['name'] or url}")

        time.sleep(0.5)

    status["last_check"] = datetime.now().isoformat()
    status["properties"] = results
    save_status(status)

    active = sum(1 for r in results.values() if r["status"] == "ACTIVE")
    sold = sum(1 for r in results.values() if r["status"] == "SOLD")
    errors = sum(1 for r in results.values() if r["status"].startswith("ERROR"))

    print(f"\n  有効: {active}件 / 売却済: {sold}件 / エラー: {errors}件")
    if newly_sold:
        print(f"  新たに売却済み: {len(newly_sold)}件")

    # --- Step 3: レポート再生成（毎回実行） ---
    print("\n[4/5] レポート再生成")
    report_ok = regenerate_reports()

    # --- Step 4: GitHub Pagesデプロイ ---
    print("\n[5/5] GitHub Pagesデプロイ")
    deployed = deploy_to_gh_pages()

    # --- Step 5: リマインダー通知（レポートURL付き） ---
    report_links = "\n".join(f"・{k}: {v}" for k, v in REPORT_URLS.items())

    if newly_sold:
        sold_names = ", ".join(p["name"] or "不明" for p in newly_sold[:3])
        if len(newly_sold) > 3:
            sold_names += f" 他{len(newly_sold)-3}件"
        msg = f"[物件更新] {len(newly_sold)}件売却済 / レポート更新済"
        notes = f"売却済: {sold_names}\n\n最新レポート:\n{report_links}"
        send_reminder(msg, notes)
    elif deployed:
        msg = f"[物件更新] レポート更新済（有効{active}件）"
        notes = f"最新レポート:\n{report_links}"
        send_reminder(msg, notes)

    print(f"\n=== 完了 ===")
    print(f"レポート:")
    for city, url in REPORT_URLS.items():
        print(f"  {city}: {url}")


if __name__ == "__main__":
    main()
