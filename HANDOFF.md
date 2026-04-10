# HANDOFF

## [Constancy] 2026-04-10
- [WARN] data_freshness: Property Status: last updated 50h ago (threshold: 28h)
- [ERROR] hardcoded_data: [ESCALATED: 18d unresolved] Large inline data (91 lines) at line 36. Consider externalizing to YAML/JSON.
- [WARN] structural_reform: generate_market.py is 1664 lines (threshold: 800). Consider splitting.
- [ERROR] structural_reform: [ESCALATED: 18d unresolved] property_pipeline.py is 2277 lines (threshold: 800). Consider splitting.
- [WARN] structural_reform: Stale temp/debug file (7 days old). Delete it.
- [WARN] structural_reform: Stale temp/debug file (7 days old). Delete it.
- [WARN] structural_reform: Stale temp/debug file (7 days old). Delete it.
- [WARN] structural_reform: Stale temp/debug file (10 days old). Delete it.
- [WARN] structural_reform: Stale temp/debug file (14 days old). Delete it.
- [WARN] html_ui: Font size violation(s): line 190: fixed 48px
- [WARN] html_ui: Font size violation(s): line 191: fixed 48px
- [WARN] html_ui: Font size violation(s): line 191: fixed 48px
- [WARN] html_ui: Font size violation(s): line 190: fixed 48px
- [WARN] html_ui: Font size violation(s): line 190: fixed 48px
- [WARN] html_ui: Font size violation(s): line 190: fixed 48px
- [WARN] html_ui: Font size violation(s): line 191: fixed 48px
- [WARN] blank_cells: ダッシュ「—」177個 (閾値20) — データ欠損の可能性
- [ERROR] first_seen_coverage: 掲載日カバレッジ 2% (2/127) — 閾値80%
- [ERROR] property_name_quality: 駅名が物件名になっている: 2件 — ['値下げしました！東武練馬駅徒歩7分', '値下げしました！東武練馬駅徒歩7分']
- [ERROR] qa_market_name_quality: 2 station-pattern names: ['値下げしました！東武練馬駅徒歩7分', '値下げしました！東武練馬駅徒歩7分']
- [WARN] qa_market_duplicate_detection: 2 duplicate (price, area) pairs: [(('4980', '55.72'), ['fukuoka-kubun', 'fukuoka-kubun']), (('19500', '419.4'), ['tokyo-ittomono', 'tokyo-ittomono'])]
- [WARN] qa_market_data_accuracy: 4/86 (4.7%) — price mismatch: トピレック博多 raw=990.0 html=1000.0; price mismatch: トピレック博多 raw=990.0 html=1000.0; price mismatch: アンピールやよい坂 305 raw=920.0 html=950.0; price mismatch: ふれんず物件(中央区) raw=800.0 html=950.0
- [WARN] qa_market_oc_income_coverage: OC 289件中 197件が年間収入欠落 (68%) — 利回り逆算で補完
- [ERROR] qa_market_yield_consistency: 2件の利回り/年間収入乖離(>20%): プレサンス難波南アーバニッシュ: expected=30.8万 actual=72.0万 (57%乖離); 複数路線が徒歩圏内でアクセス良好: expected=153.3万 actual=88.2万 (74%乖離)
- [WARN] qa_market_name_cross_reference: 24件の物件名クロスリファレンス不一致: 目黒区東山(44㎡): ['中銀東山マンシオン', '池尻大橋駅 / 1LDK / 44.03㎡']; 福岡市博多区千代(26㎡): ['■■■【福岡', 'JGM県庁口 502']; 福岡市博多区博多駅前(22㎡): ['ふれんず物件(博多区)', 'ライオンズステーションプラザ博多 7階部分', 'ピュアドームエクセル博多']; 福岡市博多区博多駅南(22㎡): ['ふれんず物件(博多区)', 'ライオンズステーションプラザ博多 7階部分']; 福岡市博多区比恵町(20㎡): ['ふれんず物件(博多区)', '■■■【福岡'] ... +19 more
- [ERROR] data_accuracy: スクレイプデータとHTMLレンダリングの不一致率 26.1% (29/111件)。パイプライン変換バグの可能性。例: 1499.0万円/41.78㎡; 3080.0万円/40.75㎡; 4980.0万円/60.61㎡; 1890.0万円/55.62㎡; 3490.0万円/56.7㎡
- [ERROR] visual_regression: [mobile] console_error: 2 JS errors: ['Failed to load resource: net::ERR_INTERNET_DISCONNECTED', 'Failed to load resource: net::ERR_INTERNET_DISCONNECTED']
- [ERROR] visual_regression: [desktop] console_error: 2 JS errors: ['Failed to load resource: net::ERR_INTERNET_DISCONNECTED', 'Failed to load resource: net::ERR_INTERNET_DISCONNECTED']
- [ERROR] visual_regression: [mobile] console_error: 2 JS errors: ['Failed to load resource: net::ERR_INTERNET_DISCONNECTED', 'Failed to load resource: net::ERR_INTERNET_DISCONNECTED']
- [ERROR] visual_regression: [desktop] console_error: 2 JS errors: ['Failed to load resource: net::ERR_INTERNET_DISCONNECTED', 'Failed to load resource: net::ERR_INTERNET_DISCONNECTED']
- [ERROR] visual_regression: [mobile] console_error: 2 JS errors: ['Failed to load resource: net::ERR_INTERNET_DISCONNECTED', 'Failed to load resource: net::ERR_INTERNET_DISCONNECTED']
- [ERROR] visual_regression: [desktop] console_error: 2 JS errors: ['Failed to load resource: net::ERR_INTERNET_DISCONNECTED', 'Failed to load resource: net::ERR_INTERNET_DISCONNECTED']
- [ERROR] visual_regression: [mobile] console_error: 1 JS errors: ['Failed to load resource: net::ERR_INTERNET_DISCONNECTED']
- [ERROR] visual_regression: [desktop] console_error: 1 JS errors: ['Failed to load resource: net::ERR_INTERNET_DISCONNECTED']
- [ERROR] visual_regression: [mobile] console_error: 1 JS errors: ['Failed to load resource: net::ERR_INTERNET_DISCONNECTED']
- [ERROR] visual_regression: [desktop] console_error: 1 JS errors: ['Failed to load resource: net::ERR_INTERNET_DISCONNECTED']
- [ERROR] visual_regression: [mobile] console_error: 1 JS errors: ['Failed to load resource: net::ERR_INTERNET_DISCONNECTED']
- [ERROR] visual_regression: [desktop] console_error: 1 JS errors: ['Failed to load resource: net::ERR_INTERNET_DISCONNECTED']

