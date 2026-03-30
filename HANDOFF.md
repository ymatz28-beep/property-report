# HANDOFF

## [Constancy] 2026-03-29
- [WARN] hardcoded_data: Large inline data (91 lines) at line 36. Consider externalizing to YAML/JSON.
- [WARN] html_ui: Has gnav but missing hamburger toggle — mobile nav broken
- [WARN] timestamp_format: Date-only timestamp 'Generated: 2026-02-20' — should include HH:MM
- [WARN] property_patrol_steps: 物件パトロール失敗ステップ (2026-03-29 06:35): 【F宅建検索】タイムアウト (5分超過) → Fix: エラーログを確認
- [WARN] blank_cells: ダッシュ「—」106個 (閾値20) — データ欠損の可能性
- [WARN] numeric_outliers: 利回り: 異常値 3件 — 26.5>20, 22.9>20, 22.9>20
- [ERROR] property_name_quality: 駅名が物件名になっている: 2件 — ['「東武練馬」駅徒歩2分！2020年築RC造１棟マンション！', '「東武練馬」駅徒歩2分！2020年築RC造１棟マンション！']
- [WARN] qa_market_duplicate_detection: 8 duplicate (price, area) pairs: [(('3900', '40.07'), ['osaka-kubun', 'osaka-kubun']), (('4900', '46.01'), ['fukuoka-kubun', 'fukuoka-kubun']), (('3180', '52.98'), ['fukuoka-kubun', 'fukuoka-kubun'])]
- [ERROR] data_accuracy: スクレイプデータとHTMLレンダリングの不一致率 6.5% (11/169件)。パイプライン変換バグの可能性。例: 4480.0万円/45.62㎡; 18880.0万円/271.58㎡; 4780.0万円/64.15㎡; 2580.0万円/46.86㎡; 17304.0万円/314.59㎡

## Last Updated
2026-03-30

<!-- [Constancy] 2026-03-28: WARN hardcoded_data(91行inline) / structural_reform(4ファイル500行超) / html_ui(hamburger未実装) / timestamp_format(HH:MM欠落) / property_patrol_steps(管理費タイムアウト=設計仕様) / ERROR git_uncommitted(15files, 95h) -->

## Completed (取得諸費用計上 + 掲載日クリーンアップ + 福岡格安デバッグ 2026-03-30)
- **Before**: revenue_calc.pyが取得諸費用（登記+取得税+仲介+印紙+司法書士）を未計上。CCR・回収年数の分母が頭金のみ。first_seen.jsonに不正確なバックフィル日付（2/22, 2/23, 2/26, 3/1）が1,644件混入。福岡格安区分が一時的に25件→12件に減少
- **After**: revenue_calc.pyに取得諸費用7%を追加、CCR・回収年数の分母を「頭金+諸費用」に修正。market.htmlテンプレートを「初期必要資金（頭金+諸費用）」表示に変更。不正確な掲載日1,644件を除去。福岡格安は`_load_budget`自体が25件正常出力を確認（別セッションの一時的影響）→再生成で福岡: 区分68+一棟15+戸建10+格安25、QA 7 PASS/1 WARN/0 FAIL
- **Commits**: なし（コミット情報はトランスクリプトに記載なし）

## Completed (kaizen Visual Regression チェック追加 2026-03-29 x-ref)
- **Before**: HTMLレポートのレイアウト崩れ（モバイル水平オーバーフロー、JS errors、空白ページ等）を検知する仕組みがなく、目視頼み。CSSや構造変更でUIが壊れても気づけなかった
- **After**: Playwright headless Chromiumで全HTMLをmobile(375px)+desktop(1440px)でレンダリングし5項目チェック（JSコンソールエラー/水平オーバーフロー/空白ページ/必須要素欠落/fixed要素重なり）。初回実行で7件検出→偽陽性4件修正（critical_selectorsを`table`→`content`に拡張: `.card,.kpi,.metric,ul,ol,section`追加）→実問題3件に絞り込み: Asset Dashboard/FIRE Strategy/Property Marketのモバイル水平オーバーフロー
- **Commits**: kaizen-agent `208f292`（visual_regression.py新規+patrol.py+common.py更新、3ファイル204行追加）

## Completed (ふれんず物件名詳細取得 + 管理費/修繕分離 + 表示改善 2026-03-28)
- **Before**: ふれんず区分物件の物件名が住所表示のまま（「福岡市南区塩原3丁目」「福岡市南区中尾2丁目」等）。管理費と修繕積立金が合算表示。㎡単価が「535,934円/㎡」のような冗長表示。ふれんず一棟ものに詳細ページenrichmentなし
- **After**: 物件名を詳細ページから取得し正式名称表示（「ホワイトシャトー大橋 壱番館」「Ｄ－ｒｏｏｍ中尾 弐番館」等）。管理費+修繕積立金を分離取得（60件enriched）。㎡単価を万円表示に簡略化（535,934円/㎡→53.6万/㎡）。ふれんず一棟にも詳細ページenrichment追加+エルフ藤修正
- **Commits**: property-analyzer `c7e06f7`(物件名取得+リスト改善), `6653e9d`(㎡単価簡略化), `9996b8c`(一棟enrichment+エルフ藤), `6f2ae0b`(管理費+修繕分離)

