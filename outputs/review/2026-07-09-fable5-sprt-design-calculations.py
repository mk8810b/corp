#!/usr/bin/env python3
"""D-019（検証加速: 逐次検定＋プロベーション期）設計のための数値検証スクリプト（Fable5, 2026-07-09）。

憲法第2章-5（数値の再計算は必ずPythonで行う）に基づき、設計メモ
outputs/review/2026-07-09-fable5-validation-acceleration-design.md の全数値の根拠計算を
再現可能な形で残す。実行: python3 outputs/review/2026-07-09-fable5-sprt-design-calculations.py

前提値の出典:
- 損切り-10%/利確+25%・資金300万円: corp/board.md D-002
- 実効値 勝ち+19.42%/負け-12.5%・実務分岐勝率39.2%: outputs/review/2026-07-09-fable5-strategy-review.md §5-1
- テール込み負け分布（負けの95%が-12.5%・4%が-30%・1%が-80%）: D-015の**仮定値**（実測なし）
- ランダムウォーク到達確率 10/35=28.57%: 戦略レビュー §5-1（ギャンブラーの破産問題）
- 決済までの日柄（首抜け時間）の分布は**実測データが存在しないため全て仮定値**であり、
  カレンダー換算はシナリオ幅で示す（第2条: 仮定と実測を区別して明記）。
"""

import math
import random
import statistics
from collections import Counter

# ---------------------------------------------------------------- 定数
C0 = 3_000_000            # 当初資金（D-002）
W_EFF = 0.1942            # 勝ちの実効値（税・スリッページ込み、戦略レビュー§5-1）
L_BASE = 0.125            # 負けの実効値（平均ギャップ込み、同上）
LOSS_DIST = [(0.95, 0.125), (0.04, 0.30), (0.01, 0.80)]  # D-015基本仮定（仮定値）

P_RAND = 10 / 35          # 0.2857 ランダムウォークの+25%先行到達確率 = エッジ無し
P_BE = 0.392              # 実務損益分岐勝率（平均ギャップ込み、テールなし）
P_BE_TAIL = None          # 下で計算（テール込み 〜41.7%）
P_GOOD = 0.50             # 「明確に良い」設計対立仮説

ALPHA = 0.05              # 第一種過誤（各SPRT。従来の片側5%を踏襲）
BETA = 0.20               # 第二種過誤（各SPRT名目。検出力80%を踏襲）
LN_A = math.log((1 - BETA) / ALPHA)    # 上側境界 ln(16) = 2.7726
LN_B = math.log(BETA / (1 - ALPHA))    # 下側境界 ln(0.2105) = -1.5581
N_TRUNC = 150             # 打ち切り（バリア決済ベース）
TERM_GRAD_LLR = LN_A / 2  # 終端卒業閾値（n=150到達時: LLR_G≥lnA/2で卒業）
TERM_KILL_LLR = 0.0       # 終端撤退閾値（同: LLR_K≥0で撤退）
# 打ち切り時の終端判定規則: n=150到達時は上記閾値で卒業/撤退/灰色のいずれかに必ず
# 分類して閉じる（終端規則なしでは「未決着」が結合実効検出力を約70%へ下げる）。
# 終端卒業閾値lnA/2は、結合手続きの実効α（p=39.2%での誤卒業率）が名目5%を超えない
# よう調整した値（閾値0では実効α≈8.0%に膨らむことをモンテカルロで確認済み）。
# 終端撤退閾値は0のまま: 「分岐勝率ちょうどで撤退」は期待値≈0の局面で実弾を
# 止めるだけの保守側の誤りであり、第3条の趣旨に沿うため厳格化しない（非対称設計）。

SEP = "=" * 74


def sec(title):
    print(f"\n{SEP}\n{title}\n{SEP}")


