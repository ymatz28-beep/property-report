# HANDOFF

## [Constancy] 2026-03-18
- [WARN] structural_reform: search_multi_site.py is 1022 lines (threshold: 500). Consider splitting.
- [WARN] structural_reform: generate_search_report_common.py is 1158 lines (threshold: 500). Consider splitting.

## 最終更新: 2026-03-18（Projects横断 MEMORY.md更新 — downloads-router/tax_annual）

## 完了済み（2026-03-18 GHA lib/欠落修正 `5d4bddb`）
- **lib/をproperty-reportリポに追加** — renderer.py, design_tokens.py, templates(base/components/pages)。GHA上でlib.rendererが見つからずレポート生成が**全滅していた**根本原因を修正
- **sys.pathローカル/GHA両対応** — generate_search_report_common.pyのsys.pathをカレントディレクトリ(GHA)と親ディレクトリ(ローカル)の両方を検索するよう修正
- **jinja2をrequirements.txtに追加** — renderer依存
- **ローカル全4レポート成功確認** — 大阪50件/福岡65件/東京50件/問い合わせ10件、全QA OK
- **rebase+push完了** — GHAパトロールとfirst_seen.jsonコンフリクト→theirs採用で解決。`5d4bddb`をpush
- **GHAパトロール再トリガー済み** — Gmail通知で結果確認待ち

## 完了済み（2026-03-18 GHAパトロールGmail通知）
- **daily-patrol.yml にGmail通知ステップ追加（`4e8e594`）** — パトロール完了後、GHAワークフロー内でSMTP直接送信。PC閉じてもスマホGmailに届く。3パターン: ✅完了（レポートリンク）/ ⚠️部分成功（GHAログリンク）/ ❌失敗（自動リトライ通知）。secrets(GMAIL_ADDRESS/APP_PASSWORD/NOTIFY_ADDRESS)は設定済み

## 完了済み（2026-03-18 Projects#50 マネタイズ構想 横断影響）
- **マネタイズ戦略に不動産ドメイン組込** — 5ドメイン(健康/投資/AI/不動産/リーダーシップ)×PWA/SaaS戦略。property-analyzerの既存資産(スコアリングエンジン/パトロールデータ/収益計算)を「Property Quick Calc」として収益化候補に位置付け
- **monetization-strategy.md作成（Projects memory）** — 不動産ドメインの差別化(11軸スコアリング+パトロール自動化+民泊収益試算)とマネタイズパスを記録

## 完了済み（2026-03-18 kaizen-agent#72 横断影響）
- **lib同期drift修正（kaizen側 `5883ddf`）** — qa_output.py, renderer.pyをProjects/libからkaizen-agent/libに同期。property reportのQA/レンダリングに使われる共有ライブラリの不整合が解消
- **Digest夕方にSPOTLIGHT/SIGNALS追加（kaizen側 `19aee22`）** — 朝限定だったSPOTLIGHT/SIGNALSが夕方Digestにも表示。物件関連シグナルも夕方配信で確認可能に
- **CF Pages deploy-privateジョブ修正（kaizen側）** — PYTHONPATH/symlink設定、テンプレート4ファイルgit追加、content-level staleness検出。iuma-private.pages.devへのデプロイ安定性向上
- **IMAP診断ログ追加（kaizen側 `2639dc4`）** — 接続先・ソース数・取得件数をログ出力。Expert Insight IMAP問題の即座診断が可能に
- **GHA夕方Digest送信確認（kaizen側）** — SPOTLIGHT+SIGNALS+全セクション正常表示を実送信で確認

## 完了済み（直近セッション 2026-03-18 グランドデザインWWH再構築）
- **grand-design-new-products.md WWH再構築** — Property Quick Calc（不動産即判定）セクションにWhat/Why/How構造を適用。リスクと対策セクション追加（判定基準独善性・OCR精度・市況変動・法的リスク）
- **プロダクト優先順位変更** — 健康トラッカー Phase 0完了→Phase 1進行中で#1に昇格。不動産即判定は#2に
- **WWHフレームワーク CLAUDE.md昇格** — 「何かを新しく作る・設計する時は、必ずWWH分析を行う。例外なし。」3S直後・Constancy直前に配置
- **原則の階層確定** — WWH（企画）→ 3S（設計）→ Constancy（検証）→ Ritualize（運用）

