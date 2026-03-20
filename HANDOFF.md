# HANDOFF

## [Constancy] 2026-03-20
- [WARN] hardcoded_data: Large inline data (91 lines) at line 36. Consider externalizing to YAML/JSON.
- [WARN] structural_reform: search_multi_site.py is 1022 lines (threshold: 500). Consider splitting.
- [WARN] structural_reform: generate_search_report_common.py is 1171 lines (threshold: 500). Consider splitting.
- [WARN] html_ui: Has gnav but missing hamburger toggle — mobile nav broken

## 最終更新: 2026-03-20 Session #54

## 完了済み（2026-03-20 内覧分析フル自動生成）

### naiken-analysis.html フル自動生成化
- **物件別投資分析 (`_naiken_invest_analysis`)**: 都市別㎡賃料ベースの想定賃料・表面利回り・実質CF・㎡単価相対評価・築年数リスクを自動算出
- **メリット/リスク自動判定 (`_naiken_merits_risks`)**: ㎡単価・面積・ペット・耐震・築年数・管理費・短期賃貸を属性ベースで自動分類（メリット/リスク/要確認）
- **物件別チェックリスト (`_naiken_checklist`)**: 築年数に応じた動的チェック項目生成（旧耐震は耐震診断追加等）
- **担当者向け質問リスト (`_naiken_questions`)**: 管理規約・修繕・耐震等の質問を自動生成。担当者名付き
- **共通確認事項セクション**: ハードフィルター（ペット/マンスリー）+ 投資判断チェック + 2拠点生活実用性
- **アーカイブ機能**: 上書き前に `output/archive/naiken-{date}.html` に前版を自動保存
- **デザイン刷新**: タグ（tag-blue/green/yellow）、invest-grid、verdict-caution、schedule-banner等の新CSSコンポーネント
- **QA全38項目PASS**: データ整合性(4) + 出力品質(28: 構造/UI/データ正確性/旧データ排除) + アーカイブ(1) + パイプライン統合(5) + 冪等性(1) + プレースホルダー(1) + デプロイ(3: HTTP200+福岡版+大阪旧版排除) + 次回パトロールシミュレーション(2)
- 出力277行（旧手動版420行と同等構造、コード生成で保守コスト削減）
- **rebase競合解消**: GHA auto-patrol(`fda2d10`)との競合をstash+rebaseで解決。push成功(`f067cc6`)

## 完了済み（2026-03-20 agent_memory連携 + GHAクロスリポアクセス）

### agent_memory自動同期 (`185c549`)
- **sync_from_agent_memory()**: inbox-zeroのagent_memory.yamlから物件問い合わせ状況を自動同期
  - 物件名マッチでステータス自動アップグレード（flagged→in_discussion→viewing）
  - フリーテキストから内覧日時を抽出
  - ハードフィルタ結果（ペット可/民泊可）を確定条件として同期
  - ステータスはアップグレードのみ、ダウングレードしない
- **run_daily_patrol.py Step 5.6**: auto-flagとダッシュボード生成の間にsyncステップ追加
- **inquiries.yaml更新**: 3物件を3/21内覧(viewing)に設定（アンピール天神東、クリオラベルヴィ呉服町、コスモ博多古門戸）
- **naiken-analysis.html再生成**: 3/21福岡3物件内覧用分析レポート

### GHAクロスリポアクセス (`830df2a`)
- **_load_agent_memory() GitHub APIフォールバック**: ローカルパスが存在しない場合（GHA環境）、GitHub API経由でinbox-zeroリポのagent_memory.yamlを取得
- **GH_PAT secret**: daily-patrol.ymlにGH_PAT環境変数追加（プライベートリポアクセス用）

### gh-pagesデプロイGHAスタック解消
- **run #23314418165**: 正常完了（33m14s）。スタックではなく長時間実行だった
- **Pages build**: 成功（45s, `23315739603`）

## 完了済み（2026-03-20 デプロイ修正 + ポートフォリオツール + テンプレート同期 + パイプライン改善）

### gh-pagesデプロイ修正 (`22ea0f8`)
- **デプロイ条件修正**: data_committed=true時のみ→パトロール実行時は常にデプロイ（HTMLのみ変更時のデプロイ漏れ防止）
- **GHA Python deploy()スキップ**: GHA上では未認証clone失敗→workflowシェルステップでデプロイ
- **git add *.html**: `git add -A`→`*.html`限定で__pycache__/lib/.githubのgh-pages混入防止
- **既存staleアーティファクト除去**: gh-pages上の__pycache__/.github/lib/を除去

### ポートフォリオツール・物件ドキュメント追加 (`648a213`)
- **ポートフォリオ分析ツール追加**: property docs + patrol data更新

### テンプレート同期 (`d7eefc6`)
- **property_report.html**: canonical lib（Projects/lib）からテンプレート同期

### パイプライン改善 (`2e8c4d4`)
- **チサンマンション削除**: 自宅物件をパトロール対象から除外
- **担当者肩書き表示追加**: 問い合わせ先の表示改善

### 内覧スケジュール可視化 (`79de0a5`)
- **内覧スケジュール可視化機能追加**: アクティブ物件6件追加
- パイプラインでの内覧予定管理を強化

