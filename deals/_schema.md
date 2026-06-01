# Deal Cockpit — 物件追加の手順（汎用）

1物件を深掘りして「賃貸 / 民泊 / 旅館業」の収支を比較し、対話型シミュレーターで
投資判断するためのモジュール。検索パイプライン（generate_market.py 系）とは独立。

## 新しい物件を追加する
1. `deals/placespot-shinbashi.yaml` を複製してリネーム（例 `deals/<id>.yaml`）
2. 値を差し替える（`deal.id` はファイル固有に。出力は `output/deal-<id>.html`）
3. `python deals/build_deal_cockpit.py deals/<id>.yaml` を実行 → HTML生成＋ブラウザ起動

## YAML の要点
- `acquisition.asking_price_yen`: ベースライン。HTMLではスライダーで可変
- `scenarios.rental`: 業者が賃貸収支を出さないことが多い → 当方推計。`is_estimate: true` で「推計」バッジ表示
- `scenarios.minpaku.legal_day_cap: 180`: 民泊新法の年間営業上限。特区エリアなら `is_minpaku_special_zone: true` にし cap を 365 に
- `scenarios.{minpaku,ryokan}.var_opex_rate`: 業者収支表から「変動経費合計 ÷ 売上」で実測した率
- `thresholds.target_ccr_pct`: 「化ける」と判断する自己資金配当率の線

## 計算の定義（HTML内JSと一致）
- NOI = 売上 − 運営経費（返済前）
- 初期投資総額 = 取得価格 + 取得諸費用(price×rate) + 改装費 + (民泊/旅館のみ)セットアップ費
- 自己資金 = 総事業費 × 自己資金比率 / 借入 = 残り / 返済 = 元利均等
- 税引前CF = NOI − 年間返済 ／ CCR = CF ÷ 自己資金 ／ 回収年数 = 自己資金 ÷ CF
- 損益分岐取得価格: CF=0 の価格、および CCR=目標% の価格を逆算

## 検証（D=C）
業者の収支計画表がある場合、cap無し前提で NOI を再現できるか必ず突合する
（placespot は誤差 0.5% 以内で一致を確認済み 2026-06-01）。
