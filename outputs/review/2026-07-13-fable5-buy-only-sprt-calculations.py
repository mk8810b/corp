#!/usr/bin/env python3
"""BUY限定SPRT再設計（D-021案）の数値検証スクリプト（Fable5, 2026-07-13）。

対応レビュー: outputs/review/2026-07-13-fable5-buy-only-sprt-redesign.md
本文中の数値的主張は全て本スクリプトで再計算・再現可能（憲法第2条・第2章-5）。
依存: Python 3標準ライブラリのみ（scipy不使用。Beta分位点は自前の数値積分＋二分法）。

計算内容:
  §1 BUY発生率の区間推定（観測: 判断14件中BUY 0件、2026-07-09〜07-11の2バッチ）
     - Clopper-Pearson 片側95%上限（x=0の閉形式: 1-α^(1/n)）
     - 「3の法則」近似（3/n）
     - Jeffreys事前 Beta(0.5, 0.5) → 事後 Beta(0.5, 14.5) の中央値・90%/95%分位点
  §2 BUY限定にした場合の逐次検定（D-019 SPRT）の所要カレンダー時間の試算
     - E[N]=59〜92件（D-019モンテカルロ実測値）への到達年数を、
       週次判断件数 × BUY率 × バリア決済率 の感度分析で計算
     - 12ヶ月終端（D-019）到達時点の期待BUY決済数
     - 最速卒業（12連勝）・最速撤退（18連敗）の理論下限時間
"""

import math

# ---------- 汎用: Beta(a,b) CDF（a=0.5の特異点は x=t^2 置換で除去） ----------

def beta_cdf_half(q: float, b: float) -> float:
    """Beta(0.5, b) の CDF を数値積分で返す（0<=q<=1）。
    pdf ∝ x^{-1/2}(1-x)^{b-1}。x=t^2 と置くと ∫ 2(1-t^2)^{b-1} dt（滑らか）。"""
    if q <= 0:
        return 0.0
    if q >= 1:
        return 1.0

    def g(t: float) -> float:
        return 2.0 * (1.0 - t * t) ** (b - 1.0)

    def simpson(f, lo, hi, n=20000):
        h = (hi - lo) / n
        s = f(lo) + f(hi)
        for i in range(1, n):
            s += f(lo + i * h) * (4 if i % 2 else 2)
        return s * h / 3.0

    total = simpson(g, 0.0, 1.0)
    part = simpson(g, 0.0, math.sqrt(q))
    return part / total


def beta_ppf_half(p: float, b: float) -> float:
    """Beta(0.5, b) の分位点（二分法）。"""
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if beta_cdf_half(mid, b) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


# ---------- §1 BUY発生率の区間推定 ----------

def section1():
    n, x = 14, 0
    print("=" * 72)
    print(f"§1 BUY発生率の区間推定（観測: 判断{n}件中BUY {x}件）")
    print("=" * 72)

    # Clopper-Pearson 片側95%上限（x=0では閉形式）
    for conf in (0.90, 0.95):
        alpha = 1 - conf
        ub = 1 - alpha ** (1 / n)
        print(f"Clopper-Pearson 片側{conf*100:.0f}%上限: p_buy <= {ub*100:.1f}%")
    print(f"「3の法則」近似（3/n）: p_buy <= {3/n*100:.1f}%")

    # Jeffreys 事後 Beta(0.5, n+0.5)
    b = n + 0.5
    med = beta_ppf_half(0.5, b)
    q90 = beta_ppf_half(0.90, b)
    q95 = beta_ppf_half(0.95, b)
    print(f"Jeffreys事後 Beta(0.5, {b}): 中央値 {med*100:.2f}% / "
          f"90%点 {q90*100:.1f}% / 95%点 {q95*100:.1f}%")
    print()
    print("注意（本文§2に明記）: 14件は2026-07-09（8件）・07-11（6件）の2バッチであり、")
    print("同一地合い・同一発掘条件による相関を持つ。iid前提の区間は楽観側（狭い側）に")
    print("バイアスされうる。また判定関数はD-012（積極的BUY基準）制定後まだ2週未満の運用で、")
    print("将来のBUY率がこの観測と同分布である保証はない。")
    return {"cp95": 1 - 0.05 ** (1 / n), "jeffreys_med": med, "jeffreys_q95": q95}


# ---------- §2 BUY限定SPRTの所要カレンダー時間 ----------

