# HANDOFF

## Last Updated
2026-04-02

## Completed (SSoT + intel_extractor + Pipeline v2 + スコアリング修正 2026-04-02)
- **Before**: データが5ファイルに分散しSSoTなし（修正が伝播しない）。パイプラインは都市タブで進捗不明。サブリース物件が混在。メールの知見が構造化されない。住所の「博多駅南」が「博多駅エリア」と誤判定（竹下徒歩15分が100pt 1位）。大名サンハイツ/美野島シャトー/博多ニッコーハイツがパイプライン未登録/誤pass
- **After**:
  - **Property Registry SSoT**: property_status.json → 中央レジストリ（overrides + write-through sync）。1箇所修正で全出力に伝播
  - **intel_extractor**: Ollama(qwen3:8b)で6タイプ抽出（rent_actual/rent_constraint/market_opinion/future_action/listing_status/general_intel）。future_actionはパイプライン自動登録
  - **Pipeline Dashboard v2**: ステージタブ化（進行中/内見/査定中/完了/候補）。KPI 5枠。passed最下部折りたたみ
  - **サブリース即除外**: 5箇所（scrape/report/auto-flag/lifecycle/profitable）。中野さん知見に基づくルール
  - **--recalc**: rent_estimateからCF/CCR再計算
  - **reply_assist統合**: intel_extractor差し込み + ダッシュボード自動再生成トリガー
  - **lifecycle sweep**: [future:YYYY-MM]タグで誤pass防止
  - **スコアリング修正**: 住所の「駅南/駅前」パターンを除外。トピレック博多88→68pt
  - **データ修正**: ルエ・メゾン(170万→580万/ふれんずURL)、博多ニッコーハイツ(passed→in_discussion復元)、大名サンハイツ/美野島シャトー(新規登録,5月以降内覧)
  - **SSoT伝播原則**: CLAUDE.md Workflow Rulesに昇格（全プロジェクト横断）
  - **topic seeds**: 5件追加（855-859）
- **Pushed**: property-analyzer `2c93aad`, inbox-zero `352dfb8`

## In Progress / Next Actions
1. **🔥 パイプライン候補物件の見直し**: FLAG_THRESHOLD=55は適切か？スコアリング基準の再検討。竹下徒歩15分が候補に残る問題（スコアは修正済みだがCF/CCR試算がflagged段階で入っていない）
2. **候補物件の自動CF/CCR試算**: flagged 17件にスコアだけでなく投資判断の数字を入れる
3. **中野さんへの返信ドラフト精査**: 4/2自動ドラフトは実態（電話済み・OC内見不可・澤畠さん打診）を反映していない
4. **内見済み3件の銀行査定フォロー**: プレイスポット/GSハイム/ローズマンション → 筑波銀行結果確認
5. **Property Registry E2Eテスト**: overridesがPropertyRowに実適用されるか確認
6. **一棟もの物件**: 中野さんが未公開物件を探すと言っていた（3/24）→ フォロー

## Key Decisions
- 2026-04-02: **SSoT伝播原則**: 全プロジェクト横断。1箇所修正→全箇所伝播。CLAUDE.md昇格
- 2026-04-02: **サブリース即除外**: 家賃改定不可→物件価格も上がらない→CF/CGなし。全ステージで除外
- 2026-04-02: **投資方針**: OC物件は内見不可（賃貸中）→外観案内は保留→澤畠さんに評価打診準備
- 2026-04-02: **Pipeline UI**: 都市タブ→ステージタブに全面変更

## Blockers
- なし

## History (last 20)
1. 2026-04-02: SSoT Property Registry + Pipeline v2 + サブリース除外 + intel_extractor + スコアリング修正
2. 2026-04-01: 健美家利回り修正 + DEFAULT_CITY + メールドラフト作成
3. 2026-03-31: マーケット品質改善（広告コピー7パターン+戸建て除外+OC収入補完）
4. 2026-03-31: パイプライン形骸化解消（lifecycle自動管理+メール連動+UI刷新）
5. 2026-03-30: 取得諸費用計上+掲載日クリーンアップ+福岡格安デバッグ
6. 2026-03-29: kaizen Visual Regression チェック追加
7. 2026-03-28: 朝夕2系統テンプレートリライト+section_navコンポーネント
8. 2026-03-27: Cisco Talent Review+property_patrol_steps内部失敗検知
9. 2026-03-26: kaizen-agent QA改革（patrol復活+インフラ整備）
10. 2026-03-25: CLAUDE.md Before/After必須化昇格