## 完了済み（セッション 2026-03-17 問い合わせメッセージ文面改善）
- **全3パターンに共通コンテキスト追加** — エリア（大阪市西区・北区・中央区 / 博多区・中央区 / 渋谷区・新宿区等）、予算5,000万円以内、リノベ前優先、不在期間「2ヶ月ほど不在にすることもあり」を全テンプレートに追加
- **ペット可/相談可の文面改善** — 「ペット○○と記載がございましたが、念のため問題ございませんでしょうか」に変更。ペット不明は従来通り「ペット飼育は可能でしょうか」
- **2拠点生活「検討→実施」統一** — 全3パターン（portal_form/investor_portal/direct_email）で「2拠点生活を実施しており」に変更。property-reportへデプロイ済み（`4ad01af`）

## 完了済み（セッション 2026-03-17 kaizen-agent constancy横断影響）
- **GHA health ワークフロー単位検出（kaizen側）** — constancy github_actions_healthがリポ単位→ワークフロー単位に強化。property-report "Daily Property Patrol" 単発失敗は閾値(2回連続)未満で正常扱い。毎晩自動検出→Daily Digest配信

## 完了済み（2026-03-16 kaizen-agent#69 Cloud完全移行 横断影響）
- **GHAスケジュール再有効化（kaizen側）** — Daily Digest cron停止(3/11以降)が解消。property patrol結果を含むDigest配信が自動再開
- **pipeline health GHA対応（kaizen側）** — GHA上でもpipeline健全性チェックが動作。property patrol CIの死活監視が改善
- **inbox-patrol廃止（kaizen側）** — 形骸化していたinbox-patrolをlaunchd/コードから削除。kaizen launchd 5→4ジョブに簡素化
- **Knowledge Insights全Digest化（kaizen側）** — evening/midday digestにもYTナレッジ含まれるように。物件関連ナレッジも全時間帯で配信

## 完了済み（2026-03-16 kaizen-agent#63 横断影響）
- **CLAUDE.md Verification Before Done強化** — commit+pushはサブリポ単位で実行する明文化。完了時Before/After/Remainingサマリ義務化（ステップ6追加）
- **patrol_launcher.py Phase 2.5-4追加（kaizen側）** — constancy_checks含むフェーズ追加。git_uncommitted検出チェック新設
- **Gmail Sentデデュプ修正（kaizen側）** — 動的フォルダ検出 + MIMEデコードで日本語ロケール対応
- **midday digest追加（kaizen側）** — 1日2回→3回（morning/midday/evening）

## 完了済み（セッション 2026-03-16 scripts#48 横断影響）
- **.gitignore修正** — `!data/patrol_summary.json` 追加。Cloud Tier (GHA) がクロスリポでpatrol_summary.jsonを取得する際の404を修正
- **daily-patrol.yml push失敗修正（同日earlier）** — パトロール実行中にmainが別commitで先行し`git push`がrejected。`git pull --rebase origin main`をpush前に追加して解決。失敗runをre-run済み

## 完了済み（セッション 2026-03-13 問い合わせメッセージ改訂）
- **MAX_PER_CITY 20→10に変更** — 各都市10件ずつ計30件に縮小
- **問い合わせメッセージ全面改訂** — 以下の方針でテンプレート3パターン(portal_form/investor_portal/direct_email)を書き直し:
  - **2拠点生活ロジック**: 東京と○○の2拠点生活 → 不在時にウィークリー・マンスリー活用 → だから法人購入、という背景を自然に説明
  - **短期賃貸確認**: 管理規約取り寄せではなく「ウィークリー・マンスリーのような利用は可能か」の確認に留める
  - **ペット簡潔化**: 可/相談可→「チワワ（3kg）で問題ないか」、不明→「飼育可能か」のみ
  - **条件付き内覧**: 「上記の利用が可能であれば、ぜひ内覧をお願いしたい」のニュアンスに統一
  - **冗長削除**: 不要な前置き・署名欄を削除し簡潔化

## 完了済み（セッション 2026-03-13 stock-analyzer#41 横断改善）
- **通知グランドデザイン改革（横断影響）** — Gmail v2テンプレート(Bloomberg風)導入。物件セクション含むDaily Digestの見た目が一新
- **daily_digest.py一本化** — kaizen-agent側の1127行コピーをcanonical版(lib/)へのsymlinkに統一。物件通知のコードパスが簡素化
- **notification.md全面改訂** — LINE月間75-105通(枠38-53%)に予算改訂。物件関連LINE通知はHIGH新物件検出時のみの方針変更なし

