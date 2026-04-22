# property-report HANDOFF

## [Auto-Kaizen] 2026-04-20
- [WARN] property-report/HANDOFF.md not updated in 7 days (threshold: 7).




## Last Updated
2026-03-29

## Completed (プレイスポットCF損益分岐シミュレーション + 銀行リフォーム融資相談 2026-03-29 x-ref)
- **Before**: プレイスポットしんばしビル本館（SRC造/1975年築/2,480万）のCF損益分岐が不明。リフォーム費用の融資方法も未相談
- **After**: revenue_calc.pyで4シナリオ（家賃13-14万×ローン15-20年）をシミュレーション。現行2,480万は全シナリオCF赤字（月CF -0.4〜-3.9万）。20年融資+家賃14万なら▲100万（2,380万）でCFトントン、家賃13万なら▲270万（2,210万）必要。15年ローンは▲580-710万で非現実的。澤畠さん（筑波銀行）へリフォーム融資相談メールをドラフト+送信済（thread 19aed7a499a86ed8）
- **Commits**: property-analyzer側。property-report直接変更なし

## Completed (Projects Skill Routing + story-intake 2026-03-27 x-ref)
- **Before**: CCスキルの発火がコマンド暗記式。story-intakeは「実は〜」「昔〜があって」のみトリガー、「インタビューして」では発火しなかった
- **After**: Projects/CLAUDE.mdにSkill Routingテーブル追加（8パターン自動発火）。story-intakeに「インタビューして」「話を聞いて」「ネタにして」トリガー追加。SNSネタ0→20件、SNS Dashboard新設、CCスキル3→18個
- **Commits**: Projects root（CLAUDE.md編集）、~/.claude/skills/story-intake/SKILL.md編集。property-report直接変更なし

## 完了済み（直近セッション 2026-03-25）

### dotfiles環境完備+drift自動検出（2026-03-25 x-ref）
- **Brewfile拡張**: 10→15パッケージ（deno, mlx, tesseract, zeromq, python@3.14追加）— dotfiles `c88ae1f`
- **setup.sh拡張**: 4→8ステップ（npm global, launchd plist移行, ollama, venv自動化 + 手動認証チェックリスト）
- **launchd plist**: 7個をdotfiles/launchd/にバックアップ（daily-digest, downloads-router, leader-digest, market-refresh, reminders-sync, stock-analyzer, webex-digest）
- **kaizen-agent drift検出**: 毎晩brew leaves + npm global vs dotfiles比較。差分あれば自動修正+commit — kaizen `3553059`
- **IME辞書**: Google IME設定ファイルをdotfilesに追加

### kaizen-agent横断セキュリティ監査（2026-03-21 x-ref）
- **property-report全7ファイル: Private URL漏洩なし** — `iuma-private.pages.dev`への参照ゼロ確認
- **renderer.py `_public_nav`**: Hub/Property/Travelのみ。Private URLなし
- **2層設計（scope=public/private）が正常機能**: _private_navに追加してもPublic側に波及しない設計を確認

### GHAデプロイ成功+ライブ検証（#58後半）
- **GHA run 23326607063 成功**: patrol + deploy + Gmail通知 全ステップ完了（約33分、接続リセット1回あるも正常完了）
- **ライブサイト全修正反映確認**: toggle CSS✅、44pxタッチターゲット✅、sticky header✅、class名統一(gnav)✅
- **3ページブラウザ目視確認**: minpaku-osaka / index / inquiry-pipeline をopenで開いて検証
- **Auto-deploy** (`3fd5c36`): 2026-03-20自動デプロイ成功
- **3/20パトロール正常稼働確認**: 巡回・更新・通知すべて正常動作

### モバイルハンバーガー修正（#58）
- **全7ページ修正** (`bf4f51c`): sticky/toggle/touch-target/z-index/class統一
- テンプレートcanonical+local同時修正、横断QA全PASS

