# HANDOFF

---
**📍 今どこ**: 不動産2件の出口判断。仙台クレストモールは「売る」で資料完成・あとは業者へ送るだけ。福岡薬院は「貸す」方向で家賃相場と管理会社まで調査済み、次セッションで詰める段階。
**✅ 前回(2026-06-05)**: 薬院（福岡市中央区薬院2-44-904・55㎡リノベ済デザイナーズ区分・薬院大通3分・SRC築約50年）を貸す前提で調査。家賃相場=標準11万/強気13万、福岡の管理手数料最安=集金代行3〜4%（デザイナーズ客付けはgoodroom/スタイルプラス）。実ローン（筑波2.85%/15年・月返済約10万）＋区分管理費2.5万を入れると、貸しても現金は月3万持ち出し・純資産は月4万増の「長期戦」と判明。
**▶ 次(薬院・別セッション)**: (1)筑波銀行の返済予定表が届いたら残債を入れて「売る vs 貸す」の手取りを確定（返済表は現状ローカル未保存・Yumaが後で追加）、(2)固定資産税の実額（ドライブ `wealth-strategy/drive-data/chisan-hakata/kotei-shisan-zei-*.pdf`）を試算に反映、(3)薬院の賃貸査定問い合わせ文＋更新版「売却vs賃貸」試算を作成。
---

## 2026-06-05 セッション記録: 不動産2件の出口判断

### 仙台クレストモール = 「売る」で確定（資料完成・送付待ち）
- 物件: 仙台市太白区茂ケ崎3-3-22・木造一棟8戸・1985年築・延床198.74㎡・Robot Home仙台支店管理・公庫融資（残債約1,860万・完済2038年12月・年1.9%元金均等）。家賃月246,000円（2026送金明細実額）・NOI年約281万。
- 売出方針: 高値アンカー2,950万円（表面10.0%）。売り急ぎ不要（毎月黒字）。
- 成果物フォルダ: `/Users/ytejima/Documents/Projects/property-report/crestmall-sale/`
  - `crestmall_sale_teaser.pdf`（買主/業者向け売り込み2枚・昨日6/4作成・完成）
  - `crestmall_factsheet.pdf`（査定用1枚シート・本日作成・号室別は転記欄・1K23㎡確定）
  - `outreach_drafts.md`（Robot Home打診＋楽待査定＋仙台ローカル業者の問い合わせ文3本・署名【氏名/電話/メール】差し替え要）
- 残タスク: Robot Home仙台支店へ打診＋楽待で査定（複数社・一般媒介）。送るだけの状態。

### 福岡薬院 = 「貸す」方向で検討中（次セッション）
- 物件: チサンマンション第3博多 904号室＝薬院2-44-904・区分・55㎡・SRC11階建9階・1974年築・約8年前フルリノベ（インダストリアル）・薬院大通3分/薬院7分・商業地域/住居兼事務所可・購入参考1,980万・管理費12,600+修繕積立12,800=月25,400・現状は自社事務所利用。
- 実ローン: 筑波銀行1,540万・15年・2.85%・月返済約10万（※残債未確定＝返済予定表待ち）。
- 調査結果: 家賃相場 標準11万/強気13万（goodroom実例で薬院大通近接50㎡台が10〜15万）。管理手数料 福岡相場=集金代行3〜4%/フル4〜5%/サブリース10〜20%。福岡R不動産は仲介専門で管理はやらない。
- 既存資産: `property-analyzer/deals/financing/11_薬院_売却vs賃貸_試算.md`（旧・家賃16万/金利2.0%20年の推計版→実数で要更新）、`output/yakuin-sell-or-rent.html`、`deals/financing/build_yakuin_page.py`、ドライブ `wealth-strategy/drive-data/chisan-hakata/`（物件広告・固定資産税・重説等）。
- 注意: 貸すと別の事務所が必要（現在この部屋が自社事務所）。この前提の確認が未済。