## Completed (main→gh-pages自動デプロイworkflow追加 + ライブページ物件名修正 2026-03-28)
- **Before**: `main`へのpushで完了報告していたが、GitHub Pagesは`gh-pages`ブランチからデプロイする設計のため、ライブページに変更が反映されず毎回「治ってない」が再発。手動でgh-pagesにデプロイする必要があった
- **After**: `deploy-on-push.yml`を新規作成し、`main`への`output/*.html`変更push時にGHAが自動でgh-pagesにデプロイする恒久対策を実装。ライブページでシティパレス21・ホワイトシャトー大橋・Ｄ－ｒｏｏｍ中尾の物件名が正しく表示されることをcurl+open目視で確認。gh-pagesへの手動デプロイ(`e653048`)も実施
- **Commits**: property-analyzer `056b90b`(workflow), gh-pages `e653048`(手動デプロイ)

## Completed (kaizen auto_fix_patrol Phase 1.7 動作確認 + GHA正常稼働確認 2026-03-28 x-ref)
- **Before**: kaizen patrolが問題を検知するだけで手動修復が必要だった。output_drift(market-intel.html古い)、git_uncommitted(property-analyzer未push)が毎回手作業。GHAリポ名がproperty-analyzerと誤認(正: property-report)
- **After**: auto_fix_patrol.py Phase 1.7が自動修復実行: output_drift→market-intel.html再生成、git_uncommitted→property-analyzer auto-commit+push(`9fc9bfb`)。4 fixed / 0 failed / 3 skipped。GHA Daily Property Patrol success確認(3/27 21:39, Run 23668652488)。リポ名 property-report を確認
- **Commits**: property-analyzer `9fc9bfb`(auto: kaizen patrol sync), kaizen-agent `1159ee3`(Phase 1.7テスト+lib sync)

## Completed (infra-manifest leader-digest sleep-resilient化 + xbookmarks script path修正 2026-03-28 x-ref)
- **Before**: leader-digestが`StartCalendarInterval`（07:00/12:00/17:30固定）でPC sleep中に実行漏れ。xbookmarksのinfra-manifest scriptパスが旧`run_pipeline.sh`のまま
- **After**: leader-digestを`StartInterval 10800s`（3h間隔、冪等・sleep-resilient）に変更。xbookmarks scriptパスを`run_pipeline.py`に修正（前セッションTCC対応の反映）
- **Commits**: scripts `4744eac`

## Completed (Market ページ sticky section nav + section_navコンポーネント横展開 2026-03-28)
- **Before**: Marketページに区分・一棟・戸建てへのジャンプナビなし。セクションナビは各ページにインラインで4パターンがバラバラに実装（合計95行CSS + 36行JS重複）
- **After**: Market sticky section nav（区分/一棟/戸建て）追加。再利用可能 `section_nav.html` コンポーネント（CSS+HTML+JSの3マクロ）を作成し横展開: health_dashboardインライン63行→3行、stock_reportインライン48行→3行に圧縮。全ページで統一デザイン（pill形状、backdrop blur、モバイル横スクロール、IntersectionObserver）
- **Commits**: property-analyzer `4bf703d`, ルートリポ `6faea33`(コンポーネント作成), `825a8df`(health+stock migration)

## Completed (統一Market + Simulate + Portfolioページ構築 2026-03-28)
- **Before**: Market/Simulate/Portfolioページが未実装 or 断片的。property_cardマクロなし、収益分析表示なし
- **After**: 統一Marketページ構築 — property_cardマクロで収益分析（想定家賃・管理費・CF・利回り）を物件カードに統合(`7f7ca72`)。Simulate+Portfolioページ追加+CSS修正(`29e8534`)。統一ダッシュボードとして3ページが連携
- **Commits**: property-analyzer `7f7ca72`, `29e8534`

## Completed (kaizen patrol auto-sync + auto-patrol正常稼働確認 2026-03-28)
- **Before**: lib/renderer.pyとlib/templates/pages/property_report.htmlがルートリポとproperty-analyzerで同期ずれ(lib_sync_drift)。GHA手動トリガー(Run ID: 23629990106)後の初回パトロール結果が未確認
- **After**: kaizen patrol auto-fixでrenderer.py+property_report.htmlを自動同期。Auto-patrol 3/28 06:40正常稼働: 1212物件(前日1229), 新規48件, 削除67件, 22ステップ中21成功(ok_count=21/step_count=22)。唯一の失敗はenrich_maintenance.pyタイムアウト(設計上の仕様: 600s budget制、翌日継続)。patrol_alerts.jsonにproperty_patrol_steps警告2件が記録され翌朝Digestに自動掲載される状態を確認
- **Commits**: property-analyzer `b9d3d40`(kaizen patrol sync), `51ee67a`(auto-patrol data update)

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

