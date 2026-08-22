# -*- coding: utf-8 -*-
"""JDG-O85 校閲: 7719 の独立再計算（憲法第2章-5）。データ出典は確定版メモ本文に記載。"""
import json, math, statistics

print("="*70); print("[1] 株価・出来高・σ20（kabutan日足、校閲が2026-08-22T01:20〜01:21Zに独立再取得）")
d=[(x[0], float(x[1][3]), float(x[1][6]), float(x[1][1]), float(x[1][2]), float(x[1][0]))
   for x in json.load(open('7719-20260822-weekly-series.json'))]   # date, close, vol, high, low, open
incl, excl = d[:20], d[1:21]
print("  含む窓:", incl[-1][0], "〜", incl[0][0], " / 除く窓:", excl[-1][0], "〜", excl[0][0])
v_i=statistics.mean(x[2] for x in incl); v_e=statistics.mean(x[2] for x in excl)
print("  20日平均出来高 含む窓=%.1f株 除く窓=%.1f株" % (v_i, v_e))
print("  08-21出来高1,886,000株 → 倍率 含む窓=%.4f倍 / 除く窓=%.4f倍" % (1886000/v_i, 1886000/v_e))
print("  20日平均売買代金(終値×出来高) 含む窓=%.4f億円 / 除く窓=%.4f億円"
      % (statistics.mean(x[1]*x[2] for x in incl)/1e8, statistics.mean(x[1]*x[2] for x in excl)/1e8))
def sig(win, log):
    c=[x[1] for x in win][::-1]
    r=[(math.log(c[i+1]/c[i]) if log else c[i+1]/c[i]-1) for i in range(len(c)-1)]
    return statistics.pstdev(r), statistics.stdev(r)
print("  σ20（8系列, n(リターン)=19）:")
sig_max=0
for wl,w in [("含む窓",incl),("除く窓",excl)]:
    for ll,lg in [("対数",True),("単純",False)]:
        p,s=sig(w,lg); sig_max=max(sig_max,p,s)
        print("    %s×%s収益率: pstdev=%.4f%%  stdev=%.4f%%" % (wl,ll,p*100,s*100))
print("  ※D-018条文は「日次終値変動率」＝単純収益率。主指標は 含む窓×単純×pstdev=%.4f%%" % (sig(incl,False)[0]*100))
print("  08-21 前日比: %.4f%%（435→467）" % ((467/435-1)*100))
print("  08-21 四本値: 始443 / 高515 / 安429 / 終467  → 終値は当日高値を %.2f%% 下回る"
      % ((1-467/515)*100))
print("  制限値幅（前日終値435円→±80円）上限=%d円 ＝ 08-21高値515円（ストップ高）" % (435+80))
w60=d[:60]; mx=max(w60,key=lambda x:x[1])
print("  直近60営業日の終値最高値: %s の %.0f円（判定基準日終値467円は %.2f%% 下）"
      % (mx[0], mx[1], (1-467/mx[1])*100))
print("  1Q短信開示(2026-07-15 16:00)翌営業日 07-16: 出来高2,209,900株・高値570円・終値513円")

print("="*70); print("[2] TOPIX対比（ベータ調整なし）")
tp,tc=4059.73,4067.29
sc=(467/435-1)*100; tcp=(tc/tp-1)*100
print("  7719 %.4f%% / TOPIX %.4f%% / 単純差 %.4fpt" % (sc,tcp,sc-tcp))

print("="*70); print("[3] 時価総額・単元")
sh=7177791; print("  467円 × %d株 = %d円 = %.4f億円" % (sh,467*sh,467*sh/1e8))
print("  1単元(100株) = %d円 / D-019 2%%目標=%d円 3%%上限=%d円 → 2%%枠の内側"
      % (46700, 3_000_000*0.02, 3_000_000*0.03))

print("="*70); print("[4] D-018 参考条文（PASSのため台帳へ転記しない）")
close=467.0; tick=1.0
for lbl,s in [("含む窓×単純pstdev(主)",sig(incl,False)[0]),("含む窓×対数pstdev",sig(incl,True)[0]),
              ("除く窓×単純pstdev",sig(excl,False)[0]),("含む窓×単純stdev",sig(incl,False)[1])]:
    two=close*0.02; sy=close*s; g=max(two,sy,tick)
    print("  %-22s 2%%成分=%.2f円 σ20成分=%.2f円 → 支配=%s ゲート=%.2f円 上抜け=%d円 下抜け=%d円"
          % (lbl,two,sy,"σ20" if sy>two else "2%",g,math.ceil(close+g),math.floor(close-g)))