def section2(est):
    print()
    print("=" * 72)
    print("§2 BUY限定SPRTの所要カレンダー時間の試算（感度分析）")
    print("=" * 72)
    print("""前提（すべて仮定値であることに注意。第2条）:
- E[N]（SPRT期待停止件数）= 59〜92件、代表値80件（D-019モンテカルロ実測。
  outputs/review/2026-07-09-fable5-sprt-design-calculations.py）
- 週次判断件数 w = 5〜10件/週（D-007。実績は2バッチのみ）
- バリア決済率 s（登録のうちEXPIREDにならずHIT_PROFIT/HIT_LOSSで決済される比率）
  = 0.75 を基準（D-019はEXPIRED>25%で枠組み再検討としており、その上限と整合）。
  感度: 0.60 / 0.90
- 決済ラグ（登録→バリア到達）中央値 6〜12週（D-019 §2-4と同じ仮定）を、
  総所要時間への加算項として近似（最後の登録コホートの決済待ち）
""")
    EN_LO, EN_MID, EN_HI = 59, 80, 92
    lag_lo, lag_hi = 6, 12  # 週

    p_scenarios = [
        ("Jeffreys中央値", est["jeffreys_med"]),
        ("2%", 0.02),
        ("5%", 0.05),
        ("10%", 0.10),
        ("CP片側95%上限", est["cp95"]),
    ]
    print(f"{'BUY率シナリオ':<18}{'BUY/週':>8}{'決済/週':>8}"
          f"{'E[N]=80到達（登録のみ）':>24}{'ラグ込み概算':>16}")
    W, S = 8, 0.75  # 代表ケース: 週8件・決済率75%
    rows = []
    for name, p in p_scenarios:
        buys_per_week = W * p
        settle_per_week = buys_per_week * S
        weeks = EN_MID / settle_per_week
        total_lo = weeks + lag_lo
        total_hi = weeks + lag_hi
        rows.append((name, p, weeks, total_lo, total_hi))
        print(f"{name:<18}{buys_per_week:>8.2f}{settle_per_week:>8.2f}"
              f"{weeks/52:>20.1f}年{total_lo/52:>7.1f}〜{total_hi/52:.1f}年")

    print()
    print("感度分析（E[N]=80固定、ラグ加算前の登録所要年数）:")
    print(f"{'BUY率':>8} | " + " | ".join(f"w={w},s={s}" for w in (5, 8, 10) for s in (0.6, 0.75, 0.9)))
    for name, p in p_scenarios:
        cells = []
        for w in (5, 8, 10):
            for s in (0.6, 0.75, 0.9):
                cells.append(f"{EN_MID/(w*p*s)/52:>8.1f}")
        print(f"{p*100:>7.1f}% | " + " | ".join(cells) + "  年")

    print()
    print("E[N]の幅（59〜92件）による違い（代表ケース w=8, s=0.75, ラグ中間9週）:")
    for name, p in p_scenarios:
        spw = W * p * S
        lo = (EN_LO / spw + 9) / 52
        hi = (EN_HI / spw + 9) / 52
        print(f"  BUY率{p*100:>5.1f}%: {lo:.1f}〜{hi:.1f}年")

    # 12ヶ月終端時点の期待BUY決済数
    print()
    print("D-019の12ヶ月終端到達時点の期待BUY決済数（w=8, s=0.75, ラグ中央値9週控除）:")
    effective_weeks = 52 - 9
    for name, p in p_scenarios:
        n12 = effective_weeks * W * p * S
        print(f"  BUY率{p*100:>5.1f}%: 約{n12:.1f}件"
              f"（SPRT最速卒業12件・最速撤退18件・E[N]=59〜92件と比較）")

    # 最速停止の理論下限
    print()
    print("最速停止の理論下限（12連勝で卒業/18連敗で撤退。D-019 §2-2）:")
    for name, p in p_scenarios:
        spw = W * p * S
        print(f"  BUY率{p*100:>5.1f}%: 12件蓄積に{12/spw/52:.1f}年・18件蓄積に{18/spw/52:.1f}年"
              f"（＋ラグ{lag_lo}〜{lag_hi}週）")

    # 参考: 全区分ベース（現行D-019前提）との比較
    print()
    print("参考: 現行D-019（全区分入力）の同条件試算 — 全登録が標本になる場合:")
    spw_all = W * S
    print(f"  E[N]=80到達: {(EN_MID/spw_all)/52:.2f}年＋ラグ ≈ "
          f"{(EN_MID/spw_all+lag_lo)/52:.1f}〜{(EN_MID/spw_all+lag_hi)/52:.1f}年"
          f"（D-019設計メモ§2-4の4〜7ヶ月と整合）")


if __name__ == "__main__":
    est = section1()
    section2(est)