### Projects Session #51 クロスリファレンス
- **lib_sync_drift解消確認**: property-analyzer lib/ push(`5d4bddb`)済み、constancy drift WARN解消
- **ルートリポsubproject track解除** (`9c5a370`): .gitignoreにproperty-report等8サブプロジェクト列挙。git_uncommitted 104→1
- **全constancy WARN一掃**: git_uncommitted(93+→0)、lib_sync_drift(4→0)、notification SSoT(9→0)をProjects横断で解消
- **gh-pagesデプロイ修正GHA実行**: `workflow_dispatch` 20:02 JST発火。デプロイ条件修正+staleアーティファクト除去の動作確認待ち

### kaizen-agent側の関連変更（x-ref）
- **#80 daily_digest.py分割** (`1c78c01`): 2755行→lib/digest/7モジュールに分割。property-analyzerのlib同期にdigest/追加必要
- **#79 constancy lib_sync_drift拡張** (`969e9c2`): property-analyzer/lib/をドリフト検出対象に追加
- **#78 lib/自己完結化**: lib/(renderer.py/design_tokens/テンプレート)をproperty-analyzerリポに直接コピー
- **#77 GHA完了Gmail直接通知**: daily-patrol.ymlにSMTP通知ステップ追加済み

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

## 進行中 / 未完了
- **lib/digest/ 同期未実施**: kaizen-agent側でdaily_digest.pyがlib/digest/パッケージに分割された(#80, `1c78c01`)。property-analyzerのlib/同期にdigest/パッケージ追加が必要
- **Constancy structural_reform WARN 2件**: search_multi_site.py 1022行 / generate_search_report_common.py 1171行
- **モバイルgnav hamburgerトグル未実装**: html_ui WARN

## Next Actions
1. **3/21福岡内覧 最終確認** — naiken-analysis.htmlフル自動生成済み。ブラウザ目視で投資分析数値・質問リストの妥当性を確認
2. **Constancy警告対応** — search_multi_site.py 1022行の分割、generate_search_report_common.py 1171行の分割
3. **lib/digest/同期対応** — kaizen-agent #80でdaily_digest.pyがlib/digest/に分割。property-analyzerのlib同期設定を更新
4. **モバイルgnav修正** — hamburgerトグル未実装のWARN対応
5. **inquiries.yaml重複3組解消** — inq-007/008, inq-013/014, inq-029/030
6. **Reply Assist統合テスト** — inbox-zero reply_assist.pyのproperty.yaml + agent_memory.yaml連携を実メールで検証
7. **改善アイデア: agent_memory双方向同期** — 現在はagent_memory→inquiries.yamlの片方向。内覧結果(viewed/decided/passed)をinquiries.yaml→agent_memoryに逆同期し、reply_assistが内覧済み情報を活用できるようにする

## Key Decisions
- **gh-pagesデプロイ方針（2026-03-20）**: `git add *.html`限定（-A禁止）。Python deploy()はGHA上スキップ。デプロイ条件=パトロール実行時は常時
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
- **agent_memory連携方針（2026-03-20）**: inbox-zeroのagent_memory.yamlをSSoTとし、property_pipeline.pyがsyncで取り込む。ステータスはアップグレードのみ（ダウングレード禁止）。GHAではGitHub API+GH_PATでクロスリポアクセス
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
- **特区民泊の新規受付は2026年5月29日で終了** → 残り約2ヶ月
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
| 日付 | サマリー |
|------|----------|
| 2026-03-20 #54 | QA全38項目PASS(データ整合性/出力品質/アーカイブ/パイプライン統合/冪等性/プレースホルダー/デプロイ/パトロールシミュ)。GHA auto-patrol rebase競合解消(`f067cc6`) |
| 2026-03-20 #53 | naiken-analysis.htmlフル自動生成化: 投資分析+メリット/リスク+チェックリスト+質問リスト+共通確認+アーカイブ+デザイン刷新 |
| 2026-03-20 #52 | agent_memory自動同期(`185c549`)+GHAクロスリポアクセス(`830df2a`)+GHAスタック解消(正常完了33m)+3/21福岡内覧3物件設定 |
| 2026-03-20 #51 | gh-pagesデプロイ修正(`22ea0f8`)+ポートフォリオツール(`648a213`)+テンプレート同期(`d7eefc6`)+パイプライン改善(`2e8c4d4`)+内覧可視化(`79de0a5`)+Projects横断constancy一掃(lib_sync_drift解消) |
| 2026-03-19 Session#72 | Pipeline構築+ティアフィルタ+Resilience原則+パトロール並列化+横展開(stock/kaizen)+Design Leverage Rule+open必須ルール |
| 2026-03-18 x-ref | GHA lib/欠落修正(`5d4bddb`)+Gmail通知追加(`4e8e594`)+マネタイズ戦略+WWH再構築+downloads-router 3層ルーティング |
| 2026-03-17 | 問い合わせ文面改善(共通コンテキスト+ペット丁寧表現+2拠点統一)+kaizen constancy WF単位強化 |
| 2026-03-16 | Cloud完全移行横断+.gitignore修正+lib同期drift+inbox-patrol廃止+Cloud-Primary Phase 2 |
| 2026-03-13 | 鮮度情報(first-seen)全ページ展開+CSS var --gnav-height+constancy github_actions_health |
| 2026-03-12 | 通知SSoT確立+URL encoding修正 |
| 2026-03-09 | Gnav統一+MAX_PER_CITY=10厳選 |
| 2026-03-07 | gnav 2層構造+全11軸スコアリング完成 |
