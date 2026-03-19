# HANDOFF

## [Constancy] 2026-03-19
- [WARN] hardcoded_data: Large inline data (91 lines) at line 36. Consider externalizing to YAML/JSON.
- [WARN] structural_reform: search_multi_site.py is 1022 lines (threshold: 500). Consider splitting.
- [WARN] structural_reform: generate_search_report_common.py is 1171 lines (threshold: 500). Consider splitting.
- [WARN] html_ui: Has gnav but missing hamburger toggle — mobile nav broken
- [WARN] html_ui: Has gnav but missing hamburger toggle — mobile nav broken
- [ERROR] git_uncommitted: Property Analyzer: 6 uncommitted file(s), oldest 435h ago (threshold: 24h). GHA runs on old code until pushed.

## 最終更新: 2026-03-19（Session #72 — Resilience原則 + パイプラインレジリエント化 + ティアフィルタ）

## 完了済み（2026-03-19 Pipeline構築 + Resilience原則 + パトロール最適化）

### 物件問い合わせパイプライン構築
- **property_pipeline.py** — 物件問い合わせライフサイクル管理CLI（648行）
- **data/inquiries.yaml** — 状態管理SSoT。30物件auto-flagged（10×3都市）
- Status flow: discovered → flagged → inquired → in_discussion → viewing → viewed → decided | passed
- `--auto-flag`: daily patrol連動で高スコア物件を自動フラグ
- `--extract ID`: メール返信からClaude AIで構造化データ抽出
- `--viewing ID DATE`: 内見予定 → action_item自動生成
- run_daily_patrol.py Step 5.5にauto_flag+dashboard生成を統合

### ティアベースフィルタ（`094ba95`→`a9f7a2e`）
- **Before**: フラットMAX_DISPLAY=20で全スコア帯を均等カット
- **After**: Green(80+)=常に全数表示、Yellow(65-79)=Greenが20未満の場合のみ補充、Orange/Red(<65)=完全除外
- テスト結果: 大阪19G+1Y=20件、福岡33G+0Y=33件、東京16G+0Y=16件

### Resilience原則（CLAUDE.md昇格 `82d79b0`）
- **思想体系**: 3S → Constancy → **Resilience** → Ritualize の4層構造に
- 「失敗は前提。途中で壊れてもできたところまで活かし壊れた箇所を通知する」
- Resilienceチェック: ①失敗時に後続は止まるべきか？ ②部分的成功をどう保存・報告するか？ ③外部障害を正常変化と区別できるか？

### 物件パトロールResilience化（`1efbfea`→`1f0be28`→`8882169`）
- **Source-failure guard**: ソースが前回比70%以上減少→スクレイピング障害と判定→差分計算から除外
- **全ステップtry/except隔離**: 1ステップの障害が全体を巻き込まない
- **検索5スクリプト並列化**: 直列~30min → 並列~10min（Popenベース）
- **timeout修正**: multi_site 180→600s、LIFULL 120→300s、restate 180→300s、enrich 180→300s
- **dead URL タイムバジェット**: 300s上限、超過分はスキップ
- **patrol_summary.json**: failed_steps[] + failed_sources[] を構造化記録
- **Daily Digest連携**: PROPERTYセクションに「⚠ 部分障害: xxx」を黄色表示（AM/PM両方）

### 横展開 Resilience（全プロジェクト）
- **stock-analyzer** (`8f82902`): _run_step() blast-radius isolation + pipeline_summary.json + _resilience_summary()
- **kaizen-agent** (`6999aa6`→`139a2e6`): run_step() + step_results tracking + nonlocal SyntaxError修正

### ルール強化
- **Design Leverage Rule** — dashboard-rules.mdに4ステップ必須チェック追加
- **Verification Before Done ステップ5** — push後のopen必須ルール追加。例外なし・指示不要
- **原則の階層更新** — WWH(企画) → 3S(設計) → Constancy(検証) → Resilience(障害耐性) → Ritualize(運用)

## Next Actions
1. **Reply Assist統合テスト** — inbox-zero reply_assist.pyのproperty.yaml + agent_memory.yaml連携を実メールで検証
2. **Daily Digest統合テスト** — 次回パトロール実行でfailed_steps表示がDigestに反映されるか確認
3. **Constancy警告対応** — search_multi_site.py 1022行の分割検討、generate_search_report_common.py 1171行の分割検討
4. **inquiries.yaml重複3組解消** — inq-007/008, inq-013/014, inq-029/030
5. **pipeline_summary.json → Constancy検査連携** — stock-analyzerのpipeline死活をconstancy_checks.pyのdelivery_healthに追加