## [Constancy] 2026-06-05
- [ERROR] hardcoded_data: [ESCALATED: 51d unresolved] Large inline data (91 lines) at line 36. Consider externalizing to YAML/JSON or add `# kaizen-allow: hardcoded_data` 3 lines above to suppress.
- [WARN] hardcoded_data: Large inline data (83 lines) at line 360. Consider externalizing to YAML/JSON or add `# kaizen-allow: hardcoded_data` 3 lines above to suppress.
- [ERROR] structural_reform: [ESCALATED: 51d unresolved] generate_market.py is 1664 lines (threshold: 800). Consider splitting.
- [ERROR] structural_reform: [ESCALATED: 51d unresolved] property_pipeline.py is 2279 lines (threshold: 800). Consider splitting.
- [ERROR] structural_reform: [ESCALATED: 51d unresolved] Stale temp/debug file (62 days old). Delete it.
- [ERROR] structural_reform: [ESCALATED: 51d unresolved] Stale temp/debug file (62 days old). Delete it.
- [ERROR] structural_reform: [ESCALATED: 51d unresolved] Stale temp/debug file (62 days old). Delete it.
- [ERROR] structural_reform: [ESCALATED: 51d unresolved] Stale temp/debug file (65 days old). Delete it.
- [ERROR] html_ui: [ESCALATED: 51d unresolved] Font size violation(s): line 190: fixed 48px
- [WARN] html_ui: Missing gnav (site-header) — no navigation
- [ERROR] html_ui: [ESCALATED: 51d unresolved] Font size violation(s): line 190: fixed 48px
- [WARN] html_ui: Missing gnav (site-header) — no navigation
- [WARN] html_ui: Missing gnav (site-header) — no navigation
- [ERROR] property_patrol_steps: [ESCALATED: 42d unresolved] 物件パトロール失敗ステップ (2026-06-04 07:58): 【Hub KPI JSON生成】エラー終了 (exit 1) → Fix: エラーログを確認
- [ERROR] property_patrol_steps: [ESCALATED: 42d unresolved] 物件パトロール失敗ステップ (2026-06-04 07:58): 【自動フラグ付与】異常終了: expected '<document start>', but found '<scalar>'
  in "/Users/ytejima/Documents/Projects/property-a → Fix: エラーログを確認
- [ERROR] property_patrol_steps: [ESCALATED: 42d unresolved] 物件パトロール失敗ステップ (2026-06-04 07:58): 【パイプラインライフサイクル】異常終了: expected '<document start>', but found '<scalar>'
  in "/Users/ytejima/Documents/Projects/property-a → Fix: エラーログを確認
- [ERROR] property_patrol_steps: [ESCALATED: 42d unresolved] 物件パトロール失敗ステップ (2026-06-04 07:58): 【問い合わせダッシュボード】異常終了: expected '<document start>', but found '<scalar>'
  in "/Users/ytejima/Documents/Projects/property-a → Fix: エラーログを確認
- [ERROR] property_patrol_steps: [ESCALATED: 42d unresolved] 物件パトロール失敗ステップ (2026-06-04 07:58): 【内覧分析レポート】異常終了: expected '<document start>', but found '<scalar>'
  in "/Users/ytejima/Documents/Projects/property-a → Fix: エラーログを確認
