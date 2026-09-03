# -*- coding: utf-8 -*-
"""JDG-O80 校閲・独立再計算スクリプト（6444 サンデン、判定基準日 2026-08-18）
入力: kabutan日足キャッシュ（scratchpad/6444/kabutan_day_p{1,2}.html、取得2026-08-18T23:16:20Z）
      有価証券報告書 S100XUJB（EDINET、取得2026-08-18T23:14:36Z）
      決算短信 140120260804508780.pdf（TDnet、取得2026-08-18T23:10:03Z）
      TDnet 第三者割当 140120260807513057.pdf（取得2026-08-18T23:10:47Z）

実行方法: 上記キャッシュを置いたディレクトリをカレントディレクトリとして実行する
      （相対パス 6444/kabutan_day_p{1,2}.html を参照）。実行結果の全文は
      outputs/judgement/6444-20260819-scan.md 22節に添付済み。
バッジ: JDG-O80（校閲）／対象メモ: outputs/judgement/6444-20260819-scan.md
"""
import re, math, statistics, json

# ---------- 1. 株価系列の再取得（HTMLキャッシュから独立にパース） ----------
rows = {}
for f in ['6444/kabutan_day_p1.html', '6444/kabutan_day_p2.html']:
    s = open(f, encoding='utf-8', errors='replace').read()
    for p in s.split('<tr>'):
        m = re.search(r'<th scope="row"><time datetime="(20\d\d-\d\d-\d\d)">', p)
        if not m: continue
        tds = [re.sub('<[^>]+>', '', t).strip().replace(',', '')
               for t in re.findall(r'<td[^>]*>(.*?)</td>', p, re.S)]
        if len(tds) == 7:
            rows.setdefault(m.group(1), tds)
ds = sorted(rows)
close = {d: float(rows[d][3]) for d in ds}
vol   = {d: float(rows[d][6]) for d in ds}
high  = {d: float(rows[d][1]) for d in ds}

print("=== 0. 系列の健全性 ===")
print("取得営業日数:", len(ds), "／期間:", ds[0], "〜", ds[-1])
print("判定基準日 2026-08-18: 終値", close['2026-08-18'], "／出来高", int(vol['2026-08-18']),
      "／高値", high['2026-08-18'])

BASE = '2026-08-18'
i_base = ds.index(BASE)
winA = ds[i_base-19:i_base+1]           # 判定日を含む20営業日
winB = ds[i_base-20:i_base]             # 判定日を含まない20営業日
print("窓A:", winA[0], "〜", winA[-1], "(n=%d)" % len(winA))
print("窓B:", winB[0], "〜", winB[-1], "(n=%d)" % len(winB))

# ---------- 2. σ20（4通り: 窓A/B × 母/標本、対数リターン）＋ 単純リターン版 ----------
def sigmas(win):
    c = [close[d] for d in win]
    log_r = [math.log(c[i+1]/c[i]) for i in range(len(c)-1)]
    sim_r = [c[i+1]/c[i]-1 for i in range(len(c)-1)]
    return dict(log_p=statistics.pstdev(log_r), log_s=statistics.stdev(log_r),
                sim_p=statistics.pstdev(sim_r), sim_s=statistics.stdev(sim_r), n=len(log_r))

sA, sB = sigmas(winA), sigmas(winB)
print("\n=== 1. σ20（日次）%表示 / 年率(×√252) ===")
for lbl, s in [("窓A", sA), ("窓B", sB)]:
    for k in ['log_p','log_s','sim_p','sim_s']:
        print(f"  {lbl} {k}: {s[k]*100:.4f}%  年率 {s[k]*math.sqrt(252)*100:.2f}%  (n={s['n']})")

# ---------- 3. D-018 上抜け/下抜けゲート ----------
C = close[BASE]; TICK = 1.0
print("\n=== 2. D-018 ゲート（基準 %.1f円、呼び値1ティック=%.1f円） ===" % (C, TICK))
ups, dns = set(), set()
for lbl, s in [("窓A", sA), ("窓B", sB)]:
    for k in ['log_p','log_s','sim_p','sim_s']:
        two = C*0.02; sig = C*s[k]; gate = max(two, sig, TICK)
        up = math.ceil(C+gate); dn = math.floor(C-gate)
        ups.add(up); dns.add(dn)
        print(f"  {lbl} {k}: 2%={two:.4f} σ20成分={sig:.4f} → gate={gate:.4f} 上抜け>={up} 下抜け<={dn}")