## Last Updated
2026-04-09

## Completed (横断監査: APIキー除去+デッドコード削除+gnav SSoT化 2026-04-09)
- **Before**: ① config.yamlにAPIキー平文記載 ② lib/renderer.py(222行)+lib/styles/(353行)+lib/__init__.py(3行)がデッドコード（sys.pathで共有Projects/lib/が先に解決されるため未使用） ③ generate_search_report_common.pyのsite_header_html()がHub/Property/Travelリンクをハードコード（lib/renderer.get_nav_html() SSoT違反）
- **After**: ① config.yamlからAPIキー除去（キー自体は既に無効） ② lib/renderer.py+lib/styles/+lib/__init__.py削除（-578行）。templates/はcreate_env(extra_dirs)で使用中のため維持 ③ site_header_html()→lib/renderer.get_nav_html()に委譲（section-navはproperty固有で維持）
- **Commits**: 未コミット

## Completed (GHA cron完全無効化 — ローカルlaunchd一本化 2026-04-09)
- **Before**: daily-patrol.ymlにcron `0 14 * * *`（JST 23:00）が残存。4/7のローカルファースト化後もGHAが毎晩発火し続け、条件付きスキップとはいえGHA minutes消費+ローカルとの二重管理が残る
- **After**: daily-patrol.ymlからschedule cronを完全削除（workflow_dispatchのみ残す）。ローカルlaunchd（6h間隔）が唯一のPrimary。kaizen Dead Man's Switchが36h stale時にworkflow_dispatch自動トリガーするためGHAフォールバックは維持
- **Commits**: `4c7a1c2`