## Key Decisions
- **ティアベースフィルタ閾値**: Green 80+, Yellow 65-79, Orange/Red 除外。MAX_YELLOW_FILL=20
- **MAX_DISPLAY廃止**: フラット件数制限ではなくティアベースに完全移行
- **検索並列化**: 5スクリプトは別ファイルに書き出すため並列安全。enrich_maintenance.pyのみ後続
- **Source-failure guard閾値**: 70%以上ドロップ（最低10件以上）で障害判定
- **Resilience通知設計**: Digestに統合（ボトルネック防止: collect_property()はtry/except済み、patrol障害がDigest全体を止めない）
- **Design Leverage Rule**: 新規UI構築前に既存デザイン資産を必ず参照。違反基準明確化
- **Verification Before Done open必須**: push後に影響URLを全てブラウザ表示。指示不要
- **Gnav統一順序確定（2026-03-09）**: Private: `Stock → Market Intel → Intel → Wealth → Action → Property → Travel`。Public: `Hub → Property → Travel`
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
- **特区民泊の新規受付は2026年5月29日で終了** → 残り約2.5ヶ月
- #1 扇町の民泊可否が最重要の未確認事項
- athome全都市でCAPTCHA認証ブロック（解決不可）
- DTI約61.7% → 個人追加融資困難。法人融資で対応
- **GitHub Pagesキャッシュ**: max-age=600（10分）。デプロイ直後は404/古い版が出る

## 環境構築メモ (PC交換用)
- Python 3.13
- `pip install -r requirements.txt`（anthropic, pyyaml, openpyxl, reportlab, Pillow, numpy, requests, beautifulsoup4, jinja2, playwright）
- `playwright install chromium`
- 環境変数: ANTHROPIC_API_KEY
- GitHub Pages: report-dashboard(gh-pages) / property-report(gh-pages) / trip-planner(main)

## History
- 2026-03-19 Session#72: Pipeline構築+ティアフィルタ+Resilience原則+パトロール並列化+横展開(stock/kaizen)+Design Leverage Rule+open必須ルール
- 2026-03-18 Projects横断MEMORY更新: downloads-router 3層ルーティング記述拡充(個人→Drive/Cisco→OneDrive/証券CSV→data-bridge、不動産キーワード自動判定)。tax_annual.yaml参照追加(wealth-strategy PL連携用)
- 2026-03-18 GHA lib/欠落修正: lib/をリポに追加+sys.path両対応+jinja2追加。GHAレポート生成全滅の根本原因修正(`5d4bddb`)。パトロール再トリガー済み
- 2026-03-18 GHAパトロールGmail通知: daily-patrol.ymlにSMTP直接通知追加(`4e8e594`)。✅完了/⚠️部分成功/❌失敗の3パターン。PC閉じてもスマホGmailに届く設計
- 2026-03-18 Projects#50横断: マネタイズ5ドメイン戦略に不動産組込。Property Quick Calcとしてproperty-analyzer既存資産を収益化候補に。monetization-strategy.md作成
- 2026-03-18 kaizen#72横断: lib同期drift修正(qa_output.py/renderer.py)。Digest夕方SPOTLIGHT/SIGNALS追加。CF Pages deploy-private修正。IMAP診断ログ追加
- 2026-03-18 グランドデザインWWH再構築: Property Quick Calc設計にWWH適用+リスク対策追加。プロダクト優先順位変更(健康トラッカー#1→不動産即判定#2)。WWHフレームワークCLAUDE.md昇格
- 2026-03-17 問い合わせ文面改善: 共通コンテキスト追加(エリア/予算/リノベ/不在期間)+ペット可/相談可の丁寧表現+2拠点生活「検討→実施」統一。property-reportデプロイ済み
- 2026-03-17 kaizen constancy横断: github_actions_healthがリポ単位→ワークフロー単位に強化。連続失敗閾値で誤検知抑制
- 2026-03-16 kaizen#69 Cloud完全移行横断: GHAスケジュール再有効化。Daily Digest cron停止(3/11以降)が解消
- 2026-03-16 scripts#48横断: .gitignore `!data/patrol_summary.json` 追加（Cloud Tier 404修正）。daily-patrol.yml rebase修正
- 2026-03-16 lib同期drift修正（kaizen側）
- 2026-03-16 inbox-patrol廃止（形骸化）→ kaizen launchd簡素化
- 2026-03-16 Phase 2: Cloud-Primary + lib統合 + GHAスケジュール
- 2026-03-13 鮮度情報（first-seen）全ページ展開
- 2026-03-13 CSS var --gnav-height / constancy github_actions_health
- 2026-03-12 通知SSoT確立 / URL encoding修正
- 2026-03-09 Gnav統一 / MAX_PER_CITY=10 厳選
- 2026-03-07 gnav 2層構造 / 全11軸スコアリング完成
