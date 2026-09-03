# -*- coding: utf-8 -*-
"""
JDG-O94（校閲）独立検算スクリプト — 6444 サンデン / 6444-T8（押し目形成・沈静化確認）の追試
入力: kabutan.jp 日足HTML（本校閲が curl + ブラウザ相当UA で独立に再取得したキャッシュ）
      6444: https://kabutan.jp/stock/kabuka?code=6444&ashi=day&page=1 / &page=2
      TOPIX: https://kabutan.jp/stock/kabuka?code=0010&ashi=day&page=1
      取得日時: 2026-08-26T22:54:41Z / 22:54:50Z（UTC）
注意: kabutan日足表の日付セルは YY/MM/DD 形式（例 26/08/26）。
憲法第2章-5（再計算は必ずPython）・絶対制約第2条（出典・取得日時の明記）。
"""
import re, os, statistics

BASE = os.environ.get('KABU_DIR', '.')

def parse(path):
    h = open(path, encoding='utf-8').read()
    rows = []
    for m in re.finditer(r'(\d{2})/(\d{2})/(\d{2})(.*?)</tr>', h, re.S):
        yy, mm, dd, rest = m.groups()
        tds = re.findall(r'<td[^>]*>(.*?)</td>', rest, re.S)
        vals = [re.sub(r'<[^>]+>', '', t).replace(',', '').replace('&nbsp;', '').strip() for t in tds]
        if len(vals) >= 7:
            rows.append({
                'date': '20%s-%s-%s' % (yy, mm, dd),
                'open': float(vals[0]), 'high': float(vals[1]), 'low': float(vals[2]),
                'close': float(vals[3]), 'vol': int(vals[6]),
            })
    return rows

r1 = parse(os.path.join(BASE, '6444_kabuka.html'))
r2 = parse(os.path.join(BASE, '6444_kabuka_p2.html'))
seen, ser = set(), []
for r in r1 + r2:
    if r['date'] not in seen:
        seen.add(r['date']); ser.append(r)
ser.sort(key=lambda x: x['date'])

print("=== 0. 取得系列 ===")
print("営業日数: %d  期間: %s 〜 %s" % (len(ser), ser[0]['date'], ser[-1]['date']))

print("\n=== 1. 直近6営業日（本校閲が独立再取得・再パース） ===")
print("日付        始値  高値  安値  終値   前日比   前日比%   出来高")
for i, r in enumerate(ser[-6:]):
    idx = ser.index(r)
    prev = ser[idx-1]['close'] if idx > 0 else None
    d = r['close'] - prev if prev else 0.0
    p = d / prev * 100 if prev else 0.0
    print("%s  %5.0f %5.0f %5.0f %5.0f  %+6.0f  %+7.4f%%  %9d" %
          (r['date'], r['open'], r['high'], r['low'], r['close'], d, p, r['vol']))

# ---- T8 条文の固定値（判断メモ JDG-O80 15節・watchlist 594行目。再算出しない） ----
BASE_HIGH = 211.0      # 2026-08-18 年初来高値・52週高値（固定値）
VOL_AVG20 = 171285     # 窓A・2026-08-18時点の直近20営業日平均出来高（固定値）

print("\n=== 2. T8 判定（固定値: 基準高値%.0f円 / 20日平均出来高%d株） ===" % (BASE_HIGH, VOL_AVG20))
lo = BASE_HIGH * 0.85
hi = BASE_HIGH * 0.95
print("帯（%%ベース）: %.4f円(-15%%) 〜 %.4f円(-5%%)" % (lo, hi))
import math
print("帯（整数終値ベース）: %d円 〜 %d円" % (math.ceil(lo), math.floor(hi)))

streak = 0
hit_date = None
for r in ser:
    if r['date'] < '2026-08-14':
        continue
    drop = (BASE_HIGH - r['close']) / BASE_HIGH * 100
    inband = 5.0 <= drop <= 15.0
    volok = r['vol'] <= VOL_AVG20
    streak = streak + 1 if (inband and volok) else 0
    if streak >= 2 and hit_date is None:
        hit_date = r['date']
    print("%s: 終値%.0f円 下落率%.4f%% 帯内=%-5s 出来高%7d株(平均比%.4f倍) 出来高<=平均=%-5s 連続=%d"
          % (r['date'], r['close'], drop, inband, r['vol'], r['vol']/VOL_AVG20, volok, streak))