## Completed (kaizen patrol横断QA調査 2026-03-28 x-ref)
- **Before**: patrol_alerts.json(error 1/warn 102/total 205)の内訳が未精査。QAインフラ(qa_output.py/patrol.py)の横断的な正常性が未確認
- **After**: クロスプロジェクト調査完了。property関連: property_patrol_steps 2件=管理費タイムアウト(設計仕様、アクション不要)。auto_fix_summary: lib_sync_drift 2ファイル自動同期済み(renderer.py+property_report.html)。QAインフラ正常稼働確認: qa_output.py(12ページタイプ対応)、patrol.py(8ドメインMECE検査)、collect_patrol_alerts()(Digest自動掲載)の3層が連動
- **Commits**: なし（調査のみ、property-analyzer側の変更なし）

## 完了済み（2026-03-25以前 — 詳細はHistory参照）
- 3/25 x-ref: Projects LINE dedup修正(`de4524f`)+CLAUDE.md Before/Afterルール昇格(`573d5db`)
- 3/25: 筑波銀行融資照会+新規物件4件(inq-046〜049)+一棟もの品質改善(dedup 29→20件, 利回りバリデーション, KPI)+dotfiles drift検出
- 3/24: 一棟ものスコアリング(`f2e43b0`)+健美家検索(`96b3ba8`)+GHA通知ヒューマンリーダブル化(`a4bdf8b`)+レジリエンス強化+kaizen config修正
- 3/24 x-ref: Digest low-priority非表示+Expert Insight video_url伝播
- 3/23: ittomono再デプロイ+gnav解消+モバイルQA+収益ウォーターフォール統合+Cisco enrichment+constancy_checks分割
- 3/22: IPv4 SSL修正+0件上書き防止+gnav Newsletter+2C原則
- 3/21: infra-manifest deployments+パトロール3回連続success
- 3/20: ハンバーガー修正全7ページ+GHA新deploy+naiken自動生成+QA38項目
- 3/19: Pipeline構築(648行)+ティアベースフィルタ+Resilience原則+並列化(30min→10min)

## In Progress / Next Actions
1. **アンピール天神東 賃料相場調査完了 → 澤畠さんに回答** — 融資審査用の想定賃料を確定し、必要なら追加情報を返信
2. **筑波銀行融資回答フォロー** — 3月末期限（残2日）。回答なければ澤畠さんに進捗確認
3. **未コミットファイルpush**: property_card.html, market.html, pipeline.html, portfolio.html, output/index.html が変更済み未commit。com.yuma.property-patrol.plist が未追跡
4. **QA warn=102件の精査** — patrol_alerts: error 1件(stock-analyzer), warn 102件, total 205件。property関連はproperty_patrol_steps 2件(管理費タイムアウト=設計仕様)。ノイズか本物か未仕分け
5. **inq-049 福岡薬院駅物件（score 99）精査** — ふれんず掲載、1986年築だが薬院駅3分の好立地。詳細調査・融資検討の優先候補
6. **特区民泊候補物件の問い合わせ送付** — 期限5/29、残り約2ヶ月
7. **GHA actions Node.js 24対応** — checkout@v4→v5, setup-python@v5→v6等（期限: 2026-06-02）
8. **Constancy警告対応** — 巨大ファイル4件の分割検討(property_pipeline.py 1547行, generate_ittomono_report.py 1281行, generate_search_report_common.py 1165行, search_multi_site.py 1022行) + mobile nav hamburger未実装 + timestamp HH:MM未対応
9. **inquiries.yaml重複3組解消** — inq-007/008, inq-013/014, inq-029/030
10. **改善アイデア: 融資照会テンプレート自動生成** — inquiries.yamlの物件データ+賃料相場自動調査から、銀行向け融資照会メールのドラフトを自動生成

### 継続中（外部待ち）
- **澤畠さん（筑波銀行）融資回答待ち** — 3/24にアンピール天神東405号室の融資照会メール送信済み。売主3月末期限で急ぎ
- **アンピール天神東 賃料相場調査** — 融資審査用の想定賃料算出（前セッション途中）
- **中野さん未公開一棟もの提案待ち** — 非公開物件情報の提供待ち

