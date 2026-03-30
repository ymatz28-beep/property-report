#!/usr/bin/env python3
"""
毎朝の物件巡回パトロールスクリプト
- 全サイト×全都市で物件検索
- 既存URLの生死チェック（掲載終了検出）
- レポート再生成 + gh-pagesデプロイ
- 差分サマリー通知
- 失敗ステップの自動リトライ

cron設定例:
  0 6 * * * cd ~/Documents/Projects/property-analyzer && python3 run_daily_patrol.py >> data/patrol.log 2>&1
"""

import json
import re
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

# Actionable fix suggestions: step_name -> reason_key -> fix text
STEP_FIX: dict[str, dict[str, str]] = {
    "search_suumo.py (osaka)": {
        "timeout": "SUUMO大阪タイムアウト。4区×詳細取得が遅延",
        "default": "SUUMO側のブロック可能性。User-Agent or wait時間を見直す",
    },
    "search_suumo.py (fukuoka)": {
        "timeout": "SUUMO福岡タイムアウト。3区×詳細取得が遅延",
        "default": "SUUMO側のブロック可能性。User-Agent or wait時間を見直す",
    },
    "search_suumo.py (tokyo)": {
        "timeout": "SUUMO東京タイムアウト。10区×詳細取得が遅延",
        "default": "SUUMO側のブロック可能性。User-Agent or wait時間を見直す",
    },
    "enrich_maintenance.py": {
        "timeout": "設計上の仕様（600s budget制）。未取得分は翌日継続。アクション不要",
        "default": "管理費ページのHTML構造変化の可能性。パーサー確認",
    },
    "search_multi_site.py": {
        "timeout": "Yahoo/楽待スクレイプ負荷増。並列化 or 都市分割を検討",
        "default": "サイト構造変化の可能性。セレクタ確認",
    },
    "generate_osaka_report.py": {"default": "レポートデータ不整合。手動で python3 generate_osaka_report.py を実行"},
    "generate_fukuoka_report.py": {"default": "レポートデータ不整合。手動で python3 generate_fukuoka_report.py を実行"},
    "generate_tokyo_report.py": {"default": "レポートデータ不整合。手動で python3 generate_tokyo_report.py を実行"},
    "generate_ittomono_report.py": {"default": "一棟ものデータ不整合。手動で python3 generate_ittomono_report.py を実行"},
}

# Human-readable labels: step_name -> (label, impact_when_failed)
STEP_LABELS = {
    "search_suumo.py (osaka)": ("SUUMO物件検索(大阪)", "SUUMO大阪の物件データが未更新"),
    "search_suumo.py (fukuoka)": ("SUUMO物件検索(福岡)", "SUUMO福岡の物件データが未更新"),
    "search_suumo.py (tokyo)": ("SUUMO物件検索(東京)", "SUUMO東京の物件データが未更新"),
    "search_multi_site.py": ("Yahoo不動産/楽待検索", "Yahoo/楽待の物件データが未更新"),
    "search_restate.py": ("RE-STATE検索", "RE-STATEの物件データが未更新"),
    "search_ftakken.py": ("F宅建検索", "F宅建の物件データが未更新"),
    "search_lifull.py": ("LIFULL検索", "LIFULLの物件データが未更新"),
    "search_ittomono.py": ("一棟もの検索", "一棟もの物件データが未更新"),
    "search_yield_focused.py": ("利回りフォーカス検索", "利回り特化物件データが未更新"),
    "enrich_maintenance.py": ("管理費データ取得", "管理費・修繕積立金が未更新"),
    "generate_osaka_report.py": ("大阪レポート生成", "大阪レポートが古いまま"),
    "generate_fukuoka_report.py": ("福岡レポート生成", "福岡レポートが古いまま"),
    "generate_tokyo_report.py": ("東京レポート生成", "東京レポートが古いまま"),
    "generate_ittomono_report.py": ("一棟ものレポート生成", "一棟ものレポートが古いまま"),
    "generate_inquiry_messages.py": ("問い合わせ文面生成", "問い合わせ文面が未更新"),
    "first_seen": ("初回検出日記録", "新規物件の初回検出日が未記録"),
    "url_check": ("掲載終了チェック", "売却済み物件の検出が未実行"),
    "pipeline_flag": ("自動フラグ付与", "高スコア物件の自動フラグが未実行"),
    "pipeline_lifecycle": ("パイプラインライフサイクル", "掲載終了・価格変動・ステータス同期"),
    "pipeline_dashboard": ("問い合わせダッシュボード", "問い合わせ管理画面が未更新"),
    "naiken_analysis": ("内覧分析レポート", "内覧比較レポートが未更新"),
    "deploy": ("デプロイ", "レポートが公開されていない"),
}


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def _read_stderr_tail(path: Path, max_chars: int = 500) -> str:
    """Read last N chars of a stderr temp file."""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        return content[-max_chars:].strip() if content else ""
    except Exception:
        return ""


