# HANDOFF

## 最終更新: 2026-02-26（セッション80）

## 完了済み（直近セッション80）
- **CLAUDE.md圧縮+強化**: 303→288行。Compact InstructionsをPro Planに統合、Codex Delegationを圧縮
- **Autonomous QAセクション追加**: デプロイ後URL検証・デザイン横断比較・データ品質チェック・モバイル検証の自律チェック体制
- **Self-Improvement昇格ルール追加**: 同種ミス2回以上 → tasks/lessons.mdからCLAUDE.mdに恒久ルール化
- **Task/Subagent活用ルール追加**: メインコンテキスト温存+トークン節約のため、並列調査・大量探索時は積極提案
- **プロジェクトセレクター改善**: `c` コマンドに最近使用フィルタ追加（RECENT_DAYS=3）、HIDDEN_PROJECTS、`c -a` で全表示
- **dotfiles/.zshrc → ~/.zshrc同期**: _project_last_used関数、HIDDEN_PROJECTS、RECENT_DAYS追加

## 完了済み（前セッション78-79）
- カウカモparser修正 + Yahoo parser全面書き換え + 管理費enrichment + 厳選フィルタ
- 統合ランディングページ + サイト構造修正 + デザイン統一 + スマホ対応 + daikoku削除

## 完了済み（過去セッション）
- SUUMO管理費enrichment修正 + QA自動化 + スコア2文字ラベル（77）
- スコア内訳UI改善 + 内覧分析ページ作成（76）
- 管理費スコアリング + ペット不可ハードフィルタ + ランディングページ（75）
- 楽待pmax修正 + 全3都市再検索 + 売却済/OC除外（74）
- f-takkenリンク修正 + R不動産 + 東京版 + 億超えパース修正（73）
- フルオートパイプライン構築（68）
- マルチソース検索 + f-takkenスクレイパー（67）

## 進行中 / 未完了
- #1 扇町の民泊可否 — **2026-02-25内覧予定。大嶺さんに直接確認する**
- **athome CAPTCHA** — 認証パズル（認証中）でHTTP/Playwright両方ブロック。解決策なし
- Webレポート v2（公開用・プライバシー対策版）の設計・実装
- ポートフォリオダッシュボードの数値確定

## 次回アクション（優先順）
1. **daily patrol定期実行設定** — cron / GitHub Actions で毎日自動巡回
2. **内覧結果の反映** — 扇町・天満橋の内覧結果をデータに反映
3. **athome代替策検討** — CAPTCHA回避不可。別サイト（LIFULL等）の追加を検討
4. **Yahoo大阪改善** — 現在1件のみ（297件中ターゲットエリア内1件）。エリア条件見直し
5. フルオートパイプラインのGitHub Actions化
6. `.gitignore` に `data/*_debug*.html` を追加
7. **dotfiles symlink化検討** — ~/dotfiles/.zshrc → ~/.zshrc のシンボリックリンク化

## Key Decisions
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
- 2026-02-20 セッション63: FinancialProfile統合コミット