# ---------------------------------------------------------------- §0 分岐勝率の再確認
sec("§0 損益分岐勝率の再確認（既存値の再計算）")
p_ideal = 0.10 / 0.35
p_tax = 0.10 / (0.25 * (1 - 0.20315) + 0.10)
p_real = L_BASE / (W_EFF + L_BASE)
e_loss_tail = sum(p * l for p, l in LOSS_DIST)
p_tail = e_loss_tail / (W_EFF + e_loss_tail)
P_BE_TAIL = p_tail
print(f"理想（±バリア理想約定・コストゼロ）      p* = {p_ideal*100:.2f}%")
print(f"＋譲渡益課税20.315%                       p* = {p_tax*100:.2f}%")
print(f"＋スリッページ・平均ギャップ（=実務）     p* = {p_real*100:.2f}%")
print(f"＋壊滅ギャップテール（D-015基本仮定）     p* = {p_tail*100:.2f}%")
print(f"ランダムウォークの到達確率（エッジ無し）  p  = {P_RAND*100:.2f}%")

# ---------------------------------------------------------------- §1 固定nの再現と決定整合性
sec("§1 固定標本二項検定のn（正規近似）— 従来の102の再現と決定整合な検定のn")

def fixed_n(p0, p1):
    za, zb = 1.6449, 0.8416  # z_{0.05}, z_{0.20}（従来設計の片側5%・検出力80%）
    num = za * math.sqrt(p0 * (1 - p0)) + zb * math.sqrt(p1 * (1 - p1))
    return (num / abs(p1 - p0)) ** 2

for p0, p1, label in [
    (P_RAND, 0.40, "従来設計: H0 p=28.6%(エッジ無し) vs H1 p=40%"),
    (P_BE, P_GOOD, "決定整合(卒業): H0 p=39.2%(実務分岐) vs H1 p=50%"),
    (P_BE, P_RAND, "決定整合(撤退): H0 p=39.2% vs H1 p=28.6%"),
]:
    print(f"  {label:<48} n ≈ {fixed_n(p0, p1):.0f}")
print("→ 従来の『n=102』はエッジ有無（28.6% vs 40%）の検定であり、実運用可否")
print("  （実務分岐39.2%超か）を直接答えない。決定整合な固定検定は n≈124〜128 必要。")

# ---------------------------------------------------------------- §2 SPRT境界
sec("§2 二重SPRT（Sobel–Wald型・3結論方式）の境界値")

# 検定G（卒業）: H0 p=0.392 vs H1 p=0.50（H1採択=卒業）
SG_W = math.log(P_GOOD / P_BE)
SG_L = math.log((1 - P_GOOD) / (1 - P_BE))
# 検定K（撤退）: H0 p=0.392 vs H1 p=0.2857（H1採択=撤退）
SK_W = math.log(P_RAND / P_BE)
SK_L = math.log((1 - P_RAND) / (1 - P_BE))

print(f"共通境界: ln A = ln((1-β)/α) = {LN_A:.4f} / ln B = ln(β/(1-α)) = {LN_B:.4f}")
print(f"検定G（卒業）: LLR_G = w·{SG_W:+.4f} + l·{SG_L:+.4f}   （w=勝ち数, l=負け数）")
print(f"検定K（撤退）: LLR_K = w·{SK_W:+.4f} + l·{SK_L:+.4f}")

def llr_g(w, n):
    return w * SG_W + (n - w) * SG_L

def llr_k(w, n):
    return w * SK_W + (n - w) * SK_L

def k_grad(n):
    """卒業に必要な最小勝ち数（存在しなければNone）"""
    for w in range(n + 1):
        if llr_g(w, n) >= LN_A:
            return w
    return None

def k_kill(n):
    """撤退境界に達する最大勝ち数（存在しなければNone）"""
    best = None
    for w in range(n + 1):
        if llr_k(w, n) >= LN_A:
            best = w
    return best

# 直線形（運用参照用）
grad_slope = -SG_L / (SG_W - SG_L)
grad_icpt = LN_A / (SG_W - SG_L)
kill_slope = SK_L / (SK_L - SK_W)
kill_icpt = -LN_A / (SK_L - SK_W)
print(f"\n直線形: 卒業 ⇔ w ≥ {grad_icpt:.3f} + {grad_slope:.4f}·n")
print(f"        撤退 ⇔ w ≤ {kill_icpt:.3f} + {kill_slope:.4f}·n")

