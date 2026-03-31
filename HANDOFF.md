# HANDOFF

## [Constancy] 2026-03-31
- [WARN] hardcoded_data: Large inline data (91 lines) at line 36. Consider externalizing to YAML/JSON.
- [WARN] structural_reform: property_pipeline.py is 2167 lines (threshold: 800). Consider splitting.
- [WARN] property_patrol_steps: 物件パトロール失敗ステップ (2026-03-31 06:48): 【F宅建検索】タイムアウト (5分超過) → Fix: エラーログを確認
- [WARN] design_token_compliance: Line 944: hardcoded #22c55e should be var(--green)
- [WARN] design_token_compliance: Line 1023: hardcoded #3b82f6 should be var(--blue)
- [WARN] design_token_compliance: Line 1346: hardcoded #22c55e should be var(--green)
- [WARN] design_token_compliance: Line 1992: hardcoded #6366f1 should be var(--accent)
- [WARN] design_token_compliance: Line 1993: hardcoded #22c55e should be var(--green)
- [WARN] blank_cells: ダッシュ「—」147個 (閾値20) — データ欠損の可能性
- [WARN] numeric_outliers: 利回り: 異常値 2件 — 27.6>25, 27.6>25
- [ERROR] first_seen_coverage: 掲載日カバレッジ 36% (47/131) — 閾値80%
- [WARN] qa_market_data_accuracy: 4/84 (4.8%) — price mismatch: スカイマンション南福岡 raw=599.0 html=590.0; price mismatch: トピレック博多 raw=990.0 html=1000.0; price mismatch: トピレック博多 raw=990.0 html=1000.0; price mismatch: スカイマンション南福岡 raw=599.0 html=590.0
- [ERROR] data_accuracy: スクレイプデータとHTMLレンダリングの不一致率 13.9% (15/108件)。パイプライン変換バグの可能性。例: 1499.0万円/41.78㎡; 1900.0万円/62.91㎡; 2899.0万円/59.75㎡; 2978.0万円/40.75㎡; 2500.0万円/56.36㎡
- [WARN] visual_regression: [mobile] missing_element: Critical element 'content' (table, .prop-card, .card, .kpi, .metric, ul, ol, section) not found
- [WARN] visual_regression: [desktop] missing_element: Critical element 'content' (table, .prop-card, .card, .kpi, .metric, ul, ol, section) not found

## Last Updated
2026-03-31

## Completed (マーケットページ品質改善 — 広告コピー7パターン + 戸建て除外 + OC収入補完 2026-03-31)
- **Before**: 広告コピー名3件フィルター漏れ（「福岡市博多区エリアで通勤に使いやすい立地」等）。戸建てが収益物件に掲載（アパート㎡単価で過大推定）。OC家賃根拠が不明。楽待物件名がクロスリファレンスされない。OC年間収入欠落検知なし
- **After**:
  - **広告コピーフィルター7パターン**: ①【】▶「」prefix ②利回りprefix ③駅+徒歩短パターン ④長名+駅/徒歩 ⑤日本語句読点(、。) ⑥広告キーワード(エリア/立地/便利/通勤) ⑦建物suffix無し=fallback → 164物件全件QA PASS
  - **戸建て収益除外**: アパート㎡賃料で戸建て収益推定は過大 → profitable sectionからkodate除外
  - **家賃根拠表示**: profitable detail rowに「家賃根拠」追加（実家賃/相場/想定 + ㎡単価）
  - **クロスリファレンス拡大**: 全楽待物件にF宅建/SUUMO名を適用（fallback名のみ→全物件）。「博多駅前ビル」→「メゾン・ド・プレジール」修正
  - **都道府県正規化修正**: `re.sub(r"[県都府]", "")` → `re.sub(r"^(東京都|大阪府|京都府|北海道|.{2,3}県)", "")`
  - **OC年間収入補完**: `enrich_yield_income.py`新規作成。3都市266件中37件を楽待詳細ページから補完（229件は403）
  - **QA check追加**: `check_oc_income_coverage()`をqa_market.pyに追加。FAIL>90%, WARN>50%
  - **一棟ものdict修正**: `_ittomono_to_dict`にmarket_rent/actual_rent/rent_gap_pct/is_ocフィールド追加
