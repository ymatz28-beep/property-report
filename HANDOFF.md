# HANDOFF

## [Constancy] 2026-03-28
- [WARN] hardcoded_data: Large inline data (91 lines) at line 36. Consider externalizing to YAML/JSON.
- [WARN] structural_reform: property_pipeline.py is 1547 lines (threshold: 500). Consider splitting.
- [WARN] structural_reform: search_multi_site.py is 1022 lines (threshold: 500). Consider splitting.
- [WARN] structural_reform: generate_ittomono_report.py is 1281 lines (threshold: 500). Consider splitting.
- [WARN] structural_reform: generate_search_report_common.py is 1165 lines (threshold: 500). Consider splitting.
- [WARN] html_ui: Has gnav but missing hamburger toggle — mobile nav broken
- [WARN] timestamp_format: Date-only timestamp 'Generated: 2026-02-20' — should include HH:MM
- [WARN] property_patrol_steps: 物件パトロール失敗ステップ (2026-03-28 06:40): 【管理費データ取得】タイムアウト (15分超過) → Fix: 設計上の仕様（600s budget制）。未取得分は翌日継続。アクション不要
- [ERROR] git_uncommitted: Property Analyzer: 15 uncommitted file(s), oldest 95h ago (threshold: 24h). GHA runs on old code until pushed.

## Last Updated
2026-03-28

## Completed (save_patrol_summary price_man パース修正 + SUUMO一棟物件調査断念 + ふれんず確認 2026-03-28)
- **Before**: `save_patrol_summary()` が一棟ものファイルの score カラム (col0) を price_man として読み込もうとし ValueError (`'健美家 中野区鷺宮1丁目#2tut'`) でクラッシュ → patrol_summary.json が毎回未更新。SUUMO一棟物件URLが未調査
- **After**: `_safe_price_man()` ヘルパー追加（`run_daily_patrol.py` L547-554）で安全にパース（異常値は 0 にフォールバック）。リモート競合20ファイルをHEAD版で一括解消しpush完了。SUUMO一棟物件URL (`/b/kodate/kw/一棟物件/`) を調査→キーワード検索で中古マンション/一戸建て/土地が混在、投資用一棟マンション/アパートではないため断念。ふれんず一棟もの25件確認済み（`ftakken_ittomono_fukuoka_raw.txt`、5000万〜7000万、木造/S造小規模）
- **Commits**: property-analyzer `7ae527b`（ddaad7c をリベース後 push）

## Completed (一棟ものスクレイパー修正 + SUUMO並列化 + kaizen patrol step監視 2026-03-27)
- **Before**: SUUMO detail fetchが逐次処理で25分超過タイムアウト、failed_steps: ['search_suumo.py', 'enrich_maintenance.py']が3/24から3日間継続。一棟ものスクレイパーのno-lookback parserでデータ汚染。GHA workflow conclusionがsuccess（continue-on-error）でもpatrol_summary.json内のfailed_stepsが検知されず隠蔽状態
- **After**: SUUMO detail fetchを並列化してタイムアウト解消(`8a5060e`)。一棟ものスクレイパーのno-lookback parser修正+re-scrape(`f601fe9`,`a46d5c7`)。URL-match priority in dedup+district map拡張(`743a80a`)。物件パトロールメールにFix提案追加(`78917b2`)。kaizen-agentに`check_property_patrol_steps`追加→毎晩patrol_summary.jsonのfailed_stepsを読み取り、朝Digestに自動表示(kaizen-agent `732cf2f`)。GHA手動トリガー実行済み(Run ID: 23629990106)、修正後初回パトロール結果待ち
- **Commits**: property-analyzer `8a5060e`(並列化), `f601fe9`(scraper修正), `a46d5c7`(re-scrape), `743a80a`(dedup+district), `78917b2`(Fix提案), kaizen-agent `732cf2f`(patrol step監視)

## Completed (一棟ものクロスリスティング汚染対策 + QAゲート追加 2026-03-26)
- **Before**: 一棟ものレポートに他都市の物件が混入していた（東京19件+大阪門真市1件が汚染データ）。URL上は正しい都市だが実際の所在地が異なるクロスリスティング。また、デプロイ前のQAゲートがstock-analyzerにしかなく、property-analyzerは品質チェックなしで公開されていた
- **After**: URL-location cross-validationを追加し、URLの都市名と実際の所在地が一致しない物件を自動除外。汚染20件をパージ。`run_daily_patrol.py`にデプロイ前QAゲート(`qa_output.check_directory()`)を追加、4/4 PASS確認済み
- **Commits**: property-analyzer `638872a`(クロスリスティング汚染対策+延床面積列追加), `633e349`(東京19件パージ), `93510ca`(大阪門真市1件除去), `59b345b`(URL-location cross-validation), `0f2963e`(QAゲート追加)