n_min_grad = next(n for n in range(1, 100) if k_grad(n) is not None and k_grad(n) <= n)
n_min_kill = next(n for n in range(1, 100) if k_kill(n) is not None and k_kill(n) >= 0)
print(f"最速の卒業: {n_min_grad}連勝 / 最速の撤退: {n_min_kill}連敗")

# 打ち切り時の終端判定閾値
W_GRAD_TRUNC = next(w for w in range(N_TRUNC + 1) if llr_g(w, N_TRUNC) >= TERM_GRAD_LLR)
W_KILL_TRUNC = max(w for w in range(N_TRUNC + 1) if llr_k(w, N_TRUNC) >= TERM_KILL_LLR)
print(f"終端判定（n={N_TRUNC}到達時）: w ≥ {W_GRAD_TRUNC} で卒業 / "
      f"w ≤ {W_KILL_TRUNC} で撤退 / その間は灰色")

print(f"\n決済数n別の判定境界（w=バリア決済のうちHIT_PROFITの数）:")
print(f"  {'n':>4} {'撤退(w≤)':>10} {'卒業(w≥)':>10}")
for n in range(10, N_TRUNC + 1, 10):
    kk = k_kill(n)
    kg = k_grad(n)
    print(f"  {n:>4} {('-' if kk is None else kk):>10} {('-' if kg is None or kg > n else kg):>10}")

# ---------------------------------------------------------------- §3 Waldの近似期待停止数
sec("§3 Wald近似による期待停止数（設計点・単独検定ベースの理論値）")

def wald_en(p, p0, p1):
    sw = math.log(p1 / p0)
    sl = math.log((1 - p1) / (1 - p0))
    ez = p * sw + (1 - p) * sl
    if abs(ez) < 1e-12:
        return float("nan")
    # 受容確率の近似（Wald）: h(p)を解く代わりに設計点のみ評価
    if p <= p0:
        return ((1 - ALPHA) * LN_B + ALPHA * LN_A) / ez
    return (BETA * LN_B + (1 - BETA) * LN_A) / ez

print(f"検定G単独: E[N | p=0.392] ≈ {wald_en(P_BE, P_BE, P_GOOD):.0f} / "
      f"E[N | p=0.50] ≈ {wald_en(P_GOOD, P_BE, P_GOOD):.0f}")
print(f"検定K単独: E[N | p=0.392] ≈ {wald_en(P_BE, P_BE, P_RAND):.0f} / "
      f"E[N | p=0.286] ≈ {wald_en(P_RAND, P_BE, P_RAND):.0f}")
print("（境界超過分を無視するWald近似。結合手続きの実性能は§4のモンテカルロを正とする）")

# ---------------------------------------------------------------- §4 結合手続きのOC（モンテカルロ）
sec("§4 結合手続き（二重SPRT＋打ち切り150）の作動特性（モンテカルロ5万試行）")

def run_combined(p, sims=50_000, n_trunc=N_TRUNC, seed_base="D019"):
    rng = random.Random(f"{seed_base}-{p}")
    outcomes = Counter()
    ns = []
    for _ in range(sims):
        w = 0
        g_state = k_state = None
        res = None
        for n in range(1, n_trunc + 1):
            if rng.random() < p:
                w += 1
            l = n - w
            if g_state is None:
                v = w * SG_W + l * SG_L
                if v >= LN_A:
                    g_state = "h1"
                elif v <= LN_B:
                    g_state = "h0"
            if k_state is None:
                v = w * SK_W + l * SK_L
                if v >= LN_A:
                    k_state = "h1"
                elif v <= LN_B:
                    k_state = "h0"
            if g_state == "h1":
                res = "卒業"
                break
            if k_state == "h1":
                res = "撤退"
                break
            if g_state == "h0" and k_state == "h0":
                res = "灰色"
                break
        if res is None:
            # 終端判定規則（n=n_trunc到達時）
            n = n_trunc
            if llr_g(w, n) >= TERM_GRAD_LLR:
                res = "卒業"
            elif llr_k(w, n) >= TERM_KILL_LLR:
                res = "撤退"
            else:
                res = "灰色"
        outcomes[res] += 1
        ns.append(n)
    return outcomes, ns