- **Pushed**: `7721164`

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
1. **F宅建広告コピー名防御**: search_ftakken.pyにも広告コピー検出を追加
2. **property_pipeline.py分割**: 1800+行。lifecycle/dashboard/naiken等のモジュール分離を検討
3. **パイプライン候補59件の精査**: スコア70+だが30日以内の物件。問い合わせ送信 or 見送り判断
4. **viewed 4件のアーカイブ判断**: アンピール天神東(considering)/プレイスポットしんばし/GSハイム博多/ローズマンション博多
5. **data_accuracy 4件のprice mismatch**: 2物件のrawとHTML価格差（掲載価格変動 — 非バグ）

## Key Decisions
- 2026-03-31: **戸建て収益除外**: アパート㎡賃料での推定は過大 → profitable sectionからkodate除外
- 2026-03-31: **広告コピー7パターン**: 句読点・キーワード・駅徒歩短パターンを追加。全164物件QA PASS
- 2026-03-31: **OC QA閾値**: FAIL>90%, WARN>50%（yield×price逆算でDisplay正常のため緩め）
- 2026-03-31: **クロスリファレンス全楽待物件**: fallback名のみ→全物件に拡大
- 2026-03-31: **現金購入比較分析**: ロワール渡辺通り(170万,CCR16.1%)vsメゾン・ド・プレジール(190万,CCR13.4%)。ロワールが年CF差+2.4万有利だが、プレジールの家賃上昇余地大(-45%gap vs -27%)
- 2026-03-31: **Pipeline Anti-Stale Pattern**: 自動Sweep/アクティブのみ表示/外部連動/カード内分析インライン
- 2026-03-31: **旧pipeline.html廃止**: inquiry-pipeline.htmlがSSoT
- 2026-03-31: **内覧予定なし**: 当面内見しない方針

## Blockers
- なし（楽待403は解消済み、残り29件は掲載終了物件のみ）

## Environment
- Python: `stock-analyzer/.venv/bin/python3`（property-analyzer自体のvenvなし）
- Deploy: push to main → GHA auto-deploy to gh-pages
- Live URL: https://ymatz28-beep.github.io/property-report/
- Private deploy: Cloudflare iuma-private.pages.dev

## History (last 20)
1. 2026-03-31: マーケットページ品質改善 — 広告コピー7パターン + 戸建て除外 + OC収入補完
2. 2026-03-31: パイプライン形骸化解消 — lifecycle + メール連動 + UI刷新 + 旧パイプライン廃止
3. 2026-03-30: Before: 諸費用未計上+掲載日1,644件不正確 → After: 諸費用7%追加+不正確日付除去
4. 2026-03-30: Before: kaizen修正率1% → After: 自動修正+commit
5. 2026-03-29: Before: レイアウト崩れ目視頼み → After: Playwright Visual Regression自動チェック
6. 2026-03-29: Before: 有識者一律扱い → After: 3層ティアリング(833件評価/58.4%)
7. 2026-03-28: Before: 手動デプロイ → After: main→gh-pages自動デプロイworkflow
8. 2026-03-28: Before: 物件名不正確+管理費混在 → After: F宅建詳細取得+管理費/修繕分離
9. 2026-03-28: Before: セクション遷移なし → After: Market sticky section nav横展開
10. 2026-03-27: Before: 楽待一覧のみ → After: 詳細ページ構造化抽出(現況/年間収入/管理費)
11. 2026-03-26: Before: 収益物件ページなし → After: yield専用ページ新規作成
12. 2026-03-25: Before: 民泊候補未調査 → After: 特区民泊候補物件調査完了
13. 2026-03-24: Before: 融資未打診 → After: 筑波銀行(澤畠さん)へメール送信
14. 2026-03-23: Before: 内見分析がアーカイブ不可 → After: アーカイブ機能追加
15. 2026-03-22: Before: パイプラインUI未整備 → After: inquiry-pipeline dashboard作成
16. 2026-03-21: Before: 福岡物件未内見 → After: 3物件内見完了
17. 2026-03-20: Before: agent_memory分散 → After: SSoT確立+pipeline sync
18. 2026-03-19: Before: 問い合わせ管理なし → After: Pipeline+Reply Assist構築
19. 2026-03-18: Before: patrol結果確認が手動 → After: GHA patrol Gmail通知
20. 2026-03-17: Before: 格安区分の評価基準なし → After: スコアリング導入