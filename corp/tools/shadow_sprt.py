#!/usr/bin/env python3
"""シャドーポートフォリオ逐次検定（二重SPRT）の機械判定ツール（D-019, 2026-07-09新設）。

週次ルーチン（記録部LOG、Haiku可）が `corp/shadow-portfolio.md` の決済済み件数を数えて
本ツールに渡し、出力をそのまま週次サマリに転記する。判定ロジック・境界値の設計根拠と
作動特性（実効α=4.9%・検出力76〜82%・モンテカルロ検証）は
outputs/review/2026-07-09-fable5-sprt-design-calculations.py および
outputs/review/2026-07-09-fable5-validation-acceleration-design.md を参照。

使い方:
  python3 corp/tools/shadow_sprt.py --wins <HIT_PROFIT数> --losses <HIT_LOSS数> \
      [--expired <EXPIRED数>] [--buy-wins <BUYのHIT_PROFIT数>] [--buy-losses <BUYのHIT_LOSS数>]

入力の定義（playbooks/shadow-portfolio.md の運用ルールと一致させること）:
- wins   = 状態HIT_PROFITの仮想ポジション数（BUY/WATCH/PASS全区分の合計）
- losses = 状態HIT_LOSSの仮想ポジション数（同上）
- EXPIREDは二値検定の標本に含めない（別掲で件数・比率のみ監視）
- D-002のバリア値が改定された場合、改定後に登録されたポジションは別系列として
  集計する（同一のpを測る標本にならないため。本ツールには旧バリア系列のみ渡す）
"""

import argparse
import math
import sys

# ---- 設計定数（D-019。変更は新しい決定IDを要する） ----
P_RAND = 10 / 35   # 0.2857 エッジ無し（ランダムウォークの+25%先行到達確率）
P_BE = 0.392       # 実務損益分岐勝率（税・スリッページ・平均ギャップ込み）
P_GOOD = 0.50      # 卒業側の設計対立仮説
P_BE_TAIL = 0.4167 # テール込み分岐勝率（D-015仮定。灰色帯の上限フラグ用）
ALPHA, BETA = 0.05, 0.20
LN_A = math.log((1 - BETA) / ALPHA)   # 2.7726
LN_B = math.log(BETA / (1 - ALPHA))   # -1.5581
N_TRUNC = 150
TERM_GRAD_LLR = LN_A / 2              # 終端卒業閾値（実効α≤5%調整済み）
TERM_KILL_LLR = 0.0                   # 終端撤退閾値（保守側の誤りは許容する非対称設計)
BUY_GATE_MIN_N = 15                   # 卒業時のBUYサブセット整合ゲート
EXPIRED_WARN_SHARE = 0.25             # EXPIRED比率の枠組み再検討ライン

SG_W = math.log(P_GOOD / P_BE)
SG_L = math.log((1 - P_GOOD) / (1 - P_BE))
SK_W = math.log(P_RAND / P_BE)
SK_L = math.log((1 - P_RAND) / (1 - P_BE))


