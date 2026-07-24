#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2026-07-24 Fable5 発掘条件（軸C・軸D）再設計レビュー — 検証スクリプト
（憲法第2章-5準拠: 本文中の数値的主張はすべて本スクリプトで再現可能。標準ライブラリのみ使用）

対象レビュー: outputs/review/2026-07-24-fable5-axis-redesign-review.md

データの出典:
- 判断メモ16件（週2=2026-07-11の6件・週3=2026-07-18の10件、いずれも校閲確定版）:
  outputs/judgement/{code}-{date}.md
- スクリーニング成果物: outputs/screening/2026-07-11-weekly.md, 2026-07-18-weekly.md
- イベント駆動メモ: outputs/judgement/5491-20260721-event.md, 5242-20260721-event.md,
  5216-20260723-event.md, 598A-20260723-event.md, 598A-20260724-event.md
- コスト単価314,200トークン/候補: D-022（outputs/review/2026-07-13-fable5-screening-breadth-review.md §5-2）
- EDINET/TDnetの実地到達性チェック: 本スクリプト実行者が2026-07-24に実測した記録値
  （--live で再実測可能。既定はオフライン＝記録値の表示のみで決定論的）

分類タグは判断メモ記載の理由の再整理であり、分類者（Fable5）の裁量を含む。
各行に根拠となる判断メモのパスを付し、機械可読な形で監査可能にしてある。
"""

from math import comb
import sys

TOKENS_PER_CANDIDATE = 314_200  # D-022 §5-2 実測平均（調査+起案+校閲、下限値）

# ---------------------------------------------------------------------------
# §0 データ: 週2（07-11）・週3（07-18）の計16件
#   axis: 採用軸（スクリーニング成果物の記載）
#   decision: BUY/WATCH/PASS（校閲確定版）
#   pbr: 判断メモ記載のPBR（None=記載なし/算定不可）
#   flags: D-015テールフラグ該当（'b?'=3856の結論不表明「該当の蓋然性が高い」準該当）
#   c1_mode: D-012基準1（カタリスト特定済み・未織り込み）の不成立モード
#     UNIDENTIFIED   = 急騰/急落/急増の材料そのものが特定できない（取得不能）
#     PRICED_IN      = 材料は特定できたが既に織り込み済み/反応済みと判定
#     KNOWN_OLD      = 材料が既知の旧情報（週次バッチ時点で新規性なし）
#   c2_mode: D-012基準2（同業比割安×構造的欠陥なし）の不成立モード
#     DEFECT_JUSTIFIES = 割安（低PBR等）だが、割安を正当化する構造的欠陥を調査が特定
#     NOT_CHEAP        = そもそも同業比割高/絶対水準で割安でない
#     NO_DATA          = 同業比較データが欠落し立証不能
#   surge_pct: 軸C採用根拠の出来高前日比率（%、スクリーニング成果物記載）
#   recent_profit: 直近本決算の最終損益が黒字か（True/False/None=取得不能・未確定）
#   equity_ratio: 自己資本比率%（判断メモ/調査メモ記載。None=記載なし）
#   dividend: 配当実績/予想あり（True/False/None=判断メモに記載なし→取得不能扱い）
# ---------------------------------------------------------------------------

CASES = [
    # --- 週2: 2026-07-11（6件） ---
    dict(code="5240", axis="C", decision="PASS", pbr=2.05, flags=["a"],
         c1_mode="UNIDENTIFIED", c2_mode="NOT_CHEAP", surge_pct=37492.62,
         recent_profit=False, equity_ratio=None, dividend=None,
         src="outputs/judgement/5240-20260711.md"),
    dict(code="3856", axis="C", decision="PASS", pbr=0.27, flags=["b?"],
         c1_mode="PRICED_IN", c2_mode="DEFECT_JUSTIFIES", surge_pct=1765.67,
         recent_profit=None,  # 確定決算が提出延期中で存在しない
         equity_ratio=None, dividend=None,
         src="outputs/judgement/3856-20260711.md"),
    dict(code="5491", axis="D", decision="WATCH", pbr=0.194, flags=[],
         c1_mode="KNOWN_OLD", c2_mode="DEFECT_JUSTIFIES", surge_pct=None,
         recent_profit=True,  # 黒字転換
         equity_ratio=44.4, dividend=True,  # 3期ぶり復配
         src="outputs/judgement/5491-20260711.md"),
    dict(code="7215", axis="D", decision="PASS", pbr=0.20, flags=[],
         c1_mode="UNIDENTIFIED", c2_mode="DEFECT_JUSTIFIES", surge_pct=None,
         recent_profit=False,  # 2026/3期純損失837百万円
         equity_ratio=29.0, dividend=False,  # 直近赤字・無配（判断メモ1章）
         src="outputs/judgement/7215-20260711.md"),
    dict(code="7211", axis="E", decision="WATCH", pbr=0.53, flags=[],
         c1_mode="PRICED_IN", c2_mode="NOT_CHEAP", surge_pct=None,
         recent_profit=True, equity_ratio=38.0, dividend=None,
         src="outputs/judgement/7211-20260711.md"),
    dict(code="3350", axis="E", decision="PASS", pbr=0.79, flags=["c"],
         c1_mode="UNIDENTIFIED", c2_mode="DEFECT_JUSTIFIES", surge_pct=None,
         recent_profit=False,  # 最終損失950.46億円
         equity_ratio=86.2, dividend=None,
         src="outputs/judgement/3350-20260711.md"),
    # --- 週3: 2026-07-18（10件） ---
    dict(code="5242", axis="A", decision="WATCH", pbr=2.10, flags=[],
         c1_mode="UNIDENTIFIED", c2_mode="NOT_CHEAP", surge_pct=None,
         recent_profit=False,  # 経常赤字転落・純損失
         equity_ratio=55.1, dividend=None,
         src="outputs/judgement/5242-20260718.md"),
    dict(code="9439", axis="A", decision="PASS", pbr=6.96, flags=[],
         c1_mode="PRICED_IN", c2_mode="NOT_CHEAP", surge_pct=None,
         recent_profit=False, equity_ratio=None, dividend=None,
         src="outputs/judgement/9439-20260718.md"),
    dict(code="598A", axis="B", decision="WATCH", pbr=15.33, flags=[],
         c1_mode="PRICED_IN", c2_mode="NOT_CHEAP", surge_pct=None,
         recent_profit=True, equity_ratio=61.2, dividend=None,
         src="outputs/judgement/598A-20260718.md"),
    dict(code="7138", axis="B", decision="PASS", pbr=1.39, flags=["a", "c"],
         c1_mode="UNIDENTIFIED", c2_mode="DEFECT_JUSTIFIES", surge_pct=None,
         recent_profit=False,  # 3期連続赤字
         equity_ratio=72.3, dividend=None,
         src="outputs/judgement/7138-20260718.md"),
    dict(code="5216", axis="C", decision="WATCH", pbr=16.49, flags=["a"],
         c1_mode="PRICED_IN",  # 材料特定成功、ただし数時間で織り込み済み
         c2_mode="NOT_CHEAP", surge_pct=11288.38,
         recent_profit=False,  # 最終赤字3,084百万円
         equity_ratio=31.5, dividend=None,
         src="outputs/judgement/5216-20260718.md"),
    dict(code="7359", axis="C", decision="WATCH", pbr=3.07, flags=["a"],
         c1_mode="PRICED_IN",  # 開示は特定できたが強く織り込み済み＋定量コミットなし
         c2_mode="NO_DATA", surge_pct=10659.42,
         recent_profit=True, equity_ratio=22.9, dividend=None,
         src="outputs/judgement/7359-20260718.md"),
    dict(code="6619", axis="D", decision="PASS", pbr=0.24, flags=["a"],
         c1_mode="UNIDENTIFIED", c2_mode="DEFECT_JUSTIFIES", surge_pct=None,
         recent_profit=False,  # 売上88.3%減・純損失125億円
         equity_ratio=78.5, dividend=None,
         src="outputs/judgement/6619-20260718.md"),
    dict(code="7201", axis="D", decision="WATCH", pbr=0.24, flags=[],
         c1_mode="KNOWN_OLD",  # Re:Nissanは1年以上前から公知
         c2_mode="DEFECT_JUSTIFIES", surge_pct=None,
         recent_profit=False,  # 2期連続大幅赤字
         equity_ratio=24.2, dividend=False,  # 無配（同業5社中唯一）
         src="outputs/judgement/7201-20260718.md"),
    dict(code="8729", axis="E", decision="WATCH", pbr=1.65, flags=[],
         c1_mode="KNOWN_OLD", c2_mode="NOT_CHEAP", surge_pct=None,
         recent_profit=True, equity_ratio=None, dividend=True,
         src="outputs/judgement/8729-20260718.md"),
    dict(code="9501", axis="E", decision="WATCH", pbr=0.34, flags=["c"],
         c1_mode="UNIDENTIFIED", c2_mode="DEFECT_JUSTIFIES", surge_pct=None,
         recent_profit=False,  # 災害特損9,138億円・最終赤字454,263百万円
         equity_ratio=21.8, dividend=False,  # 配当予想0円
         src="outputs/judgement/9501-20260718.md"),
]

assert len(CASES) == 16, "週2+週3の16件"


def clopper_pearson_lower_all_success(n, alpha=0.05):
    """n回中n回成功を観測したときの成功率の片側(1-alpha)下側信頼限界。
    x=n の特殊形: p_lower = alpha**(1/n)（Clopper-Pearson厳密下限）。"""
    return alpha ** (1.0 / n)


def hypergeom_p_all_in(N, K, n):
    """N件中K件が性質Xを持つ母集団から無作為にn件抜いたとき、n件全てが性質Xを持つ確率
    P(X_count = n) = C(K,n)/C(N,n)。（無作為抽出帰無仮説の下での正確片側確率）"""
    return comb(K, n) / comb(N, n)


def sec(title):
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def main():
    # ------------------------------------------------------------------
    sec("§1 基礎集計（週2+週3=16件）")
    # ------------------------------------------------------------------
    from collections import Counter
    dec = Counter(c["decision"] for c in CASES)
    print(f"判定内訳: {dict(dec)}  (BUY={dec.get('BUY',0)})")
    assert dec.get("BUY", 0) == 0
    by_axis = {}
    for c in CASES:
        by_axis.setdefault(c["axis"], []).append(c)
    for ax in "ABCDE":
        rows = by_axis.get(ax, [])
        print(f"軸{ax}: {len(rows)}件 -> " + ", ".join(
            f"{r['code']}({r['decision']})" for r in rows))
    # 基準1・基準2は16件全てで不成立（判断メモの明示的判定）
    print("D-012基準1不成立: 16/16件、基準2不成立: 16/16件（全判断メモが明示）")

    # ------------------------------------------------------------------
    sec("§2 仮説C: 軸C（出来高急増率の極端上位）→ 基準1不成立の系統性")
    # ------------------------------------------------------------------
    axC = by_axis["C"]
    print("軸C採用4件の基準1不成立モード:")
    for c in axC:
        print(f"  {c['code']}: {c['c1_mode']}  (出来高前日比 +{c['surge_pct']:,}% "
              f"= {c['surge_pct']/100+1:,.1f}倍)  [{c['src']}]")
    n_c = len(axC)
    k_c = sum(1 for c in axC if c["c1_mode"] in ("UNIDENTIFIED", "PRICED_IN"))
    print(f"-> 『材料未特定 or 織り込み済み』での基準1不成立: {k_c}/{n_c}")
    lb = clopper_pearson_lower_all_success(n_c)
    print(f"   点推定100%、不成立率の片側95%下限（Clopper-Pearson）= {lb:.3f}（n={n_c}）")
    # 軸A（直近営業日の値上がり率上位）は軸Cと同型の「急変事後」選抜
    axAC = axC + by_axis["A"]
    k_ac = sum(1 for c in axAC if c["c1_mode"] in ("UNIDENTIFIED", "PRICED_IN"))
    lb6 = clopper_pearson_lower_all_success(len(axAC))
    print(f"軸A∪C（急変事後の選抜、同型）: {k_ac}/{len(axAC)}、片側95%下限 = {lb6:.3f}")
    # 出来高急増倍率 vs D-018の「有意な出来高」閾値1.5倍
    ratios = sorted(c["surge_pct"] / 100 + 1 for c in axC)
    print(f"軸C採用銘柄の出来高倍率: {['%.1f倍' % r for r in ratios]}")
    print(f"  D-018検証済みの『出来高を伴う』閾値=1.5倍に対し {ratios[0]/1.5:.0f}〜"
          f"{ratios[-1]/1.5:.0f}倍の超過。定義上『市場が既に爆発的に反応した後』の帯を採っている")

    # ------------------------------------------------------------------
    sec("§3 仮説D: 軸D（低PBR絶対下位）→ 基準2不成立の系統性")
    # ------------------------------------------------------------------
    axD = by_axis["D"]
    print("軸D採用4件の基準2不成立モード:")
    for c in axD:
        print(f"  {c['code']}: PBR{c['pbr']}倍 -> {c['c2_mode']}  [{c['src']}]")
    k_d = sum(1 for c in axD if c["c2_mode"] == "DEFECT_JUSTIFIES")
    print(f"-> 『割安を正当化する構造的欠陥を特定』での基準2不成立: {k_d}/{len(axD)}")
    # 軸によらず低PBR帯（判断メモ記載PBR<=0.34）の全数
    low_pbr = [c for c in CASES if c["pbr"] is not None and c["pbr"] <= 0.34]
    print(f"\nPBR<=0.34の候補（採用軸不問）: {len(low_pbr)}件")
    for c in sorted(low_pbr, key=lambda x: x["pbr"]):
        print(f"  {c['code']} (軸{c['axis']}, PBR{c['pbr']}): {c['c2_mode']}")
    k_low = sum(1 for c in low_pbr if c["c2_mode"] == "DEFECT_JUSTIFIES")
    lb_low = clopper_pearson_lower_all_success(len(low_pbr))
    print(f"-> 構造的欠陥/懸念の特定による棄却: {k_low}/{len(low_pbr)}"
          f"（点推定100%、片側95%下限 = {lb_low:.3f}）")

    # ------------------------------------------------------------------
    sec("§4 連関の正確検定（参考値。カテゴリ定義が部分的に軸定義由来である点に注意）")
    # ------------------------------------------------------------------
    defect = [c for c in CASES if c["c2_mode"] == "DEFECT_JUSTIFIES"]
    print(f"『構造的欠陥型の基準2棄却』全体: {len(defect)}/16 "
          f"({[c['code'] for c in defect]})")
    p1 = hypergeom_p_all_in(16, len(defect), 4)
    print(f"軸D 4件が全て構造的欠陥型に入る無作為確率（超幾何、正確片側）: "
          f"C({len(defect)},4)/C(16,4) = {p1:.4f}")
    flagged = [c for c in CASES if c["flags"]]
    print(f"\nD-015テールフラグ該当（準該当含む）: {len(flagged)}/16 "
          f"({[c['code'] for c in flagged]})")
    axC_flag = sum(1 for c in axC if c["flags"])
    p2 = hypergeom_p_all_in(16, len(flagged), 4)
    print(f"軸C該当率: {axC_flag}/4（うち3856は結論不表明の準該当）。"
          f"軸C 4件が全てフラグ該当となる無作為確率: {p2:.4f}")
    print("注意: 2つのp値は独立でなく、カテゴリ定義に事後的裁量を含む。"
          "『統計的証明』ではなく系統性の記述的補助として扱うこと。")

    # ------------------------------------------------------------------
    sec("§5 コスト影響（第4条。単価はD-022実測 314,200トークン/候補・下限値）")
    # ------------------------------------------------------------------
    cost_axC = len(axC) * TOKENS_PER_CANDIDATE
    cost_flagged = len(flagged) * TOKENS_PER_CANDIDATE
    cost_total = 16 * TOKENS_PER_CANDIDATE
    print(f"2週間の全16候補の下流コスト: {cost_total:,} トークン")
    print(f"軸C由来4件（基準1が定義上ほぼ到達不能な候補）: {cost_axC:,} トークン "
          f"({cost_axC/cost_total:.0%})")
    print(f"テールフラグ該当8件: {cost_flagged:,} トークン ({cost_flagged/cost_total:.0%})")

    # ------------------------------------------------------------------
    sec("§6 再設計案(a) 軸D複合フィルタの弁別力（PBR<=0.34の6件でのバックチェック）")
    # ------------------------------------------------------------------
    print("フィルタ候補ごとに、構造的欠陥6件のうち何件を事前に除外できたか"
          "（5491=前回レビューで『最もBUYに近かった』1件は残したい）:")
    def apply(f, label):
        excl, kept, unknown = [], [], []
        for c in low_pbr:
            v = f(c)
            (unknown if v is None else (kept if v else excl)).append(c["code"])
        print(f"  {label}: 除外={excl} 通過={kept} 判定不能={unknown}")
        return excl, kept, unknown
    apply(lambda c: c["recent_profit"], "直近本決算が最終黒字")
    apply(lambda c: (None if c["equity_ratio"] is None else c["equity_ratio"] >= 40),
          "自己資本比率>=40%")
    apply(lambda c: (None if c["equity_ratio"] is None else c["equity_ratio"] >= 30),
          "自己資本比率>=30%")
    apply(lambda c: c["dividend"], "配当（実績or予想）あり")
    print("-> 『直近黒字』が単独で最も弁別的: 6件中5件を除外し（3856は確定決算不存在で"
          "判定不能=除外扱い）、通過は5491のみ。自己資本比率は単独では弁別力が弱い"
          "（6619=78.5%・7138=72.3%が通過してしまう。希薄化調達で比率が嵩上げされるため）")

    # ------------------------------------------------------------------
    sec("§7 再設計案(b) 開示紐付けの実地検証（2026-07-24実測の記録値）")
    # ------------------------------------------------------------------
    # 記録値（本スクリプト作成時にFable5が実測。--live で再実測可能）
    # EDINET: corp/tools/edinet_fetch.py list_documents_by_date() 使用（APIキー恒久登録済み）
    EDINET_MEASURED = {
        "2026-07-16": dict(total=162, with_sec=45, uniq=39),
        "2026-07-17": dict(total=396, with_sec=69, uniq=55),
    }
    # 2026-07-17金曜スナップショットの軸Cランキング個別株（ETF/ETN除外後）
    AXIS_C_STOCKS_0717 = ["5216", "7359", "3185", "2354", "7640"]
    EDINET_CAPTURE = []          # 実測: 両日とも交差0件
    TDNET_MEASURED = {
        "2026-07-16": dict(uniq=131, captured=["7359", "7640"]),
        "2026-07-17": dict(uniq=238, captured=["3185"]),
    }
    print("EDINET書類一覧API（取得日時2026-07-24T17:30Z、"
          "https://api.edinet-fsa.go.jp/api/v2/documents.json）:")
    for d, v in EDINET_MEASURED.items():
        print(f"  {d}: 全{v['total']}件、上場銘柄コード付き{v['with_sec']}件"
              f"（ユニーク{v['uniq']}銘柄）")
    print(f"  軸C個別株{AXIS_C_STOCKS_0717}との交差: {EDINET_CAPTURE} = 0/5"
          f"（当日・前営業日とも）")
    print("TDnet日次一覧（取得日時2026-07-24、curl UA指定、"
          "https://www.release.tdnet.info/inbs/I_list_NNN_YYYYMMDD.html、HTTP 200）:")
    td_captured = set()
    for d, v in TDNET_MEASURED.items():
        print(f"  {d}: ユニーク{v['uniq']}銘柄、軸C個別株の捕捉: {v['captured']}")
        td_captured.update(v["captured"])
    print(f"  当日∪前営業日のTDnet捕捉率: {len(td_captured)}/5 = {sorted(td_captured)}")
    print("  含意: (i) EDINETのみのハード紐付けは実測で供給ゼロ→不採用。"
          "(ii) TDnet紐付けは7359の実カタリスト（07/16 16:00開示）を正しく捕捉。"
          "(iii) 5216の実材料（会社プレス/フィスコ配信）はTDnetにも無い"
          "→紐付けの捕捉率は100%にならない（ソフト運用+フォールバックが必要）")

    # ------------------------------------------------------------------
    sec("§8 候補供給量（D-007: 5〜10件/週）への影響試算")
    # ------------------------------------------------------------------
    print("現行容量: 5軸×各2 = 10件/週（2026-07-18に実達成）")
    print("軸D複合フィルタ: 2週間でランキング上位から浮上した候補のうち"
          "フィルタ通過は5491のみ（1/4採用分）。ランキングをPBR昇順に深く辿る"
          "追加取得（+2〜5ページ/週、LLMコスト比で無視可能）で2枠充足を図るが、"
          "通過率は未実測。充足不能週は現行D-008の『軸不足の明記』で運用")
    print("軸C∩TDnet: 07-17実測で3/5捕捉 → 2枠は概ね充足見込みだが空集合週はあり得る"
          "→フォールバック（現行定義+紐付け無しの明記）で容量維持")
    print("最悪ケース試算: D=1件+C=フォールバック2件 → 週9件。D-007帯(5-10)内、"
          "D-022帯上限目標(8-10)も維持可能")

    # ------------------------------------------------------------------
    sec("§9 イベント駆動メモからの追加事実（市場反応速度の実測）")
    # ------------------------------------------------------------------
    # 5216: 材料発表(07/17 12:42-12:55)→当日中に出来高117.66倍・高値+30.57%→
    #        6営業日後に材料発表前水準へ全戻り
    pre, now, high = 157, 158, 205
    rt = (now - pre) / pre * 100
    dd = (high - now) / high * 100
    print(f"5216（軸C・材料特定成功例）: 材料発表前157円 → 6営業日後158円 = "
          f"+{rt:.2f}%（全戻り）、高値205円比 -{dd:.2f}% "
          f"[outputs/judgement/5216-20260723-event.md]")
    print("  -> 週次バッチ（土曜、材料から1営業日以上経過）が拾える時点で超過リターンは"
          "既に消失し始めており、6営業日で実質ゼロ")
    print("5491（07-21イベント）: 出来高2.45倍のトリガー成立日にEDINET/TDnet/株探/"
          "Yahoo!の4系統で開示ゼロ [outputs/judgement/5491-20260721-event.md]")
    print("  -> 『出来高急増=開示イベントの代理指標』（D-012帰結2）の対応は弱い。"
          "急増は開示なしでも頻発する")
    print("5242（07-21イベント）: 累計+56.95%の急騰も2度の調査で材料特定できず"
          "（軸A由来だが同型） [outputs/judgement/5242-20260721-event.md]")

    # ------------------------------------------------------------------
    sec("§10 総括値（レビュー本文の要旨に対応）")
    # ------------------------------------------------------------------
    print(f"- 軸C→基準1不成立: 4/4（軸A含め6/6）、不成立率の片側95%下限 "
          f"{clopper_pearson_lower_all_success(4):.2f}（n=4）/ "
          f"{clopper_pearson_lower_all_success(6):.2f}（n=6）")
    print(f"- 低PBR帯(<=0.34)→構造的欠陥型の基準2棄却: 6/6、片側95%下限 "
          f"{clopper_pearson_lower_all_success(6):.2f}")
    print(f"- 軸C→テールフラグ該当: 4/4（準該当1含む）")
    print(f"- 参考p値（無作為抽出帰無仮説・正確片側）: 軸D×欠陥型 {p1:.3f} / "
          f"軸C×フラグ {p2:.3f}")
    print(f"- 定義上不整合な候補への2週間の下流コスト: 軸C分 {cost_axC:,} トークン")
    print("- いずれもn=4〜6の小標本であり『証明』ではない。系統性の方向は前回レビュー"
          "（2026-07-13、週3データ取得前）の仮説と一致（部分的な事前登録性あり）")


def live_check():
    """--live: EDINET/TDnetの実地チェックを再実行する（ネットワーク必要・非決定論的）。
    §7の記録値の再現用。標準ライブラリ+corp/tools/edinet_fetch.pyのみ使用。"""
    import re
    import urllib.request
    sys.path.insert(0, "corp/tools")
    import edinet_fetch as ef
    axis_c = ["5216", "7359", "3185", "2354", "7640"]
    for date in ("2026-07-16", "2026-07-17"):
        resp = ef.list_documents_by_date(date)
        results = resp.get("results") or []
        codes = {(r.get("secCode") or "").strip()[:4]
                 for r in results if (r.get("secCode") or "").strip()}
        print(f"EDINET {date}: 全{len(results)}件 ユニーク{len(codes)}銘柄 "
              f"軸C交差={[c for c in axis_c if c in codes]} "
              f"(取得日時 {resp['_fetched_at']})")
    for d in ("20260716", "20260717"):
        codes = set()
        for p in range(1, 9):
            url = f"https://www.release.tdnet.info/inbs/I_list_{p:03d}_{d}.html"
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    html = r.read().decode("utf-8", errors="replace")
            except Exception as e:
                print(f"TDnet {url}: {e}")
                break
            if len(html) < 3000:
                break
            codes.update(c[:4] for c in re.findall(r">(\d{4}[0-9A-Z])</td", html))
        print(f"TDnet {d}: ユニーク{len(codes)}銘柄 "
              f"軸C捕捉={[c for c in axis_c if c in codes]}")


if __name__ == "__main__":
    main()
    if "--live" in sys.argv:
        print()
        print("#" * 72)
        print("# --live 再実測（非決定論的・ネットワーク必要）")
        print("#" * 72)
        live_check()
