#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tdnet_scan.py — TDnet日次一覧の能動スキャンツール（D-024、2026-07-29新設・4週間の試験運用）

Syntropia Research スクリーニング部（SCR）向け。D-012エッジ仮説（適時開示の当日読み込みに
よる未認知事実の発見）の実行経路として、TDnet適時開示情報閲覧サービスの日次一覧を取得し、
機械フィルタ（材料型キーワード判定→フロア照合→除外リスト適用）のみをLLMトークンゼロで行う。
設計根拠: `outputs/review/2026-07-29-fable5-proactive-scan-review.md`。
運用定義: `playbooks/screening.md` 2-4節、`corp/RUNBOOK.md`「朝スキャンルーチン」節。

## 提供する機能

1. `fetch_tdnet_day(date_str)`        : 指定日のTDnet日次一覧を取得（全ページ、時刻・コード・
                                          会社名・表題のタプルのリスト）
2. `is_material(title)`               : 表題文字列から材料型開示かを機械判定（キーワード正規表現。
                                          第2条: 分類器は粗く、誤検知・見落としがあり得る）
3. `check_floor(code)`                : kabutan.jp確定終値ページから直近20営業日の終値・出来高を
                                          取得し、D-004/D-009/D-013のフロア条件を機械判定する
4. `load_exclusion_codes(...)`        : `corp/portfolio.md`（状態=HELD）・`corp/watchlist.md`
                                          （状態=ACTIVE）からコードを読み取り、除外集合を作る
5. `scan(date_str, ...)`              : 1〜4を組み合わせ、優先度スコア付きの候補リストを返す

## CLIの使い方

    # 指定日のTDnet一覧を取得し、材料型×フロア通過の候補を一覧表示（保有・WATCH銘柄は除外）
    python3 corp/tools/tdnet_scan.py --date 2026-07-30

    # 時刻帯を絞る（朝スキャン: 前営業日引け後+当日寄り前 / 日次拡張: 当日場中のみ等）
    python3 corp/tools/tdnet_scan.py --date 2026-07-30 --after-hours-only
    python3 corp/tools/tdnet_scan.py --date 2026-07-30 --intraday-only

    # JSON出力（後続のHaiku一次読解・企業調査への引き渡しに使う）
    python3 corp/tools/tdnet_scan.py --date 2026-07-30 --json

備考: 出来高急増率等の値動き軸（screening.md 2-1の軸C）とは独立。本ツールは開示起点のみを扱い、
値動きは一切参照しない（能動スキャンの設計思想そのもの——事前検出、事後の値動き選抜ではない）。
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Iterable, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
TDNET_URL_TMPL = "https://www.release.tdnet.info/inbs/I_list_{page:03d}_{yyyymmdd}.html"
KABUTAN_KABUKA_URL_TMPL = "https://kabutan.jp/stock/kabuka?code={code}&ashi=day&page=1"

# 材料型キーワード（前回Fable5レビュー2026-07-29検証で使用したものと同一。第2条: 粗い分類器であり
# 「受注」等の定型的な月次開示も拾いうる。試験運用中の較正対象——playbooks/screening.md 2-4参照）
MATERIAL_PAT = re.compile(
    r"決算短信|業績予想|業績の修正|配当予想|配当の修正|上方修正|下方修正|剰余金の配当|自己株式取得|"
    r"株式分割|業務提携|資本提携|経営統合|合併|買収|子会社化|株式交換|株式移転|TOB|公開買付|MBO|"
    r"特別利益|特別損失|新製品|新技術|大口受注|受注|業績に関する|月次|通期業績|中間配当"
)

_TDNET_ROW_PAT = re.compile(
    r'kjTime"[^>]*>(\d{1,2}:\d{2})</td>\s*'
    r'<td[^>]*kjCode"[^>]*>([0-9A-Z]{4,5})</td>\s*'
    r'<td[^>]*kjName"[^>]*>([^<]+)</td>\s*'
    r'<td[^>]*kjTitle"[^>]*>(?:<a[^>]*>)?([^<]+)'
)