def run_script(name: str, args: list[str] | None = None, timeout: int = 180) -> dict:
    """Run a Python script and return detailed result.

    Returns dict: ok, reason, stderr_tail, elapsed_sec, exit_code, timeout (if applicable)
    Stderr captured to temp file (not pipe) to avoid deadlock while preserving diagnostics.
    """
    import os as _os, signal as _sig
    cmd = [sys.executable, name] + (args or [])
    log(f"  Running: {' '.join(cmd)}")

    t0 = time.time()
    stderr_path = DATA_DIR / f".stderr_{Path(name).stem}.tmp"

    try:
        with open(stderr_path, "w") as stderr_file:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=stderr_file,
                cwd=str(BASE_DIR), start_new_session=True,
            )
        # Parent's fd closed; child retains its own copy via dup2

        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                _os.killpg(proc.pid, _sig.SIGKILL)
            except OSError:
                proc.kill()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            log(f"  [WARN] {name} timed out ({timeout}s)")
            return {"ok": False, "reason": "timeout",
                    "stderr_tail": _read_stderr_tail(stderr_path),
                    "elapsed_sec": round(time.time() - t0),
                    "exit_code": -1, "timeout": timeout}

        stderr_tail = _read_stderr_tail(stderr_path)
        elapsed = round(time.time() - t0)

        if proc.returncode != 0:
            log(f"  [WARN] {name} exited with code {proc.returncode}")
            return {"ok": False, "reason": "error",
                    "stderr_tail": stderr_tail,
                    "elapsed_sec": elapsed, "exit_code": proc.returncode}

        return {"ok": True, "reason": "", "stderr_tail": "",
                "elapsed_sec": elapsed, "exit_code": 0}
    except Exception as e:
        log(f"  [ERROR] {name}: {e}")
        return {"ok": False, "reason": "crash", "stderr_tail": str(e),
                "elapsed_sec": round(time.time() - t0), "exit_code": -2}
    finally:
        stderr_path.unlink(missing_ok=True)


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
    skipped_budget = 0
    budget_seconds = 300  # 5min time budget — prevent unbounded growth

    check_start = time.time()
    for url in urls_to_check:
        if time.time() - check_start > budget_seconds:
            skipped_budget = len(urls_to_check) - checked
            log(f"  ⚠️ タイムバジェット超過 ({budget_seconds}s), 残り{skipped_budget}件スキップ")
            break

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

    log(f"  完了: {len(dead_urls)} dead / {checked} checked ({len(new_dead)} new)")
    return {"total": len(all_urls), "dead": len(dead_urls), "new_dead": len(new_dead), "skipped": skipped_budget}