## Completed (kaizen-agent QA改革 x-ref 2026-03-26)
- **Before**: kaizen-agent patrolが3/16から10日間停止、QAエラー通知なし、QAノイズ1041件で本物のエラーが埋没。patrolエラー3件放置。property-analyzerのpatrol結果は自分で見に行かないと確認できなかった。デプロイ前QAゲートはstock-analyzerのみ、他ページ（property/wealth/health/cisco/newsletter/bookmarks）はチェックなしで公開
- **After**: patrol毎晩AM3:00自動実行復活、patrolエラー3件→0件。patrol_alerts.jsonが翌朝のMorning Digestに自動掲載（自分で確認不要）。QAゲートをproperty-analyzer含む全主要ページに横展開。property-analyzer QA gate 4/4 PASS、wealth-strategy QA gate 2/2 PASS。lib/renderer.py SSoT drift修正済み。session-end.shに「具体例・数値・commit hash必須、抽象禁止」テンプレート追加（全プロジェクトのHANDOFF自動更新に適用）
- **Commits**: kaizen-agent `f395839`(lib/renderer.py SSoT drift修正)

## 完了済み（2026-03-25 Projects x-ref: LINE dedup修正 + CLAUDE.mdルール昇格）
- **LINE重複送信修正** (Projects `de4524f`): lib/digest/orchestrator.py + builders_line.py に `dedup_key="signal"` 追加（2箇所）。同一シグナルの重複LINE送信を防止
- **CLAUDE.md Before/Afterルール昇格** (Projects `573d5db`): lessons.mdの「Before/Afterサマリ必須」を Verification Before Done Step 3 に正式昇格（2回以上の催促→昇格基準充足）
- **⚠ lib_sync_drift拡大**: lib/digest/orchestrator.py, builders_line.py が変更。property-analyzerとの同期差分がさらに拡大

## 完了済み（2026-03-25 融資相談メール送信 + 新規物件追加 + 賃料相場調査）
- **筑波銀行融資相談メール送信**: アンピール天神東405号室（福岡市中央区春吉/渡辺通駅8分/65.04㎡/2LDK/2004年築RC/3,800万円指値ベース）について澤畠さんに融資可否・条件を照会。3/21現地内覧済み、売主3月末期限
- **一棟もの融資枠打診**: 1.5〜2億円規模・福岡エリアの一棟ものも並行検討中と併記
- **新規物件4件追加（inq-046〜049）**: 大阪2件（JR野田7分1LDK/3,900万、新福島2分2LDK/4,998万）、大阪1件（ドーム前千代崎5分3LDK/3,890万）、福岡1件（薬院駅3分1SLDK/3,099万/score99）
- **賃料相場調査中**: アンピール天神東の融資審査用に福岡市中央区春吉2LDK 65㎡の賃料相場を調査（セッション途中）

## 完了済み（2026-03-25 一棟もの品質改善 — yield/area/dedup/KPI）
- **content-based重複排除** (`a0a6604`): URL正規化だけでは排除できなかった同一物件を名称+住所+価格でdedup。29→20件(ユニーク)
- **利回りバリデーション** (`b64d8a7`): 表面利回り>15%を異常値として除外。面積自動検出ロジック改善
- **カードKPI改善** (`b64d8a7`): 一棟もの物件カードに主要KPI(利回り/面積/築年数等)を表示
- **リンク可視化** (`8d25a93`): 物件リンクをボタンスタイルで視覚的にクリッカブルに
- **HTML再生成** (`68d3ff2`): dedup後のittomono.html再生成、push済み
- **Auto-patrol** (`de1924f`): 3/25データ更新正常完了

## 完了済み（2026-03-25 dotfiles環境drift自動検出 — x-ref dotfiles/kaizen-agent）
- **Brewfile更新** (dotfiles `c88ae1f`): 10→15パッケージ。tesseract(poppler/property-analyzerで使用)、zeromq等追加
- **setup.sh拡張**: 4→8ステップ(npm global/launchd/ollama/venv自動化 + 手動認証チェックリスト)
- **kaizen-agent drift検出** (`3553059`): 毎晩brew leaves + npm globalをdotfilesと比較。差分あれば自動修正+commit。環境管理にD=C適用

