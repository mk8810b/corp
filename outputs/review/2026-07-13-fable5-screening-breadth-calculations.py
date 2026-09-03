#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2026-07-13 スクリーニング・発掘条件の設計診断（screening-breadth-review）検証スクリプト
本文（outputs/review/2026-07-13-fable5-screening-breadth-review.md）の数値的主張は
すべて本スクリプトで再計算・再現可能（憲法第2条・第2章-5）。

入力データはすべて既存成果物からの転記であり、出典を各定数の横に記す。
標準ライブラリのみ使用（scipy等に依存しない）。
実行: python3 outputs/review/2026-07-13-fable5-screening-breadth-calculations.py
"""

import math

print("=" * 72)
print("§1 判断14件の非BUY理由の分類集計")
print("=" * 72)

# 出典: outputs/judgement/*-20260709.md / *-20260711.md（各最終版）
# 分類タグ:
#   FLAG   = 明確な欠格事由（継続企業疑義/監査問題/MSワラント大規模希薄化/粉飾・ガバナンス不全
#            ＝D-015テール脆弱性フラグ級。財務毀損の複合を含む）
#   NOCAT  = カタリスト（急騰・出来高急増の要因）が特定できない
#   PRICED = 材料・割安が既に織り込み済み／同業比で割高
#   VTRAP  = 割安だが「割安を正当化する構造的欠陥」が特定される（D-012基準2の不成立）
#   UNCERT = 複合的な不確実性・直近イベント待ち
#   OUTRNG = 現行フロア（D-009: 100円未満 / D-013: 3,000円超）の範囲外
#            （判断当時は未制定または同日制定。現行設計なら候補に入らない）
#   ILLIQ  = 流動性フロア（D-004）充足が疑わしい（観測できた営業日値が閾値未満）
judgements = {
    # 2026-07-09バッチ（D-008改定前の「出来高ランキング上位」母集団）
    "8918": {"判定": "WATCH", "タグ": ["NOCAT", "PRICED", "OUTRNG"], "株価": 10.0},
    "4564": {"判定": "PASS",  "タグ": ["FLAG", "OUTRNG"],            "株価": 20.0},
    "9432": {"判定": "WATCH", "タグ": ["UNCERT"],                    "株価": 149.4},
    "4597": {"判定": "PASS",  "タグ": ["FLAG", "OUTRNG"],            "株価": 25.0},
    "9434": {"判定": "WATCH", "タグ": ["PRICED"],                    "株価": 215.2},
    "5803": {"判定": "WATCH", "タグ": ["NOCAT", "PRICED", "OUTRNG"], "株価": 4824.0},
    "285A": {"判定": "WATCH", "タグ": ["PRICED", "UNCERT", "OUTRNG"],"株価": 77290.0},
    "9984": {"判定": "WATCH", "タグ": ["UNCERT", "OUTRNG"],          "株価": 5751.0},
    # 2026-07-11バッチ（D-008の2段階方式・現行設計）
    "5240": {"判定": "PASS",  "タグ": ["FLAG", "NOCAT"],             "株価": 180.0},
    "3856": {"判定": "PASS",  "タグ": ["FLAG"],                      "株価": 532.0},
    "5491": {"判定": "WATCH", "タグ": ["VTRAP", "PRICED", "ILLIQ"],  "株価": 876.0},
    "7215": {"判定": "PASS",  "タグ": ["VTRAP", "ILLIQ"],            "株価": 408.0},
    "7211": {"判定": "WATCH", "タグ": ["PRICED"],                    "株価": 361.8},
    "3350": {"判定": "PASS",  "タグ": ["FLAG"],                      "株価": 248.0},
}

n_total = len(judgements)
n_buy = sum(1 for v in judgements.values() if v["判定"] == "BUY")
n_watch = sum(1 for v in judgements.values() if v["判定"] == "WATCH")
n_pass = sum(1 for v in judgements.values() if v["判定"] == "PASS")
print(f"判定内訳: BUY {n_buy} / WATCH {n_watch} / PASS {n_pass} / 計 {n_total}")
assert (n_buy, n_watch, n_pass) == (0, 8, 6)  # D-021・週次サマリと整合

tags = ["FLAG", "NOCAT", "PRICED", "VTRAP", "UNCERT", "OUTRNG", "ILLIQ"]
for t in tags:
    hits = [k for k, v in judgements.items() if t in v["タグ"]]
    print(f"  {t:6s}: {len(hits):2d}件 {hits}")

# 現行フロア範囲外（D-009/D-013）の検算: 株価100〜3,000円の外にある銘柄
outrng_calc = [k for k, v in judgements.items() if not (100.0 <= v["株価"] <= 3000.0)]
print(f"現行フロア（100〜3,000円）範囲外の検算: {len(outrng_calc)}件 {sorted(outrng_calc)}")
assert sorted(outrng_calc) == sorted(
    [k for k, v in judgements.items() if "OUTRNG" in v["タグ"]])
n_current_design = n_total - len(outrng_calc)
print(f"→ 現行スクリーニング設計を反映する判断は実質 {n_current_design}件"
      f"（07-09の9432/9434＋07-11の6件）")

print()
print("=" * 72)
print("§2 流動性フロア（D-004）充足の検算（07-11バッチの観測値）")
print("=" * 72)
# D-004フロア: 1日平均出来高10万株以上 または 1日平均売買代金1億円以上
# 出典: outputs/judgement/5491-20260711.md 5章（07/10出来高58,400株・売買代金51百万円）
#       outputs/judgement/7215-20260711.md 6章-5（07/10出来高6,200株・売買代金約256万円）
# 注意: いずれも単一営業日の観測値であり「1日平均」ではない（平均値は未取得＝取得不能）。
floor_vol, floor_val = 100_000, 100_000_000  # 株 / 円
cases = {"5491": (58_400, 51_000_000), "7215": (6_200, 2_560_000)}
for code, (vol, val) in cases.items():
    print(f"  {code}: 出来高 {vol:,}株（閾値比 {vol/floor_vol*100:.1f}%）・"
          f"売買代金 {val/1e8:.4f}億円（閾値比 {val/floor_val*100:.1f}%）"
          f" → 両閾値とも未達（単一営業日の観測値）")
print("  → 07-11バッチ6件中2件（33.3%）でフロア充足が確認されないまま下流工程へ進んだ")
print(f"    浪費された調査・判断・校閲コストの概算: 2件 × 314,200トークン ="
      f" {2*314200:,}トークン（下記§4の平均単価による）")

print()
print("=" * 72)
print("§3 発掘条件の軸容量と候補数上限（D-007/D-008）")
print("=" * 72)
per_axis_cap = 2  # D-008: 各軸から最大2銘柄
for axes in (5, 3, 2):
    print(f"  使用可能軸 {axes}軸 × 各軸上限{per_axis_cap} = 候補容量 {axes*per_axis_cap}銘柄")
print("  D-007の帯: 5〜10銘柄/週（上限側8〜10はD-019-4が決定変更なしで追求可と明記）")
print("  観測: 2026-07-11週次は3軸（C/D/E）で6銘柄 → 容量6の上限に張り付き。")
print("  軸A/B復旧時の容量10はD-007上限と一致（帯上限運用が可能になる）")

print()
print("=" * 72)
print("§4 LLMコスト実測と週次候補数拡大の費用対効果")
print("=" * 72)
# 出典: outputs/logging/2026-07-11-weekly-summary.md §4（subagent_tokens実測値）
research_total = 860_191   # 企業調査6件
draft_total = 531_609      # 投資判断起案6件
review_total = 493_400     # 校閲6件
grand_total = research_total + draft_total + review_total
per_candidate = grand_total / 6
print(f"  実測合計（6件）: {grand_total:,}トークン"
      f"（調査{research_total:,}＋起案{draft_total:,}＋校閲{review_total:,}）")
assert grand_total == 1_885_200  # 週次サマリの「全18件合計」と一致
print(f"  1候補あたり平均: {per_candidate:,.0f}トークン")
print(f"  （内訳平均: 調査{research_total/6:,.0f}／起案{draft_total/6:,.0f}／"
      f"校閲{review_total/6:,.0f}）")
print("  注: スクリーニング・リスク照合・記録・日次ルーチンのコストはメインセッション実施の")
print("      ため未計測であり、上記は下限の見積もりである。")
print()
print("  週次候補数ごとの週間コストと現状（6件/週）比:")
for w in (6, 8, 10, 12, 15):
    weekly = per_candidate * w
    print(f"    {w:2d}件/週: {weekly:,.0f}トークン/週"
          f"（+{weekly - grand_total:,.0f}, {weekly/grand_total*100:.0f}%）")

print()
print("=" * 72)
print("§5 BUY発生率の区間推定（観測0/14）と検証カレンダーへの効果")
print("=" * 72)
n_obs = 14
cp95 = 1 - 0.05 ** (1 / n_obs)   # Clopper-Pearson 片側95%上限（x=0の閉形式）
cp90 = 1 - 0.10 ** (1 / n_obs)
print(f"  Clopper-Pearson 片側95%上限: {cp95*100:.1f}% / 片側90%上限: {cp90*100:.1f}%")

# Jeffreys事後 Beta(0.5, 14.5) の中央値（数値積分＋二分法。scipy不使用）
# a=0.5のx=0特異点は置換 x=t^2（dx=2t dt）で除去する:
#   ∫0^q x^(-1/2)(1-x)^(b-1) dx = ∫0^sqrt(q) 2(1-t^2)^(b-1) dt（滑らかな被積分関数）
def _smooth_integral(upper, b, steps=100_000):
    h = upper / steps
    f = lambda t: 2.0 * (1.0 - t * t) ** (b - 1.0)
    s = 0.5 * (f(0.0) + f(upper))
    for i in range(1, steps):
        s += f(i * h)
    return s * h

def beta_cdf_half(q, b):
    """Beta(0.5, b)のCDF"""
    if q <= 0:
        return 0.0
    if q >= 1:
        return 1.0
    return _smooth_integral(math.sqrt(q), b) / _smooth_integral(1.0, b)

def beta_quantile_half(p, b):
    lo, hi = 1e-12, 1 - 1e-12
    for _ in range(60):
        mid = (lo + hi) / 2
        if beta_cdf_half(mid, b) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2

jeffreys_median = beta_quantile_half(0.5, n_obs + 0.5)
print(f"  Jeffreys事後 Beta(0.5, {n_obs}.5) 中央値: {jeffreys_median*100:.2f}%"
      f"（D-021記載の1.58%と整合すること）")

# SPRT E[N]=80件への到達年数（D-021 §4-2と同じ仮定: 決済率75%、失効・ラグ簡略化）
# 年数 ≈ E[N] / (週判断件数 × BUY率 × 52週 × 決済率)。ラグ（中央値6〜12週）は加算的に
# +0.1〜0.25年程度（D-021の表は「ラグ込み」でこの近似より数%長い）。
EN = 80
settle = 0.75
print(f"\n  E[N]={EN}件到達までの概算年数（決済率{settle:.0%}・ラグ除く。行=BUY率, 列=週判断件数）:")
pgrid = [jeffreys_median, 0.02, 0.05, 0.10, cp95]
wgrid = [6, 8, 10, 12, 15]
header = "    BUY率\\週件数 " + "".join(f"{w:>8d}" for w in wgrid)
print(header)
for p in pgrid:
    row = f"    {p*100:9.1f}%  "
    for w in wgrid:
        years = EN / (w * p * 52 * settle)
        row += f"{years:8.1f}"
    print(row)
print("  → 拡大の効果は件数に反比例（線形）。週6→10で所要年数は6/10=0.6倍、")
print("     週6→15で0.4倍。BUY率が支配的な未知数であり、拡大単独では1年以内の")
print("     統計的結論には届かない（BUY率20%近傍を除く）。")
print("  → 1 BUY判断あたりのトークン単価は候補数によらず一定:")
for p in (0.05, 0.10):
    print(f"     BUY率{p:.0%}のとき {per_candidate/p:,.0f}トークン/BUY判断")

print()
print("=" * 72)
print("§6 シャドーPF決済済み2件の事後観察（診断指標・n=2で結論不能）")
print("=" * 72)
# 出典: corp/board.md D-021（SP-007=285A・WATCH由来HIT_LOSS / SP-009=5240・PASS由来HIT_PROFIT）
print("  SP-007 285A（WATCH）→ HIT_LOSS : 見送り方向の判断が結果的に損失回避と整合")
print("  SP-009 5240（PASS） → HIT_PROFIT: 見送った銘柄が+25%バリア到達（機会逸失）")
print("  → 1勝1敗・n=2。判定関数の質について統計的に何も言えない（第2条）。")

print()
print("done.")