print("  上抜け閾値の集合:", sorted(ups), "／下抜け閾値の集合:", sorted(dns))
print("  → 推定量・窓の選択に依存するか:", "しない" if len(ups)==1 and len(dns)==1 else "する")
print("  基準日終値202円は 上抜け閾値/下抜け閾値のいずれも未充足か:",
      C < min(ups) and C > max(dns))

# ---------- 4. 出来高 20日平均・1.5倍水準 ----------
avgA = sum(vol[d] for d in winA)/len(winA)
avgB = sum(vol[d] for d in winB)/len(winB)
print("\n=== 3. 出来高 ===")
print(f"  窓A 20日平均 {avgA:,.1f}株 → 1.5倍 {math.ceil(avgA*1.5):,}株 ／当日倍率 {vol[BASE]/avgA:.4f}")
print(f"  窓B 20日平均 {avgB:,.1f}株 → 1.5倍 {math.ceil(avgB*1.5):,}株 ／当日倍率 {vol[BASE]/avgB:.4f}")

# ---------- 5. D-018×D-013 衝突チェック ----------
print("\n=== 4. D-018×D-013 衝突チェック ===")
print("  上抜け閾値 %d 円 > D-013上限3,000円 ?" % max(ups), max(ups) > 3000)
print("  下抜け閾値 %d 円 < D-009下限100円 ?" % min(dns), min(dns) < 100)

# ---------- 6. 押し目帯（D-018）: 基準高値=年初来高値211円（2026-08-18、kabutan） ----------
REF_HIGH = 211.0
lo, hi = REF_HIGH*0.85, REF_HIGH*0.95
print("\n=== 5. 押し目帯（基準高値 %.0f円＝年初来高値・52週高値、2026-08-18） ===" % REF_HIGH)
print(f"  5〜15%下落帯: 終値 {lo:.2f}円 〜 {hi:.2f}円 → 整数終値 {math.ceil(lo)}〜{math.floor(hi)}円")
print(f"  基準日終値202円の下落率: {(1-C/REF_HIGH)*100:.2f}%  → 帯内か: {lo<=C<=hi}")
print(f"  基準日出来高{int(vol[BASE]):,}株 ≦ 窓A平均{avgA:,.0f}株 か: {vol[BASE]<=avgA}")
print("  → 基準日時点で本条件は既充足ではない（INC-004型の既充足条件を回避）")

# ---------- 7. 開示後の株価反応（08-07終値を起点） ----------
print("\n=== 6. 08-07開示後の株価反応 ===")
base07 = close['2026-08-07']
for d in ['2026-08-10','2026-08-12','2026-08-13','2026-08-14','2026-08-17','2026-08-18']:
    print(f"  {d} 終値{close[d]:.0f}円 08-07終値比 {(close[d]/base07-1)*100:+.2f}% 出来高{int(vol[d]):,}株"
          f" (20日平均比 {vol[d]/avgA:.2f}倍)")
print(f"  08-07終値164円 → 08-18終値202円: {(C/base07-1)*100:+.2f}%（7営業日）")

# ---------- 8. 一過性売却益と通期予想 ----------
print("\n=== 7. 一過性売却益33億円と通期予想（単位: 百万円） ===")
gain = 3300
fc_sales, fc_op, fc_ord, fc_np = 200000, -1000, 2700, 500
h1_sales, h1_op, h1_ord, h1_np = 108512, -21, 1738, 1349
print(f"  33億円 ÷ 通期経常利益予想{fc_ord} = {gain/fc_ord*100:.1f}%  ※特別利益と経常利益の比較（規模指標）")
print(f"  33億円 ÷ 通期純利益予想{fc_np}  = {gain/fc_np*100:.1f}%")
for lbl,h,f in [("売上高",h1_sales,fc_sales),("営業損益",h1_op,fc_op),
                ("経常利益",h1_ord,fc_ord),("純利益",h1_np,fc_np)]:
    print(f"  H1進捗 {lbl}: {h}/{f} = {h/f*100:.1f}%")
