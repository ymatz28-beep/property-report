# HANDOFF

## 最終更新: 2026-02-26（セッション86）

## 完了済み（直近セッション86）
- （作業なし — Prompt is too longエラーで全リクエスト失敗。画像貼付+長大コンテキストが原因）

## 完了済み（前セッション84-85）
- **git pushエラー(exit 128)修正** — credential.helper + .git-credentials手動設定を削除。actions/checkout@v4の組み込み認証に任せる。git configもlocalに変更。データ変更がない場合はpushスキップするよう改善

## 完了済み（過去セッション）
- Daily Patrol GitHub Actions 稼働確認完了（24分41秒） + CI最適化（SOLDスキップ/タイムアウト調整/PYTHONUNBUFFERED） + gh auth workflow追加 + デフォルトブランチmain化（82）
- GitHub Actions daily-patrol.yml作成 + deploy()2重実行修正 + requirements.txt更新 + セッション74-80蓄積一括push（81）
- CLAUDE.md圧縮+強化、Autonomous QA、Self-Improvement昇格ルール、Subagent活用ルール、プロジェクトセレクター改善（80）
- カウカモparser修正 + Yahoo parser全面書き換え + 管理費enrichment + 厳選フィルタ + 統合ランディングページ + サイト構造修正 + デザイン統一 + スマホ対応 + daikoku削除（78-79）
- SUUMO管理費enrichment修正 + QA自動化 + スコア2文字ラベル（77）
- スコア内訳UI改善 + 内覧分析ページ作成（76）
- 管理費スコアリング + ペット不可ハードフィルタ + ランディングページ（75）
- 楽待pmax修正 + 全3都市再検索 + 売却済/OC除外（74）
- f-takkenリンク修正 + R不動産 + 東京版 + 億超えパース修正（73）
- フルオートパイプライン構築（68）
- マルチソース検索 + f-takkenスクレイパー（67）

## 進行中 / 未完了
- **Gmail通知認証エラー** — `535 BadCredentials`。アプリパスワードをスペースなし16文字で再設定必要（`gh secret set GMAIL_APP_PASSWORD`）
- **LINE通知未設定** — LINE Developers登録 + Messaging APIチャネル作成 + Secrets追加が必要（LINE_CHANNEL_TOKEN, LINE_USER_ID）
- #1 扇町の民泊可否 — **2026-02-25内覧予定。大嶺さんに直接確認する**
- **athome CAPTCHA** — 認証パズル（認証中）でHTTP/Playwright両方ブロック。解決策なし
- Webレポート v2（公開用・プライバシー対策版）の設計・実装
- ポートフォリオダッシュボードの数値確定

## 次回アクション（優先順）
1. **Gmail通知修正** — アプリパスワード再発行（https://myaccount.google.com/apppasswords）→ スペース除去して`gh secret set GMAIL_APP_PASSWORD` → workflow_dispatchでテスト
2. **内覧結果の反映** — 扇町・天満橋の内覧結果をデータに反映
3. **LINE通知設定** — LINE Developers登録 → Messaging APIチャネル作成 → Secrets追加
4. **athome代替策検討** — CAPTCHA回避不可。別サイト（LIFULL等）の追加を検討
5. **patrol横展開** — stock-analyzerに同パターン（データ取得→レポート生成→gh-pagesデプロイ）のGitHub Actionsを横展開（改善アイデア）

## Key Decisions
- **git push修正**: actions/checkout@v4の組み込み認証を使う。手動credential helper設定は不要かつ競合する
- **通知はcontinue-on-error: true** — Secrets未設定でもパトロール本体に影響なし。Gmail/LINE片方だけでもOK
- 物件購入は法人（iUMAプロパティマネジメント）優先
- **サイト構造**: report-dashboard（統合ハブ）→ property-report（不動産のみ）/ trip-planner（旅行のみ）/ stock/portfolio.html（株）。各サブサイトに← Dashboardリンク
- **デザイン言語**: DM Serif Display + Outfit + JetBrains Mono。ダークBG #050507、グレインテクスチャ、アニメーションorb。カテゴリ別アクセント: 不動産 #3b9eff / 旅行 #ff6b35 / 株 #8b5cf6
- **SSF設計**: CATEGORIES配列駆動。新カテゴリ追加 = 1オブジェクト追加するだけ
- ペット不可: ハードフィルタで完全除外
- 厳選フィルタ: MIN_SCORE=30 + MAX_DISPLAY=50 + ペット可優先
- 管理費enrichment: 楽待+カウカモの詳細ページから取得（enrich_maintenance.py）
- 楽待の価格パラメータ（pmin/pmax）は万円単位
- **deploy_to_gh_pages()にはgit config user設定が必須**
- **レポート更新後は自律的にQAを実行する**
- **デプロイ後は必ずWebで反映を確認する**
- 特区民泊の新規受付は2026年5月29日終了
- **同種ミス2回以上はCLAUDE.mdに昇格して恒久ルール化する**
- **property-reportのデフォルトブランチはmain**（GitHub Actions認識のため変更済み。gh-pagesはデプロイ専用）
- **gh auth にworkflowスコープ追加済み** — ワークフローファイルをローカルから直接push可能

