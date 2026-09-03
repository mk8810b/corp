#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""603A 20260902 イベント駆動 判断メモ（起案 JDG-S110）の全数値の再計算スクリプト。

憲法第2章-5（数値の再計算は必ずPythonで行う）・絶対制約第2条（出典と取得日時）に基づく。
価格系列の出典・取得日時は PRICE_SOURCE に記載。財務数値の出典は各ブロックのコメントに記載。

実行: python3 outputs/judgement/603A-20260902-event-draft-calc.py
"""
import math
import statistics

PRICE_SOURCE = {
    "url": "https://kabutan.jp/stock/kabuka?code=603A&ashi=day&page=1",
    "fetched_utc": ["2026-09-02T06:39:21Z", "2026-09-02T06:42:36Z"],
    "parser": "corp/tools/tdnet_scan.py::_parse_kabuka_history "
              "(sha256 1a2f4f5b731ca2fb06ea3cff8a9ec96e2bf15e529dc7b5fc238745733d9b6c35, 改変なし)",
    "crosscheck": "https://www.nikkei.com/nkd/company/history/dprice/?scode=603A&ba=1 "
                  "(取得 2026-09-02T06:42:36Z、08-25〜09-01の6営業日で終値・売買高が完全一致)",
    "note": "2026-09-02 の行（終値999円）は取得時刻が大引け(15:30 JST)+9〜+12分であり "
            "INC-002/INC-005 の未収束帯の内側。2ラウンドで出来高が 1,337,400→1,348,600 と "
            "変化したことを実測。よって判定基準日は 2026-09-01（確定終値）とする。",
}

# 日付降順（上場初日 2026-07-29 は前日比欄が「－」のため正本パーサが自動除外する仕様）
ROWS = [
    ("26/09/02",  999.0, 1348600),   # 未確定（参考。以下の算出には一切使用しない）
    ("26/09/01", 1090.0, 3544200),   # 判定基準日
    ("26/08/31", 1011.0, 3502700),
    ("26/08/28", 1038.0, 1376200),
    ("26/08/27",  888.0,  578500),
    ("26/08/26",  850.0,  478900),
    ("26/08/25",  869.0,  284700),
    ("26/08/24",  850.0,  518000),
    ("26/08/21",  876.0,  966900),
    ("26/08/20",  785.0,  413700),
    ("26/08/19",  760.0,  492800),
    ("26/08/18",  786.0,  559800),
    ("26/08/17",  817.0, 1072700),
    ("26/08/14",  851.0,  731000),
    ("26/08/13",  860.0,  661200),
    ("26/08/12",  886.0,  832500),
    ("26/08/10",  848.0, 1030200),
    ("26/08/07",  799.0, 1109100),
    ("26/08/06",  753.0,  384400),
    ("26/08/05",  765.0,  593100),
    ("26/08/04",  728.0,  756700),
    ("26/08/03",  728.0, 1622600),
    ("26/07/31",  700.0, 1582200),
    ("26/07/30",  796.0, 3035200),
]

ceil_tick = lambda x, t=1: math.ceil(round(x / t, 9)) * t


def p(label, value):
    print(f"{label:<58} {value}")


print("=" * 78)
print("A. 価格・出来高（判定基準日 2026-09-01・確定終値ベース）")
print("=" * 78)
series = ROWS[1:]                      # 09-02（未確定）を除外
assert series[0][0] == "26/09/01"
win = series[:20]                      # 判定基準日を含む直近20営業日（真の20営業日窓）
p("取得できた営業日数（上場初日を除く）", len(ROWS))
p("窓に採用した営業日数", len(win))
p("窓の期間", f"{win[-1][0]} 〜 {win[0][0]}")

close = win[0][1]
vol = win[0][2]
prev_close = win[1][1]
p("判定基準日 確定終値", f"{close:,.0f} 円")
p("前日(08-31)終値", f"{prev_close:,.0f} 円")
p("前日比", f"{(close / prev_close - 1) * 100:+.4f} %")
p("判定基準日 確定出来高", f"{vol:,} 株")

avg_vol_incl = statistics.mean(r[2] for r in win)
avg_vol_excl = statistics.mean(r[2] for r in series[1:21])
p("20日平均出来高（基準日を含む窓・check_floor()と同一）", f"{avg_vol_incl:,.1f} 株")
p("20日平均出来高（基準日を除く窓）", f"{avg_vol_excl:,.1f} 株")
p("出来高倍率（含む窓）", f"{vol / avg_vol_incl:.4f} 倍")
p("出来高倍率（除く窓）", f"{vol / avg_vol_excl:.4f} 倍")
p("D-018「出来高を伴う」1.5倍閾値（含む窓）", f"{math.ceil(avg_vol_incl * 1.5):,} 株")

closes_asc = [r[1] for r in reversed(win)]
rets = [math.log(closes_asc[i + 1] / closes_asc[i]) for i in range(len(closes_asc) - 1)]
sig_p = statistics.pstdev(rets) * 100
sig_s = statistics.stdev(rets) * 100
p("σ20 母標準偏差（pstdev, 19リターン）", f"{sig_p:.4f} % / 年率 {sig_p * math.sqrt(252):.2f} %")
p("σ20 標本標準偏差（stdev, 19リターン）", f"{sig_s:.4f} % / 年率 {sig_s * math.sqrt(252):.2f} %")

for name, sig in (("母標準偏差", sig_p), ("標本標準偏差", sig_s)):
    two = close * 0.02
    syen = close * sig / 100
    gate = ceil_tick(max(two, syen, 1.0))
    p(f"D-018ゲート（{name}）2%成分/σ成分/1ティック",
      f"{two:.4f} / {syen:.4f} / 1 → ゲート {gate:.0f} 円")
    p(f"　上抜け閾値（{name}）", f"{close + gate:,.0f} 円")
    p(f"　下抜け閾値（{name}）", f"{close - gate:,.0f} 円")

high_row = max(win, key=lambda r: r[1])
high = high_row[1]
p("基準高値（窓内の最高確定終値）", f"{high:,.0f} 円（{high_row[0]}）")
lo = ceil_tick(high * 0.85)            # 内側丸め: 15%超は帯外なので切り上げ
hi = math.floor(high * 0.95)           # 5%未満は帯外なので切り捨て
p("押し目帯（D-018 5〜15%・内側丸め）", f"{lo:,.0f} 円 〜 {hi:,.0f} 円")
for x in (lo - 1, lo, hi, hi + 1):
    d = (1 - x / high) * 100
    p(f"　検算 {x}円の下落率", f"{d:.3f} % → 帯内={5 <= d <= 15}")

print()
print("=" * 78)
print("B. 既存トリガー（2026-08-21基準・固定値）の機械照合")
print("=" * 78)
T1_PRICE, T1_VOL = 926, 1_485_385
T2_T8_PRICE = 826
T3_LO, T3_HI, T3_VOL = 754, 841, 990_256
for d, c, v in series[:6][::-1]:
    t1 = (c >= T1_PRICE) and (v >= T1_VOL)
    t2 = c <= T2_T8_PRICE
    t3 = (T3_LO <= c <= T3_HI) and (v <= T3_VOL)
    print(f"  {d} 終値{c:>7,.0f} 出来高{v:>10,}  T1={t1}  T2={t2}  T3={t3}")

print()
print("=" * 78)
print("C. 財務制限条項（2026-08-28開示原本 特約①②）の閾値と余裕度")
print("   出典: https://www.release.tdnet.info/inbs/140120260827527295.pdf")
print("        （sha256 b02fc23b…c4d4、RSH-S94 が取得日時 2026-08-31T07:05Z で取得）")
print("   実績: 2026年6月期決算短信 https://www.release.tdnet.info/inbs/140120260813519826.pdf")
print("   FY2023末純資産: 有価証券届出書 EDINET docID S100YL2O")
print("=" * 78)
na_fy2026 = 8_532_088      # 千円 FY2026.6期末 純資産合計
na_fy2023 = 4_617_810      # 千円 FY2023.6期末 純資産（条文が指名する基準）
ta_fy2026 = 44_294_103     # 千円 FY2026.6期末 総資産
base = max(na_fy2026, na_fy2023)
thr1 = base * 0.75
p("特約①の基準額 max(直前期末, FY2023末)", f"{base:,} 千円（= FY2026末）")
p("特約①の閾値（基準額×75%）", f"{thr1:,.0f} 千円")
p("直近実績（FY2026末純資産）との余裕額", f"{na_fy2026 - thr1:,.0f} 千円")
p("閾値／直近純資産", f"{thr1 / na_fy2026 * 100:.2f} %（＝条文の構造上 75.00% になる）")

ipo = 1_904_887            # 千円 一般募集 払込金額の総額（払込期日 2026-07-28・到来済み）
oa = 1_119_980             # 千円 第三者割当 割当価格の総額（払込期日 2026-08-26・完了は取得不能）
ni_fy2027 = 2_140_000      # 千円 FY2027 会社予想 当期純利益
for label, add in (("A' IPO払込済＋第三者割当払込あり＋会社予想達成", ipo + oa + ni_fy2027),
                   ("B' IPO払込済＋第三者割当払込なし＋会社予想達成", ipo + ni_fy2027),
                   ("C' IPO払込済のみ・FY2027損益ゼロ", ipo)):
    na = na_fy2026 + add
    p(f"{label} → FY2027末純資産", f"{na:,.0f} 千円 / 閾値比 {na / thr1 * 100:.1f}% / 余裕 {na - thr1:,.0f} 千円")
# 抵触に必要な損失（会社予想の純利益ではなく「純損失」を置く形で明示的に計算する）
for label, capital in (("A'（IPO+第三者割当の払込を織り込む）", ipo + oa),
                       ("B'（IPO払込のみを織り込む）", ipo)):
    need = na_fy2026 + capital - thr1
    p(f"特約①抵触に必要なFY2027純損失 {label}", f"{need:,.0f} 千円（約{need / 100_000:.1f}億円）")
    p("　FY2026実績（純利益+1,940,242千円）との振れ幅", f"{need + 1_940_242:,.0f} 千円")

op_fy2026 = 3_581_651      # 千円 FY2026 営業利益
ord_fy2026 = 2_867_614     # 千円 FY2026 経常利益
sales_fy2026 = 25_699_624  # 千円 FY2026 売上高
ord_fy2027e = 3_080_000    # 千円 FY2027 会社予想 経常利益
nonop = op_fy2026 - ord_fy2026
p("特約②の閾値", "経常損益 0円（経常損失を計上しないこと）")
p("直近実績 経常利益", f"{ord_fy2026:,} 千円（売上高経常利益率 {ord_fy2026 / sales_fy2026 * 100:.2f}%）")
p("FY2027会社予想 経常利益", f"{ord_fy2027e:,} 千円 → 抵触には予想比 -100.00% の悪化が必要")
p("営業外損益（純額、FY2026）", f"△{nonop:,} 千円")
p("営業利益がここまで下がると経常損失（営業外損益不変の仮定）",
  f"{nonop:,} 千円（FY2026営業利益比 {nonop / op_fy2026 * 100 - 100:+.2f}%）")

print()
print("=" * 78)
print("D. 借入の規模（同上原本。既存100百万円を返済し新規2,000百万円を実行）")
print("=" * 78)
repay, draw, line = 100_000, 2_000_000, 3_000_000   # 千円
debt_fy2026 = 400_000 + 1_792_619 + 16_570_965      # 千円 借入金（短期＋1年内＋長期）
net = draw - repay
p("借入残高の純増", f"{net:,} 千円")
p("FY2026末 借入金残高", f"{debt_fy2026:,} 千円")
p("純増率（対借入金残高）", f"{net / debt_fy2026 * 100:+.2f} %")
p("純増額の総資産比", f"{net / ta_fy2026 * 100:.2f} %")
p("コミットメントライン総額／引出後残枠／利用率",
  f"{line:,} 千円 / {line - draw:,} 千円 / {draw / line * 100:.1f} %")
p("純増額 ÷ 第三者割当の割当価格総額", f"{net / oa:.4f} 倍")
p("純増額 ÷ FY2026末純資産", f"{net / na_fy2026 * 100:.2f} %")
p("希薄化の有無", "なし（金銭消費貸借であり株式・新株予約権の発行を伴わない）")

print()
print("=" * 78)
print("E. バリュエーション（判定基準日終値1,090円）")
print("=" * 78)
sh_pre, sh_post = 34_799_000, 36_380_000
eps_fy2027_disclosed = 61.88   # 円 会社開示（第三者割当の希薄化を織り込まない）
for name, sh in (("増資前 34,799,000株", sh_pre), ("増資後 36,380,000株", sh_post)):
    bps = na_fy2026 / sh * 1000
    p(f"BPS（FY2026末純資産ベース・{name}）", f"{bps:.2f} 円 → PBR {close / bps:.2f} 倍")
    p(f"時価総額（{name}）", f"{close * sh / 1e8:.1f} 億円")
bps_pro = (na_fy2026 + ipo + oa) / sh_post * 1000
p("BPS（IPO・第三者割当の払込を織り込むプロフォーマ）", f"{bps_pro:.2f} 円 → PBR {close / bps_pro:.2f} 倍")
p("PER（会社開示EPS 61.88円）", f"{close / eps_fy2027_disclosed:.2f} 倍")
eps_dil = 2_140_000_000 / 35_938_523    # 加重平均（JDG-O86 6-3節の算定を再現）
p("PER（希薄化考慮の加重平均EPS 59.55円）", f"{close / eps_dil:.2f} 倍")
p("2026-08-21（前回判定基準日876円）比", f"{(close / 876 - 1) * 100:+.2f} %")
p("第三者割当の割当価格708.40円 に対する株価", f"{close / 708.40 * 100:.2f} %")

print()
print("=" * 78)
print("F. サイジング参考（D-002/D-011/D-013/D-019。BUY提案は存在しない）")
print("=" * 78)
cash = 3_000_000          # 円 corp/cash.md 2026-07-09申告のデフォルト値（HELD 0件）
unit = close * 100
p("1単元(100株)購入額", f"{unit:,.0f} 円")
p("資金残高（corp/cash.md 3,000,000円・HELD 0件）比", f"{unit / cash * 100:.4f} %")
p("D-019 2%目標 / 3%上限", f"{cash * 0.02:,.0f} 円 / {cash * 0.03:,.0f} 円")
p("D-019判定", "1単元が3%上限を超過 → 「実弾見送り（シャドー追跡のみ）」に該当"
  if unit > cash * 0.03 else "3%上限の内側")
p("D-013 株価上限3,000円との関係", f"終値1,090円は上限まで {3000 / close * 100 - 100:.1f}% の余裕")
for label, e in (("基準終値", close),):
    p(f"参考バリア（{label} {e:,.0f}円）", f"損切り -10% = {ceil_tick(e * 0.90):,.0f}円 / 利確 +25% = {ceil_tick(e * 1.25):,.0f}円")

print()
print("=" * 78)
print("G. 同業比較（判定基準日 2026-09-01 の確定終値に揃えた PER/PBR）")
print("   出典: kabutan 個別ページ https://kabutan.jp/stock/?code=<コード>（取得 2026-09-02T06:46Z、")
print("        表示は 2026-09-02 場中値ベース）と日足ページの 2026-09-01 確定終値。")
print("   BPS・EPSは基準日間で不変であるため、PBR/PERを 終値(09-01)/場中値(09-02) で機械的に")
print("   スケールして基準日を揃えた（近似ではなく定義どおりの換算）。")
print("=" * 78)
PEERS = [
    # コード, 銘柄, kabutan PER(09-02場中), PBR(09-02場中), 09-02場中終値, 09-01確定終値
    ("603A", "アイ・グリッド・ソリューションズ", 17.0, 4.26, 999.0, 1090.0),
    ("9517", "イーレックス",                  12.2, 0.93, 845.0,  880.0),
    ("9519", "レノバ",                        23.1, 0.59, 870.0,  924.0),
    ("350A", "デジタルグリッド",              16.8, 3.12, 770.0,  797.0),
    ("9514", "エフオン",                      5.6,  0.37, 344.0,  349.0),
]
print(f"{'コード':<6}{'銘柄':<22}{'PER(09-01)':>12}{'PBR(09-01)':>12}")
adj = []
for code, name, per, pbr, now, base in PEERS:
    k = base / now
    adj.append((code, name, per * k, pbr * k))
    print(f"{code:<6}{name:<22}{per * k:>12.2f}{pbr * k:>12.2f}")
pbr_rank = sorted(adj, key=lambda x: -x[3])
per_rank = sorted(adj, key=lambda x: -x[2])
print("PBR 降順:", " > ".join(f"{c}{v:.2f}" for c, n, _, v in pbr_rank))
print("PER 降順:", " > ".join(f"{c}{v:.2f}" for c, n, v, _ in per_rank))
print("→ 603AのPBRは5社中1位（最も高い）、PERは5社中2位（高い方から）")

print()
print("=" * 78)
print("H. (β)＝FY2027営業利益率の内部矛盾（JDG-O86 6-2節）の材料性の尺度")
print("=" * 78)
sales27, op27 = 30_966_000, 3_844_000    # 千円 FY2027会社予想（決算短信原本）
m26 = op_fy2026 / sales_fy2026
m27 = op27 / sales27
p("FY2026実績 営業利益率", f"{m26 * 100:.2f} %")
p("FY2027会社予想 営業利益率", f"{m27 * 100:.2f} %（{(m27 - m26) * 100:+.2f} pt）")
op27_at_m26 = sales27 * m26
p("FY2027売上予想 × FY2026営業利益率", f"{op27_at_m26:,.0f} 千円")
gap = op27_at_m26 - op27
p("会社予想営業利益との差（＝(β)が答える量）", f"{gap:,.0f} 千円")
p("　会社予想営業利益に対する比率", f"{gap / op27 * 100:+.2f} %")
p("　時価総額（1,090円×36,380,000株）に対する実額比", f"{gap / (close * sh_post / 1000) * 100:.2f} %")
p("　PER一定なら株価インパクトの目安", f"約 {gap / op27 * 100:.1f} %（利益比例）")