h2 = dict(sales=fc_sales-h1_sales, op=fc_op-h1_op, ord=fc_ord-h1_ord, np=fc_np-h1_np)
print("  現行予想が含意するH2:", h2)
print("\n  --- 予想据置きが成立するために必要なH2追加損失（税効果別の感度）---")
for tax in [0.0, 0.20, 0.30, 0.40]:
    after = gain*(1-tax)
    landing = h1_np + h2['np'] + after
    need = landing - fc_np
    print(f"   実効税率{tax*100:>4.0f}%: 税引後寄与{after:8.1f} → 通期着地{landing:8.1f}"
          f"（予想{fc_np}の{landing/fc_np:.2f}倍）／予想維持に要する追加損失 {need:8.1f}")
print(f"  ※既存予想が既に織り込むH2純損失は {abs(h2['np'])} 百万円であり、"
      f"税引後売却益（{gain*0.7:.0f}〜{gain:.0f}）の{abs(h2['np'])/gain*100:.1f}〜{abs(h2['np'])/(gain*0.7)*100:.1f}%にすぎない")

# ---------- 9. 持分法投資利益の寄与 ----------
print("\n=== 8. 中間期 経常黒字転換の主因 ===")
eq = 2710; op = -21; ord_ = 1738; py_ord = -618
print(f"  H1経常利益{ord_} = 営業損益{op} + 営業外（持分法投資利益{eq}を含む）")
print(f"  持分法投資利益{eq} ÷ 経常利益{ord_} = {eq/ord_*100:.1f}%")
print(f"  持分法を除いた経常損益 ≒ {ord_-eq} 百万円（前年同期経常{py_ord}）")
print(f"  → 経常黒字{ord_}は持分法投資利益{eq}なしには成立しない（{ord_-eq}<0）")

# ---------- 10. 営業損益の期数（TDnet 08-07 第三者割当 10(1) 最近3年間の業績） ----------
print("\n=== 9. 営業損益の連続赤字期数（出典: TDnet 140120260807513057.pdf 10.(1)） ===")
op_hist = {"2023.12期": -11018, "2024.12期": -6446, "2025.12期": -1507, "2026.12期(会社予想)": -1000}
for k,v in op_hist.items(): print(f"  {k}: {v:,} 百万円")
print(f"  → 実績3期連続の営業赤字、会社予想どおりなら {len(op_hist)} 期連続")
print(f"  H1実績 営業損益 {h1_op} 百万円（前年同期 -1493 百万円）")

# ---------- 11. 支配株主の議決権比率 ----------
print("\n=== 10. 支配株主（海信日本オートモーティブエアコンシステムズ合同会社）の比率 ===")
held = 81_627_000
issued_2025 = 111_693_313
treasury_total = 120_518            # 有報(5)所有者別状況 注1: 自己株式120,518株
treasury_full_units = 120_500       # 有報(7)議決権の状況 完全議決権株式(自己株式等)
total_votes = 1_115_015             # 有報(7) 総株主の議決権
print(f"  (a) 所有株式数割合（自己株式120,518株控除）= {held}/{issued_2025-treasury_total}"
      f" = {held/(issued_2025-treasury_total)*100:.4f}%  ← 有報(6)大株主の状況の印字値 73.16% と一致")
print(f"  (b) 起案の分母（自己株式120,500株控除）    = {held/(issued_2025-treasury_full_units)*100:.4f}%")
print(f"  (c) 議決権比率 = {held//100}/{total_votes} = {(held//100)/total_votes*100:.4f}%"
      f"  ← 有報「関係会社の状況」の議決権所有割合(被所有・直接) 73.2% と一致")
alloc = 83_627_000
print(f"  (d) 2021-05-31第三者割当の引受株数 {alloc:,}株 / 当時の発行済{issued_2025:,}株"
      f" = {alloc/issued_2025*100:.2f}%（自己株式控除後 {alloc/(issued_2025-treasury_total)*100:.2f}%）"
      f" ← 有報CG節の「議決権の75％」と整合")
