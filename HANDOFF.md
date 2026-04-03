# HANDOFF

## Last Updated
2026-04-03

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
1. **Phase 3: enrich拡張**: 楽待詳細ページ取得時にサブリースの「Point」欄スキャン + 複数駅補完（ネットワーク依存、後日）
2. **中野さんへの返信ドラフト精査**: 4/2自動ドラフトは実態（電話済み・OC内見不可・澤畠さん打診）を反映していない
3. **内見済み3件の銀行査定フォロー**: プレイスポット/GSハイム/ローズマンション → 筑波銀行結果確認
4. **一棟もの物件**: 中野さんが未公開物件を探すと言っていた（3/24）→ フォロー
5. **Name Quality FAIL**: 東京の「値下げしました！東武練馬駅徒歩7分」→ auto_fixのBUILDING_MARKERSに該当しないパターン。手動修正 or パターン追加

## Key Decisions
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
1. 2026-04-03: データ品質自動QA+自動修正パイプライン（qa_market 4チェック + auto_fix_data_quality + deploy_market.sh + 複数駅対応 + パイプライン免除 + 手動修正6件 + メゾン・ド・サブリース推定）
2. 2026-04-02: SSoT Property Registry + Pipeline v2 + サブリース除外 + intel_extractor + スコアリング修正
3. 2026-04-01: 健美家利回り修正 + DEFAULT_CITY + メールドラフト作成
4. 2026-03-31: マーケット品質改善（広告コピー7パターン+戸建て除外+OC収入補完）
5. 2026-03-31: パイプライン形骸化解消（lifecycle自動管理+メール連動+UI刷新）
6. 2026-03-30: 取得諸費用計上+掲載日クリーンアップ+福岡格安デバッグ
7. 2026-03-29: kaizen Visual Regression チェック追加
8. 2026-03-28: 朝夕2系統テンプレートリライト+section_navコンポーネント
9. 2026-03-27: Cisco Talent Review+property_patrol_steps内部失敗検知
10. 2026-03-26: kaizen-agent QA改革（patrol復活+インフラ整備）
11. 2026-03-25: CLAUDE.md Before/After必須化昇格
12. 2026-03-24: 内見分析ダッシュボード+reply_assist+中野さん対応
13. 2026-03-23: Dashboard gnav統一+property inquiry pipeline
14. 2026-03-22: 不動産パイプライン構築+物件スコアリング
15. 2026-03-21: Dashboard UX改善+モバイル最適化
16. 2026-03-20: Property analyzer福岡+大阪+東京統合
17. 2026-03-19: Agent memory構築+Reply assist Phase 3
18. 2026-03-18: Property dashboard公開+Cloudflare Access設定
19. 2026-03-17: Market report統合ページ構築
20. 2026-03-16: 収益物件フィルタ設計+CF/CCR計算