## 前セッション完了
- **GHA deployスクリプトをclone方式に書き換え** — merge conflict構造的排除 + 3日分gap recovery + GHA初回テスト成功 + Gmail通知✅確認
- **GHA Daily PatrolにGmail通知ステップ追加** (`4e8e594`): 成功/部分成功/失敗をGmailで通知
- **物件リスト20件厳選+UX改善** (#40): MAX_DISPLAY 50→20、クロスページナビ、鮮度インジケーター

## 進行中 / 未完了
- **LINE通知未設定** — LINE Developers登録 + Messaging APIチャネル作成 + Secrets追加が必要
- **athome CAPTCHA** — 認証パズルでHTTP/Playwright両方ブロック。解決策なし
- **Node.js 20 deprecation警告** — actions/checkout@v4, actions/setup-python@v5がNode.js 20で動作中。2026年6月2日以降Node.js 24強制。v5/v6へのアップデートが必要

## 次回アクション（優先順）
1. **澤畠さん（筑波銀行）融資回答フォロー** — 物件一覧メール送信済+リフォーム融資相談メール送信済。20年融資可否の回答待ち。3月末期限
2. **中野さん未公開一棟もの提案待ち** — 提案受領後にittomono検索結果と照合・分析
3. **ittomono.htmlのGHAデプロイ反映** — property-analyzerで生成済み、daily-patrol.ymlのデプロイ対象に追加
4. **GHA actionsのNode.js 24対応** — checkout@v4→v5, setup-python@v5→v6 にアップデート（6月2日期限）
5. **LINE通知設定** — LINE Developers登録 → Messaging APIチャネル作成 → Secrets追加
6. **💡改善: 面積精度改善** — property-analyzerの次回スクレイプで面積データの精度向上を反映

## Key Decisions
- **deploy方式をclone方式に変更（2026-03-20）**: 作業ツリー内checkout→pushではなく、`/tmp/gh-pages-deploy`に別クローン→HTML上書き→push。merge conflictが構造的に不可能
- **問い合わせ共通コンテキスト（2026-03-17）**: 全テンプレートにエリア具体名（都市別）、予算5,000万円以内、リノベ前優先、不在期間「2ヶ月ほど」を統一追加
- **2拠点生活は「実施」（2026-03-17）**: 「検討しており」→「実施しており」。すでに開始済みの事実を反映
- **MAX_DISPLAY 20（2026-03-13）**: 全エリアの物件リスト表示を50→20に削減。情報過多防止、一覧性向上
- **鮮度インジケーター（2026-03-13）**: 物件の初出日をgit履歴から復元し、各物件にfreshness表示。新着/既知の判別を容易に
- **スマホ更新はGitHub Pagesの3リポのみ（2026-03-10確定）**: stock/wealth/intelはCloudflare Pages+リモートリポなし。ROI低いため対応見送り
- **Self-hosted Runner不採用（2026-03-10）**: 3S不適合。ubuntu-latestで十分
- **gnav統一順序（2026-03-09確定）**: 全iuma-privateページのnav = `Stock → Market Intel → Intel → Wealth → Action → Property → Travel`
- **gnav 2層構造（2026-03-07確定）**: site-header(gnav) = グローバルナビ + .gnav(Hub/大阪/福岡/東京/内覧分析/問い合わせ) = property固有サブナビ。両方必須
- **Typography 3層仕組み化（2026-03-04）**: (1)CLAUDE.mdルール (2)design_tokens.py定義元修正 (3)lint-typography.sh毎晩自動検査。fs-display上限36px、h1最大40px
- **Daily Digest統合通知（2026-03-04）**: QA warningはDaily Digest経由で通知（digest→Gmail, alerts→LINE）
- **Public/Private分離（2026-03-02）**: property-report=公開（GitHub Pages）、portfolio=Cloudflare Access
- **モバイル対応方式（2026-03-02）**: テーブル横スクロール + 重要列のみ表示。4段階ブレークポイント
- **Auto-update方式**: property-analyzerからの自動生成 → gh-pagesにpush
- **git push修正**: actions/checkout@v4の組み込み認証を使う。手動credential helper設定は不要
- **通知はcontinue-on-error: true** — Secrets未設定でもパトロール本体に影響なし
- **Gmail通知はGHA側SMTP直送（2026-03-18）**: Daily Digest統合ではなく、パトロール完了直後にGHA workflow内からSMTP送信。PC閉じてても届く
- 物件購入は法人（iUMAプロパティマネジメント）優先
- **サイト構造**: report-dashboard（統合ハブ）→ property-report（不動産）。← Dashboardリンク
- **SSF設計**: CATEGORIES配列駆動。新カテゴリ追加 = 1オブジェクト追加するだけ
- ペット不可: ハードフィルタで完全除外
- 厳選フィルタ: MIN_SCORE=30 + MAX_DISPLAY=20 + ペット可優先
- 管理費enrichment: 楽待+カウカモの詳細ページから取得
- 楽待の価格パラメータ（pmin/pmax）は万円単位
- **deploy_to_gh_pages()にはgit config user設定が必須**
- **レポート更新後は自律的にQAを実行する**
- **デプロイ後は必ずWebで反映を確認する**
- **patrol並行push対策（2026-03-16）**: daily-patrol.ymlに`git pull --rebase`追加。Issue auto-commit等との並行pushでreject→自動rebaseで解決
- 特区民泊の新規受付は2026年5月29日終了
- **プレイスポット20年融資が投資判断の分岐点（2026-03-29）**: 15年ローンだとADS 162.7万 vs NOI 116万で大幅赤字。20年なら130.3万に下がり、家賃14万取れれば▲100万指値でCFトントン。融資期間が物件Go/No-Goを決定する
- **リフォーム費用の融資方法を銀行に相談（2026-03-29）**: プレイスポット+GSハイム博多の内装更新200〜300万。物件融資に含めるか別途リフォームローンか、澤畠さんに打診済
- **property-reportのデフォルトブランチはmain**（gh-pagesはデプロイ専用）
- **gh auth にworkflowスコープ追加済み**
- **subproject track分離（Projects #51, 2026-03-20）**: ルートリポの.gitignoreにproperty-report/追加。ルートリポからのtrack除外（独自リポ管理）
- **z-index階層統一（2026-03-20）**: site-header=100(sticky,top:0) > gnav=90(sticky,top:52px)。ハンバーガードロップダウン=200（親stacking context内）。gnav旧値9999は過剰だった
- **infra-manifest.yaml登録（2026-03-20 x-ref）**: property-reportがdeployments SSoTに正式登録。platform=github-pages, trigger=GHA daily-patrol.yml(21:00 JST), branch=gh-pages

## ブロッカー / 注意事項
- **特区民泊の新規受付は2026年5月29日で終了** → 残り約2.3ヶ月
- **Node.js 20 deprecation（6月2日期限）** — GHA actionsをNode.js 24対応版にアップデート必要
- athome全都市でCAPTCHA認証ブロック（解決不可）
- Yahoo大阪はターゲットエリア内1件のみ
- DTI約61.7% → 個人追加融資困難。法人融資で対応
- property-analyzerが上流。データ生成はそちらで行い、HTMLをこのリポにpush
- **GitHub Pagesキャッシュ**: max-age=600（10分）。デプロイ直後は404/古い版が出る → Cmd+Shift+Rでハードリロード

## 環境構築メモ (PC交換用)
- Python 3.14（dotfiles Brewfileで管理、python@3.10/3.13も併存）
- `pip install -r requirements.txt`（anthropic, pyyaml, openpyxl, reportlab, Pillow, numpy, requests, beautifulsoup4, playwright）
- `playwright install chromium`
- 環境変数: ANTHROPIC_API_KEY
- GitHub Pages: https://ymatz28-beep.github.io/property-report/
- デフォルトブランチ: main（gh-pagesはデプロイ専用）
- property-analyzerからの自動pushで更新される
- 手動変更時はgh-pagesブランチで作業 → push
- Mobile Update: 'update'ラベル付きIssueで自動反映（ANTHROPIC_API_KEY secret設定済み）
- **PC交換時**: `~/dotfiles/setup.sh`で一括セットアップ（brew bundle + npm global + launchd plist + venv）

## History
| 日付 | サマリー |
|------|----------|
| 2026-03-29 x-ref | Before: プレイスポットCF損益分岐不明+リフォーム融資未相談 → After: 4シナリオCFシミュレーション完了（20年+14万→▲100万でトントン）+澤畠さんにリフォーム融資相談メール送信済 |
| 2026-03-27 x-ref | Before: スキル発火がコマンド暗記式、story-intakeトリガー不足 → After: Skill Routing 8パターン自動発火+story-intakeに「インタビューして」追加。property-report直接変更なし |
| 2026-03-25 x-ref | dotfiles Brewfile拡張(10→15pkg) + setup.sh 4→8ステップ + launchd 7plist移行 + kaizen-agent環境drift自動検出追加(`3553059`)。property-report直接変更なし |
| 2026-03-24 x-ref | kaizen-agent action_tracker.py: Ciscoアイテムにdigest source連携追加（`_load_digest_index()`+ソースバッジ+Leader Digestリンク+折りたたみサマリー）。cisco-os/leader_digest.pyも複数回改修。property-report直接変更なし |
| 2026-03-23 x-ref | kaizen-agent #90: constancy_checks.py分割(1712→202L facade+6モジュール)+violation_tracker新規(14日放置→自動エスカレーション)。property-reportのgnav_consistency警告も追跡対象に。push済(`a34b7bc`) |
| 2026-03-22 x-ref | trip-planner fukuoka.html作成: 温泉・グルメ・エリアガイド・アクセス・Tips。gnav共有（Hub/Property/Travel）でproperty-reportへのリンク含む |
| 2026-03-21 x-ref | kaizen-agent横断セキュリティ監査: property-report全7ファイルPrivate URL漏洩なし✅。renderer.py _public_nav正常。2層scope設計が正常機能 |
| 2026-03-20 x-ref | infra-manifest.yaml deployments section追加: property-reportをGitHub Pagesデプロイターゲットとして文書化（trigger/branch/url）。deploy-private.shはmanual fallbackに明確化 |
| 2026-03-21 #58 | GHAデプロイ完了+ライブ検証: toggle CSS/44px touch-target/sticky header/class統一 全反映確認。パトロール・更新・通知すべて正常稼働確認 |
| 2026-03-20 #58 | モバイルハンバーガー修正(`bf4f51c`): 全7ページ(sticky/toggle/touch-target/z-index/class統一)、テンプレートcanonical+local同時修正、横断QA全PASS |
| 2026-03-20 | GHA deployスクリプトをclone方式に書き換え（merge conflict根絶）+ 3日分gap recovery + GHA初回テスト成功(33m18s) + Gmail通知✅確認 |
| 2026-03-20 x-ref | Projects #51 クロスリファレンス: subproject track分離(.gitignore追加)。property-report固有作業なし |
| 2026-03-18 | GHA Daily PatrolにGmail通知追加(`4e8e594`): 成功✅/部分成功⚠️/失敗❌をSMTP直送 |
| 2026-03-17 | 問い合わせ文面改善: 共通コンテキスト追加(エリア/予算/リノベ/不在期間)+ペット丁寧表現+2拠点「検討→実施」統一。property-analyzerからデプロイ |
| 2026-03-17 #70 x-ref | kaizen-agent GHA health monitoring対象に追加: Daily Property Patrol + pages-build-deploymentをワークフロー単位で自動監視（kaizen `99b48b8`） |
| 2026-03-16 #48 | .gitignore修正: `!data/patrol_summary.json` 追加（GHAクロスリポ取得404修正）+ patrol復旧(git pull --rebase追加で並行push対策) |
| 2026-03-13 #40 | 物件リスト50→20件厳選 + クロスページナビ追加 + 初出日git履歴復元 + 鮮度インジケーター全ページ展開 + page-nav QA再発防止 + ソース略称化(17→9件短縮) |
| 2026-03-10 | APIキー再設定(3リポ) + workflow修正(--api-keyフラグ削除) + Self-hosted Runner撤去 |
| 2026-03-09 | iuma-private gnav統一: 全ページnav順序を7項目に統一(Intel追加) + Cloudflareデプロイ |
| 2026-03-07 | gnav復元: 都市3ページにproperty固有サブナビ追加(78fb034) + Mobile Update workflow追加 |
| 2026-03-05 | **#43** gnav修正: 大阪/福岡/東京にsite-header追加+private URL除去 |
| 2026-03-04 | **#42** Typography全面適用: h1 6ファイル clamp修正 + fs-display 48→36px + lint-typography.sh仕組み化。Auto-update 2回 |
| 2026-03-03 | Auto-update reports 1回 |