## Completed (Phase 1 自動化モジュール3点実装 + 中野メール下書き 2026-04-09)
- **Before**: メール下書き作成→inquiries.yaml手動更新が必要。予約確認メール（新幹線/チケット/航空券/ホテル）→Calendar手動登録。viewing_date経過後も手動でviewed遷移が必要。中野さんへのOCサブリース確認+プレイスポット価格交渉メールが未送信
- **After**:
  - **pipeline_signal**: `lib/pipeline_signal.py`新設（115行）。`emit()`がsubject/bodyキーワードからaction_type自動分類（評価依頼→inquired, 価格交渉→in_discussion, 見送り→passed等）→inquiries.yaml自動更新。upgrade guardでステータス逆行防止。agent_memory.yamlからbroker email→物件名フォールバック解決
  - **calendar_inject**: `inbox-zero/calendar_inject.py`新設。`detect_booking()`が新幹線(EX予約)/チケット(ぴあ/e+)/航空券(ANA/JAL)/ホテル(Booking等)→構造化イベントdict抽出。4テストケース全パス。gcal_create_eventに直接渡せる設計（Gmail MCP非依存）
  - **viewing auto-transition**: `property_pipeline.py`に`auto_transition_viewed()`追加。`--lifecycle`実行時にviewing_date<todayの物件を自動でviewed遷移+notes追記
  - **中野メール下書き**: OC7物件サブリース確認+プレイスポットしんばしビル本館1,980万円値下げ打診。2回修正（①「澤畠さん（筑波銀行）」→「銀行」に簡略化、②「興味を持っている顧客」の言い回しを中野→売主への伝え方として構造化）
- **Commits**: 未commit（unstaged）

## Completed (ローカルファースト化 + idle_guard + GHAフォールバック 2026-04-07)
- **Before**: GHAが実質Primary（毎朝JST 06:00に無条件実行、月900分消費）。ローカルはGHAのpatrol_summary.json更新で20hクールダウンに引っかかり3/30以降停止。GHAフォールバック機構なし（毎晩無条件実行）。PC起動時に全ジョブ同時発火でCPU/ネットワーク負荷
- **After**: 
  - **source分離**: patrol_summary.jsonに`source: "local"/"gha"`を記録。`_should_skip()`がGHA結果を無視→ローカルのクールダウンブロック解消
  - **plist修正**: StartInterval 86400→21600（6h、manifest準拠）
  - **idle_guard統合**: `lib/idle_guard.py`新設。PC起動時にアイドル待機（5分無操作/最大2h）→深夜は即実行
  - **GHA条件付きフォールバック**: cron JST 06:00→23:00。24h以内にローカル成功ならGHA全ステップスキップ（minutes消費ほぼゼロ）
  - **Playwrightキャッシュ**: actions/cacheでChromiumバイナリをキャッシュ（毎回150MB DL→キャッシュヒット時30秒）
  - **Dead Man's Switch**: kaizen-patrolが36h stale検知で`gh workflow run`自動トリガー（3重フォールバック）
  - **ローカル即実行確認**: PID=37266で起動、全27ステップ成功（34分）、source: local記録済み
- **Commits**: `0149267` (GHA cron disable), `c430201` (URL recheck 615件ERROR_TIMEOUT), `4e53628` (bg color fix), `32796f2` (kaizen patrol fix)

