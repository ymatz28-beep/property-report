# HANDOFF

## 最終更新: 2026-03-05（Projects#43 gnav修正+iuma-private hub更新+筑波銀行返済計画）

## 完了済み（Projects#43）
- **property-report gnav修正（#43）** — 大阪/福岡/東京ページにgnav追加。private URL（Stock/Wealth/Action）除去、PublicリンクのみのProperty/Tripに限定。gh-pagesデプロイ済み（2ae066c）
- **iuma-private hubにProperty/Travel追加** — privateハブにリンク追加+デプロイ済み
- **筑波銀行 西浦和 返済計画表反映** — ¥144M/2.40%/¥507,107（月額返済）
- **筑波銀行 東浦和 土地つなぎ融資判明** — ¥47.3M/2.65%/利息のみ（期間中）
- **wealth dashboard 更新+デプロイ** — 上記2物件の返済計画を反映
- **lessons.md gnav欠落記録** — property-reportのgnav private URLリスクをlessons.mdに記録

## 完了済み（Projects#42）
- **Typography Rule全面適用** — property-report 6ファイルのh1 `clamp(28-46px)→clamp(20-26px)`、`--fs-display` `48px→36px`。push済み
  - minpaku output: fs-display 48px→36px。Cloudflareデプロイ済み
  - `design_tokens.py`: `--fs-display` `clamp(24px,5vw,48px)→clamp(22px,4vw,36px)`（唯一の定義元修正）
  - DESIGN_SYSTEM.md更新済み
- **lint-typography.sh作成** — 全HTML横断でfont-size>40pxを自動検出。patrol.sh Phase 2.5に組み込み
- **エコシステム根本改革レビュー（Creator→Critic完了）** — 個別レポートページのgnavにprivate URL残存をCriticが指摘。修正必要
- **worktree全クリーンアップ** — 6個の残存worktreeを削除

## 完了済み（セッション95-96）
- **gnav統一 + フォントInter統一** — 全ダッシュボード/レポートにグローバルナビ追加、フォントをInter統一
  - Private hub (iuma-private.pages.dev): h1削除・gnav追加・デプロイ完了
  - Public hub (report-dashboard): h1削除・gnav追加・push済み
  - Stock report / Action dashboard: gnav統一・フォントInter統一・再生成・デプロイ済み
  - Wealth pages / Trip planner / iuma-hub.html: gnav追加・フォントInter統一済み
  - inquiry-messages.html: site_header追加済み。タイトルから"iUMA"プレフィックス削除
- **site-header簡素化** — `.site-brand`（"iUMA"テキスト）を全property reportページから削除。ナビリンクのみのシンプルヘッダーに。モバイルブレークポイント768px→375pxに変更
- **管理費表示バグ修正** — dedup index=0 falsy bug修正、`_row_data_richness`優先度ロジック改善、fee=0ペナルティ(-3)追加、「データなし」表示、parse閾値1000→500
- **3都市レポート再生成+デプロイ** — rebaseコンフリクト解決（5ファイル: property_status.json + 4 HTML）→再生成→push完了
  - 管理費表示率: 大阪100%、福岡100%、東京90%
  - QA: 大阪50件OK、福岡70件OK、東京50件OK
- **git rebaseトラブル解決** — stash残留によるrebase continueループを、abort→stash drop→pull --rebase→theirs採用+再生成で解決
- **iUMA hub統合リンク検証** — iuma-hub.htmlからProperty Portfolio（`output/portfolio_dashboard.html` LOCAL）とProperty Reports（gh-pages WEB）の2系統リンクを確認
- **ポートフォリオダッシュボード基盤作成**（未コミット） — `generate_portfolio.py`（YAML→Jinja2→HTML）+ `templates/portfolio_dashboard.html` + `qa_validate.py`（利回り/DSCR/CCR/スコア/ローン計算の機械的検証）

## 完了済み（セッション94）
- **ペット不明スコア改善** — `pet_score_for_row()` の不明(空欄)スコアを0→-15に変更
- **テーブル列幅調整** — 最寄駅の「徒歩○分」が見えるように幅配分を最適化
- **3都市レポート検索条件表示更新** — 「ペット可は高加点（+15）、不明は-15」に変更
- **CLAUDE.md Autonomous QAルール強化** — レポートデプロイ後のQA巡回を自律実行ルールに昇格
- **QA巡回実施** — 3都市全レポートでペット不可混入ゼロ、上位5件全てペット+10以上を確認