print("  出来高1.5倍: 含む窓 %d株以上 / 除く窓 %d株以上"
      % (math.ceil(v_i*1.5), math.ceil(v_e*1.5)))
bh=mx[1]
print("  押し目帯（基準高値=60営業日終値高値 %.0f円）: %d円〜%d円（△15%%〜△5%%）"
      % (bh, math.ceil(bh*0.85), math.floor(bh*0.95)))
print("  → 判定基準日終値467円は既に帯の内側（△%.2f%%）" % ((1-467/bh)*100))
cap=3000
print("  D-018×D-013衝突: 上限3,000円まで %.4f%% の距離。上抜け閾値(最大)=%d円 < 3,000円 → 衝突なし"
      % ((cap-close)/cap*100, math.ceil(close+max(close*0.02, close*sig_max, tick))))
need=(cap-close)/close*100
print("  上限に到達するに必要なσ20 = %.2f%%（現実的にあり得ない）" % need)

print("="*70); print("[5] 基準3: 会社自身の期間計画を分母にした進捗率（JDG-O63の規約）")
q1=dict(sales=1227103, op=141162, ord=131749, ni=57825)          # 千円（1Q短信 P/L）
h1=dict(sales=2841000, op=207000, ord=226000, ni=159000)          # 千円（会社公表 第2四半期累計予想）
fy=dict(sales=5392000, op=336000, ord=352000, ni=235000)          # 千円（会社公表 通期予想）
jp=dict(sales="売上高",op="営業利益",ord="経常利益",ni="親会社株主帰属純利益")
print("  会社計画の上期構成比（上期予想÷通期予想、50%%が均等）:")
for k in q1: print("    %-12s %.2f%%  (%+.2fpt)" % (jp[k], h1[k]/fy[k]*100, h1[k]/fy[k]*100-50))
print("  Q1の対上期計画進捗率（線形50%%が基準）★正しい分母:")
for k in q1: print("    %-12s %.2f%%  (%+.2fpt)" % (jp[k], q1[k]/h1[k]*100, q1[k]/h1[k]*100-50))
print("  （参考）Q1の対通期進捗率（線形25%%。起案が用いた誤った分母）:")
for k in q1: print("    %-12s %.2f%%  (%+.2fpt)" % (jp[k], q1[k]/fy[k]*100, q1[k]/fy[k]*100-25))

print("="*70); print("[6] 経常利益→親会社帰属純利益の乖離の分解（1Q短信 連結P/L 原本、千円）")
o,eg,el,pre,tax,nib,nci,nip=131749,239,5991,125996,44225,81770,23944,57825
print("  原本の縦計（各段1千円以内の丸め差）:")
print("    経常%d +特利%d -特損%d = %d （原本の税引前 %d、差 %d）" % (o,eg,el,o+eg-el,pre,o+eg-el-pre))
print("    税引前%d -法人税等%d = %d （原本の税引後 %d、差 %d）" % (pre,tax,pre-tax,nib,pre-tax-nib))
print("    税引後%d -非支配%d = %d （原本の親会社帰属 %d、差 %d）" % (nib,nci,nib-nci,nip,nib-nci-nip))
gap=o-nip
print("  経常→親会社帰属の目減り: %d千円（経常の%.2f%%）。内訳:" % (gap, gap/o*100))
for lbl,val in [("特別損益ネット", el-eg), ("法人税等", tax), ("非支配株主持分", nci)]:
    print("    %-14s %8d千円  経常比 %.2fpt" % (lbl,val,val/o*100))
print("  実効税率 %.2f%% / 非支配株主持分の税引後利益に占める比率 %.2f%%" % (tax/pre*100, nci/nib*100))
print("  経常→親会社帰属の変換率: Q1実績 %.2f%% / 前年同期実績 %.2f%% / 会社の上期計画 %.2f%% / 会社の通期計画 %.2f%%"
      % (nip/o*100, 8267/16929*100, h1['ni']/h1['ord']*100, fy['ni']/fy['ord']*100))

