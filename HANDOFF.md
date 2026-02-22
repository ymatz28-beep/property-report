# HANDOFF

## 最終更新: 2026-02-22（セッション69）

## 完了済み（直近セッション）
- HANDOFF.md の確認・更新（セッション69: コード変更なし。未コミット6ファイル＋未追跡5ファイルの状態継続）

## 完了済み（過去セッション）
- HANDOFF.md の確認・更新（セッション3-66）
- property-analyzer コードベース全体の把握
- 確定申告パターン分析（2021-2024）の読み込み・投資家プロフィール把握
- 大阪R不動産 4物件のWebスクレイピング・基本情報取得
- 4物件の自宅兼民泊モデル分析（compare_osaka_r.py）
- Webレポート v1 作成・GitHub Pages公開（https://ymatz28-beep.github.io/property-report/）
- iUMA第8期決算書（R6.7.1-R7.6.30）の全ページ読み込み・データ抽出
- iUMA勘定科目内訳明細書（預貯金・借入金・仮受金等）の抽出
- ポートフォリオ戦略ダッシュボード（ローカルHTML）作成
  - `output/portfolio_dashboard.html` — 全11セクション、Chart.js、ダークテーマ
  - 個人4物件 + 法人4物件の統合ビュー
  - 年収定義の修正（給与所得 / 不動産収入 / 不動産所得を分離）
  - 税務分析（個人損益通算 vs 法人税率）
  - CF分析、融資一覧、大阪候補比較、戦略・ロードマップ
- 不動産業者（大阪R不動産）からの回答取得・重要事項調査報告書分析（2026-02-21）
  - 全4物件の管理規約・民泊可否・ペット・修繕履歴を確認
- **投資家プロフィール（FinancialProfile）の分析パイプライン統合**
  - `run.py`: 9ステップに拡張。Google Drive → ローカルPDF → キャッシュの3段階でプロフィール取得
  - `src/financing.py`: 実年収・既存借入によるDTIチェック追加（45%/50%閾値）
  - `src/tax_compare.py`: 給与所得＋不動産所得の合算で累進税率を適用（損益通算対応）
  - `src/risk.py`: 財務リスク評価追加（DTI、ポートフォリオ集中、レバレッジ倍率）
  - `config.yaml`: Google Drive連携設定セクション追加
  - `test_daikoku.py`: テスト用FinancialProfileでの統合テスト追加

## 進行中 / 未完了
- 変更ファイル6件が**未コミット**（config.yaml, run.py, src/financing.py, src/risk.py, src/tax_compare.py, test_daikoku.py）
- 未追跡ファイル: .claude/, HANDOFF.md, compare_osaka_r.py, output/osaka_r_report.html, output/portfolio_dashboard.html
- `src/tax_extractor.py` のインポートが `run.py` に追加されたが、このファイル自体の変更は未確認（既存のはず）
- Webレポート v2（公開用・プライバシー対策版）の設計・実装
- ポートフォリオダッシュボードの数値確定（西浦和・東浦和の取得価額・融資額）
- GitHub Pages v1レポートのプライバシー対策 or 非公開化

## 次回アクション（優先順）
1. **未コミット変更をコミット**（FinancialProfile統合の6ファイル + 未追跡ファイル）— **62セッション放置中、最優先**
2. **#1 扇町の民泊可否を大嶺さんに確認**（重要事項調査報告書の「専有部分用途」欄）
3. 扇町が民泊可の場合 → 自宅兼民泊モデルで再分析（investor_profile付き）
4. 扇町が民泊不可の場合 → 方向性2（#3東天満を純粋自宅＋節税で評価）と方向性3（別物件探し）を本格検討
5. 西浦和・東浦和の取得価額・融資額をGoogle Driveから取得（ダッシュボード数値確定用）
6. レポートv2のHTML設計・実装（プライバシー対策適用）
7. GitHub Pages v1の非公開化 or v2で差し替え
8. **改善アイデア**: HANDOFF更新だけのセッションが**63回連続**。276行の変更が63セッション以上放置されている。**次回セッション冒頭でコミットすべき**。コマンド1つで完了:
   ```
   git add config.yaml run.py src/financing.py src/risk.py src/tax_compare.py test_daikoku.py compare_osaka_r.py output/ HANDOFF.md .claude/ && git commit -m "feat: integrate FinancialProfile into analysis pipeline"
   ```
   **根本対策**: SessionEnd hookがproperty-analyzerのHANDOFFを毎回更新するが、実作業がない限りノイズにしかならない。**hookの対象からproperty-analyzerを除外する** or **git diffが空ならHANDOFF更新をスキップするロジックを追加する**ことで、無意味なセッション消費を防げる

## ブロッカー / 注意事項
- **大阪4物件中3物件が民泊禁止確定** → 自宅兼民泊モデルは扇町以外成立しない
- #1 扇町の民泊可否が最重要の未確認事項
- **特区民泊の新規受付は2026年5月29日で終了** → 期限に注意（残り約3ヶ月）
- Google Drive MCP接続エラー（invalid_request）→ ローカルファイル or ユーザー提供で回避
- 西浦和・東浦和の取得価額・融資条件が未取得 → ダッシュボードの総額が未確定
- 東浦和は土地のみ契約済、建物金消2026年8月 → 稼働は2026年後半以降
- 現在の公開レポート（v1）にはプライバシー対策が未適用（民泊前提の分析が掲載中）
- iUMA第8期の既存物件の正体（日本政策金融公庫20M融資対象）が不明
- クレストモール仙台の詳細（所有 or 管理受託?）が不明
- DTI約61.7%（閾値45%超過）→ 追加融資困難

## 環境構築メモ (PC交換用)
- Python 3.13
- `pip install -r requirements.txt`（anthropic, pyyaml, openpyxl, reportlab, Pillow, numpy）
- 環境変数: ANTHROPIC_API_KEY
- GitHub Pages: property-report リポ（gh-pagesブランチ）
- `gh` CLI でデプロイ
- ローカルHTMLレポート確認: `open output/portfolio_dashboard.html`