print("→ T8成立日: %s" % hit_date)

print("\n=== 3. T2（確定終値195円以下）の独立判定 ===")
for r in ser[-5:]:
    print("%s: 終値%.0f円 <= 195円 ? %s" % (r['date'], r['close'], r['close'] <= 195))

print("\n=== 4. T1（209円以上 かつ 出来高256,928株以上）の独立判定 ===")
for r in ser[-5:]:
    print("%s: 終値%.0f円>=209 ? %-5s / 出来高%d>=256928 ? %-5s → 成立=%s"
          % (r['date'], r['close'], r['close'] >= 209, r['vol'], r['vol'] >= 256928,
             r['close'] >= 209 and r['vol'] >= 256928))

print("\n=== 5. 固定値の由来検証（再算出ではなく、固定値が2026-08-18時点で正しく算出されたかの追認） ===")
idx18 = [i for i, r in enumerate(ser) if r['date'] == '2026-08-18'][0]
w_a = ser[idx18-19:idx18+1]          # 窓A: 判定日を含む直近20営業日
avg_a = sum(x['vol'] for x in w_a) / len(w_a)
print("窓A（%s〜%s, n=%d）平均出来高 = %.4f株 → 条文の固定値 %d株 と一致: %s"
      % (w_a[0]['date'], w_a[-1]['date'], len(w_a), avg_a, VOL_AVG20, round(avg_a) == VOL_AVG20))
hi52 = max(x['high'] for x in ser)
print("取得系列（%d営業日）の最高値 = %.0f円（%s）→ 条文の基準高値 %.0f円 と一致: %s"
      % (len(ser), hi52, [x['date'] for x in ser if x['high'] == hi52][0], BASE_HIGH, hi52 == BASE_HIGH))

print("\n=== 6. TOPIX対比（記録用・判定には不使用） ===")
t = parse(os.path.join(BASE, 'topix_kabuka.html'))
t.sort(key=lambda x: x['date'])
tc = {x['date']: x['close'] for x in t}
prev_c = [x['close'] for x in ser if x['date'] == '2026-08-25'][0]
cur_c = [x['close'] for x in ser if x['date'] == '2026-08-26'][0]
r6444 = (cur_c - prev_c) / prev_c * 100
rtpx = (tc['2026-08-26'] - tc['2026-08-25']) / tc['2026-08-25'] * 100
print("TOPIX 2026-08-25 %.2f → 2026-08-26 %.2f : %+.4f%%" % (tc['2026-08-25'], tc['2026-08-26'], rtpx))
print("6444 %.0f → %.0f : %+.4f%% / TOPIX対比 %+.4fpt" % (prev_c, cur_c, r6444, r6444 - rtpx))

print("\n=== 7. バリュエーション（終値199円。EPS/BPSは JDG-O80 8節の確定値を継承） ===")
EPS, BPS = 4.46, 275.79
per = 199.0 / EPS
pbr = 199.0 / BPS
roe = EPS / BPS * 100
print("PER = 199.0 / %.2f = %.4f倍" % (EPS, per))
print("PBR = 199.0 / %.2f = %.4f倍" % (BPS, pbr))
print("ROE = %.2f / %.2f * 100 = %.4f%%" % (EPS, BPS, roe))
print("恒等式検算 PBR = PER x ROE/100 = %.4f （一致: %s）" % (per*roe/100, abs(per*roe/100 - pbr) < 1e-9))
print("JDG-O80時点（終値202円）PBR = %.4f倍 → 差分 %+.4f倍 (%.4f%%)"
      % (202.0/BPS, pbr - 202.0/BPS, (pbr/(202.0/BPS) - 1)*100))

print("\n=== 8. 直近の押し目帯・出来高条件の充足頻度（無限後退リスクの定量記録・判定には不使用） ===")
n_band = sum(1 for r in ser if 5.0 <= (BASE_HIGH-r['close'])/BASE_HIGH*100 <= 15.0)
n_both = sum(1 for r in ser if 5.0 <= (BASE_HIGH-r['close'])/BASE_HIGH*100 <= 15.0 and r['vol'] <= VOL_AVG20)
print("取得系列%d営業日のうち 帯内=%d日 / 帯内かつ出来高条件充足=%d日" % (len(ser), n_band, n_both))