## 完了済み（2026-03-24 一棟もの投資スコアリング + 健美家検索 + 内覧結果）
- **健美家検索追加** (`96b3ba8`): search_kenbiya.pyで一棟もの物件の検索ソース追加
- **3/21福岡内覧結果反映** (`96b3ba8`): inquiries.yamlに内覧結果を記録
- **投資スコアリング** (`f2e43b0`): 一棟もの物件にスコアリング+都市別Top20フィルタ追加

## 完了済み（2026-03-24 Daily Digest Inbox low-priority非表示 — kaizen-agent x-ref）
- **daily_digest.html テンプレート修正**: INBOX DIGESTセクションでlow priorityメールを非表示に。バッジカウントもhigh/midのみに修正（`rejectattr('priority','equalto','low')`フィルタ追加）
- **テスト確認**: 10件中2件表示(high/mid)、8件非表示(low)。目視確認済み
- **Push**: ルートリポ `fc0679f` + kaizen-agent `5eb63b0`（push済み）
- **Leader Digest CIRCUITカレンダー残像**: Google Calendar APIでは削除済みだがmacOS EventKit（yma.tz.28カレンダー）にキャッシュが残存。カレンダーApp同期更新（Cmd+Shift+R）で解消可能

## 完了済み（2026-03-24 GHA通知ヒューマンリーダブル化 + push + 手動トリガー）
- **人間が読める通知フォーマット**: GHA workflow通知ステップを全面改善。`search_suumo.py`→`SUUMO物件検索`、原因・影響・リトライ結果を日本語で明記。Before:「失敗ステップ: search_suumo.py」→ After:「❌ SUUMO物件検索 / 原因: タイムアウト (25分超過) / 影響: SUUMO経由の新規物件が未検出 / → リトライ済み・再失敗」。通知本文を4セクション構造化（━━ 失敗 / ━━ ソース障害 / ━━ 正常 / ━━ 結果）。`removed_count`/`step_count`/`ok_count`/`elapsed_min`追加。`PATROL_OUTCOME`env var削除（patrol_summary.jsonベース判定に完全移行）
- **stderrキャプチャ追加**: `run_script()`のstderrを`DEVNULL`→一時ファイルにキャプチャ。戻り値を`bool`→`dict`に変更(`ok`, `reason`, `stderr_tail`, `elapsed_sec`, `exit_code`)
- **failure_details構造化**: patrol_summary.jsonに`failure_details`配列追加（`label`/`reason`/`impact`/`stderr_tail`/`retried`）。GHA通知がこれを読み取り人間可読な診断を生成。inline Python 95行、構文検証済み
- **commit+push完了**: `a4bdf8b` (stash+rebase+push、リモート競合解消)
- **リモート反映確認**: `gh api`でGHA workflow YAMLの`failure_details`/`stderr_tail`コード反映を確認済み
- **手動トリガー済み**: `gh workflow run daily-patrol.yml` 実行（04:01 UTC）。新フォーマット通知メールの確認待ち

## 完了済み（2026-03-24 パトロールレジリエンス強化 — 自動リトライ + 失敗メタデータ構造化）
- **タイムアウト自動リトライ**: `retry_failed_searches()` を検索フェーズ後に追加。タイムアウト失敗したステップのみ時間余裕があれば自動リトライ
- **失敗メタデータ構造化**: 全失敗ステップに `reason`（"timeout"/"crash"）+ `stderr_tail` フィールドを追加。patrol_summary.jsonで障害原因の特定が可能に
- **`save_patrol_summary` 全ステップ伝達**: `failed_steps=failed_names` → `all_steps=all_steps` に変更。成功/失敗の詳細メタデータを構造化サマリーに完全記録
- **安全アクセスパターン**: `s["ok"]` → `s.get("ok")` に統一。メタデータ拡張時のKeyError防止
- **`search_results` 初期化**: try/except外で空リスト初期化し、検索フェーズ全体エラー時もリトライロジックが安全に動作