## ブロッカー / 注意事項
- **特区民泊の新規受付は2026年5月29日で終了** → 残り約3ヶ月
- #1 扇町の民泊可否が最重要の未確認事項
- athome全都市でCAPTCHA認証ブロック（解決不可）
- Yahoo大阪はターゲットエリア内1件のみ
- DTI約61.7% → 個人追加融資困難。法人融資で対応
- ~/dotfiles/.zshrcと~/.zshrcが別ファイル（未symlink）。編集時は両方更新必要

## 環境構築メモ (PC交換用)
- Python 3.13
- `pip install -r requirements.txt`（anthropic, pyyaml, openpyxl, reportlab, Pillow, numpy, requests, beautifulsoup4, playwright）
- `playwright install chromium`
- 環境変数: ANTHROPIC_API_KEY
- GitHub Pages:
  - `report-dashboard` — 統合ハブ（gh-pagesブランチ）: https://ymatz28-beep.github.io/report-dashboard/
  - `property-report` — 不動産（gh-pagesブランチ）: https://ymatz28-beep.github.io/property-report/
  - `trip-planner` — 旅行（mainブランチ）: https://ymatz28-beep.github.io/trip-planner/
- `gh` CLI でデプロイ

## History
- 2026-02-26 セッション86: Prompt is too longエラーで作業不可（画像+長大コンテキスト。2セッション連続）
- 2026-02-26 セッション85: Prompt is too longエラーで作業不可（画像貼付が原因の可能性）
- 2026-02-26 セッション84: git pushエラー修正（credential helper競合解消 + 条件付きpush）
- 2026-02-26 セッション83: Gmail+LINE通知追加 + テスト実行成功(25m5s) + Gmail認証エラー発覚(BadCredentials) + git pushエラー(exit 128)
- 2026-02-26 セッション82: Daily Patrol GitHub Actions稼働確認完了(24m41s) + CI最適化(SOLDスキップ/タイムアウト調整/PYTHONUNBUFFERED) + gh auth workflow追加 + デフォルトブランチmain化
- 2026-02-26 セッション81: GitHub Actions daily-patrol作成 + deploy()2重実行修正 + requirements.txt更新 + セッション74-80蓄積一括push
- 2026-02-26 セッション80: CLAUDE.md圧縮(303→288行) + Autonomous QA + Self-Improvement昇格ルール + Subagent活用ルール + プロジェクトセレクター改善(c -a, HIDDEN, RECENT_DAYS)
- 2026-02-26 セッション78-79: カウカモparser修正 + Yahoo parser全面書き換え + 管理費enrichment + 厳選フィルタ + 統合ランディングページ + サイト構造修正 + デザイン統一 + スマホ対応 + daikoku削除
- 2026-02-25 セッション77: SUUMO管理費enrichmentスクリプト修正 + QA自動化 + スコア2文字ラベル
- 2026-02-25 セッション76: スコア内訳UI改善 + 内覧分析ページ作成 + Hub追加 + デプロイ
- 2026-02-25 セッション75: 管理費スコアリング + ペット不可ハードフィルタ + ランディングページ + デプロイ修正
- 2026-02-24 セッション74: HANDOFF更新（セッション73トランスクリプトからの反映）
- 2026-02-23 セッション73: リンク修正 + R不動産統合 + ペット/OC/駅距離/エリアスコア修正 + 東京版作成
- 2026-02-22 セッション68: フルオートパイプライン構築
- 2026-02-22 セッション67: マルチソース検索 + f-takkenスクレイパー
- 2026-02-22 セッション66: 大阪・福岡レポート + 民泊スコアリング
- 2026-02-21 セッション65: 重要事項調査報告書分析
- 2026-02-21 セッション64: SEARCH_CRITERIA.md作成