## 完了済み（セッション 2026-03-13 stock-analyzer#40 横断改善）
- **鮮度情報（first-seen）全ページ展開** — 物件の初出日を `data/first_seen.json` に歴史的に復元・記録。property reportに初出日カラム追加。freshnessヘッダー表示
- **物件20件厳選** — 全エリア `MAX_DISPLAY` を50→20に変更（`generate_search_report_common.py`）。情報過多→厳選表示に方針転換
- **ソース略称化** — 17ソース中9件のソース名を短縮表示（レポート可読性向上）
- **page-nav QA** — セクションジャンプナビ消失の再発防止ルール追加（`lib/qa_output.py`）
- **CSS var `--gnav-height`** — gnav高さをCSS変数化。全sticky要素（section-jump等）がこの変数を参照する設計に統一（`lib/styles/design_tokens.py` + `lib/templates/components/nav.html`）
- **section-jump sticky修正** — `top:52px` でgnavの下にスタックするよう修正。`scroll-margin-top` も連動

## 完了済み（セッション 2026-03-13 kaizen-agent#58）
- **Property Patrol URL encoding修正+push** — `run_daily_patrol.py` `check_url_alive()` の `UnicodeEncodeError` 修正。全URL componentをpercent-encode。4日間連続GitHub Actions失敗の根本原因
- **constancy `github_actions_health`新設（kaizen側）** — Property Patrol 4日連続失敗が契機。`gh run list`で監視対象リポの連続失敗を自動検出。config.yamlでrepo/閾値管理
- **Verification Before Done CLAUDE.md昇格（kaizen側）** — 3S+PDCAを自律的に実行するための4ステップ必須チェックリスト

## 完了済み（セッション 2026-03-12 Projects横断）
- **daily-patrol.yml通知ステップ削除+push** — GitHub Actions workflow から `dawidd6/action-send-mail@v3`（Gmail）と `curl api.line.me`（LINE）を除去し、リモートに反映。ローカル変更のみでpush忘れが根本原因だった
- **通知SSoT確立** — 全通知(Gmail/LINE)は `lib/daily_digest.py` に一元化。property-analyzer単体の通知コードは全廃。kaizen-agent `notification_ssot` チェックが毎晩自動検出
- **launchd全4パイプライン復旧** — macOS TCC が `~/Documents/` への StandardOutPath/StandardErrorPath を遮断 → exit 78で全ジョブ停止。`/tmp/` に移動+`bootout/bootstrap` で復旧。※ daily-digest/inbox-patrol は plist再変更で再発中（exit 78）
- **CLAUDE.md「ローカル変更≠反映」ルール追加** — GitHub Actions workflow変更はcommit+push必須、launchd plist変更はbootout/bootstrap必須を明文化
- **9件の通知SSoT違反検出** — `qa_notify.py`, `stock-analyzer/notify.py`, `kaizen-agent/auto_fix_deploy.py` 等にデッドコード残存。constancyチェックが毎晩フラグ

## 完了済み（過去セッション要約）
- 2026-03-10: property-report ANTHROPIC_API_KEY設定、Mobile Update workflow修正、kaizen QA/Constancy巡回、民泊候補LINE単体通知廃止
- 2026-03-09: Gnav順序統一(全ページ)、パトロール通知JSON化、カレンダー形骸化清掃、DRY修正(newsletter_sources/gmail_utils新設)
- 2026-03-07: property-report gnav復元(都市ページ) + Mobile Update workflow追加
- 2026-03-05: property-report gnav修正、筑波銀行2物件返済計画反映、wealth dashboard更新
- 2026-03-04: Typography全面適用 + lint-typography.sh + gnav統一 + Inter統一 + 管理費dedupバグ修正 + ポートフォリオ基盤作成
- 2026-03-02: ペット不明スコア-15 + スマホ最適化(横スクロール方式) + Yahoo/R不動産enrichment + SUUMOスクレイパー作成
- 過去: git push修正、Daily Patrol GitHub Actions、カウカモ/Yahoo parser、全3都市レポート構築

## 進行中 / 未完了
- **GHAパトロール修正の動作確認待ち** — `5d4bddb`をpush+再トリガー済み。Gmail通知+gh-pagesレポート更新で修正完了を確認する
- **通知デッドコード残存** — `run_daily_patrol.py` 内のLINE通知コメントアウト部分等。notification_ssotチェックが検出済み。機能影響なし
- **P1: property-shared.css外部化** — 全CSSを1ファイルに集約し、変更が1箇所で全ページに反映される仕組みを構築
- **スコアリング改善（管理費ペナルティ強化）** — 現状max -5では高コスト物件が上位に残る
- **athome CAPTCHA** — 認証パズルでHTTP/Playwright両方ブロック。解決策なし
- **ポートフォリオダッシュボード数値確定+コミット** — generate_portfolio.py / qa_validate.py / templates/ が未コミット

