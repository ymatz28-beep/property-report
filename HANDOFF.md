# HANDOFF

## [Constancy] 2026-03-30
- [WARN] hardcoded_data: Large inline data (91 lines) at line 36. Consider externalizing to YAML/JSON.
- [WARN] structural_reform: property_pipeline.py is 1800+ lines (threshold: 800). Consider splitting.
- [WARN] property_patrol_steps: 物件パトロール失敗ステップ (2026-03-30 06:37): 【F宅建検索】タイムアウト (5分超過) → Fix: エラーログを確認
- [WARN] blank_cells: ダッシュ「—」320個 (閾値20) — データ欠損の可能性
- [WARN] numeric_outliers: 利回り: 異常値 1件 — 30.7>25
- [WARN] first_seen_coverage: 掲載日カバレッジ 59% (114/193) — 閾値80%
- [ERROR] data_accuracy: スクレイプデータとHTMLレンダリングの不一致率 12.3% (22/179件)

## Last Updated
2026-03-31

## Completed (パイプライン形骸化解消 — lifecycle自動管理 + メール連動 + UI刷新 2026-03-31)
- **Before**: パイプライン76件中67件が`flagged`のまま放置。`pipeline.html`(旧)と`inquiry-pipeline.html`(新)が重複。マーケットデータ・メール返信との連動なし。in_discussion 3件が返信なしのまま残存。広告コピー名が3件混入
- **After**:
  - **Lifecycle自動管理**: `sweep_stale()`で掲載終了/未返信14日/停滞14日/エイジアウト30日/スコア70未満を自動パス。`track_price_changes()`で価格変動検出(10%以上値下げは🔥通知)。`--lifecycle` CLIコマンド追加
  - **メール連動**: reply_assistがproperty email処理後、`property_pipeline.py --sync`を非同期Popenトリガー
  - **日次パトロール統合**: run_daily_patrol.pyステップ5.6に`lifecycle()`組み込み
  - **UI刷新**: KPIカード=アクティブのみ(進行中/内見/内見済/決定)。flaggedは折りたたみ、passedは非表示。各カードに投資分析折りたたみ(▸ 想定賃料/利回り/CF/CCR/回収年数)。inquiredに「未返信 X日」バッジ、in_discussionに「動きなし X日」バッジ
  - **旧パイプライン廃止**: `generate_pipeline.py` + `lib/templates/pages/pipeline.html` + `output/pipeline.html` 削除。全navリンクを`inquiry-pipeline.html`に統一
  - **広告コピー名修正**: inquiries.yaml 3件修正 + `_clean_property_name()`で今後のauto_flag時に自動クリーニング + `search_multi_site.py`楽待パーサーに広告コピー検出追加
  - **in_discussion 3件パス**: 博多ニッコーハイツ/クリオ渡辺通/ニューライフ薬院 → 返信なし・内覧予定なしで見送り
  - **初回lifecycle実行結果**: 掲載終了1件+低スコア7件自動パス、価格変動8件検出
- **変更ファイル**: property_pipeline.py, reply_assist.py, run_daily_patrol.py, generate_market.py, search_multi_site.py, inquiries.yaml
- **削除**: generate_pipeline.py, lib/templates/pages/pipeline.html, output/pipeline.html

## Completed (取得諸費用計上 + 掲載日クリーンアップ + 福岡格安デバッグ 2026-03-30)
- **Before**: revenue_calc.pyが取得諸費用（登記+取得税+仲介+印紙+司法書士）を未計上。CCR・回収年数の分母が頭金のみ。first_seen.jsonに不正確なバックフィル日付（2/22, 2/23, 2/26, 3/1）が1,644件混入。福岡格安区分が一時的に25件→12件に減少
- **After**: revenue_calc.pyに取得諸費用7%を追加、CCR・回収年数の分母を「頭金+諸費用」に修正。market.htmlテンプレートを「初期必要資金（頭金+諸費用）」表示に変更。不正確な掲載日1,644件を除去。福岡格安は`_load_budget`自体が25件正常出力を確認

