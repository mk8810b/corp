# -*- coding: utf-8 -*-
"""
6444 サンデン株式会社 6444-T8成立（押し目形成・沈静化確認）検算スクリプト
JDG-S101（起案）。出典: kabutan.jp日足（curl取得、UA指定）2026-08-26T07:24:16Z。
"""

base_high = 211.0  # 2026-08-18 年初来高値・52週高値（固定値、outputs/judgement/6444-20260819-scan.md 14-4節）
vol_avg_A = 171285.0  # 窓A・2026-08-18時点20営業日平均出来高（固定値、同メモ14-1節）

days = [
    ("2026-08-21", 202, 112100),
    ("2026-08-24", 201, 70500),
    ("2026-08-25", 197, 73600),
    ("2026-08-26", 199, 116200),
]

print("=== T8 帯・出来高の判定（基準高値211円・20日平均出来高171,285株はいずれも固定値） ===")
band_lo = base_high * 0.85
band_hi = base_high * 0.95
print(f"帯（%ベース）: {band_lo:.4f}円(-15%) 〜 {band_hi:.4f}円(-5%)")
print(f"帯（整数終値ベース、切り上げ/切り下げ）: 180円 〜 200円")
print()

run = 0
for date, close, vol in days:
    decline_pct = (base_high - close) / base_high * 100
    in_band = 180 <= close <= 200
    vol_ok = vol <= vol_avg_A
    if in_band and vol_ok:
        run += 1
    else:
        run = 0
    print(f"{date}: 終値{close}円 下落率{decline_pct:.4f}% 帯内={in_band} 出来高{vol:,}株(平均比{vol/vol_avg_A:.4f}倍) 出来高<=平均={vol_ok} 連続日数={run}")

print()
print(f"T8成立: {'2026-08-26 (連続2営業日達成)' if run>=2 else '不成立'}")

print()
print("=== T2（下抜け195円以下）との独立判定 ===")
for date, close, vol in days:
    print(f"{date}: 終値{close}円 <= 195円? {close <= 195}")

print()
print("=== 前日比（2026-08-26） ===")
prev_close = 197.0
close_2626 = 199.0
chg = close_2626 - prev_close
chg_pct = chg / prev_close * 100
print(f"前日終値{prev_close}円 → 当日終値{close_2626}円: 変化{chg:+.1f}円 ({chg_pct:+.4f}%)")

print()
print("=== バリュエーション再計算（2026-08-26終値199円） ===")
eps_fc = 4.46
bps = 275.79
close = 199.0
per = close/eps_fc
pbr = close/bps
roe = eps_fc/bps*100
print(f"PER = {close}/{eps_fc} = {per:.4f}倍")
print(f"PBR = {close}/{bps} = {pbr:.4f}倍")
print(f"ROE(通期予想ベース) = {eps_fc}/{bps}*100 = {roe:.4f}%")
print(f"恒等式検算 PBR = PER*ROE/100 = {per*roe/100:.4f}  (一致確認: {abs(per*roe/100 - pbr) < 1e-9})")

print()
print("=== TOPIX対比（2026-08-26） ===")
topix_close = 4111.02
topix_prev = 4093.67
topix_chg = topix_close - topix_prev
topix_chg_pct = topix_chg/topix_prev*100
print(f"TOPIX: 前日{topix_prev} → 当日{topix_close} 変化{topix_chg:+.2f}pt ({topix_chg_pct:+.4f}%)")
print(f"6444の当日騰落率 {chg_pct:+.4f}% - TOPIX {topix_chg_pct:+.4f}% = 対TOPIX超過 {chg_pct-topix_chg_pct:+.4f}pt")