def _now_iso() -> str:
    # Date.now()相当の絶対時刻はツール実行環境のシステム時計に依存する（第2条: 呼び出し側が
    # 取得日時を記録する。本関数はログ出力の便宜のみに使う）。
    import datetime

    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _curl_get(url: str, timeout: int = 30, tries: int = 4) -> str:
    """curlでGETする（一過性の失敗はリトライする）。

    2026-08-06・08-07の朝スキャンで、数百銘柄のフロア照合の途中に一過性のcurl失敗
    （code=35 `Recv failure: Connection reset by peer`、code=18 `Transferred a partial file`）が
    発生し、**リトライが無いためスキャン全体が異常終了する**事象が2営業日連続で起きた。
    ネットワーク層の一過性エラーで必須ルーチンが止まるのは実行可能性の問題であり、
    判定基準・フィルタ条件・データソースには一切影響しない純粋な堅牢化として指数バックオフの
    リトライを入れる（憲法第8章の範囲内。D-026と同じく「判定を変えず、失敗を減らすだけ」）。
    リトライを尽くしても失敗した場合は従来どおり例外を送出する（第2条: 黙って空データを
    返さない）。
    """
    last = None
    for attempt in range(tries):
        try:
            r = subprocess.run(
                ["curl", "-sS", "-A", UA, url], capture_output=True, timeout=timeout
            )
            if r.returncode == 0:
                return r.stdout.decode("utf-8", "replace")
            last = f"curl failed (code={r.returncode}): {url}\n{r.stderr.decode('utf-8', 'replace')}"
        except subprocess.TimeoutExpired as e:  # noqa: PERF203
            last = f"curl timeout ({timeout}s): {url}\n{e}"
        if attempt < tries - 1:
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"{last}\n（{tries}回リトライしても失敗）")


def fetch_tdnet_day(date_str: str, max_pages: int = 12) -> list[tuple[str, str, str, str]]:
    """指定日（YYYY-MM-DD）のTDnet日次一覧を全ページ取得する。

    戻り値: [(時刻HH:MM, コード, 会社名, 表題), ...]（一覧の掲載順）
    取得元: https://www.release.tdnet.info/inbs/I_list_NNN_YYYYMMDD.html （curl・UA指定）

    注: TDnetのkjCode欄は証券コードにチェックデジット相当の桁を1つ付した5桁表記
    （例: 実際の証券コード「3903」→ TDnet表示「39030」、「310A」→「310A0」）。
    本関数は末尾1桁を除去し、他の台帳（corp/watchlist.md・corp/portfolio.md等）と
    同じ4桁（英字混在含む）の証券コード表記に正規化して返す。
    """
    yyyymmdd = date_str.replace("-", "")
    rows: list[tuple[str, str, str, str]] = []
    total: Optional[int] = None
    for page in range(1, max_pages + 1):
        url = TDNET_URL_TMPL.format(page=page, yyyymmdd=yyyymmdd)
        html = _curl_get(url)
        m = re.search(r"全(\d+)件", html)
        if m:
            total = int(m.group(1))
        page_rows = _TDNET_ROW_PAT.findall(html)
        if not page_rows:
            break
        rows.extend(page_rows)
        if total is not None and len(rows) >= total:
            break
    normalized = [(t, code[:-1] if len(code) == 5 else code, name, title) for t, code, name, title in rows]
    return normalized


def _time_to_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def filter_by_time_window(
    rows: Iterable[tuple[str, str, str, str]],
    *,
    after_hours_only: bool = False,
    intraday_only: bool = False,
    pre_open_only: bool = False,
) -> list[tuple[str, str, str, str]]:
    """時刻帯で絞り込む。引け後(>=15:30)・寄り前(<9:00)・場中(9:00-15:30)の3区分。

    朝スキャン（D-024）は「前営業日引け後分＋当日寄り前分」を対象とするため、通常は
    after_hours_only と pre_open_only を別々の日付に対して呼び出し、結果を結合する運用を想定する。
    """
    out = []
    for t, code, name, title in rows:
        minutes = _time_to_minutes(t)
        if after_hours_only and minutes < 930:  # 15:30
            continue
        if pre_open_only and minutes >= 540:  # 9:00
            continue
        if intraday_only and not (540 <= minutes < 930):
            continue
        out.append((t, code, name, title))
    return out


def is_material(title: str) -> bool:
    return bool(MATERIAL_PAT.search(title))


def _parse_kabuka_history(html: str) -> list[dict]:
    text = re.sub(r"<[^>]+>", "|", html)
    text = text.replace("\r\n", "\n")
    pattern = re.compile(
        r"(\d{2}/\d{2}/\d{2})\|\|\n"
        r"\|([\d,.]+)\|\n\|([\d,.]+)\|\n\|([\d,.]+)\|\n\|([\d,.]+)\|\n"
        r"\|?\|?([+\-][\d,.]+|0)\|?\|?\n"
        r"\|?\|?([+\-][\d,.]+|0\.00)\|?\|?\n"
        r"\|([\d,]+)\|"
    )
    rows = []
    for m in pattern.finditer(text):
        date, o, h, l, c, chg, chgp, vol = m.groups()
        rows.append({"date": date, "close": float(c.replace(",", "")), "volume": int(vol.replace(",", ""))})
    return rows