## 完了済み（2026-03-24 kaizen-agent patrol config修正 — gnav false positive解消 x-ref）
- **nav_python_files SSoT移行反映**: kaizen-agent `config.yaml` の `private_site_qa.nav_python_files` を空リストに更新。`deploy_private.py` と `leader_digest.py` が `get_nav_html()` SSoTに移行済みのため、ハードコードnav検出対象から除外
- **patrol再実行で検証**: false positive（gnav_consistency + private_site_qa計33件→削減）を確認
- **property-analyzerへの影響**: HANDOFF.mdへのConstancy inject内容が精度向上（偽陽性排除）

## 完了済み（2026-03-24 Expert Insight YouTube video_url伝播 — lib/stock-analyzer x-ref）
- **パイプライン全体にvideo_url追加**: transcript_fetcher→video_summarizer→daily_synthesizer→intel_reportの4段にvideo_urlフィールドを伝播。ソースリンクが動画URL（チャンネルURLではなく）を指すように修正
- **折りたたみ詳細の復活**: LLMプロンプトに `▸` マーカー必須を明記。`insight: "概要 ▸ 詳細"` 形式で必ず折りたたみ生成
- **後方互換**: 旧アーカイブ(102件, video_urlなし)はchannels.yamlのチャンネルURLにfallback
- **Verification Before Done再違反**: commit+pushのみで完了報告→ユーザー指摘。テスト→デプロイ→open は不可分（lessons.md記録済み）
- **Push**: `stock-analyzer` @ `bc103c6`, `lib` (ローカルcommit)
- **⚠ lib_sync_drift拡大**: lib/intel_report.pyが変更されたため、property-analyzerとのドリフトがさらに拡大

## 完了済み（2026-03-23 Expert Insight カード構造刷新 — Projects x-ref）
- **intel_dashboard.html リファクタ**: カード構造をLeader Digest準拠に変更。insight_summaryを常時表示、insight_detailを折りたたみ「詳細を見る」に格納、ソースリンクボタン(青アクセント)追加
- **有識者ランキング導線修正**: Expert Insightナビバーに「有識者ランキング」リンク追加(gold-accent)。以前はMarket Intelページ最下部にのみ存在し事実上アクセス不能だった
- **kaizen-agent同期**: intel_dashboard.html + intel_research.htmlをkaizen-agentにコピー
- **Expert Insight再生成**: 49 insights (7日間)、正常生成確認
- **⚠ lib_sync_drift**: lib/intel_report.py + lib/templates/pages/ の変更によりドリフト拡大の可能性あり

## 完了済み（2026-03-23 kaizen-agent Cisco digest enrichment — x-ref）
- **action_tracker.py Cisco項目enrichment**: `_load_digest_index()`新設 + `_render_item_card()`拡張。Ciscoドメインのアクション項目にソースバッジ・Leader Digestリンク・折りたたみ要約を自動付与
- **Leader Digest v10**: cisco-os/leader_digest.py大幅更新（10バージョン経過）。テスト: `generate_digest_html()` OK
- **Action Tracker動作確認**: `--preview` テスト正常（84 total / 74 pending / 8 done / 2 blocked）
- **lib/共有ファイル更新**: `lib/digest/orchestrator.py`, `delivery_gmail.py`, `builders_line.py`, `collectors_inbox.py`, `lib/templates/email/daily_digest.html` が変更
- **⚠ lib_sync_drift拡大**: 上記lib/変更によりproperty-analyzerとの同期差分がさらに拡大。「進行中/未完了」のlib/digest/同期課題がより重要に

## 完了済み（2026-03-23 ittomono再デプロイ + gnav/モバイルQA）

### ittomono.html 再生成・再デプロイ (`49c39fc`)
- **問題**: 収益シミュレーション統合commit(`4421316`)にittomono.htmlが含まれていなかった（last-modified 3/22のまま）
- **対応**: `generate_ittomono_report.py` 再実行 → 62件(福岡8/東京54) → commit+push済み
- **gnav二重表示**: 解消済み確認。gnavに「一棟もの」1回のみ（`global_nav_html()` を `_NAV_PAGES` SSoTに統一済み）
- **モバイル最適化確認**:
  - 一棟もの: 960px以下→カードビュー自動切替、640px以下→パディング微調整。対応済み
  - 内覧分析: flexbox + max-width:900px、waterfallは`.rv-desc{min-width:0}` + `.rv-bottom{flex-wrap:wrap}` で折り返し対応済み

## 完了済み（2026-03-23 収益シミュレーション waterfall 追加）