def parse_raw_files() -> dict[str, dict]:
    """Parse all raw files. Returns {url: {name, price, location, source}}.

    Handles two column layouts:
    - Standard: source|name|price|location|...|url   (col 0 = text source label)
    - Ittomono: score|source|name|price|location|...|url  (col 0 = numeric score)
    Detection: if col 0 is a bare integer, it's a score prefix → shift by 1.
    """
    properties = {}
    for f in DATA_DIR.glob("*_raw.txt"):
        source = f.stem.replace("_raw", "")
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) < 4:
                continue
            url = parts[-1].strip()
            if not url.startswith("http"):
                continue

            # Detect score-prefixed format (ittomono_*_raw.txt):
            # col 0 is a bare integer score like "75" or "83"
            offset = 0
            try:
                int(parts[0].strip())
                # col 0 is numeric → ittomono format with score prefix
                offset = 1
            except (ValueError, IndexError):
                pass

            name_idx = 1 + offset
            price_idx = 2 + offset
            loc_idx = 3 + offset

            properties[url] = {
                "name": parts[name_idx].strip() if len(parts) > name_idx else "",
                "price": parts[price_idx].strip() if len(parts) > price_idx else "",
                "location": parts[loc_idx].strip() if len(parts) > loc_idx else "",
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
    """Compare before/after snapshots. Returns diff summary.

    Source-failure guard: if a source lost >70% of its properties,
    treat it as a scraping failure and exclude from diff calculation.
    """
    # Per-source counts
    from collections import Counter
    before_by_src = Counter(v["source"] for v in before.values())
    after_by_src = Counter(v["source"] for v in after.values())

    # Detect failed sources (>70% drop)
    failed_sources: set[str] = set()
    for src, cnt in before_by_src.items():
        after_cnt = after_by_src.get(src, 0)
        if cnt >= 10 and after_cnt < cnt * 0.3:
            failed_sources.add(src)
            log(f"  ⚠️ ソース障害検出: {src} ({cnt}→{after_cnt}件, -{cnt - after_cnt}件) — 差分から除外")

    before_urls = {u for u, v in before.items() if v["source"] not in failed_sources}
    after_urls = {u for u, v in after.items() if v["source"] not in failed_sources}

    new_urls = after_urls - before_urls
    removed_urls = before_urls - after_urls

    new_props = [after[u] for u in sorted(new_urls)]
    removed_props = [before[u] for u in sorted(removed_urls)]

    return {
        "new": new_props,
        "removed": removed_props,
        "before_count": len(before_urls),
        "after_count": len(after_urls),
        "failed_sources": sorted(failed_sources),
    }


def search_all_sites() -> list[dict]:
    """Run searches: SUUMO first (heaviest), then rest in parallel.

    Returns list of step result dicts with ok, reason, stderr_tail, etc.
    """
    import os as _os, signal as _sig
    results = []

    # Phase 1: SUUMO — 3 cities in parallel (was sequential = 25min timeout risk)
    # osaka(4区)+fukuoka(3区)+tokyo(10区) each under 10min → total ~10min
    log("=== 物件検索: SUUMO (3都市並列) ===")
    suumo_cities = [("osaka", 600), ("fukuoka", 500), ("tokyo", 900)]
    suumo_procs: dict[str, tuple[subprocess.Popen, Path, float]] = {}
    for city, _timeout in suumo_cities:
        stderr_path = DATA_DIR / f".stderr_suumo_{city}.tmp"
        cmd = [sys.executable, "search_suumo.py", city]
        log(f"  Starting: search_suumo.py {city}")
        with open(stderr_path, "w") as sf:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=sf,
                cwd=str(BASE_DIR), start_new_session=True,
            )
        suumo_procs[city] = (proc, stderr_path, time.time())

    import os as _os, signal as _sig
    suumo_ok = True
    for city, timeout in suumo_cities:
        proc, stderr_path, t0 = suumo_procs[city]
        step_name = f"search_suumo.py ({city})"
        try:
            proc.wait(timeout=timeout)
            elapsed = round(time.time() - t0)
            if proc.returncode == 0:
                results.append({"step": step_name, "ok": True, "reason": "",
                                "stderr_tail": "", "elapsed_sec": elapsed, "exit_code": 0})
            else:
                suumo_ok = False
                stderr_tail = _read_stderr_tail(stderr_path)
                log(f"  ⚠️ {step_name} 失敗 (exit {proc.returncode})")
                results.append({"step": step_name, "ok": False, "reason": "error",
                                "stderr_tail": stderr_tail, "elapsed_sec": elapsed,
                                "exit_code": proc.returncode})
        except subprocess.TimeoutExpired:
            try:
                _os.killpg(proc.pid, _sig.SIGKILL)
            except OSError:
                proc.kill()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            suumo_ok = False
            stderr_tail = _read_stderr_tail(stderr_path)
            log(f"  ⚠️ {step_name} タイムアウト ({timeout}s)")
            results.append({"step": step_name, "ok": False, "reason": "timeout",
                            "stderr_tail": stderr_tail,
                            "elapsed_sec": round(time.time() - t0),
                            "exit_code": -1, "timeout": timeout})
        finally:
            stderr_path.unlink(missing_ok=True)

    if not suumo_ok:
        log("  ⚠️ SUUMO 一部失敗 — 他ソースで続行")

    # Phase 2: Remaining scrapers in parallel (lighter, separate files)
    log("=== 物件検索: 他ソース（並列） ===")
    parallel_steps = [
        ("search_multi_site.py", 600),
        ("search_restate.py", 300),
        ("search_ftakken.py", 300),
        ("search_lifull.py", 300),
        ("search_ittomono.py", 600),
        ("search_yield_focused.py", 600),
    ]

    # Start all parallel processes with stderr capture
    procs: dict[str, tuple[subprocess.Popen, Path, float]] = {}
    for script, _timeout in parallel_steps:
        cmd = [sys.executable, script]
        log(f"  Starting: {script}")
        stderr_path = DATA_DIR / f".stderr_{Path(script).stem}.tmp"
        with open(stderr_path, "w") as stderr_file:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=stderr_file,
                cwd=str(BASE_DIR), start_new_session=True,
            )
        procs[script] = (proc, stderr_path, time.time())

    # Wait for all parallel processes
    for script, timeout in parallel_steps:
        proc, stderr_path, t0 = procs[script]
        try:
            proc.wait(timeout=timeout)
            elapsed = round(time.time() - t0)
            ok = proc.returncode == 0
            if not ok:
                stderr_tail = _read_stderr_tail(stderr_path)
                log(f"  ⚠️ {script} 失敗 (exit {proc.returncode}) — 続行")
                results.append({"step": script, "ok": False, "reason": "error",
                                "stderr_tail": stderr_tail, "elapsed_sec": elapsed,
                                "exit_code": proc.returncode})
            else:
                results.append({"step": script, "ok": True, "reason": "",
                                "stderr_tail": "", "elapsed_sec": elapsed, "exit_code": 0})
        except subprocess.TimeoutExpired:
            try:
                _os.killpg(proc.pid, _sig.SIGKILL)
            except OSError:
                proc.kill()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            stderr_tail = _read_stderr_tail(stderr_path)
            log(f"  ⚠️ {script} タイムアウト ({timeout}s) — 続行")
            results.append({"step": script, "ok": False, "reason": "timeout",
                            "stderr_tail": stderr_tail,
                            "elapsed_sec": round(time.time() - t0),
                            "exit_code": -1, "timeout": timeout})
        finally:
            stderr_path.unlink(missing_ok=True)

    # Phase 3: Enrich maintenance fees (depends on search results)
    log("=== 管理費enrichment ===")
    result = run_script("enrich_maintenance.py", timeout=900)
    results.append({"step": "enrich_maintenance.py", **result})
    return results