## Completed (lib SSoT shim化 + patrol cooldownガード 2026-04-06)
- **Before**: `lib/renderer.py`(205行)と`lib/styles/design_tokens.py`(249行)がproperty-analyzer内にフルコピーとして存在。canonical `Projects/lib/`と二重管理。`generate_inquiry_messages.py`はshared libのimportパスが未設定。`run_daily_patrol.py`は短いStartIntervalで連続実行される可能性（クールダウンなし）
- **After**: `lib/renderer.py`→24行shimに置換（canonical `Projects/lib/renderer.py`に委譲）。`lib/styles/design_tokens.py`→22行shimに置換。`generate_inquiry_messages.py`にsys.path設定追加。`run_daily_patrol.py`に`_should_skip()`追加（前回実行から20h未満ならスキップ、`--force`で強制実行可）
- **Commits**: 未commit（unstaged）

## Completed (kaizen-agent ジョブ依存関係チェック追加 2026-04-06)
- **Before**: ジョブ間の依存関係が暗黙的。property-patrolの出力ファイルをdaily-digestやkaizen-patrolが消費していたが、1つ壊れても影響範囲が不明
- **After**: infra-manifest.yamlに7ジョブの依存関係を宣言（outputs/consumed_by/consumes）。`check_job_dependencies()`が毎晩4項目を自動検証（outputs存在・鮮度・consumed_by整合性・consumes鮮度）。property-patrolは`consumed_by: [daily-digest, kaizen-patrol]`として登録
- **Commits**: kaizen-agent未commit（checks/infra.py + patrol.py + scripts/infra-manifest.yaml）

## Completed (共有gnav Pattern B化 + Cisco昇格 2026-04-06)
- **Before**: gnavは全13項目をフラットに並べていた。モバイルではハンバーガー内に全項目表示。HealthがPrimary枠、CiscoはOverflow枠
- **After**: lib/renderer.py `get_nav_html()` をPattern B（primary 5項目 + ⋯ドロップダウン8項目）にリファクタ。Primary: Stock / Market Intel / Cisco / Action / Property。Overflow: Wealth / Insight / Health / Travel / Newsletter / Bookmarks / SNS / Self-Insight。モバイルは全項目フラットリスト維持
- **Commits**: lib未commit（unstaged）

## Completed (データ品質自動QA+自動修正パイプライン 2026-04-03)
- **Before**: 楽待の虚偽利回り・サブリース・物件名偽装・複数駅欠落を全て手動で発見→手動修正。Kaizenは「パイプラインが動いたか」しかチェックせず、データ品質をQAしていなかった。CPも手動で忘れがち（3回発生）
- **After**:
  - **qa_market.py 4チェック追加**: Yield Consistency（利回り乖離検出）/ Sublease In Raw（間接サブリースキーワード）/ Name Cross Reference（物件名クロスリファレンス不一致）/ Multi Station（複数駅欠落）
  - **auto_fix_data_quality.py 新設**: 利回り自動修正（年間収入から再計算）/ 物件名自動置換（他サイトクロスリファレンス+ad-copyプレフィックス除去）/ サブリース自動マーク
  - **deploy_market.sh**: 1コマンドで auto-fix→生成→QA→commit→push→ブラウザ表示。CP忘れが構造的に不可能
  - **複数駅対応**: search_ftakken.py が交通欄全駅取得。parse_walk_minutesが最短値採用。_clean_station_textが最短順ソート
  - **パイプライン物件フィルタ免除**: in_discussion等のパイプライン物件はROI/徒歩フィルタを免除（URL+name/price/areaのcross-sourceマッチ）
  - **手動修正**: ルエ・メゾン・ロワール渡辺通り（渡辺通9分/薬院10分追加→収益復活）/ グランフォーレラグゼ博多駅南（実家賃6.6%に修正）/ サンシティ博多フレックス21（物件名修正）/ ライオンズステーションプラザ箱崎（物件名修正）/ ライオンズステーションプラザ博多（サブリースマーク）/ スカイマンション南福岡（春日駅エリア外除外）
  - **メゾン・ド・系サブリース推定ルール**: メゾン・ド・+≤500万+楽待→サブリース自動マーク（6件検出、4件収益除外）
  - **topic seeds**: 4件追加（863-866: 楽待データ品質問題）