### 内覧分析に収益ウォーターフォール統合
- **`_naiken_invest_analysis` 拡張**: `revenue_analyze()` を統合し、物件別にフル収益シミュレーションを自動生成
  - 収入→CF: 年間賃料収入 → 空室損 → 運営経費 → NOI → ローン返済 → 年間/月間CF
  - 減価償却→節税: 建物価格 → 残存耐用年数 → 年間償却額 → 損益通算の節税効果
  - 管理費込みCF: management_fee がある場合、管理費控除後の月間CFも表示
  - ボトムサマリ: 税引後CF / 実質利回り / 自己資金回収年数
  - 前提条件表示: 頭金比率 / 金利 / ローン年数 / 空室率 / 経費率 / 建物比率（区分RC 50%）
- **verdict分類**: 高CF物件 / 安定CF / 薄利 / CF赤字 の4段階をピル表示
- **新CSSコンポーネント**: `.revenue-block`, `.rv-header`, `.rv-row`, `.rv-subtotal`, `.rv-total`, `.rv-highlight`, `.rv-bottom` 等のウォーターフォール専用スタイル追加
- **naiken-analysis.html 再生成確認**: 32KB出力、正常生成

## 完了済み（3/23以前 — 詳細はHistory参照）
- 3/23: ittomono再デプロイ+gnav解消+モバイルQA / 収益ウォーターフォール統合 / Action Tracker property連携確認 / constancy_checks分割+violation_tracker
- 3/22: IPv4 SSL修正+cert生成スクリプト / 0件上書き防止+タイムアウト増加 / gnav Newsletter+gnav_consistency+2C原則
- 3/21: infra-manifest deployments / パトロール正常稼働確認(3回連続success)
- 3/20: ハンバーガー修正全7ページ / gnav QA+Self-Insight / GHA新deploy初回成功 / naiken自動生成+QA38項目 / agent_memory連携+GHAクロスリポ / デプロイ修正+パイプライン改善
- 3/19: Pipeline構築(property_pipeline.py 648行) / ティアベースフィルタ(Green全数+Yellow補充) / Resilience原則+パトロール並列化(30min→10min)

## In Progress / Next Actions
1. **GHA手動トリガー結果確認（Run ID: 23629990106）** — SUUMO並列化修正後の初回パトロール。failed_stepsが空になるか確認。完了後`git pull`でローカル同期
2. **アンピール天神東 賃料相場調査完了 → 澤畠さんに回答** — 融資審査用の想定賃料を確定し、必要なら追加情報を返信
3. **筑波銀行融資回答フォロー** — 3月末期限（残4日）。回答なければ澤畠さんに進捗確認
4. **明朝Digest確認: PATROL ALERTSセクション表示検証** — kaizen-agent `check_property_patrol_steps` 実装済み・未検証。朝Digestにpatrol結果が表示されるか確認
5. **QA warn=103件の精査** — エラーは0件だが警告103件残存。ノイズか本物か未仕分け
6. **inq-049 福岡薬院駅物件（score 99）精査** — ふれんず掲載、1986年築だが薬院駅3分の好立地。詳細調査・融資検討の優先候補
7. **特区民泊候補物件の問い合わせ送付** — 期限5/29、残り約2ヶ月
8. **GHA actions Node.js 24対応** — checkout@v4→v5, setup-python@v5→v6等（期限: 2026-06-02）
9. **Constancy警告対応** — 巨大ファイル4件の分割検討(generate_ittomono_report.py 1239行等)
10. **lib/digest/同期対応** — kaizen-agent #80でdaily_digest.pyがlib/digest/に分割。property-analyzerのlib同期設定を更新
11. **inquiries.yaml重複3組解消** — inq-007/008, inq-013/014, inq-029/030
12. **改善アイデア: 融資照会テンプレート自動生成** — inquiries.yamlの物件データ+賃料相場自動調査から、銀行向け融資照会メールのドラフトを自動生成

### 継続中（外部待ち）
- **澤畠さん（筑波銀行）融資回答待ち** — 3/24にアンピール天神東405号室の融資照会メール送信済み。売主3月末期限で急ぎ
- **アンピール天神東 賃料相場調査** — 融資審査用の想定賃料算出（前セッション途中）
- **中野さん未公開一棟もの提案待ち** — 非公開物件情報の提供待ち

