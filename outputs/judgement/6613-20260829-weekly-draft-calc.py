#!/usr/bin/env python3
"""JDG-S108 起案（6613 ＱＤレーザ・2026-08-29週次）の全数値再計算スクリプト。

価格系列の出典: https://kabutan.jp/stock/kabuka?code=6613&ashi=day&page=1 ・ &page=2
                （curl・ブラウザ相当UA、取得日時 2026-08-30T23:28:27Z、61営業日・欠落なし）
併置ファイル: 6613-20260829-weekly-draft-price-series.json（上記からパースした日足の生データ）
実行: python3 6613-20260829-weekly-draft-calc.py
"""
import json, math, os, statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(HERE, '6613-20260829-weekly-draft-price-series.json')))
num = lambda s: float(s.replace(',', ''))
dates  = [r[0] for r in rows]
closes = [num(r[4]) for r in rows]
vols   = [num(r[7]) for r in rows]
assert dates[0] == '26/08/28', dates[0]
CLOSE = closes[0]

print("=== 0. 価格系列 ===")
print("範囲:", dates[-1], "->", dates[0], " n =", len(rows))
print("判定基準日 26/08/28: 終値", CLOSE, " 前日比", rows[0][5], "/", rows[0][6], "% 出来高", rows[0][7])

print("\n=== 1. 窓A（判定基準日を含む直近20営業日 = 出来高20日平均と同じ窓）===")
cl, vo = closes[:20], vols[:20]
avg_vol = sum(vo) / 20
avg_amt = sum(v * c for v, c in zip(vo, cl)) / 20
print("窓A:", dates[19], "->", dates[0])
print("20日平均出来高:", round(avg_vol, 1), "株")
print("20日平均売買代金:", round(avg_amt / 1e8, 4), "億円")

def sigma(series):
    ch = list(reversed(series))
    simp = [ch[i] / ch[i-1] - 1 for i in range(1, len(ch))]
    logr = [math.log(ch[i] / ch[i-1]) for i in range(1, len(ch))]
    return {'pstdev_simple': st.pstdev(simp) * 100, 'stdev_simple': st.stdev(simp) * 100,
            'pstdev_log':    st.pstdev(logr) * 100, 'stdev_log':    st.stdev(logr) * 100}

sA = sigma(cl)
print("σ20（窓A・4推定量, %）:", {k: round(v, 4) for k, v in sA.items()})

two_pct   = CLOSE * 0.02
sigma_yen = CLOSE * max(sA.values()) / 100
TICK      = 1.0                      # JPX 呼値の単位: 3,000円以下は1円
GATE      = math.ceil(max(two_pct, sigma_yen, TICK))
VOL15     = math.ceil(avg_vol * 1.5)
print("2%成分:", round(two_pct, 2), "円 / σ20成分:", round(sigma_yen, 2), "円 / tick:", TICK, "円")
print("GATE =", GATE, "円  → 上抜け", CLOSE + GATE, "円 / 下抜け", CLOSE - GATE, "円")
print("出来高1.5倍閾値:", VOL15, "株")

print("\n=== 2. 窓の感度分析（校閲者向け、9-2節）===")
sB = sigma(closes[:21])
gB = math.ceil(max(two_pct, CLOSE * max(sB.values()) / 100, TICK))
print("窓B（21終値=20リターン）σ20最大:", round(max(sB.values()), 4), "% → GATE", gB,
      "円 / 上抜け", CLOSE + gB, "/ 下抜け", CLOSE - gB)

print("\n=== 3. 基準率（窓A実データ、9-3節）===")
up, dn = CLOSE + GATE, CLOSE - GATE
print("終値>=上抜け:", sum(1 for c in cl if c >= up), "日")
print("出来高>=1.5倍:", sum(1 for v in vo if v >= VOL15), "日")
print("T1(価格AND出来高):", sum(1 for c, v in zip(cl, vo) if c >= up and v >= VOL15), "日")
print("終値<=下抜け（水準ベース・過大評価）:", sum(1 for c in cl if c <= dn), "日")
print("同2営業日連続（T7・水準ベース）:", sum(1 for i in range(len(cl)-1) if cl[i] <= dn and cl[i+1] <= dn), "日")
ch = list(reversed(cl))
mv = [(ch[i] / ch[i-1] - 1) * 100 for i in range(1, len(ch))]
thr = GATE / CLOSE * 100
print(f"変化率ベース（閾値{thr:.2f}%）: 下落", sum(1 for m in mv if m <= -thr),
      "/ 上昇", sum(1 for m in mv if m >= thr), "/ 絶対値", sum(1 for m in mv if abs(m) >= thr), "（19変化中）")
print("窓A 日次変動 min/max:", round(min(mv), 2), "/", round(max(mv), 2), "%")