print("灰色 = 両検定ともH0(p≈39.2%近傍)受容、または終端判定で中間帯 → CEO裁定へ")
print(f"  {'真の勝率':>8} {'P(卒業)':>8} {'P(撤退)':>8} {'P(灰色)':>8} "
      f"{'E[N]':>6} {'中央値N':>7}")
oc_results = {}
for p in (0.25, P_RAND, 0.33, 0.36, P_BE, 0.42, 0.45, P_GOOD, 0.55):
    oc, ns = run_combined(p)
    s = sum(oc.values())
    oc_results[round(p, 4)] = (oc, ns)
    print(f"  {p*100:>7.1f}% {oc['卒業']/s*100:>7.2f}% {oc['撤退']/s*100:>7.2f}% "
          f"{oc['灰色']/s*100:>7.2f}% "
          f"{statistics.mean(ns):>6.0f} {statistics.median(ns):>7.0f}")
print("\n検証ポイント:")
oc392 = oc_results[round(P_BE, 4)][0]
s392 = sum(oc392.values())
print(f"  誤卒業率 P(卒業|p=39.2%) = {oc392['卒業']/s392*100:.2f}%（実効α。名目5%以下を確認）")
oc286 = oc_results[round(P_RAND, 4)][0]
s286 = sum(oc286.values())
print(f"  正撤退率 P(撤退|p=28.6%) = {oc286['撤退']/s286*100:.2f}%（実効検出力・撤退側）")
oc50 = oc_results[round(P_GOOD, 4)][0]
s50 = sum(oc50.values())
print(f"  正卒業率 P(卒業|p=50%)  = {oc50['卒業']/s50*100:.2f}%（実効検出力・卒業側。"
      f"名目80%をやや下回るが、")
print("  不足分は『卒業見送り=プロベーション継続』という低コスト側の誤りに落ちる。")
print("  灰色終了時はCEO裁定で検証延長・条件変更が可能であり、誤卒業（実弾フルサイズ化の")
print("  誤り）の抑制を優先する非対称設計として許容する。")

# ---------------------------------------------------------------- §5 カレンダー換算
sec("§5 カレンダー時間への換算（決済ラグは実測なしの仮定シナリオ）")

def weeks_to_reach(n_target, per_week, median_lag_w, expiry_w=26, t_max=400):
    """週次per_week件登録・決済ラグを週次ハザード幾何分布（中央値median_lag_w、
    26週で失効=バリア決済せず標本から外れる）と仮定した場合に、バリア決済の累計が
    n_targetに達する週数。"""
    h = 1 - 0.5 ** (1 / median_lag_w)
    for t in range(1, t_max):
        settled = 0.0
        for k in range(1, t + 1):
            tau = t - k
            settled += per_week * (1 - (1 - h) ** min(tau, expiry_w))
        if settled >= n_target:
            return t
    return None

for m in (6, 12):
    h = 1 - 0.5 ** (1 / m)
    print(f"  ラグ中央値{m}週の仮定 → 26週時点の失効率（バリア未到達率） = "
          f"{(1-h)**26*100:.1f}%")

en_kill = statistics.mean(oc_results[round(P_RAND, 4)][1])
en_grad = statistics.mean(oc_results[round(P_GOOD, 4)][1])
scenarios = [
    (f"撤退が正しい場合（p=28.6%, E[N]≈{en_kill:.0f}）", en_kill),
    (f"卒業が正しい場合（p=50%, E[N]≈{en_grad:.0f}）", en_grad),
    ("灰色帯で打ち切りまで走る場合（N=150）", N_TRUNC),
    ("（比較）従来の固定n=102", 102),
    ("（比較）決定整合な固定n=128", 128),
]
print(f"\n  {'シナリオ':<44} " + " ".join(f"{f'週{w}件/ラグ{m}週':>14}"
      for w in (5, 8) for m in (6, 12)))
