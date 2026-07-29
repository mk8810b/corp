#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2026-07-29 Fable5レビュー「TDnet/EDINET能動スキャン（D-012エッジ仮説の実測経路）」検証スクリプト
=================================================================================================

レビュー本文: outputs/review/2026-07-29-fable5-proactive-scan-review.md
本文中の全ての数値的主張は本スクリプトの実行結果として再現できる（憲法第2章-5・絶対制約第2条）。

使い方:
  python3 2026-07-29-fable5-proactive-scan-calculations.py            # オフライン決定論モード（既定）
  python3 2026-07-29-fable5-proactive-scan-calculations.py --live     # TDnet/EDINET/kabutanを再取得して再集計
                                                                      # （EDINETは環境変数EDINET_API_KEYが必要）

設計方針:
- 既定はオフライン決定論。§1〜§4の実測値は2026-07-29に実際にネットワーク取得した生データを
  定数として埋め込み（各定数に取得元URL・取得日時を明記）、派生統計は毎回再計算する。
- --live 指定時は同じ取得ロジックで再取得する（外部サイトの仕様変更・過去日の保持期限
  〔TDnet日次一覧は概ね1ヶ月分〕により将来は再現しない可能性がある——本文§6に明記）。
- 標準ライブラリのみ使用。
"""

import argparse
import json
import math
import re
import sys
from collections import Counter

# =================================================================================
# 取得メタデータ（第2条: 取得元・取得日時）
# =================================================================================

FETCH_META = {
    "tdnet": {
        "url_pattern": "https://www.release.tdnet.info/inbs/I_list_{page:03d}_{YYYYMMDD}.html",
        "method": "curl -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'（WebFetchは非使用。RUNBOOK既知制約準拠）",
        "fetched_at": "2026-07-29T08:35:29Z（主要6営業日分）/ 2026-07-29T08:40:21Z（追加3営業日分・実例遡及照合）",
    },
    "edinet": {
        "url_pattern": "https://api.edinet-fsa.go.jp/api/v2/documents.json?date=YYYY-MM-DD&type=2&Subscription-Key=***REDACTED***",
        "method": "urllib（EDINET公式API v2。APIキーは環境変数EDINET_API_KEY、出力ではリダクション）",
        "fetched_at": "2026-07-29T08:36:07Z",
    },
    "kabutan_floor_sample": {
        "url_pattern": "https://kabutan.jp/stock/kabuka?code=<code>&ashi=day&page=1",
        "method": "curl（UA指定）。直近20営業日（2026-07-28以前）の終値・出来高から平均出来高・平均売買代金を算出",
        "fetched_at": "2026-07-29T08:38:27Z",
    },
}

# =================================================================================
# §0 実例7件（6銘柄）のタイムライン再検証
#     出典: 各判断メモ・企業調査メモ（パスを各レコードに記載）。株価・出来高は当該メモに
#     記録済みの確定値（原典はkabutan.jp確定終値ページ等、取得日時は各メモに記録済み）の転記。
# =================================================================================

CASES = [
    dict(
        code="1518", name="三井松島HD",
        source="outputs/judgement/1518-20260725.md / outputs/research/1518-20260725.md",
        disclosure_channel="TDnet 2026-07-22 16:00（上方修正+増配 / 山洋子会社化の2件。本スクリプト§3で遡及実測）"
                           "＋EDINET臨時報告書S100YRLN 07-22 16:40提出＋株探記事 07-22 17:05",
        disclosure_timing="引け後（15:30以降）",
        prices=dict(c_pre=1553, c_d1=1953, o_d2=2199, c_d2=2241,
                    vol_d1=79_200, vol_d2=3_839_800, vol_normal=(105_500 + 118_200) / 2),
        notes="D+1はストップ高で始高安終=1,953円が完全一致（気配のまま出来高79,200株のみ約定）",
    ),
    dict(
        code="5074", name="テスHD",
        source="outputs/judgement/5074-20260725.md / outputs/research/5074-20260725.md",
        disclosure_channel="TDnet 2026-07-23 15:00（業績予想・配当予想の修正。§3で遡及実測）",
        disclosure_timing="引け間際（大引け15:30の30分前）",
        prices=dict(c_pre=761, c_d0=804, c_d1=723, vol_d0=3_824_800, vol_d1=5_246_100),
        notes="開示から30分の場中残余時間で+5.65%。翌営業日-10.07%で発表前水準を-4.99%下回る（出尽くし）",
    ),
    dict(
        code="5216", name="倉元製作所",
        source="outputs/judgement/5216-20260723-event.md / outputs/research/5216-20260718.md",
        disclosure_channel="会社サイト＋フィスコ/みんかぶ配信 2026-07-17 12:42〜12:55（場中）。"
                           "TDnet掲載は0件（§3で遡及実測）・EDINETも0件（D-023実測と整合）",
        disclosure_timing="場中（12時台）・TDnet/EDINET非掲載",
        prices=dict(c_pre=157, h_d0=205, c_d0=184, c_d6=158, vol_pre=69_700, vol_d0=8_201_200),
        notes="発表から数時間で高値+30.6%→6営業日後に発表前比+0.64%の全戻り",
    ),
    dict(
        code="5491", name="日本金属",
        source="outputs/judgement/5491-20260721-event.md",
        disclosure_channel="開示なし（EDINET API・TDnet・株探・Yahoo!の4系統で当日開示ゼロを実測済み）",
        disclosure_timing="開示不存在（出来高2.45倍の価格イベントのみ）",
        prices=dict(c_pre=887, c_d0=901, vol_d0=88_900, vol_avg20=36_260),
        notes="出来高急増≠開示イベント。スキャンは（正しく）何も返さないケース",
    ),
    dict(
        code="7359", name="東京通信グループ",
        source="outputs/judgement/7359-20260718.md / 7359-20260728-event-draft.md",
        disclosure_channel="TDnet 2026-07-16 16:00（筆頭株主の保有方針。§3で遡及実測）",
        disclosure_timing="引け後（16:00）",
        prices=dict(c_pre=228, h_d1=273, c_d1=236, c_d8=223,
                    vol_pre=13_800, vol_d1=1_535_500),
        notes="翌営業日に出来高+11,026%・高値+19.7%→終値+3.5%（寄り天）→2週間で発表前水準未満へ剥落",
    ),
    dict(
        code="7201", name="日産自動車",
        source="outputs/judgement/7201-20260729-event.md",
        disclosure_channel="開示なし（EDINET直近14日0件・株探で個社材料なし。トヨタ主導のバリュー株物色）",
        disclosure_timing="開示不存在（セクター/スタイル要因の急騰）",
        prices=dict(c_pre=337.4, c_d0=358.2, vol_d0=57_420_700, vol_avg20=31_103_570),
        notes="同業5社が同日+2.45〜+7.28%。スキャンは（正しく）何も返さないケース",
    ),
    dict(
        code="8541", name="愛媛銀行",
        source="outputs/judgement/8541-20260727-event.md / 8541-20260729-event.md / outputs/research/8541-20260725.md",
        disclosure_channel="日経先行報道（07-24朝）→TDnet 07-24 08:30『当行に関する一部報道について』→"
                           "TDnet 07-24 15:30 基本合意（§3で遡及実測）→EDINET臨時報告書S100YS6U 15:39提出",
        disclosure_timing="報道先行（寄り前8:30に『報道について』開示・正式開示は15:30/15:39）",
        prices=dict(c_pre=2508, c_d0=2794, c_d1=2917, c_d3=2794, vol_ratio_d0=11.71),
        notes="正式開示（15:30/15:39）の時点で当日+11.40%の反応が完了。その後は材料なき続伸→巻き戻し",
    ),
]


def pct(a, b):
    return (a / b - 1) * 100


def section0():
    print("=" * 96)
    print("§0 実例7件（6銘柄）の再検証: 開示時刻・反応時刻・『当日スキャンで間に合ったか』")
    print("=" * 96)

    # --- 1518 ---
    c = CASES[0]["prices"]
    r2d = pct(c["c_d2"], c["c_pre"])          # 2日累計
    gap = pct(c["o_d2"], c["c_pre"])          # D+2寄り付きギャップ
    intraday = pct(c["c_d2"], c["o_d2"])      # D+2ザラ場
    gap_share_log = math.log(c["o_d2"] / c["c_pre"]) / math.log(c["c_d2"] / c["c_pre"]) * 100
    d1 = pct(c["c_d1"], c["c_pre"])
    fill_ratio = c["vol_d1"] / c["vol_normal"]
    print(f"\n[1518] 開示: 07-22 16:00 TDnet（引け後）")
    print(f"  D+1(07/23)ストップ高 +{d1:.2f}%（約定 {c['vol_d1']:,}株 = 平常日比 {fill_ratio:.2f}倍のみ）")
    print(f"  D+2(07/24)寄りギャップ +{gap:.2f}% / ザラ場 +{intraday:.2f}% / 2日累計 +{r2d:.2f}%")
    print(f"  2日累計反応のうち寄り付きギャップまでの寄与（対数分解）= {gap_share_log:.1f}%")
    print(f"  → 分類: 引け後開示。夜間スキャン→翌朝寄り前の読了は時刻的に可能だった。")
    print(f"    ただし翌日はS高気配で約定可能量が平常日出来高の{fill_ratio:.2f}倍に留まり、")
    print(f"    現実的な約定はD+2寄り（既に+{gap:.1f}%）以降 → 『読める』と『買える』は別問題。")

    # --- 5074 ---
    c = CASES[1]["prices"]
    print(f"\n[5074] 開示: 07-23 15:00 TDnet（大引け15:30の30分前）")
    print(f"  当日終値 +{pct(c['c_d0'], c['c_pre']):.2f}%（開示後30分で反応）/ 翌日 {pct(c['c_d1'], c['c_d0']):.2f}% "
          f"/ 発表前比累計 {pct(c['c_d1'], c['c_pre']):.2f}%")
    print(f"  → 分類: 引け間際開示・即時反応。15:30スキャンは当日中に検知可能だが、")
    print(f"    検知時点で+5.65%済み。しかも翌日に発表前水準割れ＝『未反応に見える状態』で")
    print(f"    追随していれば-10%を直撃した逆選択の実例。")

    # --- 5216 ---
    c = CASES[2]["prices"]
    print(f"\n[5216] 材料: 07-17 12:42〜12:55 会社サイト/フィスコ配信（場中）。TDnet掲載0件（§3実測）")
    print(f"  当日高値 +{pct(c['h_d0'], c['c_pre']):.1f}% / 出来高 {c['vol_d0']/c['vol_pre']:.1f}倍 / "
          f"6営業日後 +{pct(c['c_d6'], c['c_pre']):.2f}%（全戻り）")
    print(f"  → 分類: TDnet/EDINETスキャンの捕捉圏外（構造的ミス）＋場中数時間で反応消化。原理的に効かない。")

    # --- 5491 / 7201 ---
    for i, d in ((3, "5491"), (5, "7201")):
        c = CASES[i]["prices"]
        print(f"\n[{d}] 開示ゼロの価格イベント（{CASES[i]['disclosure_timing']}）")
        print(f"  → 分類: スキャン対象外。開示起点スキャンはこの種のイベントを生成しない（誤検知ゼロ側の挙動）。")

    # --- 7359 ---
    c = CASES[4]["prices"]
    print(f"\n[7359] 開示: 07-16 16:00 TDnet（引け後）")
    print(f"  翌日: 出来高 {pct(c['vol_d1'], c['vol_pre']):,.0f}%増 / 高値 +{pct(c['h_d1'], c['c_pre']):.2f}% / "
          f"終値 +{pct(c['c_d1'], c['c_pre']):.2f}%（寄り天）")
    print(f"  8営業日後 {pct(c['c_d8'], c['c_pre']):.2f}%（発表前水準割れ）")
    print(f"  → 分類: 引け後開示。夜間スキャン→翌朝読了は時刻的に可能だった。ただし開示内容に定量的")
    print(f"    コミットメントがなく、正しい判定は非BUY。当日読了の価値は『誤って追随買いしないこと』の側。")

    # --- 8541 ---
    c = CASES[6]["prices"]
    print(f"\n[8541] 開示: 日経先行報道（07-24朝）→TDnet 08:30『報道について』→15:30正式・EDINET 15:39")
    print(f"  正式開示日 +{pct(c['c_d0'], c['c_pre']):.2f}%（出来高{c['vol_ratio_d0']}倍）: 正式開示時点で反応完了")
    print(f"  → 分類: 報道先行型。正式開示のスキャンは構造的に遅い。ただし寄り前08:30の『一部報道について』")
    print(f"    開示は朝スキャンで捕捉可能だった（内容は未確定コメントであり、それ単独でのBUY根拠には遠い）。")

    # --- 分類サマリ ---
    print("\n--- 分類サマリ（7実例） ---")
    rows = [
        ("1518", "引け後(16:00)", "捕捉可能（夜間/朝スキャン）", "△ 読了は間に合うが約定はS高気配・ギャップで大半消化"),
        ("5074", "引け間際(15:00)", "当日15:30スキャンで捕捉可能", "× 30分で反応済み＋翌日出尽くし（逆選択リスクの実例）"),
        ("5216", "場中(12時台)・TDnet外", "捕捉不能（プレス/フィスコのみ）", "× 原理的に効かない"),
        ("5491", "開示なし", "スキャン対象外", "—（開示起点では発生しない）"),
        ("7359", "引け後(16:00)", "捕捉可能（夜間/朝スキャン）", "△ 時刻は間に合うが内容にエッジなし（正解は非BUY）"),
        ("7201", "開示なし", "スキャン対象外", "—（セクター要因）"),
        ("8541", "報道先行＋寄り前8:30", "8:30分のみ捕捉可能", "× 正式開示は反応完了後。報道が常に先行"),
    ]
    for r in rows:
        print("  " + " | ".join(r))
    n_catchable = 3  # 1518, 7359, 8541(8:30)
    n_disclosure_driven = 5  # 1518,5074,5216,7359,8541
    print(f"\n  開示起点の5件中、TDnetスキャンが時刻的に先回りできた（寄り前に読めた）のは "
          f"{n_catchable}件（1518・7359・8541の8:30分）。ただし3件とも『読めた＝勝てた』ではない。")
    print("  重要: 7件全てが『株価が動いたから』検出された標本（選択バイアス）。"
          "『開示が出たが動かなかった』母集団（スキャンの本来の標的）はこのデータには一切含まれない。")


# =================================================================================
# §1 TDnet日次一覧の実測（2026-07-16〜07-29の9営業日、遡及取得）
#     生データ: 各日の(時刻, コード, 会社名, 表題)。ここでは日次集計値を埋め込み、
#     派生統計（比率等）を再計算する。--liveで全行再取得・再集計。
# =================================================================================

# 集計値（2026-07-29 08:35-08:40 UTC実測。パース件数はヘッダ表示『全N件』と全日一致）
TDNET_DAILY = {
    # date: dict(total, uniq_companies, pre_open, intraday_900_1500, last30_1500_1530, after_1530,
    #            material_rows, material_uniq)
    "2026-07-16": dict(total=169, note="実例遡及用（7359捕捉確認）"),
    "2026-07-17": dict(total=307, note="実例遡及用（5216非掲載確認）"),
    "2026-07-21": dict(total=212, note="実例遡及用（5491非掲載確認）"),
    "2026-07-22": dict(total=214, uniq=179, pre=23, intraday=34, last30=20, after=137, mat_rows=30, mat_uniq=27),
    "2026-07-23": dict(total=183, uniq=157, pre=0, intraday=39, last30=17, after=127, mat_rows=35, mat_uniq=27),
    "2026-07-24": dict(total=410, uniq=354, pre=6, intraday=65, last30=37, after=302, mat_rows=59, mat_uniq=51),
    "2026-07-27": dict(total=152, uniq=124, pre=2, intraday=38, last30=7, after=105, mat_rows=49, mat_uniq=38),
    "2026-07-28": dict(total=176, uniq=131, pre=1, intraday=44, last30=9, after=122, mat_rows=71, mat_uniq=60),
    "2026-07-29": dict(total=269, uniq=191, pre=7, intraday=63, last30=22, after=177, mat_rows=116, mat_uniq=94,
                       note="取得時点17:35 JSTの当日分。夕方以降の追加開示は未反映（下限値）"),
}

# 「材料型」表題キーワード（一次フィルタの機械判定案。第2条: 分類器は粗く、本文§6に限界を明記）
MATERIAL_PAT = re.compile(
    r"決算短信|業績予想|業績の修正|配当予想|配当の修正|上方修正|下方修正|剰余金の配当|自己株式取得|"
    r"株式分割|業務提携|資本提携|経営統合|合併|買収|子会社化|株式交換|株式移転|TOB|公開買付|MBO|"
    r"特別利益|特別損失|新製品|新技術|大口受注|受注|業績に関する|月次|通期業績|中間配当")


def section1():
    print("\n" + "=" * 96)
    print("§1 TDnet日次一覧の実測（適時開示の総量・提出時刻分布・材料型件数）")
    print("=" * 96)
    print(f"取得元: {FETCH_META['tdnet']['url_pattern']}")
    print(f"取得方法: {FETCH_META['tdnet']['method']}")
    print(f"取得日時: {FETCH_META['tdnet']['fetched_at']}\n")

    full_days = [d for d, v in TDNET_DAILY.items() if "uniq" in v]
    print(f"{'日付':<12}{'総件数':>6}{'社数':>6}{'寄り前':>7}{'場中':>6}{'引け間際':>8}{'引け後':>7}"
          f"{'引け後率':>8}{'材料型行':>8}{'材料型社数':>10}")
    tot = Counter()
    for d in full_days:
        v = TDNET_DAILY[d]
        after_rate = v["after"] / v["total"] * 100
        print(f"{d:<12}{v['total']:>6}{v['uniq']:>6}{v['pre']:>7}{v['intraday']:>6}{v['last30']:>8}"
              f"{v['after']:>7}{after_rate:>7.1f}%{v['mat_rows']:>8}{v['mat_uniq']:>10}")
        for k in ("total", "uniq", "pre", "intraday", "last30", "after", "mat_rows", "mat_uniq"):
            tot[k] += v[k]
    n = len(full_days)
    print(f"{'平均/日':<12}{tot['total']/n:>6.0f}{tot['uniq']/n:>6.0f}{tot['pre']/n:>7.1f}"
          f"{tot['intraday']/n:>6.1f}{tot['last30']/n:>8.1f}{tot['after']/n:>7.1f}"
          f"{tot['after']/tot['total']*100:>7.1f}%{tot['mat_rows']/n:>8.1f}{tot['mat_uniq']/n:>10.1f}")
    after_share = tot["after"] / tot["total"] * 100
    preopen_catchable = (tot["after"] + tot["pre"]) / tot["total"] * 100
    print(f"\n  引け後（>=15:30）比率: {after_share:.1f}%")
    print(f"  『翌営業日の寄り付き前に読める』理論圏（引け後＋寄り前）: {preopen_catchable:.1f}%")
    print(f"  場中（9:00-15:00）: {tot['intraday']/tot['total']*100:.1f}% / 引け間際（15:00-15:30）: "
          f"{tot['last30']/tot['total']*100:.1f}% → この帯は当日スキャンでも即時反応に原理的に勝てない帯")
    print("  ※ 07-29は取得時点（17:35 JST）までの当日分で夕方以降の追加開示を含まない下限値。")
    print("  ※ 決算集中日（8月上旬・中旬等）は未実測。観測ピークは07-24（金）の410件で、決算シーズン")
    print("    ピークはこれを大きく上回る可能性が高い（本文§6）。")


# =================================================================================
# §2 EDINET書類一覧APIの実測（同期間）
# =================================================================================

EDINET_DAILY = {
    # date: (総件数, 上場銘柄コード付き, 場中, 引け後, 寄り前, 上位書類種別)
    "2026-07-22": dict(total=161, listed=47, intraday=27, after=20, pre=0, top="臨時報告書13・確認書8・内部統制7"),
    "2026-07-23": dict(total=304, listed=62, intraday=31, after=31, pre=0, top="臨時報告書16・確認書8・訂正有報7"),
    "2026-07-24": dict(total=298, listed=85, intraday=41, after=44, pre=0, top="臨時報告書33・確認書11・発行登録追補8"),
    "2026-07-27": dict(total=223, listed=59, intraday=19, after=40, pre=0, top="臨時報告書16・確認書10・有報8"),
    "2026-07-28": dict(total=152, listed=42, intraday=27, after=15, pre=0, top="臨時報告書13・確認書7・有報5"),
    "2026-07-29": dict(total=163, listed=73, intraday=25, after=48, pre=0, top="臨時報告書30・確認書9・有報8"),
}


def section2():
    print("\n" + "=" * 96)
    print("§2 EDINET書類一覧APIの実測（同期間・比較対照）")
    print("=" * 96)
    print(f"取得元: {FETCH_META['edinet']['url_pattern']}")
    print(f"取得日時: {FETCH_META['edinet']['fetched_at']}\n")
    print(f"{'日付':<12}{'総件数':>6}{'上場コード付':>10}{'場中':>6}{'引け後':>7}  上位書類種別")
    for d, v in EDINET_DAILY.items():
        print(f"{d:<12}{v['total']:>6}{v['listed']:>10}{v['intraday']:>6}{v['after']:>7}  {v['top']}")
    avg_listed = sum(v["listed"] for v in EDINET_DAILY.values()) / len(EDINET_DAILY)
    print(f"\n  上場銘柄コード付き平均 {avg_listed:.0f}件/日。内訳は臨時報告書・確認書・有報・訂正が支配的で、")
    print("  株価カタリスト型開示（業績修正・決算短信等）はTDnet側にのみ流れる。D-023の実測（EDINET")
    print("  捕捉率0/5）と整合。→ 能動スキャンの主データソースはTDnet、EDINETは臨報等の補完に限る。")


# =================================================================================
# §3 実例開示の遡及捕捉照合（『もしスキャンが動いていたら一覧に載っていたか』）
# =================================================================================

RETRO_CAPTURE = [
    # (日付, コード, TDnet掲載, 掲載時刻・表題)
    ("2026-07-16", "7359", 1, "16:00 株主価値向上に向けた資本政策及び主要株主である筆頭株主の保有方針について"),
    ("2026-07-17", "5216", 0, "（掲載なし。材料は会社サイト/フィスコ配信のみ）"),
    ("2026-07-21", "5491", 0, "（掲載なし。開示自体が不存在）"),
    ("2026-07-22", "1518", 2, "16:00 業績予想の上方修正及び配当予想の修正（増配）/ 16:00 山洋の株式取得（子会社化）"),
    ("2026-07-23", "5074", 1, "15:00 業績予想及び配当予想の修正に関するお知らせ"),
    ("2026-07-24", "8541", 2, "08:30 当行に関する一部報道について / 15:30 いよぎんHDとの経営統合に関する基本合意"),
    ("2026-07-29", "7201", 0, "（掲載なし。セクター要因の急騰）"),
]


def section3():
    print("\n" + "=" * 96)
    print("§3 実例開示の遡及捕捉照合（TDnet日次一覧・2026-07-29実測）")
    print("=" * 96)
    for d, code, n, desc in RETRO_CAPTURE:
        print(f"  {d} {code}: 掲載{n}件  {desc}")
    disclosure_cases = ["1518", "5074", "5216", "7359", "8541"]
    captured = ["1518", "5074", "7359", "8541"]
    print(f"\n  開示起点の実例5件中、TDnet日次一覧が捕捉: {len(captured)}/{len(disclosure_cases)}件"
          f"（非捕捉は5216=TDnet外のプレス配信）")
    print("  うち『翌朝寄り前に読める』引け後・寄り前開示: 1518(16:00)・7359(16:00)・8541(08:30分)の3件。")
    print("  5074(15:00)は当日15:30スキャンで検知可能だが開示後30分で反応済み。")


# =================================================================================
# §4 フロア条件通過率の標本実測（材料型開示銘柄15社・kabutan 20営業日実測）
# =================================================================================

# 07-28の材料型開示60社（銘柄コード昇順）から機械的に4社おきに抽出した15社。
# 各社: 直近終値（07-28以前の最新）, 20営業日平均出来高, 20営業日平均売買代金(億円)
FLOOR_SAMPLE = [
    # (code, close, avg_vol_20d, avg_turnover_oku)
    ("1418", 587.0, 101_980, 0.59),
    ("1930", 1475.0, 95_415, 1.48),
    ("2678", 1272.0, 491_310, 6.14),
    ("3054", 276.0, 138_520, 0.38),
    ("3771", 1847.0, 31_990, 0.58),
    ("4290", 686.0, 362_595, 2.41),
    ("4769", 1089.0, 1_115, 0.01),
    ("5532", 3575.0, 28_425, 1.02),
    ("6436", 3766.0, 269_190, 10.19),
    ("6988", 3446.0, 3_208_075, 104.96),
    ("7477", 1718.0, 2_505, 0.05),
    ("8084", 4080.0, 39_930, 1.58),
    ("8537", 2825.0, 42_500, 1.18),
    ("8714", 1061.0, 1_125_565, 11.61),
    ("9441", 2827.0, 9_285, 0.25),
]


def clopper_pearson(k, n, alpha=0.05):
    """Clopper-Pearson二項信頼区間（両側）。ベータ分位点を二分探索で求める（標準ライブラリのみ）。"""
    def beta_cdf(x, a, b):
        # 正則化不完全ベータ関数 I_x(a,b) を数値積分（単純Simpson、十分な分割数）
        if x <= 0:
            return 0.0
        if x >= 1:
            return 1.0
        n_steps = 2000
        h = x / n_steps
        total = 0.0
        for i in range(n_steps + 1):
            t = i * h
            w = 1 if i in (0, n_steps) else (4 if i % 2 == 1 else 2)
            if 0 < t < 1:
                total += w * (t ** (a - 1)) * ((1 - t) ** (b - 1))
        integral = total * h / 3
        lnB = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
        return integral / math.exp(lnB)

    def beta_ppf(q, a, b):
        lo, hi = 0.0, 1.0
        for _ in range(60):
            mid = (lo + hi) / 2
            if beta_cdf(mid, a, b) < q:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    lower = 0.0 if k == 0 else beta_ppf(alpha / 2, k, n - k + 1)
    upper = 1.0 if k == n else beta_ppf(1 - alpha / 2, k + 1, n - k)
    return lower, upper


def section4():
    print("\n" + "=" * 96)
    print("§4 フロア条件（D-004/D-009/D-013）通過率の標本実測")
    print("=" * 96)
    print(f"取得元: {FETCH_META['kabutan_floor_sample']['url_pattern']}")
    print(f"取得日時: {FETCH_META['kabutan_floor_sample']['fetched_at']}")
    print("標本: 2026-07-28の材料型開示60社から銘柄コード順に4社おき機械抽出した15社\n")
    n_pass = 0
    for code, close, avg_vol, avg_turn_oku in FLOOR_SAMPLE:
        liq = (avg_vol >= 100_000) or (avg_turn_oku >= 1.0)
        pok = 100 <= close <= 3000
        both = liq and pok
        n_pass += both
        print(f"  {code}: 終値{close:>7,.0f}円  平均出来高{avg_vol:>10,.0f}株  平均売買代金{avg_turn_oku:>7.2f}億円"
              f"  流動性{'○' if liq else '×'} 価格帯{'○' if pok else '×'} → {'通過' if both else '除外'}")
    n = len(FLOOR_SAMPLE)
    rate = n_pass / n
    lo, hi = clopper_pearson(n_pass, n)
    print(f"\n  フロア両条件通過: {n_pass}/{n} = {rate*100:.1f}%（Clopper-Pearson 95%CI: {lo*100:.0f}〜{hi*100:.0f}%）")
    full_days = [v for d, v in TDNET_DAILY.items() if "uniq" in v]
    mat_min = min(v["mat_uniq"] for v in full_days)
    mat_max = max(v["mat_uniq"] for v in full_days)
    mat_avg = sum(v["mat_uniq"] for v in full_days) / len(full_days)
    print(f"  材料型開示 社数/日: {mat_min}〜{mat_max}（平均{mat_avg:.0f}）に通過率を適用すると、")
    print(f"  フロア通過の材料型開示は 点推定 {mat_min*rate:.0f}〜{mat_max*rate:.0f}社/日（平均{mat_avg*rate:.0f}社/日）、")
    print(f"  95%CI幅では {mat_min*lo:.0f}〜{mat_max*hi:.0f}社/日。")
    return rate, lo, hi, mat_avg


# =================================================================================
# §5 コスト試算（二段構成: 機械フィルタ＋Haiku一次読解 → 絞った候補のみ企業調査）
# =================================================================================

def section5(floor_rate, mat_avg):
    print("\n" + "=" * 96)
    print("§5 コスト試算（二段構成の能動スキャン）")
    print("=" * 96)

    # --- 実測由来の定数 ---
    research_cost_low, research_cost_high = 150_000, 190_000   # 企業調査1件あたり実測（D-022/CEO提示）
    candidate_all_in = 314_200                                  # 週次候補1件あたり全工程実測（D-022）
    weekly_band = (8, 10)                                       # D-022帯上限運用目標

    # --- 仮定値（実測ゼロ。第2条: 仮定と明記） ---
    haiku_per_doc_low, haiku_per_doc_high = 6_000, 12_000  # 開示1件のHaiku一次読解（PDF本文+プロンプト+出力）
    triage_cap_per_day = 40                                 # 決算集中日の一次読解上限（優先度キューで足切り）
    handoff_cap_day, handoff_cap_week = 2, 5                # 企業調査への引き渡し上限

    full_days = [v for d, v in TDNET_DAILY.items() if "uniq" in v]
    total_avg = sum(v["total"] for v in full_days) / len(full_days)
    shortlist_avg = mat_avg * floor_rate  # 材料型×フロア通過の平均社数/日
    print(f"\n  ファネル（5完全営業日+1部分日の実測+標本通過率。仮定値は明記）:")
    print(f"    全開示 平均{total_avg:.0f}件/日 → 材料型（表題キーワード・機械判定）平均{mat_avg:.0f}社/日")
    print(f"    → フロア通過（§4実測 {floor_rate*100:.0f}%）平均 {shortlist_avg:.0f}社/日")
    print(f"    → Haiku一次読解（上限{triage_cap_per_day}件/日の優先度キュー）")
    print(f"    → 企業調査への引き渡し ≤{handoff_cap_day}件/日・≤{handoff_cap_week}件/週（設計上限・仮定）")

    tri_low = shortlist_avg * haiku_per_doc_low * 5
    tri_high = min(shortlist_avg, triage_cap_per_day) * haiku_per_doc_high * 5
    tri_peak = triage_cap_per_day * haiku_per_doc_high * 5
    print(f"\n  Haiku一次読解コスト（仮定 {haiku_per_doc_low:,}〜{haiku_per_doc_high:,}トークン/件）:")
    print(f"    平常週: {tri_low/1e6:.2f}〜{tri_high/1e6:.2f}Mトークン/週（Haiku級）")
    print(f"    決算集中週の上限（cap全稼働）: {tri_peak/1e6:.2f}Mトークン/週")

    res_add_low = 0
    res_add_high = handoff_cap_week * research_cost_high
    print(f"\n  企業調査コスト（実測 {research_cost_low/1e4:.0f}〜{research_cost_high/1e4:.0f}万トークン/件）:")
    print(f"    追加コストは引き渡し設計に依存:")
    print(f"    (a) D-007の週次帯（5〜10件）の内数として代替する場合: 追加 ≈ {res_add_low}（構成が入れ替わるだけ）")
    print(f"    (b) 帯の外数として純増させる場合: 最大 +{res_add_high/1e6:.2f}Mトークン/週（Sonnet級）")

    weekly_now_low = weekly_band[0] * candidate_all_in
    weekly_now_high = weekly_band[1] * candidate_all_in
    print(f"\n  現行週次実測との比較: 現行 {weekly_now_low/1e6:.2f}〜{weekly_now_high/1e6:.2f}Mトークン/週"
          f"（{weekly_band[0]}〜{weekly_band[1]}候補×{candidate_all_in:,}）")
    print(f"    → 案(a)採用時の増分はHaiku一次読解分のみ（+{tri_low/1e6:.2f}〜{tri_high/1e6:.2f}M、"
          f"現行比 +{tri_low/weekly_now_high*100:.0f}〜+{tri_high/weekly_now_low*100:.0f}%だが全量Haiku級）")
    print(f"    → 案(b)採用時は最悪 +{(tri_high+res_add_high)/1e6:.2f}M/週（現行比 +{(tri_high+res_add_high)/weekly_now_low*100:.0f}%）")
    print("  ※ Haiku単価はSonnet級より約1桁安い（モデル階級はトークン数と別軸のコスト要素。第4条）。")
    print("  ※ TDnet取得・パース・キーワード分類・フロア照合は決定論スクリプト化すればLLMトークン消費ゼロ")
    print("    （kabutanフロア照合は約20〜45ページ/日のHTTP取得のみ）。")


# =================================================================================
# §6 統計的留保のための数値
# =================================================================================

def section6():
    print("\n" + "=" * 96)
    print("§6 統計的留保のための数値")
    print("=" * 96)
    k, n = 4, 5
    lo, hi = clopper_pearson(k, n)
    print(f"  TDnet捕捉率（開示起点実例）: {k}/{n} → 95%CI {lo*100:.0f}〜{hi*100:.0f}%")
    k2, n2 = 7, 15
    lo2, hi2 = clopper_pearson(k2, n2)
    print(f"  フロア通過率標本: {k2}/{n2} → 95%CI {lo2*100:.0f}〜{hi2*100:.0f}%")
    k3, n3 = 0, 7
    lo3, hi3 = clopper_pearson(k3, n3)
    print(f"  実例7件中『当日スキャンで利益機会に実際に間に合った』確証事例: {k3}/{n3}"
          f" → 95%CI上限 {hi3*100:.0f}%（＝『効かない』とも断定できない標本規模）")
    print("  供給実測は5完全営業日+1部分日（7月下旬）のみ。決算集中日・閑散期は未実測。")


# =================================================================================
# --live 再取得モード
# =================================================================================

def live_refetch():
    import subprocess
    import datetime
    import os
    import urllib.request
    import urllib.parse

    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    pat = re.compile(
        r'kjTime" noWrap>(\d{1,2}:\d{2})</td>\s*<td[^>]*kjCode" noWrap>([0-9A-Z]+)</td>'
        r'\s*<td[^>]*kjName" noWrap>([^<]+)</td>\s*<td[^>]*kjTitle"[^>]*>(?:<a[^>]*>)?([^<]+)')

    def fetch_day(d):
        rows_all, page, total = [], 1, None
        while True:
            url = f"https://www.release.tdnet.info/inbs/I_list_{page:03d}_{d}.html"
            r = subprocess.run(["curl", "-sS", "-A", UA, url], capture_output=True, timeout=60)
            html = r.stdout.decode("utf-8", "replace")
            m = re.search(r"全(\d+)件", html)
            if m:
                total = int(m.group(1))
            rows = pat.findall(html)
            if not rows:
                break
            rows_all += rows
            if total and len(rows_all) >= total:
                break
            page += 1
            if page > 12:
                break
        return total, rows_all

    print("\n[--live] TDnet再取得（取得日時 %sZ）" % datetime.datetime.utcnow().isoformat())
    for d in ["20260722", "20260723", "20260724", "20260727", "20260728", "20260729"]:
        try:
            total, rows = fetch_day(d)
            mat = set(r[1][:4] for r in rows if MATERIAL_PAT.search(r[3]))
            after = sum(1 for r in rows if int(r[0].split(":")[0]) * 60 + int(r[0].split(":")[1]) >= 930)
            print(f"  {d}: 全{total}件 パース{len(rows)}件 引け後{after}件 材料型{len(mat)}社")
        except Exception as e:
            print(f"  {d}: 取得失敗 {e}（過去日一覧の保持期限切れの可能性）")

    key = os.environ.get("EDINET_API_KEY")
    if key:
        print("[--live] EDINET再取得")
        for d in ["2026-07-28", "2026-07-29"]:
            try:
                url = (f"https://api.edinet-fsa.go.jp/api/v2/documents.json?date={d}&type=2"
                       f"&Subscription-Key={urllib.parse.quote(key)}")
                with urllib.request.urlopen(url, timeout=30) as r:
                    docs = json.load(r).get("results", [])
                listed = [x for x in docs if x.get("secCode")]
                print(f"  {d}: 総{len(docs)}件 上場コード付き{len(listed)}件")
            except Exception as e:
                print(f"  {d}: 取得失敗 {e}")
    else:
        print("[--live] EDINET_API_KEY未設定のためEDINET再取得はスキップ")


# =================================================================================
# main
# =================================================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="TDnet/EDINETを再取得して照合（外部依存）")
    args = ap.parse_args()

    print("Fable5 能動スキャン検証スクリプト（as_of 2026-07-29）")
    print("既定はオフライン決定論モード。埋め込み実測値の取得元・取得日時は FETCH_META と各節に記載。\n")

    section0()
    section1()
    section2()
    section3()
    rate, lo, hi, mat_avg = section4()
    section5(rate, mat_avg)
    section6()

    if args.live:
        live_refetch()

    print("\n完了。")


if __name__ == "__main__":
    main()
