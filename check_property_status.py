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
    "fukuoka": "https://ymatz28-beep.github.io/property-report/minpaku-fukuoka.html",
    "osaka": "https://ymatz28-beep.github.io/property-report/minpaku-osaka.html",
    "tokyo": "https://ymatz28-beep.github.io/property-report/minpaku-tokyo.html",
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


def _generate_index_html() -> str:
    """ランディングページHTMLを生成"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    reports = [
        ("minpaku-osaka.html", "大阪", "民泊向け中古マンション候補", "#6ee7ff"),
        ("minpaku-fukuoka.html", "福岡", "民泊向け中古マンション候補", "#ff6b6b"),
        ("minpaku-tokyo.html", "東京", "民泊向け中古マンション候補", "#a78bfa"),
        ("naiken-analysis.html", "内覧分析", "内覧予定物件の比較・分析", "#a78bfa"),
    ]
    cards = ""
    for href, city, desc, color in reports:
        cards += f"""
        <a href="{href}" class="report-card" style="--card-accent:{color}">
          <div class="card-city">{city}</div>
          <div class="card-desc">{desc}</div>
          <div class="card-arrow">&rarr;</div>
        </a>"""
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Property Report Hub</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=Noto+Sans+JP:wght@400;700;900&display=swap" rel="stylesheet">
  <style>
    :root {{ --bg:#0b0f16; --card:rgba(255,255,255,0.04); --line:rgba(255,255,255,0.10); --text:#edf3ff; --muted:#a9b3c6; }}
    * {{ box-sizing:border-box; margin:0; }}
    body {{ font-family:'Inter','Noto Sans JP',sans-serif; background:radial-gradient(ellipse at 20% -10%,rgba(110,231,255,0.08),transparent 50%),radial-gradient(ellipse at 80% 10%,rgba(167,139,250,0.06),transparent 50%),linear-gradient(180deg,#070b11,#0b0f16 30%,#0d1320); color:var(--text); min-height:100vh; }}
    .wrap {{ max-width:800px; margin:0 auto; padding:80px 20px 60px; }}
    h1 {{ font-size:clamp(28px,5vw,48px); font-weight:900; text-align:center; line-height:1.1; }}
    .sub {{ text-align:center; color:var(--muted); margin-top:12px; font-size:14px; }}
    .grid {{ margin-top:48px; display:grid; gap:16px; }}
    .report-card {{
      display:grid; grid-template-columns:auto 1fr auto; align-items:center; gap:16px;
      padding:24px 28px; border-radius:18px; text-decoration:none; color:var(--text);
      border:1px solid var(--line); background:var(--card);
      transition:all .2s;
    }}
    .report-card:hover {{ border-color:var(--card-accent); background:rgba(255,255,255,0.06); transform:translateY(-2px); }}
    .card-city {{ font-size:28px; font-weight:900; color:var(--card-accent); min-width:60px; }}
    .card-desc {{ font-size:14px; color:var(--muted); }}
    .card-arrow {{ font-size:24px; color:var(--card-accent); opacity:0.5; }}
    .report-card:hover .card-arrow {{ opacity:1; }}
    .footer {{ margin-top:60px; text-align:center; color:var(--muted); font-size:12px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Property Report Hub</h1>
    <p class="sub">iUMAプロパティマネジメント — 不動産投資分析レポート</p>
    <div class="grid">{cards}
    </div>
    <div class="footer">Last updated: {now}</div>
  </div>
</body>
</html>"""


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

        # Set git identity in temp repo (required for commit in fresh clone)
        subprocess.run(["git", "config", "user.email", "noreply@github.com"], cwd=deploy_dir, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Property Report Bot"], cwd=deploy_dir, capture_output=True)

        # Remove old report files
        for old in ["fukuoka_search_report.html", "osaka_search_report.html", "tokyo_search_report.html"]:
            old_path = deploy_dir / old
            if old_path.exists():
                old_path.unlink()

        # Copy all output HTML files (reports, inquiry, index, naiken, etc.)
        # Exclude confidential/local-only files from public deploy
        _DEPLOY_EXCLUDE = {"portfolio_dashboard.html"}
        updated = False
        for report in OUTPUT_DIR.glob("*.html"):
            if report.name in _DEPLOY_EXCLUDE:
                continue
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
        commit_result = subprocess.run(
            ["git", "commit", "-m", f"Auto-update reports {now}"],
            cwd=deploy_dir, capture_output=True, timeout=10,
        )
        if commit_result.returncode != 0:
            print(f"  コミットエラー: {commit_result.stderr.decode()[:300]}")
            return False
        push_result = subprocess.run(
            ["git", "push", "origin", "gh-pages"],
            cwd=deploy_dir, capture_output=True, timeout=60,
        )
        if push_result.returncode == 0:
            print("  GitHub Pages push完了。ビルド待ち...")
            # Wait for GitHub Pages build and verify
            if _verify_gh_pages_deploy():
                print("  GitHub Pagesデプロイ完了 ✅")
                return True
            else:
                print("  ⚠ push成功したがサイト疎通確認失敗（ビルド遅延の可能性）")
                return True  # push自体は成功
        else:
            print(f"  pushエラー: {push_result.stderr.decode()[:300]}")
            return False
    except Exception as e:
        print(f"  デプロイエラー: {e}")
        return False
    finally:
        import shutil
        shutil.rmtree(deploy_dir, ignore_errors=True)


def _verify_gh_pages_deploy(max_wait: int = 90) -> bool:
    """Wait for GitHub Pages build and verify site is live."""
    verify_urls = [
        "https://ymatz28-beep.github.io/property-report/",
        "https://ymatz28-beep.github.io/property-report/minpaku-osaka.html",
    ]
    headers = {"User-Agent": "Mozilla/5.0 PropertyReportBot/1.0"}
    start = time.time()
    attempt = 0
    while time.time() - start < max_wait:
        attempt += 1
        all_ok = True
        for url in verify_urls:
            try:
                req = Request(url, headers=headers)
                with urlopen(req, timeout=10) as resp:
                    if resp.status != 200:
                        all_ok = False
                        break
            except (HTTPError, URLError, TimeoutError):
                all_ok = False
                break
        if all_ok:
            print(f"  サイト疎通確認OK（{attempt}回目、{time.time()-start:.0f}秒）")
            return True
        time.sleep(10)
    print(f"  サイト疎通確認タイムアウト（{max_wait}秒）")
    return False


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