for label, n_t in scenarios:
    cells = []
    for w in (5, 8):
        for m in (6, 12):
            t = weeks_to_reach(n_t, w, m)
            cells.append(f"{t}週≈{t/4.33:.1f}月" if t else "未達")
    print(f"  {label:<44} " + " ".join(f"{c:>14}" for c in cells))
print("→ 決済ラグ（首抜け時間）が律速。候補数を倍にしても短縮は限定的（§7で詳述）。")

# ---------------------------------------------------------------- §6 早期決済バイアスのデモ
sec("§6 早期決済バイアス（-10%バリアが近い→負けが先に決済される）のGBMデモ")

random.seed(20260709)
SIGMA_D = 0.025   # 日次ボラ2.5%（仮定: 当社ファネルの高ボラ銘柄想定）
MU_D = 0.0012     # 全体の勝率が4割台になるよう選んだデモ用ドリフト（仮定）
N_PATH = 30_000
HORIZON = 126     # 6ヶ月≈126営業日

hits = []  # (day, win)
expired = 0
for _ in range(N_PATH):
    x = 0.0
    for d in range(1, HORIZON + 1):
        x += MU_D + SIGMA_D * random.gauss(0, 1)
        if x >= math.log(1.25):
            hits.append((d, 1))
            break
        if x <= math.log(0.90):
            hits.append((d, 0))
            break
    else:
        expired += 1

p_all = sum(w for _, w in hits) / len(hits)
print(f"パス数{N_PATH:,}・日次σ{SIGMA_D*100:.1f}%・ドリフト{MU_D*100:.2f}%/日（いずれも仮定）")
print(f"バリア決済率 {len(hits)/N_PATH*100:.1f}% / 失効率 {expired/N_PATH*100:.1f}% / "
      f"最終勝率 p = {p_all*100:.1f}%")
print(f"{'決済が早い順の部分標本':<28} {'勝率':>8}")
hits.sort()
for frac in (0.10, 0.25, 0.50, 1.00):
    sub = hits[: int(len(hits) * frac)]
    print(f"  最初の{frac*100:>3.0f}%の決済のみ         {sum(w for _, w in sub)/len(sub)*100:>7.1f}%")
med_win = statistics.median([d for d, w in hits if w == 1])
med_loss = statistics.median([d for d, w in hits if w == 0])
print(f"決済までの日数中央値: 勝ち{med_win:.0f}日 vs 負け{med_loss:.0f}日")
print("→ 序盤の決済済み標本は真の勝率より低く出る（負けが先に決まる）。")
print("  撤退判定を『即時サイジング停止（安全側の措置）』と『統計的結論（成熟コホートで")
print("  確認後）』の2段階に分ける設計根拠。卒業側はこのバイアスで保守側に倒れるため安全。")

# ---------------------------------------------------------------- §7 プロベーション期サイジング
sec("§7 プロベーション期サイジングの検証（上限1〜3%の妥当性）")

def draw_loss(rng):
    u = rng.random()
    acc = 0.0
    for pr, l in LOSS_DIST:
        acc += pr
        if u < acc:
            return l
    return LOSS_DIST[-1][1]

def probation_mc(p_win, n_trades, cap, sims=20_000, seed_base="prob"):
    rng = random.Random(f"{seed_base}-{p_win}-{n_trades}-{cap}")
    finals, mins = [], []
    for _ in range(sims):
        eq = C0
        mn = C0
        for _ in range(n_trades):
            bet = cap * eq  # 比例ベット（D-015）
            if rng.random() < p_win:
                eq += bet * W_EFF
            else:
                eq -= bet * draw_loss(rng)
            mn = min(mn, eq)
        finals.append(eq)
        mins.append(mn)
    finals.sort()
    return (statistics.median(finals) / C0, finals[int(sims * 0.05)] / C0,
            sum(1 for m in mins if m < C0 * 0.95) / sims,
            sum(1 for m in mins if m < C0 * 0.90) / sims)