print("="*70); print("[7] 前年同期比の非同一基準（連結範囲の拡大。1Q短信セグメント注記2）")
print("  前第1四半期はASTOM R&D社の株式取得日が2025-03-31であり、B/Sのみ連結・P/L未連結（原本明記）")
seg_prior=dict(shiken=124645, eng=18376, digi=0, other=5136, adj=-121575)
seg_cur  =dict(shiken=174449, eng=-9542, digi=118220, other=2100, adj=-144064)
print("  前年同期 営業利益 = %d（デジタル寄与 0）" % sum(seg_prior.values()))
print("  当  期 営業利益 = %d（うちデジタル %d = %.2f%%）"
      % (sum(seg_cur.values()), seg_cur['digi'], seg_cur['digi']/sum(seg_cur.values())*100))
lo=seg_cur['shiken']+seg_cur['eng']+seg_cur['other']+seg_cur['adj']
hi=seg_cur['shiken']+seg_cur['eng']+seg_cur['other']+seg_prior['adj']
print("  デジタル事業を除いた当期営業利益の幅（調整額の帰属が原本から不明のため上下限）:")
print("    調整額増分を全額デジタル以外に負担: %d千円 → 前年比 %+.2f%%" % (lo, (lo/26582-1)*100))
print("    調整額を前年同額に固定           : %d千円 → 前年比 %+.2f%%" % (hi, (hi/26582-1)*100))
print("  ※調整額の内訳は原本に開示がなく、デジタル除きの真の前年比は【特定不能】")
print("  売上高（デジタル除き）: 前年 833,476 → 当期 %d 千円（%+.2f%%）"
      % (884226+72128+2100, (958454/833476-1)*100))

print("="*70); print("[8] 前年同期の分母の小ささ（7593 JDG-O65 の規律）")
prior=dict(sales=833476, op=26582, ord=16929, ni=8267)
for k in q1:
    print("  %-12s 前年%9d → 当期%9d  増加額%9d千円  YoY %+.2f%%"
          % (jp[k],prior[k],q1[k],q1[k]-prior[k],(q1[k]/prior[k]-1)*100))

print("="*70); print("[9] 同業比較（全社2026-08-21確定終値。校閲が2026-08-22T01:20〜01:22Zに独立再取得）")
eps_fc, bps_1q = 32.94, 247.22
peers={"7760 ＩＭＶ":(17.0,2.39,1.52),"6846 中央製作所":(7.9,0.41,3.98),"7722 国際計測器":(10.6,0.86,5.06),
       "6858 小野測器":(10.7,0.51,3.63),"6853 共和電業":(16.0,1.02,2.76)}
pers=sorted(v[0] for v in peers.values()); pbrs=sorted(v[1] for v in peers.values())
mper,mpbr=statistics.median(pers),statistics.median(pbrs)
per7,pbr7=close/eps_fc, close/bps_1q
print("  peer PER %s 中央値 %.2f / peer PBR %s 中央値 %.2f" % (pers,mper,pbrs,mpbr))
print("  7719 予想PER %.4f倍（中央値比 %+.2f%%） / PBR(1Q末BPS %.2f円) %.4f倍（中央値比 %+.2f%%）"
      % (per7,(per7/mper-1)*100,bps_1q,pbr7,(pbr7/mpbr-1)*100))
rp=sorted(pers+[per7]).index(per7)+1; rb=sorted(pbrs+[pbr7]).index(pbr7)+1
print("  安い順の順位: PER %d位/6（＝割高な方から%d番目） / PBR %d位/6（＝割高な方から%d番目）"
      % (rp,7-rp,rb,7-rb))
print("  同業中央値と並ぶ株価: PER基準 %.2f円（△%.2f%%） / PBR基準 %.2f円（△%.2f%%）"
      % (mper*eps_fc,(1-mper*eps_fc/close)*100, mpbr*bps_1q,(1-mpbr*bps_1q/close)*100))
print("  配当利回り: 7719 無配 / 同業5社 1.52〜5.06%")

print("="*70); print("[10] 経過日数")
from datetime import date
base=date(2026,8,21)
for lbl,dd in [("中期経営計画公表 2025-09-17",date(2025,9,17)),("有価証券報告書提出 2026-05-29",date(2026,5,29)),
               ("1Q決算短信 2026-07-15",date(2026,7,15)),("調査委員会設置 2026-04-22",date(2026,4,22)),
               ("委員選定 2026-06-15",date(2026,6,15)),("元取締役への訴訟提起 2025-12-15",date(2025,12,15))]:
    print("  %-32s → 判定基準日まで %d日" % (lbl,(base-dd).days))