## 完了済み（セッション93）
- **カンマ入り管理費の表示バグ修正** — `_format_maintenance_disp()` でカンマ含む管理費文字列が正常表示されるように修正
- **Yahoo不動産/R不動産のenrichment追加** — +104件の管理費内訳取得
- **管理費表示ラベル追加** — 管理のみ/合計/記載なし を区別して表示
- **ふれんずPlaywright enrichment関数の実装** — `enrich_ftakken_file()` を `enrich_maintenance.py` に追加。詳細ページから管理費+修繕積立金を個別取得する仕組み
- ⚠️ **ふれんずenrichment未実行（中断）** — 349件の詳細ページ巡回を開始したがバッファリング中に中断。0件処理済み

## 完了済み（セッション92）
- **スマホ最適化実装+デプロイ完了** — `generate_search_report_common.py` CSSメディアクエリ全面改修:
  - 768px / 640px ブレークポイント追加（計4段階: 960/768/640/480px→最終的に960/768/640の3段階）
  - ベースmin-width 1480px → 1180px に削減
  - Hero/Stats/Conditionsセクションをモバイルでコンパクト化（padding縮小、フォント縮小、sub-text非表示）
  - スコアバッジにtitle属性追加（長押しで11軸内訳を確認可能）
  - **方針決定: 列の非表示は行わない**。全12列を横スクロールで閲覧可能にする
    - 初回は hide-tablet/hide-phone で段階的に列を非表示にしたが、ユーザーから「管理費修繕や最寄駅が消える」とフィードバック → 全列維持+横スクロールに変更
  - セルフォント/paddingを768px以下で段階的に縮小
  - スコア内訳バッジのサイズも段階的に圧縮（260→180→140→120px）
  - 3都市レポート再生成+gh-pagesデプロイ完了

## 完了済み（セッション91）
- **モバイル最適化の詳細調査完了** — 11項目診断。実装はセッション92で実施

## 完了済み（セッション90）
- **プロジェクト構造・スコアリングロジック全体調査** — Exploreエージェントで`generate_search_report_common.py`のスコアリング関数（11軸）、レポートHTML/CSS、管理費パース・スコアリング・表示ロジックを網羅的に分析
- **3つの改善ポイント特定** — (1)管理費ペナルティ最大-5は弱すぎる→高コスト物件が上位に残る (2)管理修繕費の表示確認 (3)テーブルmin-width 700-800pxでスマホ横スクロール発生
- ⚠️ **Prompt is too longで中断（計3回）** — (1)Explore結果82kトークン→Read L430-609成功→Read L570-620で中断 (2)続行セッションで/compact失敗 (3)さらに続行で「どこで止まった？」の質問すらPrompt is too longで応答不可。合計6回のAPI拒否

## 完了済み（セッション89）
- **管理費データ旧形式一括修正** — SUUMO名前マッチングで92件修正（athome大阪9, multi_site福岡37, multi_site大阪9, 楽待福岡3, Yahoo福岡34）。100%完了: cowcamo東京/ftakken福岡/楽待東京

## 完了済み（セッション87-88）
- **SUUMOスクレイパー新規作成** (`search_suumo.py`) — 全3都市（大阪/福岡/東京）の中古マンション検索。詳細ページから管理費+修繕積立金をinline enrichment
- **億パーサーバグ修正** — `_parse_price_man()`が「1億1000万円」→「1000万円」と誤パース。search_suumo.py + search_lifull.py両方修正
- **東京SUUMOスラッグ修正** — `sc_shibuyaku`→`sc_shibuya`等、全10区。404エラーで0件だった東京が139件取得成功
- **日次パトロールにSUUMO組込み** — run_daily_patrol.pyにSUUMO追加（timeout=600s）
- **enrich_maintenance.py拡張** — SUUMOソース対応追加
- **LIFULL timeout修正** — networkidle待機→sleep(3)で安定化
- **QA閾値強化** — 管理費カバー率30%未満でエラー（以前はWARN）
- **GitHub Actions timeout延長** — job 60min, step 50min
- **問い合わせ文面作成** — 民泊可否確認用メッセージ（管理会社/仲介業者向け）