def check_floor(code: str) -> dict:
    """kabutan.jp確定終値ページから直近20営業日データを取得し、D-004/D-009/D-013を機械判定する。

    戻り値: dict(code, close, avg_vol_20, avg_turnover_oku, price_ok, liquidity_ok, floor_pass,
                 source_url, reason)
    取得元・取得日時は呼び出し側（本関数のreturn値のsource_url/fetched_at）に記録する（第2条）。
    """
    url = KABUTAN_KABUKA_URL_TMPL.format(code=code)
    html = _curl_get(url)
    rows = _parse_kabuka_history(html)
    if not rows:
        return dict(
            code=code, close=None, avg_vol_20=None, avg_turnover_oku=None,
            price_ok=False, liquidity_ok=False, floor_pass=False,
            source_url=url, fetched_at=_now_iso(), reason="取得不能（価格データの解析に失敗）",
        )
    latest = rows[0]
    hist = rows[:20]
    avg_vol = statistics.mean(r["volume"] for r in hist)
    avg_turnover_oku = statistics.mean(r["close"] * r["volume"] for r in hist) / 1e8
    price_ok = 100 <= latest["close"] <= 3000
    liquidity_ok = (avg_vol >= 100_000) or (avg_turnover_oku >= 1.0)
    floor_pass = price_ok and liquidity_ok
    reason = []
    if not price_ok:
        reason.append(f"価格帯フロア対象外（終値{latest['close']:.0f}円、D-009/D-013: 100〜3,000円）")
    if not liquidity_ok:
        reason.append(
            f"流動性フロア未達（平均出来高{avg_vol:,.0f}株・平均売買代金{avg_turnover_oku:.2f}億円、D-004: "
            f"10万株以上または1億円以上）"
        )
    return dict(
        code=code, close=latest["close"], avg_vol_20=round(avg_vol, 1),
        avg_turnover_oku=round(avg_turnover_oku, 3),
        price_ok=price_ok, liquidity_ok=liquidity_ok, floor_pass=floor_pass,
        source_url=url, fetched_at=_now_iso(),
        reason="フロア通過" if floor_pass else "; ".join(reason),
    )


def _parse_watchlist_active_codes(path: Path) -> set[str]:
    if not path.exists():
        return set()
    text = path.read_text(encoding="utf-8")
    codes = set()
    in_table = False
    for line in text.splitlines():
        if line.startswith("| コード |"):
            in_table = True
            continue
        if in_table:
            if not line.startswith("|"):
                if codes:
                    in_table = False
                continue
            cols = [c.strip() for c in line.strip("|").split("|")]
            if len(cols) < 4:
                continue
            code, state = cols[0], cols[3]
            if "ACTIVE" in state and re.match(r"^[0-9A-Z]{4,5}$", code):
                codes.add(code)
    return codes


def _parse_portfolio_held_codes(path: Path) -> set[str]:
    if not path.exists():
        return set()
    text = path.read_text(encoding="utf-8")
    codes = set()
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) < 2:
            continue
        code = cols[0]
        if re.match(r"^[0-9A-Z]{4,5}$", code) and "HELD" in line:
            codes.add(code)
    return codes


def load_exclusion_codes(
    watchlist_path: Optional[Path] = None, portfolio_path: Optional[Path] = None
) -> set[str]:
    """corp/watchlist.md（状態=ACTIVE）・corp/portfolio.md（状態=HELD）からコードを収集する。

    朝スキャンの候補は既存イベント駆動ルーチンとの重複を避けるため、これらのコードを除外する
    （`playbooks/screening.md` 2-4節・`corp/RUNBOOK.md`「朝スキャンルーチン」節参照）。
    """
    watchlist_path = watchlist_path or (REPO_ROOT / "corp" / "watchlist.md")
    portfolio_path = portfolio_path or (REPO_ROOT / "corp" / "portfolio.md")
    return _parse_watchlist_active_codes(watchlist_path) | _parse_portfolio_held_codes(portfolio_path)


NON_EQUITY_NAME_PAT = re.compile(
    r"ベア|ブル|ＥＴＦ|ETF|ＥＴＮ|ETN|REIT|上場投信|上場投資信託|インデックス|連動証券"
)