- [WARN] git_uncommitted: Property Analyzer: 32 uncommitted file(s), oldest 24h ago (threshold: 24h). GHA runs on old code until pushed.
- [ERROR] design_token_compliance: [ESCALATED: 51d unresolved] Line 56: hardcoded #6366f1 should be var(--accent)
- [ERROR] design_token_compliance: [ESCALATED: 51d unresolved] Line 401: hardcoded #9ca3af should be var(--text-secondary)
- [ERROR] design_token_compliance: [ESCALATED: 51d unresolved] Line 420: hardcoded #9ca3af should be var(--text-secondary)
- [ERROR] design_token_compliance: [ESCALATED: 51d unresolved] Line 559: hardcoded #6366f1 should be var(--accent)
- [ERROR] design_token_compliance: [ESCALATED: 51d unresolved] Line 560: hardcoded #22c55e should be var(--green)
- [ERROR] design_token_compliance: [ESCALATED: 51d unresolved] Line 561: hardcoded #ef4444 should be var(--red)
- [ERROR] design_token_compliance: [ESCALATED: 51d unresolved] Line 638: hardcoded #6366f1 should be var(--accent)
- [ERROR] design_token_compliance: [ESCALATED: 51d unresolved] Line 647: hardcoded #6366f1 should be var(--accent)
- [ERROR] design_token_compliance: [ESCALATED: 51d unresolved] Line 703: hardcoded #6366f1 should be var(--accent)
- [ERROR] design_token_compliance: [ESCALATED: 51d unresolved] Line 758: hardcoded #6366f1 should be var(--accent)
- [WARN] design_token_compliance: Line 6: hardcoded #c9a84c should be var(--gold)
- [WARN] design_token_compliance: Line 7: hardcoded #c9a84c should be var(--gold)
- [WARN] design_token_compliance: Line 13: hardcoded #c9a84c should be var(--gold)
- [WARN] design_token_compliance: Line 18: hardcoded #c9a84c should be var(--gold)
- [WARN] design_token_compliance: Line 20: hardcoded #1a1d27 should be var(--surface)
- [WARN] design_token_compliance: Line 21: hardcoded #c9a84c should be var(--gold)
- [WARN] design_token_compliance: Line 22: hardcoded #242836 should be var(--surface2)
- [WARN] design_token_compliance: Line 22: hardcoded #e4e4e7 should be var(--text)
- [ERROR] design_token_compliance: [ESCALATED: 49d unresolved] Line 173: hardcoded #fbbf24 should be var(--amber)
- [ERROR] design_token_compliance: [ESCALATED: 49d unresolved] Line 304: hardcoded #fbbf24 should be var(--amber)
- [ERROR] design_token_compliance: [ESCALATED: 49d unresolved] Line 343: hardcoded #4ade80 should be var(--green-light)
- [ERROR] design_token_compliance: [ESCALATED: 49d unresolved] Line 344: hardcoded #f87171 should be var(--red-light)
- [ERROR] design_token_compliance: [ESCALATED: 49d unresolved] Line 62: hardcoded #6366f1 should be var(--accent)
- [ERROR] design_token_compliance: [ESCALATED: 49d unresolved] Line 646: hardcoded #9ca3af should be var(--text-secondary)
- [ERROR] design_token_compliance: [ESCALATED: 49d unresolved] Line 665: hardcoded #9ca3af should be var(--text-secondary)
- [ERROR] design_token_compliance: [ESCALATED: 49d unresolved] Line 62: hardcoded #6366f1 should be var(--accent)
- [ERROR] design_token_compliance: [ESCALATED: 49d unresolved] Line 646: hardcoded #9ca3af should be var(--text-secondary)
- [ERROR] design_token_compliance: [ESCALATED: 49d unresolved] Line 665: hardcoded #9ca3af should be var(--text-secondary)
- [ERROR] design_token_compliance: [ESCALATED: 51d unresolved] Line 56: hardcoded #6366f1 should be var(--accent)
- [ERROR] design_token_compliance: [ESCALATED: 51d unresolved] Line 305: hardcoded #22c55e should be var(--green)
- [ERROR] design_token_compliance: [ESCALATED: 51d unresolved] Line 308: hardcoded #f87171 should be var(--red-light)
- [ERROR] design_token_compliance: [ESCALATED: 51d unresolved] Line 372: hardcoded #9ca3af should be var(--text-secondary)
- [ERROR] design_token_compliance: [ESCALATED: 51d unresolved] Line 391: hardcoded #9ca3af should be var(--text-secondary)
- [ERROR] design_token_compliance: [ESCALATED: 49d unresolved] Line 61: hardcoded #6366f1 should be var(--accent)
- [ERROR] design_token_compliance: [ESCALATED: 49d unresolved] Line 760: hardcoded #9ca3af should be var(--text-secondary)
- [ERROR] design_token_compliance: [ESCALATED: 49d unresolved] Line 779: hardcoded #9ca3af should be var(--text-secondary)
- [ERROR] design_token_compliance: [ESCALATED: 49d unresolved] Line 114: hardcoded #6366f1 should be var(--accent)
- [ERROR] design_token_compliance: [ESCALATED: 49d unresolved] Line 61: hardcoded #6366f1 should be var(--accent)
- [ERROR] design_token_compliance: [ESCALATED: 49d unresolved] Line 475: hardcoded #9ca3af should be var(--text-secondary)
- [ERROR] design_token_compliance: [ESCALATED: 49d unresolved] Line 494: hardcoded #9ca3af should be var(--text-secondary)
- [ERROR] design_token_compliance: [ESCALATED: 49d unresolved] Line 62: hardcoded #6366f1 should be var(--accent)
- [ERROR] design_token_compliance: [ESCALATED: 49d unresolved] Line 646: hardcoded #9ca3af should be var(--text-secondary)
- [ERROR] design_token_compliance: [ESCALATED: 49d unresolved] Line 665: hardcoded #9ca3af should be var(--text-secondary)
- [ERROR] blank_cells: [ESCALATED: 51d unresolved] ダッシュ「—」171個 (閾値20) — データ欠損の可能性
- [ERROR] first_seen_coverage: 掲載日カバレッジ 1% (2/147) — 閾値80%
- [ERROR] qa_market_data_accuracy: [ESCALATED: 51d unresolved] 3/100 (3.0%) — price mismatch: 高木団地住宅 二号棟 raw=698.0 html=710.0; price mismatch: コーポラス東光 206 raw=650.0 html=800.0; price mismatch: ふれんず物件(中央区) raw=800.0 html=950.0
- [ERROR] qa_market_oc_income_coverage: [ESCALATED: 51d unresolved] OC 340件中 265件が年間収入欠落 (78%) — 利回り逆算で補完
- [ERROR] qa_market_yield_consistency: 5件の利回り/年間収入乖離(>20%): プレサンス大国町アドロッソ: expected=39.0万 actual=78.0万 (50%乖離); エスライズ堺筋本町: expected=38.8万 actual=85.2万 (54%乖離); ルリオン赤羽: expected=36.1万 actual=99.4万 (64%乖離); feeth神楽坂: expected=50.7万 actual=104.8万 (52%乖離); AXAS上野北: expected=57.1万 actual=122.2万 (53%乖離)
- [ERROR] qa_market_name_cross_reference: [ESCALATED: 51d unresolved] 38件の物件名クロスリファレンス不一致: 大阪市福島区海老江(40㎡): ['グリーンシティＯＳＡＫＡ\u3000１号棟 6階 １ＬＤＫ', 'グリーンシティＯＳＡＫＡ\u3000１号棟']; 墨田区向島(44㎡): ['本所吾妻橋駅 / 1LDK / 44.61㎡', '向島パークハイツ']; 福岡市博多区御供所町(16㎡): ['【売主物件・利回り8.2％\u3000博多駅が生活圏】メゾンド祇園', 'ふれんず物件(博多区)']; 福岡市博多区美野島(18㎡): ['エステート・モア・博多グラン A棟', 'エステート・モア・博多グラン A棟 211']; 福岡市博多区美野島(25㎡): ['『博多駅・天神・キャナル・中州まで徒歩圏内』', 'ふれんず物件(博多区)'] ... +33 more
- [ERROR] data_accuracy: スクレイプデータとHTMLレンダリングの不一致率 15.6% (19/122件)。パイプライン変換バグの可能性。例: 3290.0万円/44.66㎡; 3050.0万円/52.98㎡; 2980.0万円/52.55㎡; 2820.0万円/48.8㎡; 3050.0万円/66.6㎡
- [WARN] renderer_compliance: Missing gnav (site-header / site-nav) — no navigation
- [WARN] renderer_compliance: Missing gnav (site-header / site-nav) — no navigation
- [ERROR] renderer_compliance: Missing design tokens (var(--bg) / var(--surface)) — page not using renderer.py
- [ERROR] freeze_candidates: [ESCALATED: 17d unresolved] プロジェクト 'property-analyzer' は 9999d 非活性 (凍結閾値 90d)。 _archived/ への移動または Phase 0 再定義を検討。