## 完了済み（セッション84-86）
- **git pushエラー(exit 128)修正** — credential.helper + .git-credentials手動設定を削除。actions/checkout@v4の組み込み認証に任せる

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
- ~~**公開gnavからprivate URL除去**~~ — **完了(2026-03-05)**。3都市全ページ修正+デプロイ済み
- **P1: property-shared.css外部化** — エージェントチーム議論で決定。全CSSを1ファイルに集約し、変更が1箇所で全ページに反映される仕組みを構築
- ~~**patrol QA警告: Fukuoka/Osakaモバイルスクロール**~~ — **修正済み(2026-03-07)**。3都市全ページmin-width:1180px削除+gh-pagesデプロイ済み
- **patrol QA警告: Tokyo pet-tokyo.html不在** — config修正済み、次回patrol(3/5 3AM)で解消予定
- **スコアリング改善（管理費ペナルティ強化）** — 現状max -5では高コスト物件が上位に残る。ペナルティ拡大が必要
- **Gmail通知認証エラー** — `535 BadCredentials`。アプリパスワード再設定必要
- **LINE通知方針変更** — 新物件検出時のみLINE通知。LINE Developers登録 + Secrets追加が必要
- **athome CAPTCHA** — 認証パズルでHTTP/Playwright両方ブロック。解決策なし
- **ポートフォリオダッシュボード数値確定+コミット** — generate_portfolio.py / qa_validate.py / templates/ が未コミット。数値検証後にコミット+デプロイ
- Webレポート v2（公開用・プライバシー対策版）の設計・実装

## 次回アクション（優先順）
1. ~~**公開gnavからprivate URL除去**~~ — **完了(2026-03-05)**
2. ~~**Fukuoka/Osakaモバイルスクロール修正**~~ — **修正済み(2026-03-07)**
3. **チサン博多 返済計画表** — 後回し→次セッションで反映
4. **Gmail通知修正** — アプリパスワード再発行 → `gh secret set GMAIL_APP_PASSWORD` → workflow_dispatchでテスト
5. **内覧結果の反映** — 扇町・天満橋の内覧結果をデータに反映
6. **スコアリング改善+レポート再生成+デプロイ** — 管理費ペナルティ強化（`maintenance_fee_score()`: -5→-10/-15等に拡大）
7. **LINE通知設定** — LINE Developers登録 → Messaging APIチャネル作成 → Secrets追加
8. **UI QA自動チェック** — daily patrolに`_run_ui_qa()`追加: フォント検査、site-header/gnav存在確認、iUMA混入チェック
9. 💡**改善アイデア: property-shared.css外部化** — 全ページのsite-header/gnav/フォント/変数CSSを`output/property-shared.css`に集約。CSS変更が1ファイルで全ページ反映される仕組み

## Key Decisions
- **モバイル最適化の現状と課題を詳細調査済み**（セッション91）: viewport meta ✓, レスポンシブグリッド(minmax) ✓, hide-mobile ✓(2列のみ)。不足: 768px/640pxブレークポイント未定義、テーブルmin-width 700-1480pxで横スクロール、スコア内訳列11バッジがモバイルで窮屈、生成ファイル間のmin-width不統一
- **スコアリング全11軸の構造確認済み**（セッション90、94で更新）: budget(20), area(15), earthquake(15), station(15), location(20), layout(10), pet(+15/+10/-15), maintenance(10/-5→強化予定), renovation(5/-5), brokerage(5), minpaku_penalty(0)。pet不明=-15に変更済み
- **管理費ペナルティ-5は不十分と判断**（セッション90）: 4万円超でも-5点しか減点されず、他の高スコアで相殺されて高コスト物件が上位に残る問題
- **Prompt is too long 6セッション連続**（85,86,89,90,90続行,90続行2）: Exploreエージェントが82kトークン消費→メインコンテキスト圧迫→/compactすら不可→ユーザー質問にすら応答不可。対策: 新規セッション+サブエージェント禁止+コード読み込み最小限
- **git push修正**: actions/checkout@v4の組み込み認証を使う。手動credential helper設定は不要かつ競合する
- **通知はcontinue-on-error: true** — Secrets未設定でもパトロール本体に影響なし。Gmail/LINE片方だけでもOK
- 物件購入は法人（iUMAプロパティマネジメント）優先
- **サイト構造**: report-dashboard（統合ハブ）→ property-report（不動産のみ）/ trip-planner（旅行のみ）/ stock/portfolio.html（株）。各サブサイトに← Dashboardリンク
- **デザイン言語**: DM Serif Display + Outfit + JetBrains Mono。ダークBG #050507、グレインテクスチャ、アニメーションorb。カテゴリ別アクセント: 不動産 #3b9eff / 旅行 #ff6b35 / 株 #8b5cf6
- **SSF設計**: CATEGORIES配列駆動。新カテゴリ追加 = 1オブジェクト追加するだけ
- ペット不可: ハードフィルタで完全除外。ペット不明(空欄): -15点（記載なし≒飼育不可と推定）
- 厳選フィルタ: MIN_SCORE=30 + MAX_DISPLAY=50 + ペット可優先
- 管理費enrichment: SUUMO（inline） + 楽待+カウカモ（enrich_maintenance.py） + SUUMO名前マッチング（他サイトの旧形式/空欄修正用、348物件lookup）
- 楽待の価格パラメータ（pmin/pmax）は万円単位
- **deploy_to_gh_pages()にはgit config user設定が必須**
- **レポート更新後は自律的にQAを実行する**
- **デプロイ後は必ずWebで反映を確認する**
- 特区民泊の新規受付は2026年5月29日終了
- **同種ミス2回以上はCLAUDE.mdに昇格して恒久ルール化する**
- **property-reportのデフォルトブランチはmain**（GitHub Actions認識のため変更済み。gh-pagesはデプロイ専用）
- **gh auth にworkflowスコープ追加済み** — ワークフローファイルをローカルから直接push可能
- **LINE通知は新物件検出時のみ**（kaizen#20）— 毎日パトロールは実行するがLINEは条件付き。Gmail+Webが主チャネル