## Completed (kaizen Visual Regression チェック追加 2026-03-29 x-ref)
- **Before**: HTMLレポートのレイアウト崩れを検知する仕組みがなく目視頼み
- **After**: Playwright headless Chromiumで全HTMLをmobile+desktopでレンダリングし5項目チェック

## In Progress / Next Actions
1. **未コミットファイルpush**: property_pipeline.py, reply_assist.py, run_daily_patrol.py, generate_market.py, search_multi_site.py, inquiries.yaml等の変更をcommit+push+deploy
2. **F宅建広告コピー名防御**: search_ftakken.pyにも`_is_fallback_name`相当の広告コピー検出を追加（現在はrawデータは正しいが、掲載タイトルが変わる可能性あり）
3. **property_pipeline.py分割**: 1800+行。lifecycle/dashboard/naiken等のモジュール分離を検討
4. **パイプライン候補59件の精査**: スコア70+だが30日以内の物件。問い合わせ送信 or 見送り判断
5. **viewed 4件のアーカイブ判断**: アンピール天神東(considering)/プレイスポットしんばし/GSハイム博多/ローズマンション博多 → 検討継続 or 見送り
6. **GitHub Pages反映**: push後Cmd+Shift+Rでハードリロード確認

## Key Decisions
- 2026-03-31: **Pipeline Anti-Stale Pattern**: 自動Sweep/アクティブのみ表示/外部連動/カード内分析インライン → memory保存済み、全プロジェクト横展開
- 2026-03-31: **旧pipeline.html廃止**: inquiry-pipeline.htmlがSSoT。generate_pipeline.py削除
- 2026-03-31: **sweep閾値**: 未返信14日/停滞14日/エイジアウト30日/スコア70未満
- 2026-03-31: **内覧予定なし**: 当面内見しない方針。in_discussion全件パス

## Blockers
- なし

## Environment
- Python: `stock-analyzer/.venv/bin/python3`
- Deploy: push to main → GHA auto-deploy to gh-pages
- Live URL: https://ymatz28-beep.github.io/property-report/

## History (last 20)
1. 2026-03-31: パイプライン形骸化解消 — lifecycle + メール連動 + UI刷新 + 旧パイプライン廃止
2. 2026-03-30: 取得諸費用計上 + 掲載日クリーンアップ + 福岡格安デバッグ
3. 2026-03-30: kaizen自律修正Phase A+C — 修正率1%→自動修正+commit
4. 2026-03-29: kaizen Visual Regression チェック追加
5. 2026-03-29: 有識者的中率3層ティアリング
6. 2026-03-28: main→gh-pages自動デプロイworkflow追加
7. 2026-03-28: ふれんず物件名詳細取得 + 管理費/修繕分離
8. 2026-03-28: Market sticky section nav + section_navコンポーネント横展開
9. 2026-03-27: 楽待スクレイパー詳細ページ構造化抽出
10. 2026-03-26: 収益物件(yield)ページ新規作成
11. 2026-03-25: 特区民泊候補物件調査
12. 2026-03-24: 筑波銀行融資打診メール送信
13. 2026-03-23: 内見分析ページアーカイブ機能
14. 2026-03-22: inquiry-pipeline dashboard作成
15. 2026-03-21: 福岡内見3物件（アンピール天神東/コスモ博多古門戸/クリオラベルヴィ呉服町）
16. 2026-03-20: agent_memory SSoT確立 + pipeline sync
17. 2026-03-19: Property Inquiry Pipeline構築 + Reply Assist Agent Memory構築
18. 2026-03-18: GHA patrol Gmail通知
19. 2026-03-17: 格安区分スコアリング導入
20. 2026-03-16: 一棟もの収益シミュレーター(revenue_calc.py)