def is_non_equity_instrument(name: str) -> bool:
    """ETF/ETN等、個別株ではない上場商品らしき名称かを判定する（2026-07-30発見: 材料型
    キーワード判定のみではETF/ETNの決算短信等が候補に混入するフィルタ漏れがあったため追加）。
    """
    return bool(NON_EQUITY_NAME_PAT.search(name))


def scan(
    date_str: str,
    *,
    time_window: str = "after-hours",
    exclude_codes: Optional[set[str]] = None,
    check_floor_for_candidates: bool = True,
) -> dict:
    """1回のスキャンを実行する。

    time_window: "after-hours"（引け後>=15:30） / "pre-open"（寄り前<9:00） /
                 "intraday"（場中9:00-15:30、日次ルーチンの当日反応突合用） / "all"
    """
    rows = fetch_tdnet_day(date_str)
    if time_window == "after-hours":
        rows = filter_by_time_window(rows, after_hours_only=True)
    elif time_window == "pre-open":
        rows = filter_by_time_window(rows, pre_open_only=True)
    elif time_window == "intraday":
        rows = filter_by_time_window(rows, intraday_only=True)
    # time_window == "all" の場合はフィルタしない

    exclude_codes = exclude_codes or set()
    material_rows = [(t, c, n, title) for t, c, n, title in rows if is_material(title)]
    uniq_codes = {}
    for t, c, n, title in material_rows:
        if c in exclude_codes:
            continue
        if is_non_equity_instrument(n):
            continue
        uniq_codes.setdefault(c, {"name": n, "titles": [], "times": []})
        uniq_codes[c]["titles"].append(title)
        uniq_codes[c]["times"].append(t)

    candidates = []
    for code, info in uniq_codes.items():
        entry = dict(code=code, name=info["name"], titles=info["titles"], times=info["times"])
        if check_floor_for_candidates:
            entry["floor"] = check_floor(code)
        candidates.append(entry)

    return dict(
        date=date_str,
        time_window=time_window,
        total_disclosures=len(rows),
        material_disclosures=len(material_rows),
        material_unique_companies=len(uniq_codes),
        excluded_held_or_watchlist=sum(
            1 for t, c, n, title in [(t, c, n, title) for t, c, n, title in rows if is_material(title)]
            if c in exclude_codes
        ),
        candidates=candidates,
        source_url_pattern=TDNET_URL_TMPL,
        fetched_at=_now_iso(),
    )


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", required=True, help="対象日 YYYY-MM-DD（TDnet日次一覧の日付）")
    ap.add_argument("--after-hours-only", action="store_true", help="引け後(>=15:30)提出分のみ")
    ap.add_argument("--pre-open-only", action="store_true", help="寄り前(<9:00)提出分のみ")
    ap.add_argument("--intraday-only", action="store_true", help="場中(9:00-15:30)提出分のみ")
    ap.add_argument("--no-floor-check", action="store_true", help="フロア照合をスキップ（高速・粗い一覧のみ）")
    ap.add_argument("--no-exclude", action="store_true", help="保有/WATCH銘柄の除外を行わない")
    ap.add_argument("--json", action="store_true", help="JSON形式で出力")
    args = ap.parse_args(argv)

    if args.after_hours_only:
        window = "after-hours"
    elif args.pre_open_only:
        window = "pre-open"
    elif args.intraday_only:
        window = "intraday"
    else:
        window = "all"

    exclude = set() if args.no_exclude else load_exclusion_codes()
    result = scan(
        args.date,
        time_window=window,
        exclude_codes=exclude,
        check_floor_for_candidates=not args.no_floor_check,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(f"TDnet能動スキャン結果（D-024） — 対象日: {result['date']}（時間帯: {result['time_window']}）")
    print(f"取得元パターン: {result['source_url_pattern']}")
    print(f"取得日時: {result['fetched_at']}")
    print(f"全開示件数: {result['total_disclosures']} / 材料型件数: {result['material_disclosures']} / "
          f"材料型ユニーク社数: {result['material_unique_companies']}")
    print(f"保有/WATCH銘柄として除外: {result['excluded_held_or_watchlist']}件\n")
    for c in result["candidates"]:
        floor = c.get("floor")
        if floor:
            status = "○通過" if floor["floor_pass"] else f"×除外（{floor['reason']}）"
            print(f"  {c['code']} {c['name']}: {status}")
        else:
            print(f"  {c['code']} {c['name']}: （フロア照合未実施）")
        for t, title in zip(c["times"], c["titles"]):
            print(f"      {t} {title}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