### 技術的負債
- **Constancy structural_reform WARN 4件**: property_pipeline.py 1547行 / generate_ittomono_report.py 1239行 / search_multi_site.py 1022行 / generate_search_report_common.py 1165行
- **Nav生成コードパス一本化**: 現在3パス → Jinja2統一が望ましい
- **ルートリポ未commit変更**: CLAUDE.md / philosophy.md / dashboard-rules.md / MEMORY.md のプロセス簡素化(VBD 7→3ステップ)

## Key Decisions
- **gh-pagesデプロイ方針（2026-03-20）**: `git add *.html`限定（-A禁止）。Python deploy()はGHA上スキップ。デプロイ条件=パトロール実行時は常時
- **ティアベースフィルタ閾値**: Green 80+, Yellow 65-79, Orange/Red 除外。MAX_YELLOW_FILL=20
- **MAX_DISPLAY廃止**: フラット件数制限ではなくティアベースに完全移行
- **検索並列化**: 5スクリプトは別ファイルに書き出すため並列安全。enrich_maintenance.pyのみ後続
- **Source-failure guard閾値**: 70%以上ドロップ（最低10件以上）で障害判定
- **Resilience通知設計**: Digestに統合（ボトルネック防止: collect_property()はtry/except済み、patrol障害がDigest全体を止めない）
- **Design Leverage Rule**: 新規UI構築前に既存デザイン資産を必ず参照。違反基準明確化
- **Verification Before Done open必須**: push後に影響URLを全てブラウザ表示。指示不要
- **2C原則（2026-03-21）**: Constancy(毎回コンスタントに) × Consistency(一貫性)。navやUIの変更は全ページに波及必須。gnav_consistencyが毎晩自動検証
- **Gnav統一順序更新（2026-03-21）**: Private: `Stock → Market Intel → Insight → Wealth → Action → Self-Insight → Health → Newsletter → Property → Travel`。Public: `Hub → Property → Travel`。Newsletter追加（旧: 2026-03-20 Self-Insight+Health追加）
- **gnav 2層構造（2026-03-07確定）**: site-header(グローバル) + .gnav(property固有サブナビ)
- **スコアリング全11軸**: budget(20), area(15), earthquake(15), station(15), location(20), layout(10), pet(+15/+10/-15), maintenance(10/-5→強化予定), renovation(5/-5), brokerage(5), minpaku_penalty(0)
- **CSS var --gnav-height（2026-03-13）**: sticky要素がgnav高さを参照
- **通知SSoT（2026-03-12）**: daily_digest.py一元化。他ファイルからの送信禁止
- **「ローカル変更≠反映」（2026-03-12）**: workflow→push必須、plist→bootout/bootstrap必須
- **URL encoding必須（2026-03-13）**: 日本語物件名→percent-encode
- **constancy github_actions_health（2026-03-13）**: CI連続失敗を自動検出
- **鮮度情報（first-seen）（2026-03-13）**: first_seen.jsonに永続記録
- **Verification Before Done強化（2026-03-16）**: サブリポ単位commit+push義務化 + Before/After/Remainingサマリ必須
- **WWHフレームワーク必須化（2026-03-18）**: 新規プロダクト/設計時にWhat/Why/How分析必須。HowだけでWhatとWhyを飛ばすことを禁止
- **プロダクト優先順位（2026-03-18）**: ①健康トラッカー(Phase 1進行中) → ②不動産即判定(既存資産再利用MVP) → ③健康トラッカーiOSアプリ
- **原則の階層（2026-03-19更新）**: WWH(企画) → 3S(設計) → Constancy(検証) → Resilience(障害耐性) → Ritualize(運用)
- **GHAパトロールGmail直接通知（2026-03-18）**: Daily Digest SSoTの例外として、GHAワークフロー内からSMTP直接送信。理由: PC閉じてても通知が届く必要がある（Daily DigestはGHA側でも動くが、パトロール完了直後の即時通知はワークフロー内が最速）
- **lib/リポ内包（2026-03-18）**: GHA上でlib.rendererが見つからない問題の根本対策として、lib/(renderer/design_tokens/templates)をproperty-reportリポに直接追加。sys.pathはローカル(親dir)とGHA(カレントdir)の両方を検索
- **失敗メタデータ構造化（2026-03-24）**: all_stepsの各ステップに`reason`("timeout"/"crash")+`stderr_tail`を付与。save_patrol_summaryに全ステップ伝達（failed_namesではなくall_steps）。障害原因の事後分析・自動分類の基盤
- **個別ステップリトライ設計根拠（2026-03-24）**: 既存GHAリトライは「完全失敗（data commit無し）」のみ発動。SUUMOタイムアウトは「部分失敗（他ソースでcommit成功）」のため既存リトライ対象外だった→5日間SUUMOだけ失敗し続けた根本原因。`retry_failed_searches()`はこの穴を埋める設計で既存リトライとは重複しない
- **GHA通知ヒューマンリーダブル化（2026-03-24）**: failure_detailsのlabel/reason/impact/stderr_tailをGHA workflow内Pythonスクリプトで日本語フォーマット。ステップ名→日本語ラベル(STEP_LABELS dict)、原因→タイムアウト/クラッシュ分類、リトライ結果表示
- **agent_memory連携方針（2026-03-20）**: inbox-zeroのagent_memory.yamlをSSoTとし、property_pipeline.pyがsyncで取り込む。ステータスはアップグレードのみ（ダウングレード禁止）。GHAではGitHub API+GH_PATでクロスリポアクセス
- **デプロイプラットフォーム分離（2026-03-20）**: Public=GitHub Pages(zero-auth)、Private=Cloudflare Pages+Access(email OTP)。infra-manifest.yaml `deployments`セクションにSSoT化。property-reportはGitHub Pages/gh-pagesブランチ
- **SUUMO一棟物件断念（2026-03-28）**: `/b/kodate/kw/一棟物件/` はキーワード検索（中古マンション/一戸建て/土地が混在）で投資用一棟もの構造化データではない。percent-encoded URLはGalileoCookie 301無限リダイレクト。既存の楽待+健美家+ふれんずで一棟ものは十分カバー
- **進捗表示ルール（2026-03-28）**: 時間がかかるタスクは進捗を見せながら進める（全プロジェクト共通のユーザー要望）
- **マネタイズ戦略 不動産ドメイン（2026-03-18）**: property-analyzerの既存資産(11軸スコアリング+パトロール+民泊収益試算)を「Property Quick Calc」PWAとして収益化。Phase 2でエージェントチーム設計予定
- **GHAスケジュール再有効化（2026-03-16）**: Daily Digest cron復旧。property patrol結果の自動配信再開
- **inbox-patrol廃止（2026-03-16）**: 形骸化→削除。kaizen launchd簡素化
- **表示が空=データの問題。UIを変えるな（2026-03-16）**: テンプレートの表示制御は意図的設計。表示が空→データ側を修正。UIフォールバック全表示は禁止（stock-analyzer教訓、property-analyzerにも適用）
- 物件購入は法人（iUMAプロパティマネジメント）優先
- ペット不可: ハードフィルタで完全除外。不明(空欄): -15点
- 厳選フィルタ: ティアベース（Green全数 + Yellow補充 + Orange/Red除外）
- **スマホ最適化: 横スクロール方式**（列非表示はNG）
- **LINE通知は新物件検出時のみ**。Gmail+Webが主チャネル
- 特区民泊の新規受付は2026年5月29日終了