### 技術的負債
- **Constancy structural_reform WARN 4件**: property_pipeline.py 1547行 / generate_ittomono_report.py 1239行 / search_multi_site.py 1022行 / generate_search_report_common.py 1165行
- **section_nav未移行ページ**: property_report.html, market_intel.html の `.section-jump` もコンポーネント移行可（既存動作中のため優先度低）
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
- **main→gh-pages自動デプロイ（2026-03-28）**: `deploy-on-push.yml`でoutput/*.html変更時に自動デプロイ。根本原因: `main` push ≠ デプロイだったため毎回反映漏れが発生。daily-patrol.ymlのデプロイステップはそのまま残す（既存+追加の2系統）
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
- **澤畠さん（筑波銀行）融資回答期限: 3月末（残2日）** — 3/24にアンピール天神東の融資照会メール送信済み。売主3月末期限で急ぎ。回答なければフォロー要
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

## History（最新20件）
- 2026-03-30: Before: 取得諸費用未計上+掲載日1,644件不正確+福岡格安12件に減少 → After: 諸費用7%追加+日付除去+格安25件正常確認(別セッション影響)
- 2026-03-29 x-ref: Before: UIレイアウト崩れ検知なし(目視頼み) → After: Playwright visual regression追加、偽陽性7→3件に修正(kaizen `208f292`)
- 2026-03-28: Before: ふれんず物件名が住所表示+管理費合算+㎡単価冗長 → After: 詳細ページから正式名称取得+管理費分離(60件)+万円表示(`c7e06f7`,`6f2ae0b`)
- 2026-03-28: Before: main push≠デプロイで毎回ライブ反映漏れ → After: deploy-on-push.yml追加で自動デプロイ恒久化(`056b90b`)
- 2026-03-28 x-ref: Before: patrol検知→手動修復+GHAリポ名誤認 → After: auto_fix_patrol Phase 1.7自動修復(4 fixed/0 failed)+GHA success確認(`9fc9bfb`)
- 2026-03-28 x-ref: Before: leader-digest固定時刻でsleep漏れ+xbookmarks旧パス → After: StartInterval 3h化+.py修正(scripts `4744eac`)
- 2026-03-28: Before: Market/Simulate/Portfolio未実装+セクションナビ4パターン重複 → After: 統一3ページ(`7f7ca72`,`29e8534`)+sticky nav(`4bf703d`)+section_navコンポーネント横展開(`825a8df`)
- 2026-03-28 x-ref: Before: patrol_alerts内訳未精査+QAインフラ横断確認なし → After: 調査完了、property警告2件=設計仕様、auto-fix同期正常、QA3層連動確認
- 2026-03-28: Before: lib_sync_drift(renderer.py+property_report.html)+GHA初回パトロール未確認 → After: kaizen auto-sync(`b9d3d40`)+patrol 21/22 OK, 1212物件, 新規48件
- 2026-03-28: Before: save_patrol_summaryがscoreカラムでValueError → After: _safe_price_man()追加(`7ae527b`)+SUUMO断念+ふれんず25件確認
- 2026-03-27: Before: SUUMO逐次25分タイムアウト+failed_steps3日隠蔽 → After: 並列化解消+kaizen patrol step監視+GHA手動トリガー済み
- 2026-03-26: Before: 一棟もの20件汚染データ+QAゲートなし → After: URL-location cross-validation+QAゲート4/4 PASS(`59b345b`,`0f2963e`)
- 2026-03-26 x-ref: Before: kaizen patrol 10日停止+エラー3件+QAノイズ1041件 → After: patrol AM3:00復活+エラー0件+Digest自動通知+QAゲート全ページ横展開
- 2026-03-25: Before: 融資照会未送信+一棟もの29件重複あり → After: 筑波銀行メール送信+dedup 29→20件+利回りバリデーション+物件4件追加(inq-046〜049)
- 2026-03-25 x-ref: Before: LINE重複送信+Before/After手動催促 → After: dedup_key追加(`de4524f`)+CLAUDE.mdルール昇格(`573d5db`)
- 2026-03-24: Before: 一棟もの未スコアリング+健美家未対応 → After: スコアリング(`f2e43b0`)+健美家検索(`96b3ba8`)+内覧結果反映
- 2026-03-24: Before: GHA通知が英語ステップ名のみ → After: 日本語ラベル/原因/影響の構造化通知(`a4bdf8b`)
- 2026-03-24: Before: タイムアウト部分失敗が5日間放置 → After: retry_failed_searches()+失敗メタデータ構造化(reason/stderr_tail)
- 2026-03-24 x-ref: Before: patrol false positive 33件 → After: nav_python_files SSoT移行反映で偽陽性解消
- 2026-03-23: Before: ittomono.html未更新(3/22のまま)+gnav二重表示 → After: 再デプロイ(`49c39fc`)+gnav解消+モバイルQA
<!-- 20件制限: 2026-03-23以前はarchive参照 -->