## ブロッカー / 注意事項
- **Prompt is too longが7セッションで発生（85,86,89,90,90続行,90続行2,91）** — Exploreサブエージェントの大量結果がコンテキストを圧迫。次回対策: (1)必ず新規セッションで開始 (2)画像なし (3)サブエージェント禁止（調査完了済み） (4)コード読み込みは必要最小限(50行以内) (5)/compactを早めに実行
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

## Key Decisions (追加)
- **Typography全面適用+自動検査（Projects#42）**: h1 `clamp(20-26px)`、fs-display `36px`に統一。`lint-typography.sh`でfont-size>40pxを自動検出（patrol.sh Phase 2.5）。3層仕組み化: 思想(CLAUDE.md) + 定義(design_tokens.py) + 検査(lint→patrol)
- **公開gnavのOPSECリスク（Projects#42）**: 公開property-reportページのgnavにprivateサイトURL（Stock/Wealth/Action）が含まれている。URL構造漏洩リスクあり。公開ページはproperty/tripのみに制限すべき
- **Typography Rule適用（Projects#41）**: CLAUDE.md にh1 max 40px、モバイル max 24px、装飾的巨大テキスト禁止ルール追加。property reportのフォントサイズもこれに準拠
- **iUMA hubからproperty-analyzerへの2系統リンク**（セッション96）: Public（Property Reports → gh-pages）+ Private（Property Portfolio → output/portfolio_dashboard.html LOCAL）。ポートフォリオは非公開データ含むためローカルのみ
- **ポートフォリオダッシュボードはJinja2テンプレート分離方式**（セッション95）: `generate_portfolio.py`（YAML→Jinja2→HTML）。Template Protection原則に準拠。`qa_validate.py`で利回り/DSCR/CCR等の計算を機械的に検証
- **全ダッシュボードgnav+Inter統一完了**（セッション95）: Private/Public hub、Stock、Action、Property、Wealth、Trip、iuma-hub全てにグローバルナビ+Interフォント統一。デザイン言語の一貫性確保
- **管理費dedup index=0 falsyバグ**（セッション95）: Pythonの`if not index`でindex=0がFalseと評価されデータロスが発生。`if index is None`に修正
- **rebase conflict解決パターン**（セッション95）: 出力HTMLのコンフリクトは再生成で解決。theirs採用→スクリプト再実行→git add→rebase continue
- **ふれんず詳細ページは直接アクセス不可（403）**（セッション93）: 一覧ページ→詳細ページの順でNavigateする必要あり（session cookie依存）。万円表記（「1万4990円」等）のパース対応済み
- **Yahoo不動産/R不動産からも管理費enrichment可能と確認**（セッション93）: +104件の内訳取得に成功
- **スマホ最適化: 列非表示ではなく横スクロール方式を採用**（セッション92）: ユーザーフィードバックにより、hide-mobile/tablet/phoneで列を非表示にする方式はNG。管理費修繕・最寄駅・築年・評価など全列を維持し、横スクロールで閲覧可能にする。セルサイズの段階的縮小で対応