print(f"  (e) 引受{alloc:,}株 − 現保有{held:,}株 = {alloc-held:,}株 の純減")
print(f"      発行済株式総数は第96期〜第100期を通じ {issued_2025:,}株で不変（有報 提出会社の経営指標等）")
print(f"      → 75%→73.2%への低下は希薄化でも自己株式の扱いでもなく、支配株主自身の持株減少による")
print(f"  (f) 会社法309条2項の特別決議要件（議決権の2/3=66.667%）超過か: "
      f"{(held//100)/total_votes > 2/3}（余裕 {((held//100)/total_votes-2/3)*100:.2f}pt）")
issued_20260630 = 112_933_313; votes_20260630 = 1_127_423
print(f"  (g) 参考: 2026-06-30時点の発行済{issued_20260630:,}株・議決権総数{votes_20260630:,}個"
      f"（TDnet 08-07開示）。支配株主の保有株数が不変と仮定した場合の議決権比率 "
      f"{(held//100)/votes_20260630*100:.2f}%（※保有株数の2026-06-30時点の実数は取得不能）")
print(f"  (h) 流通株式比率の上限（100% − 所有株式数割合）= {100-held/(issued_2025-treasury_total)*100:.2f}%"
      " （役員・持株会・持合等を控除する前の上限値）")

# ---------- 12. バリュエーション ----------
print("\n=== 11. バリュエーション ===")
eps_fc, bps = 4.46, 275.79
print(f"  PER = 202/{eps_fc} = {C/eps_fc:.2f}倍")
print(f"  PBR = 202/{bps} = {C/bps:.4f}倍")
print(f"  ROE(通期予想ベース) = {eps_fc}/{bps} = {eps_fc/bps*100:.2f}%")
print(f"  検算 PBR = PER×ROE = {(C/eps_fc)*(eps_fc/bps):.4f}")
mcap = C*issued_20260630/1e6
print(f"  時価総額 = 202円 × {issued_20260630:,}株 = {mcap:,.0f} 百万円")
print(f"  純資産(2026-06末) 32,423 百万円／自己資本(BPS×株数) = {bps*issued_20260630/1e6:,.0f} 百万円")

# ---------- 13. 財務体質 ----------
print("\n=== 12. 財務体質 ===")
d99 = 65514+379+3952; d100 = 70927+492+6265; dh1 = 73811+465+3050
print(f"  有利子負債: 2024.12期末 {d99:,} / 2025.12期末 {d100:,} / 2026-06末 {dh1:,} 百万円")
print(f"  2025.12期末 総資産185,633 に対する有利子負債比率 {d100/185633*100:.1f}%")
print(f"  自己資本比率: 12.4% → 12.9% → 14.4% → 16.3%")
print(f"  売却代金80億円 ÷ 有利子負債(2026-06末){dh1:,} = {8000/dh1*100:.1f}%")

# ---------- 14. D-004/D-009/D-013/D-019/D-002 ----------
print("\n=== 13. 各種フロア照合 ===")
cash = 3_000_000; unit = C*100
print(f"  D-009/D-013: 100 <= {C:.0f} <= 3000 → {100<=C<=3000}")
print(f"  D-004: 20日平均出来高 {avgA:,.0f}株（窓A）/{avgB:,.0f}株（窓B）≥100,000株 → "
      f"{avgA>=1e5 and avgB>=1e5}")
val_A = sum(close[d]*vol[d] for d in winA)/len(winA)
print(f"       20日平均売買代金（窓A・終値×出来高の平均）= {val_A/1e8:.4f}億円 ≥1億円 → {val_A>=1e8}"
      "（『または』条件のため出来高基準の充足で足りる）")
print(f"  D-019: 1単元 {unit:,.0f}円 ／ 2%目標 {cash*0.02:,.0f}円 ／ 3%上限 {cash*0.03:,.0f}円"
      f" → 2%以内: {unit<=cash*0.02}（資金残高比 {unit/cash*100:.4f}%）")
print(f"  D-002参考: 損切り {C*0.9:.1f}円（-10%）／利確 {C*1.25:.1f}円（+25%）")