- **Pushed**: `c8ff53f`

## In Progress / Next Actions
1. **Phase 2: calendar_inject → reply_assist統合**: detect_booking()の結果をgcal_create_eventに接続（hook化 or reply_assist組み込み）
2. **Phase 2: pipeline_signal → メール下書きhook統合**: Gmail MCP draft作成後に自動でemit()呼び出し
3. **OC7物件サブリース回答待ち**: 中野さんからのOC物件サブリース有無確認（メール送信済み2026-04-09）
4. **プレイスポットしんばしビル本館 価格交渉待ち**: 中野さん経由で1,980万円打診（メール送信済み2026-04-09）
5. **Phase 3: enrich拡張**: 楽待詳細ページ取得時にサブリースの「Point」欄スキャン + 複数駅補完（ネットワーク依存、後日）
6. **内見済み3件の銀行査定フォロー**: プレイスポット/GSハイム/ローズマンション → 筑波銀行結果確認
7. **一棟もの物件**: 中野さんが未公開物件を探すと言っていた（3/24）→ フォロー
8. **Name Quality FAIL**: 東京の「値下げしました！東武練馬駅徒歩7分」→ auto_fixのBUILDING_MARKERSに該当しないパターン。手動修正 or パターン追加
9. **Digest Status Bar v1**: 動作確認済み。2行折り返し・名前短縮・gnavとの視覚差別化が次の改善点

## Key Decisions
- 2026-04-09: **property-analyzer/lib/ デッドコード判定**: sys.pathで共有lib/が先に解決されるためPythonファイルは未使用→削除。templates/はcreate_env(extra_dirs)で使用中のため維持
- 2026-04-09: **Gnav 2層分離**: site-header(Hub/Property/Travel)はlib/renderer SSoT委譲。section-nav(Market/内覧等)はproperty固有で維持
- 2026-04-09: **pipeline_signalはYAML直接読み書き**: property_pipeline.pyのimport依存を回避し、inquiries.yamlを直接YAML操作。シンプルさ優先
- 2026-04-09: **calendar_injectは抽出層のみ**: Gmail MCP非依存。呼び出し側（reply_assist/hook）がgcal_create_eventを呼ぶ設計。bidirectional syncは見送り
- 2026-04-09: **ステータスはupgradeのみ（逆行防止）**: STATUS_ORDERで序列管理。passed/in_discussionにinquiredを送ってもstatus不変
- 2026-04-09: **メール文面の構造**: 中野さんへの依頼と、中野さんから売主への伝え方を分離。「興味を持っている顧客」は中野→売主の交渉文言
- 2026-04-09: **GHA cron完全廃止**: ローカルlaunchd 6hが唯一のPrimary。GHAはworkflow_dispatch（Dead Man's Switch経由）のみ。cron二重管理を構造的に排除
- 2026-04-07: **ローカルファースト + GHA条件付きフォールバック**: GHA cronは24h以内にローカル成功ならスキップ。kaizen Dead Man's Switchで36h stale時にworkflow_dispatch
- 2026-04-07: **idle_guard**: 重量ジョブはアイドル待機（property 5分/2h、kaizen 3分/1h）。深夜0-6時は即実行
- 2026-04-06: **lib SSoT shim化**: property-analyzer内のlib/renderer.py, lib/styles/design_tokens.pyをshim化し、canonical Projects/lib/に一元化。二重管理を構造的に排除
- 2026-04-06: **patrol cooldownガード(20h)**: StartIntervalの短縮に伴い、前回成功から20h未満なら自動スキップ。`--force`で上書き可
- 2026-04-06: **gnav Primary枠 = Stock / Market Intel / Cisco / Action / Property**: Healthを降格しCiscoを昇格。業務上の優先度に合わせた配置
- 2026-04-06: **gnav Pattern B（primary + overflow ⋯ドロップダウン）**: 13項目を5+8に分離。デスクトップは常時5項目+⋯、モバイルはフラット全表示
- 2026-04-03: **データ品質は検出だけでなく自動修正まで**: 検出止まりでは結局手動修正が残る。auto_fix+deploy_market.shで構造的に解決
- 2026-04-03: **Pros/Cons必須+即実行ルール**: メリット>リスクなら確認なしで即実行。全プロジェクト横断（memory保存済み）
- 2026-04-03: **メゾン・ド・+割安+楽待=サブリース推定**: 詳細ページ取得なしでも高確率で検出可能。誤検出はproperty_status overridesで個別復帰
- 2026-04-03: **パイプライン物件はフィルタ免除**: in_discussionで商談中の物件がROI/徒歩フィルタで消えるのは不適切
- 2026-04-03: **春日駅はエリア外**: classify_location_fukuokaでscore 0→除外対象