## History
- 2026-03-05 Projects#43: property-report gnav修正（3都市private URL除去+デプロイ）+ iuma-private hub更新 + 筑波銀行2物件返済計画反映（西浦和¥144M/東浦和¥47.3M）+ wealth dashboard更新
- 2026-03-04 Projects#42: Typography全面適用（6ファイルh1縮小+fs-display 36px+design_tokens修正）+ lint-typography.sh作成（patrol Phase 2.5）+ エコシステムレビューCritic指摘（gnav private URL除去必要）+ worktree 6個削除
- 2026-03-04 Projects#41: patrol QA確認 — Fukuoka/Osaka min-widthスマホスクロール警告、Tokyo pet-tokyo.html不在（config修正済み）。Typography Rule追加（CLAUDE.md）
- 2026-03-04 セッション95-96: gnav統一+Inter統一+site-header簡素化（brand削除・BP変更）+ 管理費dedupバグ修正 + rebase解決 + 3都市再生成push + iUMA hub統合リンク検証 + ポートフォリオ基盤作成（未コミット）
- 2026-03-02 セッション94: ペット不明スコア0→-15変更 + テーブル列幅調整（最寄駅拡大） + QA巡回自動化ルール追加 + 3都市再生成デプロイ
- 2026-03-02 セッション93: 管理費バグ修正(カンマ入り) + Yahoo/R不動産enrichment(+104件) + ふれんずPlaywright enrichment関数実装。349件巡回は中断（0件処理）
- 2026-03-02 kaizen#21 QA巡回: property-report/index.htmlのモバイルレスポンシブ調査。viewport+768/480px BP実装済み確認。640px以下の微調整を進行中に追加
- 2026-03-02 セッション92: スマホ最適化実装。4段階ブレークポイント追加、hero/stats/conditionsコンパクト化、スコアバッジtitle属性追加。ユーザーFBで列非表示→全列横スクロール方式に変更。3都市レポート再生成+デプロイ
- 2026-03-02 セッション91: モバイル最適化の詳細調査完了。CSS/メディアクエリ・全8HTMLレポートを分析し11項目の診断レポート生成。Prompt is too longで最終出力中断
- 2026-03-02 セッション90(+続行2回): スコアリング構造調査（全11軸分析）+ 改善3点特定。Prompt is too longで3回中断（Explore 82kトークン→/compact不可→質問応答すら不可）
- 2026-03-02 セッション89: 管理費旧形式一括修正（SUUMO名前マッチで92件修正）。レポート再生成は「Prompt is too long」で中断
- 2026-03-01 kaizen#20反映: LINE通知最適化 — 新物件検出時のみLINE通知（`send_line_if_new()`）。月間LINE使用量~5通/月に
- 2026-03-01 セッション87-88: SUUMOスクレイパー新規作成 + 億パーサーバグ修正 + 東京slugs修正 + 日次パトロール組込み + QA強化。大阪115件/福岡187件/東京112件
- 2026-02-26 セッション86: Prompt is too longエラーで作業不可（画像+長大コンテキスト。2セッション連続）
- 2026-02-26 セッション85: Prompt is too longエラーで作業不可（画像貼付が原因の可能性）
- 2026-02-26 セッション84: git pushエラー修正（credential helper競合解消 + 条件付きpush）
- 2026-02-26 セッション83: Gmail+LINE通知追加 + テスト実行成功(25m5s) + Gmail認証エラー発覚(BadCredentials) + git pushエラー(exit 128)
- 2026-02-26 セッション82: Daily Patrol GitHub Actions稼働確認完了(24m41s) + CI最適化(SOLDスキップ/タイムアウト調整/PYTHONUNBUFFERED) + gh auth workflow追加 + デフォルトブランチmain化
- 2026-02-26 セッション81: GitHub Actions daily-patrol作成 + deploy()2重実行修正 + requirements.txt更新 + セッション74-80蓄積一括push
- 2026-02-26 セッション78-80: CLAUDE.md圧縮+強化、カウカモ/Yahoo parser修正、管理費enrichment、厳選フィルタ、統合ランディング、デザイン統一、スマホ対応
- 2026-02-25 セッション75-77: 管理費スコアリング + ペット不可フィルタ + スコア内訳UI + 内覧分析ページ + SUUMO enrichment修正 + QA自動化