def generate_reports() -> list[dict]:
    """Generate all city reports. Returns step results."""
    log("=== レポート生成 ===")
    results = []
    for script in ["generate_osaka_report.py", "generate_fukuoka_report.py", "generate_tokyo_report.py"]:
        result = run_script(script)
        results.append({"step": script, **result})
        if not result["ok"]:
            log(f"  ⚠️ {script} 失敗 — 他都市は続行")
    # Generate 一棟もの report
    result = run_script("generate_ittomono_report.py")
    results.append({"step": "generate_ittomono_report.py", **result})
    if not result["ok"]:
        log("  ⚠️ generate_ittomono_report.py 失敗 — 続行")
    result = run_script("generate_inquiry_messages.py")
    results.append({"step": "generate_inquiry_messages.py", **result})
    return results


def deploy() -> None:
    """Deploy to gh-pages.

    On GHA, the workflow handles gh-pages deploy via shell step (with proper
    auth token). Skip Python deploy to avoid unauthenticated clone failure.
    """
    import os
    if os.environ.get("GITHUB_ACTIONS") == "true":
        log("=== デプロイ ===")
        log("  GHA環境 — ワークフローの shell ステップでデプロイ（Pythonスキップ）")
        return
    log("=== デプロイ ===")
    from check_property_status import deploy_to_gh_pages
    result = deploy_to_gh_pages()
    if result:
        log("  GitHub Pagesデプロイ完了")
    else:
        log("  デプロイ不要（変更なし）またはエラー")