## 次回アクション（優先順）
1. **GHAパトロール修正確認** — Gmail通知が届くか+gh-pagesレポート日付が3/18に更新されるか確認。失敗ならGHAログでlib importエラーを調査
2. **チサン博多 返済計画表** — wealth dashboardに反映
3. **内覧結果の反映** — 扇町・天満橋の内覧結果をデータに反映
4. **スコアリング改善+レポート再生成+デプロイ** — 管理費ペナルティ強化（-5→-10/-15等に拡大）
5. **通知デッドコード清掃** — notification_ssot違反ゼロを目指す
6. **property-shared.css + deploy URL一元化** — CSS外部化 + deploy URL散在統合
7. **ポートフォリオダッシュボード コミット+push** — generate_portfolio.py / qa_validate.py / templates/ が未コミット
8. **改善アイデア: lib/同期の自動化** — Projects/libとproperty-report/libが二重管理。GHAワークフローでlib/をProjects/libからコピーするステップ追加、またはgit submodule化でdrift防止

## Key Decisions
- **問い合わせメッセージ方針（2026-03-13）**: 2拠点生活→不在時ウィークリー/マンスリー活用→法人購入の背景説明。管理規約取り寄せはハードル高→可否確認に留める。ペットはチワワ3kgで問題ないかの一点確認。条件OKなら内覧したい、のニュアンス
- **問い合わせ共通コンテキスト追加（2026-03-17）**: エリア具体化（都市別）、予算5,000万円以内、リノベ前優先、不在期間2ヶ月。全テンプレート統一
- **2拠点生活は「実施」（2026-03-17）**: 「検討しており」→「実施しており」。すでに開始済みの事実を反映
- **MAX_PER_CITY 20→10（2026-03-13）**: 問い合わせ対象を厳選。上位10件に集中
- **Gnav統一順序確定（2026-03-09）**: Private: `Stock → Market Intel → Intel → Wealth → Action → Property → Travel`。Public: `Hub → Property → Travel`
- **gnav 2層構造（2026-03-07確定）**: site-header(グローバル) + .gnav(property固有サブナビ)
- **スコアリング全11軸**: budget(20), area(15), earthquake(15), station(15), location(20), layout(10), pet(+15/+10/-15), maintenance(10/-5→強化予定), renovation(5/-5), brokerage(5), minpaku_penalty(0)
- **MAX_DISPLAY 20→50（2026-03-18復元）**: 厳選しすぎでペット可物件が落ちる問題→50に戻し、ペット可優先保護ロジックで対応
- **CSS var --gnav-height（2026-03-13）**: sticky要素がgnav高さを参照
- **通知SSoT（2026-03-12）**: daily_digest.py一元化。他ファイルからの送信禁止
- **「ローカル変更≠反映」（2026-03-12）**: workflow→push必須、plist→bootout/bootstrap必須
- **URL encoding必須（2026-03-13）**: 日本語物件名→percent-encode
- **constancy github_actions_health（2026-03-13）**: CI連続失敗を自動検出
- **鮮度情報（first-seen）（2026-03-13）**: first_seen.jsonに永続記録
- **Verification Before Done強化（2026-03-16）**: サブリポ単位commit+push義務化 + Before/After/Remainingサマリ必須
- **WWHフレームワーク必須化（2026-03-18）**: 新規プロダクト/設計時にWhat/Why/How分析必須。HowだけでWhatとWhyを飛ばすことを禁止
- **プロダクト優先順位（2026-03-18）**: ①健康トラッカー(Phase 1進行中) → ②不動産即判定(既存資産再利用MVP) → ③健康トラッカーiOSアプリ
- **原則の階層（2026-03-18）**: WWH(企画) → 3S(設計) → Constancy(検証) → Ritualize(運用)
- **GHAパトロールGmail直接通知（2026-03-18）**: Daily Digest SSoTの例外として、GHAワークフロー内からSMTP直接送信。理由: PC閉じてても通知が届く必要がある（Daily DigestはGHA側でも動くが、パトロール完了直後の即時通知はワークフロー内が最速）
- **lib/リポ内包（2026-03-18）**: GHA上でlib.rendererが見つからない問題の根本対策として、lib/(renderer/design_tokens/templates)をproperty-reportリポに直接追加。sys.pathはローカル(親dir)とGHA(カレントdir)の両方を検索
- **マネタイズ戦略 不動産ドメイン（2026-03-18）**: property-analyzerの既存資産(11軸スコアリング+パトロール+民泊収益試算)を「Property Quick Calc」PWAとして収益化。Phase 2でエージェントチーム設計予定
- **GHAスケジュール再有効化（2026-03-16）**: Daily Digest cron復旧。property patrol結果の自動配信再開
- **inbox-patrol廃止（2026-03-16）**: 形骸化→削除。kaizen launchd簡素化
- **表示が空=データの問題。UIを変えるな（2026-03-16）**: テンプレートの表示制御は意図的設計。表示が空→データ側を修正。UIフォールバック全表示は禁止（stock-analyzer教訓、property-analyzerにも適用）
- 物件購入は法人（iUMAプロパティマネジメント）優先
- ペット不可: ハードフィルタで完全除外。不明(空欄): -15点
- 厳選フィルタ: MIN_SCORE=30 + MAX_DISPLAY=50 + ペット可優先保護
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
- 2026-03-18 Projects横断MEMORY更新: downloads-router 3層ルーティング記述拡充(個人→Drive/Cisco→OneDrive/証券CSV→data-bridge、不動産キーワード自動判定)。tax_annual.yaml参照追加(wealth-strategy PL連携用)
- 2026-03-18 GHA lib/欠落修正: lib/をリポに追加+sys.path両対応+jinja2追加。GHAレポート生成全滅の根本原因修正(`5d4bddb`)。パトロール再トリガー済み
- 2026-03-18 GHAパトロールGmail通知: daily-patrol.ymlにSMTP直接通知追加(`4e8e594`)。✅完了/⚠️部分成功/❌失敗の3パターン。PC閉じてもスマホGmailに届く設計
- 2026-03-18 Projects#50横断: マネタイズ5ドメイン戦略に不動産組込。Property Quick Calcとしてproperty-analyzer既存資産を収益化候補に。monetization-strategy.md作成
- 2026-03-18 kaizen#72横断: lib同期drift修正(qa_output.py/renderer.py)。Digest夕方SPOTLIGHT/SIGNALS追加。CF Pages deploy-private修正。IMAP診断ログ追加
- 2026-03-18 グランドデザインWWH再構築: Property Quick Calc設計にWWH適用+リスク対策追加。プロダクト優先順位変更(健康トラッカー#1→不動産即判定#2)。WWHフレームワークCLAUDE.md昇格
- 2026-03-17 問い合わせ文面改善: 共通コンテキスト追加(エリア/予算/リノベ/不在期間)+ペット可/相談可の丁寧表現+2拠点生活「検討→実施」統一。property-reportデプロイ済み
- 2026-03-17 kaizen constancy横断: GHA health検出がワークフロー単位に強化。property-report patrol単発失敗は閾値未満で正常。constancy命名確認(恒常性≠一貫性)
- 2026-03-16 kaizen#69横断: GHAスケジュール再有効化(Daily Digest cron復旧)。pipeline health GHA対応。inbox-patrol廃止。Knowledge Insights全Digest化
- 2026-03-16 kaizen#63横断: CLAUDE.md Verification Before Done強化（サブリポcommit+push + 状況サマリ義務化）。patrol_launcher Phase追加。Gmail Sentデデュプ修正。midday digest追加
- 2026-03-16 scripts#48横断: .gitignore `!data/patrol_summary.json` 追加（Cloud Tier 404修正）。daily-patrol.yml rebase修正
- 2026-03-13 問い合わせ改訂: MAX_PER_CITY 20→10。メッセージテンプレート全面改訂（2拠点生活ロジック、ウィークリー/マンスリー確認、チワワ3kg、条件付き内覧）
- 2026-03-13 stock#41横断: 通知グランドデザイン改革（Gmail v2 Bloomberg風）。daily_digest.py一本化。notification.md改訂
- 2026-03-13 stock#40横断: 鮮度情報(first-seen)全ページ展開。MAX_DISPLAY 50→20。ソース略称化。CSS var --gnav-height統一
- 2026-03-13 kaizen#58: Property Patrol URL encoding修正push。constancy github_actions_health新設。Verification Before Done昇格
- 2026-03-12 Projects横断: daily-patrol.yml通知除去+push。通知SSoT確立。launchd TCC復旧。「ローカル変更≠反映」ルール追加
- 2026-03-10: property-report ANTHROPIC_API_KEY設定。Mobile Update修正。kaizen QA/Constancy巡回。民泊LINE単体通知廃止
- 2026-03-09: Gnav順序統一。パトロール通知JSON化。カレンダー清掃。DRY修正。Credibility評価
- 2026-03-07: gnav復元(都市ページ) + Mobile Update workflow追加
- 2026-03-05: gnav修正。筑波銀行2物件反映。wealth dashboard更新