## Last Updated
2026-04-22 (plist PYTHONPATH 追加で subprocess import 修復)

## Completed (2026-04-22 深夜 property-patrol subprocess import 修復)
- **Before**: `run_daily_patrol.py` が走る subprocess 子 (`generate_osaka/fukuoka/tokyo_report.py` 等10件) が `No module named 'lib.state_io'` で失敗。patrol_summary.json: 18/28 ok、failed_steps 10件。原因は親の sys.path 設定が subprocess に継承されないこと
- **After**: plist (`property-analyzer/com.yuma.property-patrol.plist` SSoT + `~/Library/LaunchAgents/` 実配置) の `EnvironmentVariables` に `PYTHONPATH=/Users/yumatejima/Documents/Projects` 追加。bootout → bootstrap で reload、launchctl print で env var 反映確認、RunAtLoad 後の `/tmp/property_patrol.err` 0 bytes
- **SSoT 同期確認**: property-analyzer 配下 plist と `~/Library/LaunchAgents/` が完全一致 (2C Consistency 違反解消)
- **Commits**: `d5d9eb9 fix(plist): add PYTHONPATH so subprocess steps import lib` (property-report repo)

## Next Actions (次セッション候補)
- **schedule drift 解消**: infra-manifest.yaml 記載 "every 6h (21600s)" vs plist の 86400s (24h) の乖離。pipeline-doctor指摘。頻度変更は Twitter/SUUMO API 負荷影響あるため要判断
- hardcoded_data / 1664行 generate_market / 2279行 property_pipeline 分割は継続課題

## Last Updated (prev)
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