def _build_failure_details(all_steps: list[dict]) -> list[dict]:
    """Build human-readable failure details from step results."""
    details = []
    for s in all_steps:
        if s.get("ok"):
            continue
        step = s["step"]
        label, impact = STEP_LABELS.get(step, (step, "詳細不明"))
        reason_key = s.get("reason", "error")

        detail: dict = {
            "step": step,
            "label": label,
            "impact": impact,
            "stderr_tail": s.get("stderr_tail", ""),
        }

        if reason_key == "timeout":
            timeout_sec = s.get("timeout", s.get("elapsed_sec", 0))
            detail["reason"] = f"タイムアウト ({timeout_sec // 60}分超過)"
        elif reason_key == "crash":
            detail["reason"] = f"異常終了: {s.get('stderr_tail', '')[:100]}"
        elif s.get("exit_code") and s["exit_code"] > 0:
            detail["reason"] = f"エラー終了 (exit {s['exit_code']})"
        else:
            detail["reason"] = "エラー"

        if s.get("retried"):
            detail["retried"] = True

        fix_map = STEP_FIX.get(step, {})
        detail["fix"] = fix_map.get(reason_key, fix_map.get("default", "エラーログを確認"))

        details.append(detail)
    return details


def _safe_price_man(price_text: str) -> int:
    """Parse price text to 万円 int, returning 0 on failure.

    Handles formats: "4190万円", "1億9760万円", "2億円"
    """
    try:
        text = price_text.replace(",", "").replace("円", "").strip()
        # Handle 億+万 format: "1億9760万" → 19760
        m = re.match(r"(\d+)億(\d+)万?", text)
        if m:
            return int(m.group(1)) * 10000 + int(m.group(2))
        # Handle 億 only: "2億" → 20000
        m = re.match(r"(\d+)億", text)
        if m:
            return int(m.group(1)) * 10000
        # Handle 万 only: "4190万" → 4190
        text = text.replace("万", "")
        return int(text)
    except (ValueError, AttributeError):
        return 0


def save_patrol_summary(start: datetime, elapsed: float, diff: dict, url_report: dict,
                        all_steps: list[dict] | None = None) -> None:
    """Save patrol summary as JSON (structured data for Daily Digest + notifications).

    Crash-safe: if new_items serialization fails, writes summary without items
    rather than leaving a stale/missing patrol_summary.json.
    """
    new = diff.get("new", [])
    removed = diff.get("removed", [])
    dead_count = url_report.get("new_dead", 0) + len(removed)

    all_steps = all_steps or []
    failed_names = [s["step"] for s in all_steps if not s.get("ok")]
    failure_details = _build_failure_details(all_steps)

    # Build new_items safely — never let a single bad record kill the summary
    new_items: list[dict] = []
    for p in new:
        try:
            new_items.append({
                "name": p.get("name", ""),
                "price_text": p.get("price", ""),
                "price_man": _safe_price_man(p.get("price", "")),
                "source": p.get("source", ""),
            })
        except Exception:
            pass  # skip malformed entries silently

    summary = {
        "date": start.strftime("%Y-%m-%d %H:%M"),
        "total": diff.get("after_count", 0),
        "prev_total": diff.get("before_count", 0),
        "new_count": len(new),
        "removed_count": dead_count,
        "elapsed_min": round(elapsed / 60),
        "failed_sources": diff.get("failed_sources", []),
        "failed_steps": failed_names,
        "failure_details": failure_details,
        "step_count": len(all_steps),
        "ok_count": sum(1 for s in all_steps if s.get("ok")),
        "new_items": new_items,
        "report_url": "https://ymatz28-beep.github.io/property-report/",
    }

    summary_file = BASE_DIR / "data" / "patrol_summary.json"
    try:
        summary_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"  patrol_summary.json 保存 (total={summary['total']}, +{summary['new_count']}/-{summary['removed_count']})")
    except Exception as e:
        # Last resort: write minimal summary so downstream consumers never see stale data
        log(f"  ❌ patrol_summary.json 書き込みエラー: {e}")
        minimal = {
            "date": start.strftime("%Y-%m-%d %H:%M"),
            "step_count": len(all_steps),
            "ok_count": sum(1 for s in all_steps if s.get("ok")),
            "elapsed_min": round(elapsed / 60),
            "new_count": 0, "total": 0, "failed_steps": failed_names,
            "failure_details": [], "new_items": [],
            "error": str(e),
        }
        summary_file.write_text(json.dumps(minimal, ensure_ascii=False, indent=2), encoding="utf-8")