## ブロッカー / 注意事項
- **澤畠さん（筑波銀行）融資回答期限: 3月末** — 3/24にアンピール天神東の融資照会メール送信済み。売主3月末期限で急ぎ。回答なければフォロー要
- **特区民泊の新規受付は2026年5月29日で終了** → 残り約2ヶ月
- athome全都市でCAPTCHA認証ブロック（解決不可）
- DTI約61.7% → 個人追加融資困難。法人融資で対応
- **GitHub Pagesキャッシュ**: max-age=600（10分）。デプロイ直後は404/古い版が出る
- **GHA Node.js 20 deprecation**: actions/checkout@v4, actions/setup-python@v5が2026-06-02以降Node.js 24強制。動作影響の可能性あり

## 環境構築メモ (PC交換用)
- Python 3.13
- `pip install -r requirements.txt`（anthropic, pyyaml, openpyxl, reportlab, Pillow, numpy, requests, beautifulsoup4, jinja2, playwright）
- `playwright install chromium`
- 環境変数: ANTHROPIC_API_KEY
- **SSL証明書**: `bash scripts/generate-combined-certs.sh` でcombined_certs.pem再生成（Cisco Secure Endpoint環境必須）
- GitHub Pages: report-dashboard(gh-pages) / property-report(gh-pages) / trip-planner(main)

