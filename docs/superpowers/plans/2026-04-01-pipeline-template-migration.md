# Pipeline + 内覧分析 テンプレート移行計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pipeline Dashboard と Naiken Analysis の2ページを、インラインCSS（f-string）からJinjaテンプレートシステムに移行し、market.htmlと同じデザイントークン・コンポーネントを共有する

**Architecture:** `lib/templates/pages/` にテンプレートファイルを作成し、`lib/renderer.py` の `render()` で描画する。property_pipeline.pyはデータ準備のみに専念し、HTML生成はテンプレートに委譲する。既存のcard/analysis生成ヘルパー関数はJinja macroに段階的に置換。

**Tech Stack:** Jinja2, Python, CSS (design tokens)

---

## Phase 1: Pipeline Dashboard テンプレート化（影響範囲が小さい方から）

### Task 1: テンプレートファイル作成（空の骨格）

**Files:**
- Create: `lib/templates/pages/pipeline.html`

- [ ] **Step 1: 空テンプレートを作成**

```html
{% extends "base.html" %}

{% block title %}Pipeline{% endblock %}

{% block nav %}
{{ super() }}
{% include "components/gnav.html" %}
{% endblock %}

{% block styles %}
/* Pipeline-specific CSS — Phase 1 ではインラインCSSをそのままコピー */
{% endblock %}

{% block content %}
<div class="container" style="max-width:720px;margin:0 auto;padding:16px 12px">
  <h1>テンプレートテスト</h1>
  <p>物件数: {{ inquiries | length }}</p>
</div>
{% endblock %}
```

- [ ] **Step 2: render() で描画するテスト関数を追加**

`property_pipeline.py` の末尾に一時関数を追加:

```python
def _test_template_render():
    """Temporary: verify template renders."""
    from lib.renderer import render
    inquiries = load_inquiries()
    html = render("pages/pipeline.html", {
        "inquiries": inquiries,
        "gnav_pages": GNAV_PAGES,
        "gnav_current": "Pipeline",
    }, scope="public")
    test_path = OUTPUT / "pipeline-template-test.html"
    test_path.write_text(html, encoding="utf-8")
    print(f"[test] Template rendered → {test_path}")
```

`GNAV_PAGES` は `generate_market.py` から import するか、`property_pipeline.py` 内に定義。

- [ ] **Step 3: テスト実行**

Run: `.venv/bin/python3 -c "from property_pipeline import _test_template_render; _test_template_render()"`
Expected: `output/pipeline-template-test.html` が生成され、ブラウザで開くとgnav付きの空ページが表示される

- [ ] **Step 4: ブラウザ確認 & commit**

```bash
open output/pipeline-template-test.html
git add lib/templates/pages/pipeline.html property_pipeline.py
git commit -m "feat(pipeline): scaffold Jinja template for pipeline dashboard"
```

---

### Task 2: CSSをテンプレートに移植

**Files:**
- Modify: `lib/templates/pages/pipeline.html`
- Reference: `property_pipeline.py` lines 1910-1977（現在のインラインCSS）

- [ ] **Step 1: 現在のダッシュボードCSSをテンプレートの `{% block styles %}` にコピー**

`property_pipeline.py` の `generate_dashboard()` 内にある `.hero`, `.stats`, `.section-nav`, `.city-section`, `.inq-card` 等のCSSを、テンプレートの `{% block styles %}` に移植する。

注意: f-string の `{{` `}}` を Jinja では `{` `}` に戻す（CSS中の波括弧）。

- [ ] **Step 2: テスト実行して正しくレンダリングされるか確認**

Run: `.venv/bin/python3 -c "from property_pipeline import _test_template_render; _test_template_render()"`

- [ ] **Step 3: commit**

```bash
git add lib/templates/pages/pipeline.html
git commit -m "feat(pipeline): migrate CSS to Jinja template"
```

---

### Task 3: HTMLコンテンツをテンプレートに移植

**Files:**
- Modify: `lib/templates/pages/pipeline.html`
- Modify: `property_pipeline.py` — `generate_dashboard()` 関数

- [ ] **Step 1: テンプレートにコンテンツブロックを追加**

`{% block content %}` 内に、現在 `generate_dashboard()` がf-stringで組み立てているHTML構造を移植:
- Hero セクション（統計表示）
- Section Nav（都市タブ）
- 都市ごとのカードリスト

カード個別のHTMLは `_render_card()` が返す文字列をそのまま `{{ card_html | safe }}` で注入する（段階的移行のため、カードのJinja化はPhase 3に回す）。

- [ ] **Step 2: generate_dashboard() をテンプレート呼び出しに書き換え**

```python
def generate_dashboard() -> Path:
    from lib.renderer import render
    inquiries = load_inquiries()
    
    # データ準備（既存のロジックをそのまま維持）
    # ... 都市グループ化、カードHTML生成など ...
    
    # テンプレート描画
    html = render("pages/pipeline.html", {
        "inquiries": inquiries,
        "city_sections": city_sections,  # pre-rendered HTML per city
        "stats": stats_dict,
        "gnav_pages": GNAV_PAGES,
        "gnav_current": "Pipeline",
    }, scope="public")
    
    out = OUTPUT / "inquiry-pipeline.html"
    out.write_text(html, encoding="utf-8")
    return out
```