def retry_failed_searches(search_results: list[dict], start_time: datetime,
                          budget_min: int = 55) -> None:
    """Retry failed search steps (timeout only) if time budget allows.

    Mutates search_results in-place: updates the failed step's dict if retry succeeds.
    """
    elapsed_min = (datetime.now() - start_time).total_seconds() / 60
    remaining_min = budget_min - elapsed_min

    for r in search_results:
        if r["ok"] or r.get("reason") != "timeout":
            continue

        step = r["step"]
        original_timeout = r.get("timeout", 300)
        # Retry with half timeout to limit total impact
        retry_timeout = min(original_timeout // 2, int(remaining_min * 60) - 300)
        if retry_timeout < 120:
            label = STEP_LABELS.get(step, (step, ""))[0]
            log(f"  ⏭️ {label} リトライスキップ（残り時間不足: {remaining_min:.0f}分）")
            continue

        label = STEP_LABELS.get(step, (step, ""))[0]
        log(f"  🔄 {label} リトライ中 (timeout={retry_timeout}s)...")
        result = run_script(step, timeout=retry_timeout)

        if result["ok"]:
            log(f"  ✅ {label} リトライ成功")
            r.update(result)
        else:
            log(f"  ❌ {label} リトライも失敗")
            r["retried"] = True  # Mark as retried-and-failed

        remaining_min = (budget_min * 60 - (datetime.now() - start_time).total_seconds()) / 60


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

    # Resilience: track all step outcomes, never let one failure kill the pipeline
    all_steps: list[dict] = []
    errors: list[str] = []

    # 0. Snapshot before search
    before = parse_raw_files()
    log(f"  スナップショット: {len(before)}件")

    # 1. Search all sites (partial success OK)
    search_results: list[dict] = []
    try:
        search_results = search_all_sites()
        all_steps.extend(search_results)
    except Exception as e:
        errors.append(f"search_all_sites: {e}")
        log(f"  ❌ 検索フェーズ全体エラー: {e} — 既存データで続行")

    # 1.5. Auto-retry failed search steps (timeout only, if time allows)
    if any(not s["ok"] and s.get("reason") == "timeout" for s in search_results):
        log("=== 失敗ステップ自動リトライ ===")
        retry_failed_searches(search_results, start)

    # 2. Diff properties (safe — pure computation)
    after = parse_raw_files()
    diff = diff_properties(before, after)
    log(f"  差分: 新規{len(diff['new'])}件, 消失{len(diff['removed'])}件")

    # 3. Update first-seen registry (non-critical)
    try:
        update_first_seen()
        all_steps.append({"step": "first_seen", "ok": True})
    except Exception as e:
        errors.append(f"first_seen: {e}")
        all_steps.append({"step": "first_seen", "ok": False, "reason": "crash",
                          "stderr_tail": str(e)})
        log(f"  ⚠️ first_seen更新失敗: {e} — 続行")

    # 4. Check dead URLs (non-critical, can be slow)
    url_report = {"total": 0, "dead": 0, "new_dead": 0}
    try:
        url_report = patrol_dead_urls()
        all_steps.append({"step": "url_check", "ok": True})
    except Exception as e:
        errors.append(f"url_check: {e}")
        all_steps.append({"step": "url_check", "ok": False, "reason": "crash",
                          "stderr_tail": str(e)})
        log(f"  ⚠️ URLチェック失敗: {e} — 続行")

    # 5. Generate reports (partial success OK — per-city isolation)
    try:
        report_results = generate_reports()
        all_steps.extend(report_results)
    except Exception as e:
        errors.append(f"generate_reports: {e}")
        log(f"  ❌ レポート生成全体エラー: {e} — デプロイは試行")

    # 5.5. Pipeline lifecycle: auto-flag + sweep stale + price tracking + agent sync
    try:
        from property_pipeline import auto_flag, generate_dashboard, generate_naiken_analysis, lifecycle
        auto_flag()
        all_steps.append({"step": "pipeline_flag", "ok": True})
        log("  Pipeline auto-flag 完了")
    except Exception as e:
        all_steps.append({"step": "pipeline_flag", "ok": False, "reason": "crash",
                          "stderr_tail": str(e)})
        log(f"  ⚠️ Pipeline auto-flag skipped: {e}")

    # 5.6. Lifecycle management (sweep stale + price tracking + agent memory sync)
    try:
        lc_result = lifecycle()
        all_steps.append({"step": "pipeline_lifecycle", "ok": True})
        log(f"  Pipeline lifecycle完了: {lc_result}")
    except Exception as e:
        all_steps.append({"step": "pipeline_lifecycle", "ok": False, "reason": "crash",
                          "stderr_tail": str(e)})
        log(f"  ⚠️ Pipeline lifecycle skipped: {e}")

    # 5.7. Regenerate dashboard (after flag + sync)
    try:
        generate_dashboard()
        all_steps.append({"step": "pipeline_dashboard", "ok": True})
        log("  Pipeline dashboard生成完了")
    except Exception as e:
        all_steps.append({"step": "pipeline_dashboard", "ok": False, "reason": "crash",
                          "stderr_tail": str(e)})
        log(f"  ⚠️ Pipeline dashboard skipped: {e}")

    # 5.8. Regenerate naiken analysis (viewing properties → comparison page)
    try:
        generate_naiken_analysis()
        all_steps.append({"step": "naiken_analysis", "ok": True})
        log("  内覧分析レポート生成完了")
    except Exception as e:
        all_steps.append({"step": "naiken_analysis", "ok": False, "reason": "crash",
                          "stderr_tail": str(e)})
        log(f"  ⚠️ 内覧分析レポート skipped: {e}")

    # 6. QA Gate — verify output HTML before deploy
    try:
        import sys as _sys
        _sys.path.insert(0, str(BASE_DIR.parent / "lib"))
        from qa_output import check_directory
        qa_checked, qa_failed, qa_messages = check_directory(OUTPUT_DIR)
        if qa_failed > 0:
            log(f"  ❌ QA Gate FAILED ({qa_failed}件) — デプロイをブロック")
            for m in qa_messages:
                log(f"    {m}")
            all_steps.append({"step": "qa_gate", "ok": False, "reason": "qa_failed",
                              "stderr_tail": "; ".join(qa_messages[:3])})
        else:
            log(f"  ✓ QA Gate PASSED ({qa_checked}ファイル)")
            all_steps.append({"step": "qa_gate", "ok": True})
    except Exception as e:
        log(f"  ⚠️ QA Gate error (non-blocking): {e}")
        all_steps.append({"step": "qa_gate", "ok": True})  # non-blocking if qa_output missing

    # 7. Deploy (only if QA passed or QA unavailable)
    qa_ok = next((s for s in all_steps if s["step"] == "qa_gate"), {}).get("ok", True)
    if not qa_ok:
        log("  ⏭ デプロイスキップ（QA失敗）")
        all_steps.append({"step": "deploy", "ok": False, "reason": "qa_blocked",
                          "stderr_tail": "QA Gate blocked deploy"})
    else:
        try:
            deploy()
            all_steps.append({"step": "deploy", "ok": True})
        except Exception as e:
            errors.append(f"deploy: {e}")
            all_steps.append({"step": "deploy", "ok": False, "reason": "crash",
                              "stderr_tail": str(e)})
            log(f"  ❌ デプロイ失敗: {e}")

    elapsed = (datetime.now() - start).total_seconds()

    # Resilience summary
    ok_count = sum(1 for s in all_steps if s.get("ok"))
    fail_count = sum(1 for s in all_steps if not s.get("ok"))
    failed_names = [s["step"] for s in all_steps if not s.get("ok")]

    if fail_count == 0:
        log(f"===== 完了 ({elapsed:.0f}秒) 全{ok_count}ステップ成功 =====")
    else:
        log(f"===== 部分完了 ({elapsed:.0f}秒) {ok_count}/{ok_count + fail_count}成功, 失敗: {', '.join(failed_names)} =====")

    # Write structured summary (always — even on partial failure)
    try:
        save_patrol_summary(start, elapsed, diff, url_report, all_steps=all_steps)
    except Exception as e:
        log(f"  ❌ save_patrol_summary crashed: {e}")
        # Emergency fallback: write minimal summary so downstream never sees stale data
        try:
            minimal = {
                "date": start.strftime("%Y-%m-%d %H:%M"),
                "step_count": len(all_steps),
                "ok_count": sum(1 for s in all_steps if s.get("ok")),
                "elapsed_min": round(elapsed / 60),
                "new_count": 0, "total": 0, "failed_steps": [],
                "failure_details": [], "new_items": [],
                "error": f"save_patrol_summary crash: {e}",
            }
            (BASE_DIR / "data" / "patrol_summary.json").write_text(
                json.dumps(minimal, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass  # truly nothing we can do


if __name__ == "__main__":
    main()
