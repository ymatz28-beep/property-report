#!/usr/bin/env python3
"""
投資基準SSoT — SEARCH_CRITERIA.md の「共通条件」を機械可読化したもの。
値を変える時はここだけ直せば、これをimportする全スクレイパーに伝播する。
人間向けの説明・背景は SEARCH_CRITERIA.md 側を参照（2ファイルは値を一致させること）。
"""

# 区分マンション・戸建て（自宅兼民泊候補）の共通条件
KUBUN_PRICE_MAX_MAN = 5000   # 予算上限（理想は4000万）
KUBUN_AREA_MIN = 40          # ㎡

# 戸建て（旅館業/民泊、管理規約制約なし）— 2026-07-08 Yuma指定で区分より低い上限
KODATE_PRICE_MAX_MAN = 2999
KODATE_AREA_MIN = 40