print("\n=== 4. 押し目条項を設定しない根拠（10-3節）===")
hi20 = max(cl)
print("窓A終値高値:", hi20, "（", dates[cl.index(hi20)], "）")
print("判定基準日の下落率:", round((CLOSE / hi20 - 1) * 100, 2), "% → 5〜15%帯",
      round(hi20 * 0.95, 1), "〜", round(hi20 * 0.85, 1), "円の内側か:",
      5 <= -(CLOSE / hi20 - 1) * 100 <= 15)
quiet = []
for i in range(0, 25):
    quiet.append(vols[i] <= sum(vols[i:i+20]) / 20)   # ローリング20日平均以下
print("「20日平均以下が2営業日連続」の成立日数（直近24判定日）:",
      sum(1 for i in range(len(quiet)-1) if quiet[i] and quiet[i+1]))
print("61営業日終値高値:", max(closes), "（", dates[closes.index(max(closes))], "）→ 下落率",
      round((CLOSE / max(closes) - 1) * 100, 2), "%（15%超＝帯の外）")

print("\n=== 5. D-012基準3 進捗率（7-3節。数値は決算短信原本・D-026検算済み）===")
q1_sales, fy_sales = 436.0, 1850.0
q1_op,    fy_op    = -45.0, 3.0
q1_ni,    fy_ni    = -51.0, 441.0
py_q1_sales, py_fy_sales = 315.0, 1372.0
print("売上進捗:", round(q1_sales / fy_sales * 100, 2), "% / 線形25%との差:",
      round(q1_sales / fy_sales * 100 - 25, 2), "pt")
print("前年同期ペース:", round(py_q1_sales / py_fy_sales * 100, 2), "% / 差:",
      round(q1_sales / fy_sales * 100 - py_q1_sales / py_fy_sales * 100, 2), "pt")
print("純利益進捗:", round(q1_ni / fy_ni * 100, 2), "%（分子が負）")
print("Q2〜Q4で必要な営業利益:", fy_op - q1_op, "百万円")
print("営業利益率（通期予想）:", round(fy_op / fy_sales * 100, 4), "%")
print("純利益予想 - 営業利益予想:", fy_ni - fy_op, "百万円（≒特許権譲渡対価 約5億円）")

print("\n=== 6. 資金余力2試算の差の由来（4節）===")
cash, opcf, invcf = 2689.537, -481.0, -886.0
fcf = opcf + invcf
print("FCF =", opcf, "+", invcf, "=", fcf, "百万円")
r_op, r_fcf = cash / abs(opcf / 4), cash / abs(fcf / 4)
print("営業CF基準:", round(r_op, 2), "四半期 /", round(r_op / 4, 2), "年")
print("フリーCF基準:", round(r_fcf, 2), "四半期 /", round(r_fcf / 4, 2), "年")
print("差:", round(r_op - r_fcf, 2), "四半期（比", round(r_op / r_fcf, 3), "倍）／投資CF寄与率:",
      round(abs(invcf) / abs(fcf) * 100, 2), "%")

print("\n=== 7. バリュエーション（6節）===")
print("目標株価650円 vs 終値", CLOSE, "→ 乖離", round((650 / CLOSE - 1) * 100, 2),
      "% / 終値は目標の", round(CLOSE / 650, 2), "倍")
print("時価総額925億円 ÷ Q1末純資産4,908,388千円 → PBR概算", round(92500 / 4908.388, 2), "倍")

print("\n=== 8. D-002/D-004/D-009/D-013/D-019 機械照合（9-4・9-5・12・13節）===")
ceil_tick = lambda x, t=1: math.ceil(round(x / t, 9)) * t
for label, e in [("判定基準終値", int(CLOSE)), ("T1上抜け水準", int(CLOSE + GATE)),
                 ("T2/T7下抜け水準", int(CLOSE - GATE))]:
    print(f"{label} {e}円 → 損切り-10%: {ceil_tick(e*0.90)}円 / 利確+25%: {ceil_tick(e*1.25)}円")
print("D-009(>=100円):", CLOSE >= 100, " D-013(<=3,000円):", CLOSE <= 3000,
      " 上限までの距離:", round((3000 - CLOSE) / 3000 * 100, 3), "%")
print("D-018×D-013衝突（上抜け閾値>=3,000円か）:", CLOSE + GATE >= 3000)
CAP = 3_000_000
unit = CLOSE * 100
print("1単元購入額:", unit, "円 = 資金残高の", round(unit / CAP * 100, 3), "%")
print("D-019 2%目標:", CAP * 0.02, "円 / 3%上限:", CAP * 0.03, "円 / 1単元が3%超:", unit > CAP * 0.03)
print("D-002 1銘柄上限10%:", CAP * 0.10, "円 / 1単元が10%枠内:", unit <= CAP * 0.10)