ev_per = {p: (p * W_EFF - (1 - p) * e_loss_tail) for p in (P_RAND, 0.35, P_BE, 0.45)}
print("1トレードあたり期待損益（テール込み・投入1単位あたり）:")
for p, ev in ev_per.items():
    print(f"  勝率{p*100:5.1f}%: {ev*100:+.2f}% × 投入比率")
print("\n授業料の解析値（エッジ無し p=28.6%・比例ベット・K回の実弾トレード）:")
for cap in (0.01, 0.02, 0.03, 0.05, 0.10):
    for k in (20, 40):
        exp_total = (1 + cap * ev_per[P_RAND]) ** k - 1
        print(f"  上限{cap*100:>4.1f}%・{k:>2}回: 期待損益 {exp_total*100:+6.2f}%"
              + ("" if k == 20 else "\n"), end="")

print("\nモンテカルロ（2万試行・テール込み・比例ベット）:")
print(f"  {'条件':<26} {'中央値(倍)':>10} {'下位5%(倍)':>10} {'P(最低<95%)':>12} {'P(最低<90%)':>12}")
for p_win, label in ((P_RAND, "エッジ無し28.6%"), (0.45, "エッジあり45%")):
    for cap in (0.01, 0.02, 0.03, 0.05, 0.10):
        med, p5, r95, r90 = probation_mc(p_win, 40, cap)
        print(f"  {label}・上限{cap*100:>4.1f}%・40回 {med:>9.4f} {p5:>10.4f} "
              f"{r95*100:>11.2f}% {r90*100:>11.2f}%")

print("\n単一銘柄の壊滅シナリオ（-100%、上場廃止等）の資金影響:")
for cap in (0.01, 0.02, 0.03, 0.05, 0.10):
    print(f"  上限{cap*100:>4.1f}%: -{cap*100:.1f}%（{C0*cap:,.0f}円）")

print("\nPML（D-015: Σ投入比率×10% ≤ 5%）との整合（5ポジション同時保有時）:")
for cap in (0.02, 0.03):
    print(f"  プロベーション上限{cap*100:.0f}% × 5銘柄: PML = {5*cap*0.10*100:.2f}% ≤ 5.0% ✓")

print("\n単元株フィージビリティ（100株単元・資金300万円時の購入可能株価上限）:")
for cap in (0.01, 0.02, 0.03, 0.05, 0.10):
    print(f"  上限{cap*100:>4.1f}%: 株価 {C0*cap/100:,.0f}円 以下")
print("→ 基本2%（600円以下）＋1単元切り上げ許容3%（900円以下）。900〜3,000円の銘柄は")
print("  プロベーション期は実弾見送り（シャドーで追跡）。D-013の10%切り上げ許容の縮小版。")

# ---------------------------------------------------------------- §8 卒業時のBUYサブセット整合ゲート
sec("§8 卒業時のBUYサブセット整合ゲート（決済済みBUY≥15件・点推定≥39.2%）の通過確率")

def binom_ge(k, n, p):
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k, n + 1))

n_buy = 15
k_need = math.ceil(P_BE * n_buy)  # 15×0.392=5.88 → 6勝以上
print(f"必要勝ち数: ceil(0.392×15) = {k_need}勝以上（15戦）")
for p in (P_BE, 0.45, P_GOOD):
    print(f"  真のBUY勝率{p*100:4.1f}%のとき通過確率 = {binom_ge(k_need, n_buy, p)*100:.1f}%")
print("→ これは検定ではなく整合性チェック（n=15では検出力不足）。不通過は自動卒業を")
print("  保留しCEO裁定に回すためのゲートであり、合格/不合格の統計的証明ではない。")
