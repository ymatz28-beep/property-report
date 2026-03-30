#!/usr/bin/env python3
"""Export Rakumachi cookies from Chrome to Netscape cookie file format.

Usage:
  1. Log in to rakumachi.jp in Chrome
  2. Run: python export_rakumachi_cookies.py
  3. Cookie file saved to data/cookies_rakumachi.txt

Requires: pip install browser-cookie3
"""
from __future__ import annotations

from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
COOKIE_FILE = DATA_DIR / "cookies_rakumachi.txt"
DOMAIN = "rakumachi.jp"


def export_via_browser_cookie3() -> int:
    """Extract rakumachi cookies using browser-cookie3 (handles macOS Keychain decryption)."""
    try:
        import browser_cookie3
    except ImportError:
        print("[ERROR] browser-cookie3 not installed: pip install browser-cookie3")
        return 0

    try:
        cj = browser_cookie3.chrome(domain_name=DOMAIN)
    except Exception as e:
        print(f"[ERROR] Chrome cookie access failed: {e}")
        print("  → Chromeが起動中の場合は閉じてからリトライ")
        return 0

    cookies = [c for c in cj if DOMAIN in c.domain]
    if not cookies:
        print("[WARN] No rakumachi cookies found. Chromeでログインしてください")
        return 0

    lines = ["# Netscape HTTP Cookie File", "# https://curl.se/docs/http-cookies.html"]
    for c in cookies:
        domain = c.domain
        # Netscape format: domain_specified = TRUE if domain starts with "."
        domain_flag = "TRUE" if domain.startswith(".") else "FALSE"
        secure = "TRUE" if c.secure else "FALSE"
        expires = str(c.expires) if c.expires else "0"
        lines.append(f"{domain}\t{domain_flag}\t{c.path}\t{secure}\t{expires}\t{c.name}\t{c.value}")

    COOKIE_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[OK] {len(cookies)}個のCookieを保存: {COOKIE_FILE}")
    return len(cookies)


def verify_cookies() -> bool:
    """Test if cookies work by fetching a known detail page that normally returns 403."""
    if not COOKIE_FILE.exists():
        return False
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import search_yield_focused
    search_yield_focused._opener = None  # Reset to reload cookies

    from search_yield_focused import fetch_page

    # Test: fetch a detail page (these normally return 403 without auth)
    # Use a known fukuoka property
    test_urls = []
    yield_file = DATA_DIR / "yield_fukuoka_raw.txt"
    if yield_file.exists():
        for line in yield_file.read_text(encoding="utf-8").splitlines():
            if "rakumachi.jp" in line and "/show.html" in line:
                parts = line.split("|")
                if len(parts) >= 12:
                    test_urls.append(parts[11].strip())
                if len(test_urls) >= 1:
                    break

    if not test_urls:
        print("[WARN] テスト用URLが見つからない")
        return False

    url = test_urls[0]
    print(f"  テスト: {url[:70]}...")
    html = fetch_page(url)
    if html and len(html) > 5000 and ("現況" in html or "想定年間収入" in html):
        print("[OK] Cookie認証テスト成功 — 詳細ページ取得可能")
        return True
    elif html and len(html) > 1000:
        print("[WARN] ページは取得できたが詳細情報が不十分 — ログインセッション不完全？")
        return False
    else:
        print("[FAIL] 詳細ページ取得失敗 — ログインセッションが切れている可能性")
        return False


if __name__ == "__main__":
    print("=== 楽待Cookie Export ===")
    count = export_via_browser_cookie3()
    if count == 0:
        print("\n手動エクスポート手順:")
        print("  1. Chromeで rakumachi.jp にログイン")
        print("  2. Chrome拡張 'Get cookies.txt LOCALLY' をインストール")
        print("  3. rakumachi.jp上で拡張を実行、Netscape形式でエクスポート")
        print(f"  4. ファイルを {COOKIE_FILE} に保存")
    else:
        verify_cookies()