## Blockers
- なし

## Environment Setup
- venv: `property-analyzer/.venv/bin/python`
- deploy: `bash scripts/deploy_market.sh` （auto-fix→生成→QA→CP→open）
- dry-run: `bash scripts/deploy_market.sh --dry-run`

## History (last 20)
1. 2026-04-09: Before: config.yamlにAPIキー+lib/578行デッドコード+gnav SSoT違反 → After: キー除去+lib/削除+get_nav_html()委譲
2. 2026-04-09: Before: GHA cron残存でローカルと二重管理 → After: cron完全削除、launchd 6h一本化。`4c7a1c2`
2. 2026-04-09: Before: メール→DB/Calendar断絶+viewing手動遷移 → After: pipeline_signal+calendar_inject+auto_transition_viewed 3モジュール実装+中野メール下書き
2. 2026-04-07: Before: GHA実質Primary+ローカル3/30停止 → After: ローカルファースト化+GHA条件付きフォールバック+idle_guard+Playwrightキャッシュ+Dead Man's Switch
2. 2026-04-07: Before: Digest Status Barなし（表示なし=正常の暗黙ルール） → After: 全パイプライン常時表示（●OK/▲warn/■error）+全ジョブ日本語短縮名
3. 2026-04-06: Before: lib 2ファイルがフルコピー二重管理+patrol連続実行リスク → After: shim化でSSoT一元化+20hクールダウンガード
4. 2026-04-06: Before: ジョブ依存関係が暗黙的 → After: infra-manifest.yamlに7ジョブ依存宣言+check_job_dependencies自動検証
5. 2026-04-06: Before: gnav全13項目フラット+HealthがPrimary → After: Pattern B(primary 5+overflow 8 ⋯ドロップダウン)+Cisco昇格
6. 2026-04-03: データ品質自動QA+自動修正パイプライン（qa_market 4チェック + auto_fix_data_quality + deploy_market.sh + 複数駅対応 + パイプライン免除 + 手動修正6件 + メゾン・ド・サブリース推定）
7. 2026-04-02: SSoT Property Registry + Pipeline v2 + サブリース除外 + intel_extractor + スコアリング修正
8. 2026-04-01: 健美家利回り修正 + DEFAULT_CITY + メールドラフト作成
9. 2026-03-31: マーケット品質改善（広告コピー7パターン+戸建て除外+OC収入補完）
10. 2026-03-31: パイプライン形骸化解消（lifecycle自動管理+メール連動+UI刷新）
11. 2026-03-30: 取得諸費用計上+掲載日クリーンアップ+福岡格安デバッグ
12. 2026-03-29: kaizen Visual Regression チェック追加
13. 2026-03-28: 朝夕2系統テンプレートリライト+section_navコンポーネント
14. 2026-03-27: Cisco Talent Review+property_patrol_steps内部失敗検知
15. 2026-03-26: kaizen-agent QA改革（patrol復活+インフラ整備）
16. 2026-03-25: CLAUDE.md Before/After必須化昇格
17. 2026-03-24: 内見分析ダッシュボード+reply_assist+中野さん対応
18. 2026-03-23: Dashboard gnav統一+property inquiry pipeline