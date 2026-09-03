# 6613 校閲（JDG-O102）独立再計算スクリプト
# 入力: 6613-20260829-weekly-review-price-series.json
#   出典 https://kabutan.jp/stock/kabuka?code=6613&ashi=day&page=1 ・ &page=2
#   （curl・ブラウザ相当UA、校閲が独立に再取得、取得日時 2026-08-30T23:50:18Z）
#   2026-06-04〜2026-08-28 の **60営業日**（重複排除後・欠落なし）
# 実行: cd outputs/judgement && python3 6613-20260829-weekly-review-calc.py
import json, math, statistics as st
rows=json.load(open('6613-20260829-weekly-review-price-series.json'))          # newest-first, 60 unique trading days
num=lambda s: float(str(s).replace(',',''))
dates=[r[0] for r in rows]
closes=[num(r[4]) for r in rows]
vols=[num(r[7]) for r in rows]
chg=[num(r[6]) for r in rows]

print("=== 1. 判定基準日 ===")
print(dates[0], "close", closes[0], "chg%", chg[0], "vol", vols[0], "prev close", closes[1],
      "recomputed chg%", round((closes[0]/closes[1]-1)*100,4), "diff yen", closes[0]-closes[1])

cl,vo = closes[:20], vols[:20]
print("窓A:", dates[19], "->", dates[0], " n=",len(cl))
avg_vol=sum(vo)/20; avg_amt=sum(v*c for v,c in zip(vo,cl))/20
print("20日平均出来高:", round(avg_vol,1), " 20日平均売買代金(億):", round(avg_amt/1e8,4))

def sigma(cl):
    ch=list(reversed(cl))
    simp=[ch[i]/ch[i-1]-1 for i in range(1,len(ch))]
    logr=[math.log(ch[i]/ch[i-1]) for i in range(1,len(ch))]
    return {'pstdev_simple':st.pstdev(simp)*100,'stdev_simple':st.stdev(simp)*100,
            'pstdev_log':st.pstdev(logr)*100,'stdev_log':st.stdev(logr)*100}
sA=sigma(cl)
print("σ20窓A:", {k:round(v,4) for k,v in sA.items()})
close=closes[0]
two=close*0.02; sig=close*max(sA.values())/100; tick=1.0
gate=math.ceil(max(two,sig,tick))
print("2%成分",round(two,2)," σ20成分",round(sig,2)," GATE",gate," 上抜け",close+gate," 下抜け",close-gate)
print("出来高1.5倍:", math.ceil(avg_vol*1.5))

# 窓B (21 closes)
sB=sigma(closes[:21]); sigB=close*max(sB.values())/100; gateB=math.ceil(max(two,sigB,tick))
print("窓B σ20:", {k:round(v,4) for k,v in sB.items()}, "gateB", gateB, "上", close+gateB, "下", close-gateB)

print("\n=== 2. 基準率（窓A 20営業日） ===")
up=close+gate; dn=close-gate; vth=math.ceil(avg_vol*1.5)
print("終値>=%d: %d日"%(up,sum(1 for c in cl if c>=up)))
print("出来高>=%d: %d日"%(vth,sum(1 for v in vo if v>=vth)))
print("AND: %d日"%sum(1 for c,v in zip(cl,vo) if c>=up and v>=vth), [dates[i] for i in range(20) if cl[i]>=up and vo[i]>=vth])
print("終値<=%d: %d日"%(dn,sum(1 for c in cl if c<=dn)))
cons=sum(1 for i in range(19) if cl[i]<=dn and cl[i+1]<=dn)
print("終値<=%d が2営業日連続: %d日"%(dn,cons))
r=[(closes[i]/closes[i+1]-1)*100 for i in range(19)]
thr=gate/close*100
print("ゲート相当変化率 %.4f%%"%thr)
print("日次<=-thr:",sum(1 for x in r if x<=-thr),"/19  日次>=+thr:",sum(1 for x in r if x>=thr),"/19  |x|>=thr:",sum(1 for x in r if abs(x)>=thr),"/19")
print("窓A日次変動 min %.2f max %.2f"%(min(r),max(r)))

print("\n=== 3. 押し目条項の点検 ===")
hi20=max(cl); print("窓A終値高値", hi20, "日付", dates[cl.index(hi20)])
print("現在の下落率 %.2f%%"%((close/hi20-1)*100))
print("5-15%%帯:", round(hi20*0.95,1),"〜",round(hi20*0.85,1))
hi61=max(closes); print("全期間終値高値", hi61, dates[closes.index(hi61)], "下落率 %.2f%%"%((close/hi61-1)*100))
# ローリング20日平均以下が2営業日連続 の 直近24判定日
cnt=0; hits=[]
for i in range(24):
    ok=True
    for k in (i,i+1):
        avg=sum(vols[k:k+20])/20
        if not (vols[k]<=avg): ok=False
    if ok: cnt+=1; hits.append(dates[i])
print("『出来高が20日平均以下が2営業日連続』直近24判定日での成立:",cnt,"回",hits)

print("\n=== 4. 財務・進捗の再計算 ===")
q1s,fys=436.0,1850.0; q1o=-45.0; fyo=3.0; q1n=-51.0; fyn=441.0; pys,pyfy=315.0,1372.0
print("売上進捗 %.2f%%  線形25との差 %.2f pt"%(q1s/fys*100, q1s/fys*100-25))
print("前年同期ペース %.2f%%  差 %.2f pt"%(pys/pyfy*100, q1s/fys*100-pys/pyfy*100))
print("純利益進捗 %.2f%%"%(q1n/fyn*100))
print("Q2-Q4必要営業利益 %.1f百万円"%(fyo-q1o))
print("純利益予想-営業利益予想 = %.1f"%(fyn-fyo))
print("営業利益率予想 %.4f%%"%(fyo/fys*100))
print("通期予想増収率 %.2f%%"%((fys/pyfy-1)*100))
cash=2689.537; opcf=-481.0; invcf=-886.0; fcf=opcf+invcf
print("FCF",fcf,"営業CF基準 %.2f四半期 (%.2f年)"%(cash/abs(opcf/4), cash/abs(opcf/4)/4))
print("FCF基準 %.2f四半期 (%.2f年)"%(cash/abs(fcf/4), cash/abs(fcf/4)/4))
print("差 %.2f四半期 比 %.3f倍  投資CF比率 %.2f%%"%(cash/abs(opcf/4)-cash/abs(fcf/4), (cash/abs(opcf/4))/(cash/abs(fcf/4)), abs(invcf)/abs(fcf)*100))
print("目標株価乖離 %.2f%%  倍率 %.2f"%((650/close-1)*100, close/650))
print("1単元 %.1f円 資金残高比 %.3f%%"%(close*100, close*100/3_000_000*100))
print("D-013上限まで %.3f%%"%((3000-close)/3000*100))
print("損切-10%% %d / 利確+25%% %d"%(math.ceil(close*0.9), math.ceil(close*1.25)))
print("PBR検算: 時価総額925億 / 純資産4,908,388千円 = %.2f"%(92500000000/4908388000))
print("発行済株式 41,840,875 x close = %.4f億円"%(41840875*close/1e8))
print("株式数増加率 %.2f%%"%((41840875/35755180-1)*100))
print("潜在株式 1,218,300 / 41,840,875 = %.2f%%"%(1218300/41840875*100))
print("σ20(最大%.4f%%) に対する損切-10%%: %.3f σ"%(max(sA.values()), 10/max(sA.values())))