## History
| 日付 | サマリー |
|------|----------|
| 2026-03-28 | Before: save_patrol_summaryがscoreカラムでValueErrorクラッシュ+SUUMO一棟物件未調査 → After: _safe_price_man()追加(`7ae527b`)+SUUMO断念(キーワード検索)+ふれんず25件確認 |
| 2026-03-27 | Before: SUUMO逐次処理で25分タイムアウト+failed_steps3日継続+隠蔽 → After: 並列化でタイムアウト解消+kaizen patrol step監視追加+GHA手動トリガー済み |
| 2026-03-26 | Before: 一棟もの20件が他都市汚染データ混入+QAゲートなし → After: URL-location cross-validationで汚染排除+QAゲート4/4 PASS(`59b345b`,`0f2963e`) |
| 2026-03-26 x-ref | Before: kaizen patrol 10日停止+patrolエラー3件+QAノイズ1041件+通知なし+QAゲートstock-analyzerのみ → After: patrol AM3:00復活+エラー3→0件+朝Digest自動通知+QAゲート全主要ページ横展開(kaizen `f395839`) |
| 2026-03-25 | 筑波銀行にアンピール天神東405号室の融資照会メール送信(3,800万/65㎡/2LDK/2004年築RC)+新規物件4件追加(inq-046〜049)+賃料相場調査中 |
| 2026-03-25 x-ref | Projects LINE dedup修正(`de4524f`)+CLAUDE.md Before/Afterルール昇格(`573d5db`)。lib/digest/ drift拡大 |
| 2026-03-25 | 一棟もの品質改善: content-based dedup(29→20件)、利回りバリデーション(>15%除外)、面積自動検出、カードKPI、リンク可視化(`b64d8a7`) |
| 2026-03-25 x-ref | dotfiles環境drift自動検出(kaizen-agent `3553059`): Brewfile 10→15pkg(tesseract/zeromq追加)、setup.sh 4→8ステップ、launchd 7 plistバックアップ |
| 2026-03-24 | 一棟もの投資スコアリング(`f2e43b0`)+健美家検索追加(`96b3ba8`)+3/21福岡内覧結果反映 |
| 2026-03-24 x-ref | Daily Digest Inbox low-priority非表示(`fc0679f`/kaizen `5eb63b0`): バッジカウント修正+low除外フィルタ |
| 2026-03-24 | GHA通知ヒューマンリーダブル化完了(`a4bdf8b`): failure_details→日本語ラベル/原因/影響/リトライ結果の構造化通知 |
| 2026-03-24 | パトロールレジリエンス強化: タイムアウト自動リトライ(`retry_failed_searches`)+失敗メタデータ構造化(reason/stderr_tail) |
| 2026-03-24 x-ref | kaizen-agent patrol config修正: nav_python_files SSoT移行反映、gnav/private_site_qa false positive解消 |
| 2026-03-23 | ittomono.html再デプロイ(`49c39fc`)+gnav二重表示解消確認+モバイル最適化QA |
| 2026-03-23 | 内覧分析に収益ウォーターフォール統合: revenue_analyze()連携、CF/減価償却/節税/verdict分類 |
| 2026-03-23 #90 x-ref | kaizen-agent constancy_checks分割+violation_tracker(14日放置auto-escalation)。property-analyzer WARN追跡開始 |
| 2026-03-22 | IPv4強制SSL修正+cert生成スクリプト(`566c668`)+Expert Insightデプロイ (Projects x-ref) |
| 2026-03-22 | 0件上書き防止(search_ittomono)+タイムアウト増加(SUUMO 1500s/enrich 900s/GHA 70min) (`44c6c78`) |
| 2026-03-22 | gnav Newsletter追加(renderer.py SSoT)+gnav_consistency実装稼働開始+2C原則確立 |
| 2026-03-21 | infra-manifest.yaml deploymentsセクション追加: property-reportデプロイ構成正式ドキュメント化 |
| 2026-03-21 | パトロール正常稼働確認: 3回連続success、Gmail通知正常 |
| 2026-03-20 | モバイルハンバーガー修正: 全7ページ、テンプレートcanonical+local同時修正、横断QA全PASS |
| 2026-03-20 | GHA新deployスクリプト初回成功検証: /tmp別クローン方式でmerge conflict ゼロ |
| 2026-03-20 | naiken-analysis.htmlフル自動生成化+QA全38項目PASS+GHA rebase競合解消 |
| 2026-03-20 | agent_memory自動同期+GHAクロスリポアクセス+3/21福岡内覧3物件設定 |
<!-- 20件制限: 2026-03-20以前はarchive参照 -->