def main():
    ap = argparse.ArgumentParser(description="シャドーPF二重SPRT判定（D-019）")
    ap.add_argument("--wins", type=int, required=True, help="HIT_PROFIT件数（全区分）")
    ap.add_argument("--losses", type=int, required=True, help="HIT_LOSS件数（全区分）")
    ap.add_argument("--expired", type=int, default=0, help="EXPIRED件数（参考掲載）")
    ap.add_argument("--buy-wins", type=int, default=None, help="BUY判定のHIT_PROFIT件数")
    ap.add_argument("--buy-losses", type=int, default=None, help="BUY判定のHIT_LOSS件数")
    a = ap.parse_args()
    if a.wins < 0 or a.losses < 0 or a.expired < 0:
        sys.exit("エラー: 件数は非負整数で指定すること")

    w, l = a.wins, a.losses
    n = w + l
    print("=" * 64)
    print("シャドーポートフォリオ 逐次検定（二重SPRT・D-019）判定結果")
    print("=" * 64)
    print(f"入力: バリア決済 n={n}（HIT_PROFIT w={w} / HIT_LOSS l={l}）"
          f" / EXPIRED {a.expired}件（標本外）")
    if n == 0:
        print("バリア決済がまだ0件のため判定不能（CONTINUE）。")
        return

    phat = w / n
    llr_g = w * SG_W + l * SG_L
    llr_k = w * SK_W + l * SK_L
    print(f"勝率点推定 p̂ = {phat*100:.1f}%")
    print(f"検定G（卒業: H0 p={P_BE:.3f} vs H1 p={P_GOOD:.2f}）: "
          f"LLR_G = {llr_g:+.3f}（卒業境界 {LN_A:+.3f} / H0受容境界 {LN_B:+.3f}）")
    print(f"検定K（撤退: H0 p={P_BE:.3f} vs H1 p={P_RAND:.4f}）: "
          f"LLR_K = {llr_k:+.3f}（撤退境界 {LN_A:+.3f} / H0受容境界 {LN_B:+.3f}）")

    # 判定（毎週、累計カウントで評価する。境界は一度越えたら確定扱い）
    if n >= N_TRUNC:
        if llr_g >= TERM_GRAD_LLR:
            verdict = "GRADUATE_RECOMMEND（終端判定）"
        elif llr_k >= TERM_KILL_LLR:
            verdict = "KILL_TRIGGER（終端判定）"
        else:
            verdict = "GRAY_STOP（終端判定: 分岐勝率近傍で終了）"
    elif llr_g >= LN_A:
        verdict = "GRADUATE_RECOMMEND"
    elif llr_k >= LN_A:
        verdict = "KILL_TRIGGER"
    elif llr_g <= LN_B and llr_k <= LN_B:
        verdict = "GRAY_STOP（両H0受容: 勝率は分岐勝率39.2%近傍）"
    else:
        verdict = "CONTINUE（検証継続・プロベーション維持）"
    print(f"\n判定: {verdict}")

    # 付帯チェック
    total_closed = n + a.expired
    if total_closed > 0 and a.expired / total_closed > EXPIRED_WARN_SHARE:
        print(f"警告: EXPIRED比率 {a.expired/total_closed*100:.0f}% > 25% — 二値バリア枠組み"
              "自体の再検討が必要（新しい決定IDでCEO裁定）")

    if a.buy_wins is not None and a.buy_losses is not None:
        bn = a.buy_wins + a.buy_losses
        if bn > 0:
            bphat = a.buy_wins / bn
            gate = (bn >= BUY_GATE_MIN_N) and (bphat >= P_BE)
            print(f"BUYサブセット: n={bn}, p̂={bphat*100:.1f}% → 整合ゲート"
                  f"{'通過' if gate else '不通過'}（要件: n≥{BUY_GATE_MIN_N} かつ "
                  f"p̂≥{P_BE*100:.1f}%。これは検定ではなく整合性チェック）")
        else:
            print("BUYサブセット: 決済0件（整合ゲート判定不能）")

    print("\n-- 手続きの注意（playbooks/shadow-portfolio.md §逐次検定 参照） --")
    if verdict.startswith("GRADUATE"):
        print("・卒業は自動発効しない。BUYサブセット整合ゲート通過を確認の上、CEOへ勧告し、")
        print("  新しい決定IDの発行をもってD-011通常サイジングへ復帰する。")
        print(f"・p̂の90%信頼区間下限がテール込み分岐{P_BE_TAIL*100:.1f}%未満の場合、")
        print("  灰色帯（テール仮定次第で期待値の符号が変わる帯）である旨を勧告に明記する。")
    elif verdict.startswith("KILL"):
        print("・直ちにプロベーション期の新規実弾BUYを停止する（リスク管理部は新規BUYを")
        print("  REJECT）。これは安全側の措置であり統計的結論ではない。")
        print("・統計的結論は成熟コホート（登録から6ヶ月経過し全決済済みのポジションのみ）で")
        print("  再計算して確認する（早期決済バイアス: 負けが先に決済され序盤の勝率は低く")
        print("  出る。設計メモ§6参照）。確認後にCEOへ報告し、再設計を裁定する。")
    elif verdict.startswith("GRAY"):
        print("・勝率は分岐勝率近傍。合格/不合格の二値で報告せず、テール込み分岐（〜42%）")
        print("  との位置関係を添えてCEO裁定に回す（検証延長・条件変更・撤退のいずれか）。")
    else:
        print("・境界未達。プロベーション期を維持し、次週も本ツールで再評価する。")


if __name__ == "__main__":
    main()
