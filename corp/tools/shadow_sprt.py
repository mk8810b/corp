#!/usr/bin/env python3
"""シャドーポートフォリオ逐次検定（二重SPRT）の機械判定ツール。

D-019（2026-07-09新設）・D-021（2026-07-13: 主検定の入力をBUY判定限定に再定義）。

週次ルーチン（記録部LOG、Haiku可）が `corp/shadow-portfolio.md` の決済済み件数を数えて
本ツールに渡し、出力をそのまま週次サマリに転記する。判定ロジック・境界値の設計根拠と
作動特性（実効α=4.9%・検出力76〜82%・モンテカルロ検証）は
outputs/review/2026-07-09-fable5-sprt-design-calculations.py および
outputs/review/2026-07-09-fable5-validation-acceleration-design.md、
BUY限定化（D-021）の根拠とカレンダー試算は
outputs/review/2026-07-13-fable5-buy-only-sprt-redesign.md を参照。

使い方:
  python3 corp/tools/shadow_sprt.py --buy-wins <BUYのHIT_PROFIT数> --buy-losses <BUYのHIT_LOSS数> \
      [--buy-expired <BUYのEXPIRED数>] \
      [--ref-wins <全区分HIT_PROFIT数> --ref-losses <全区分HIT_LOSS数> --ref-expired <全区分EXPIRED数>]

入力の定義（playbooks/shadow-portfolio.md の運用ルールと一致させること）:
- 主検定（SPRT・卒業/撤退判定）の入力は**判定区分=BUYの仮想ポジション**のバリア決済のみ
  （D-021。WATCH/PASS由来の決済〔SP-007・SP-009を含む〕は主検定に入れない）。
- --ref-* は「参考: 全区分ベース（母集団診断・主検定外）」の記述統計用。BUY/WATCH/PASS
  全登録の合計を渡す。参考ブロックにはSPRT判定を出力しない（実弾規律の切替に使わないため）。
- EXPIREDは二値検定の標本に含めない（別掲で件数・比率のみ監視）。
- D-002のバリア値・BUY基準・使用モデル系列が重大変更された場合、変更後に登録された
  ポジションは別系列として集計する（本ツールには現行系列のカウントのみ渡す）。
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
EXPIRED_WARN_SHARE = 0.25             # EXPIRED比率の枠組み再検討ライン（BUY系列で判定）
# D-019の「BUYサブセット整合ゲート」は、D-021で主検定自体がBUY限定となったため吸収・廃止。

SG_W = math.log(P_GOOD / P_BE)
SG_L = math.log((1 - P_GOOD) / (1 - P_BE))
SK_W = math.log(P_RAND / P_BE)
SK_L = math.log((1 - P_RAND) / (1 - P_BE))


def main():
    ap = argparse.ArgumentParser(description="シャドーPF二重SPRT判定（D-019・D-021: BUY限定）")
    ap.add_argument("--buy-wins", type=int, required=True,
                    help="主検定入力: BUY判定のHIT_PROFIT件数")
    ap.add_argument("--buy-losses", type=int, required=True,
                    help="主検定入力: BUY判定のHIT_LOSS件数")
    ap.add_argument("--buy-expired", type=int, default=0,
                    help="BUY判定のEXPIRED件数（標本外・比率監視用）")
    ap.add_argument("--ref-wins", type=int, default=None,
                    help="参考（全区分・主検定外）: HIT_PROFIT合計")
    ap.add_argument("--ref-losses", type=int, default=None,
                    help="参考（全区分・主検定外）: HIT_LOSS合計")
    ap.add_argument("--ref-expired", type=int, default=0,
                    help="参考（全区分・主検定外）: EXPIRED合計")
    # 旧インターフェース（D-021以前）の誤用を明示的に拒否する
    ap.add_argument("--wins", type=int, default=None, help=argparse.SUPPRESS)
    ap.add_argument("--losses", type=int, default=None, help=argparse.SUPPRESS)
    a = ap.parse_args()

    if a.wins is not None or a.losses is not None:
        sys.exit("エラー: --wins/--losses は旧インターフェース（全区分入力）です。"
                 "D-021により主検定はBUY限定です: --buy-wins/--buy-losses を使い、"
                 "全区分の参考値は --ref-wins/--ref-losses で渡してください。")
    if min(a.buy_wins, a.buy_losses, a.buy_expired, a.ref_expired) < 0:
        sys.exit("エラー: 件数は非負整数で指定すること")

    w, l = a.buy_wins, a.buy_losses
    n = w + l
    print("=" * 64)
    print("シャドーポートフォリオ 逐次検定（二重SPRT・D-019/D-021）判定結果")
    print("=" * 64)
    print("【主検定（BUY限定）— 卒業/撤退を左右するのはこのブロックのみ】")
    print(f"入力: BUYバリア決済 n={n}（HIT_PROFIT w={w} / HIT_LOSS l={l}）"
          f" / BUYのEXPIRED {a.buy_expired}件（標本外）")

    verdict = None
    if n == 0:
        verdict = "CONTINUE"
        print("BUY判定のバリア決済がまだ0件のため判定不能（CONTINUE）。")
        print("注: WATCH/PASS由来の決済は主検定に入力しない（D-021。SP-007・SP-009は"
              "遡及的に除外済み）。")
    else:
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
        print(f"\n主検定の判定: {verdict}")

        # 付帯チェック（BUY系列のEXPIRED比率）
        total_closed = n + a.buy_expired
        if total_closed > 0 and a.buy_expired / total_closed > EXPIRED_WARN_SHARE:
            print(f"警告: BUY系列のEXPIRED比率 {a.buy_expired/total_closed*100:.0f}% > 25% — "
                  "二値バリア枠組み自体の再検討が必要（新しい決定IDでCEO裁定）")

    # ---- 参考ブロック（記述統計のみ。SPRT判定語は出力しない — D-021ラベリング義務） ----
    if a.ref_wins is not None and a.ref_losses is not None:
        rw, rl = a.ref_wins, a.ref_losses
        if rw < 0 or rl < 0:
            sys.exit("エラー: 件数は非負整数で指定すること")
        if rw < w or rl < l:
            sys.exit("エラー: --ref-* は全区分の合計であり、BUY件数を下回ることはできない")
        rn = rw + rl
        print("\n【参考: 全区分ベース（母集団診断・主検定外）】")
        print("※発掘条件・スクリーニング母集団を判定によらず無差別に買った場合の値動き傾向。")
        print("  判定関数の成績ではなく、卒業/撤退・実弾規律の切替には使わない（D-021）。")
        if rn == 0:
            print(f"バリア決済 0件 / EXPIRED {a.ref_expired}件")
        else:
            print(f"バリア決済 n={rn}（HIT_PROFIT {rw} / HIT_LOSS {rl}） "
                  f"勝率点推定 {rw/rn*100:.1f}% / EXPIRED {a.ref_expired}件"
                  f"（うちBUY以外: 決済{rn-n}件・EXPIRED {a.ref_expired-a.buy_expired}件）")
        print("解釈注意: 発掘条件の軸A/C（値上がり率・出来高急増）は急変日に銘柄を拾うため、")
        print("この勝率は急変日直後の値動きの性質に系統的に偏る。")

    # ---- 手続きの注意 ----
    print("\n-- 手続きの注意（playbooks/shadow-portfolio.md §逐次検定 参照） --")
    if verdict.startswith("GRADUATE"):
        print("・卒業は自動発効しない。CEOへ勧告し、新しい決定IDの発行をもって")
        print("  D-011通常サイジングへ復帰する（D-021: BUYサブセット整合ゲートは主検定の")
        print("  BUY限定化により吸収・廃止済み）。")
        print(f"・p̂の90%信頼区間下限がテール込み分岐{P_BE_TAIL*100:.1f}%未満の場合、")
        print("  灰色帯（テール仮定次第で期待値の符号が変わる帯）である旨を勧告に明記する。")
    elif verdict.startswith("KILL"):
        print("・直ちにプロベーション期の新規実弾BUYを停止する（リスク管理部は新規BUYを")
        print("  REJECT）。これは安全側の措置であり統計的結論ではない。")
        print("・統計的結論は成熟コホート（登録から6ヶ月経過し全決済済みのBUYポジションのみ）で")
        print("  再計算して確認する（早期決済バイアス: 負けが先に決済され序盤の勝率は低く")
        print("  出る。設計メモ§6参照）。確認後にCEOへ報告し、再設計を裁定する。")
    elif verdict.startswith("GRAY"):
        print("・勝率は分岐勝率近傍。合格/不合格の二値で報告せず、テール込み分岐（〜42%）")
        print("  との位置関係を添えてCEO裁定に回す（検証延長・条件変更・撤退のいずれか）。")
    else:
        print("・境界未達。プロベーション期を維持し、次週も本ツールで再評価する。")
        print("・BUY決済の蓄積は遅い（観測BUY率0/14。再設計メモ§4のカレンダー試算参照）。")
        print("  プロベーション開始から12ヶ月ごとの定期裁定チェックポイント（D-021）で")
        print("  蓄積状況をCEOへ報告すること。")


if __name__ == "__main__":
    main()