- [ ] **Step 3: テスト — 既存ダッシュボードと同じ見た目になるか確認**

Run: `.venv/bin/python3 property_pipeline.py --dashboard`
Then: `open output/inquiry-pipeline.html`

旧出力と比較して見た目が同じであることを確認。

- [ ] **Step 4: テスト関数を削除、commit**

```bash
git add lib/templates/pages/pipeline.html property_pipeline.py
git commit -m "feat(pipeline): migrate dashboard HTML to Jinja template"
```

---

## Phase 2: Naiken Analysis テンプレート化

### Task 4: Naikenテンプレート骨格作成

**Files:**
- Create: `lib/templates/pages/naiken.html`

- [ ] **Step 1: 空テンプレートを作成**

Phase 1のpipeline.htmlと同じパターン。`{% extends "base.html" %}`。

- [ ] **Step 2: CSSをテンプレートに移植**

`property_pipeline.py` lines 1714-1770 のインラインCSSを `{% block styles %}` にコピー。

- [ ] **Step 3: テスト実行**

一時テスト関数でレンダリング確認。

- [ ] **Step 4: commit**

```bash
git add lib/templates/pages/naiken.html
git commit -m "feat(naiken): scaffold Jinja template with CSS"
```

---

### Task 5: NaikenコンテンツをHTMLテンプレートに移植

**Files:**
- Modify: `lib/templates/pages/naiken.html`
- Modify: `property_pipeline.py` — `generate_naiken_analysis()` 関数

- [ ] **Step 1: テンプレートにコンテンツブロック追加**

- スケジュールバナー
- 物件カード（`_naiken_invest_analysis` 等のヘルパーが返すHTMLを `{{ section_html | safe }}` で注入）
- 共通確認事項
- アーカイブ折りたたみ

- [ ] **Step 2: generate_naiken_analysis() をテンプレート呼び出しに書き換え**

Pipeline Dashboardと同じパターン: データ準備 → `render()` 呼び出し。

- [ ] **Step 3: テスト — 既存出力と見た目比較**

Run: `.venv/bin/python3 property_pipeline.py --naiken`
Then: `open output/naiken-analysis.html`

- [ ] **Step 4: commit**

```bash
git add lib/templates/pages/naiken.html property_pipeline.py
git commit -m "feat(naiken): migrate analysis page to Jinja template"
```

---

## Phase 3: 旧インラインCSS関数の廃止 & カードのJinja化（任意）

### Task 6: site_header / global_nav のインライン関数を廃止

**Files:**
- Modify: `property_pipeline.py` — `site_header_css()` / `global_nav_css()` の import を削除
- Modify: `generate_search_report_common.py` — 関数が他で使われていなければ削除

- [ ] **Step 1: property_pipeline.py から旧import文を削除**

テンプレートが `{% include "components/nav.html" %}` で処理するため、`site_header_html()` 等のPython関数呼び出しは不要になる。

- [ ] **Step 2: 他ファイルで使用されていないか確認**

Run: `grep -r "site_header_html\|site_header_css\|global_nav_css\|global_nav_html" --include="*.py" .`

使用箇所が property_pipeline.py のみなら安全に削除可能。

- [ ] **Step 3: commit**

```bash
git commit -m "refactor: remove legacy inline CSS functions from pipeline"
```

---

### Task 7: _render_card() をJinja macroに変換（任意・大きめ）

**Files:**
- Create: `lib/templates/components/pipeline_card.html`
- Modify: `lib/templates/pages/pipeline.html`
- Modify: `property_pipeline.py` — `_render_card()` 関数を削除

この Task はオプション。Phase 1-2が完了して安定してから実施。
`_render_card()` と `_render_card_analysis()` をJinja macroに変換し、テンプレート内で `{% for inq in inquiries %}{{ pipeline_card(inq) }}{% endfor %}` で呼び出す形にする。

---

## 実行順序と安全性

| Phase | Task | 所要時間目安 | ロールバック |
|-------|------|------------|------------|
| 1 | Task 1: 骨格作成 | 5min | テンプレートファイル削除で即復元 |
| 1 | Task 2: CSS移植 | 10min | テンプレートファイル削除で即復元 |
| 1 | Task 3: HTML移植 | 20min | `git revert` で旧generate_dashboardに復元 |
| 2 | Task 4: Naiken骨格 | 5min | テンプレートファイル削除で即復元 |
| 2 | Task 5: Naiken移植 | 20min | `git revert` で旧generate_naikenに復元 |
| 3 | Task 6: 旧関数廃止 | 5min | commit revert |
| 3 | Task 7: カードmacro化 | 30min | 任意、後日でOK |

**各Phase完了時にブラウザで目視確認 + commit。Phaseごとに独立しており、途中で止めても壊れない。**
