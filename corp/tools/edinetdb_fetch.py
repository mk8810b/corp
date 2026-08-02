#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
edinetdb_fetch.py — EDINET DB（第三者構造化データAPI）連携ツール

Syntropia Research 企業調査部（RSH）・スクリーニング部門（SCR）向け。D-025（2026-08-02、
4週間の期限付き試験導入）に基づく。EDINETの有価証券報告書等をXBRL解析・構造化した
第三者サービス `https://edinetdb.jp` のAPIから、財務数値・企業マスタ・同業比較データを
取得する。

## 位置づけ（D-025、必ず守ること）

本サービスは **補助的な二次情報源** である。一次情報源（EDINET原本・企業IR・TDnet）を
置き換えるものではない。先方自身が利用規約で「XBRL解析・名寄せの過程で誤差が生じる
可能性があります。重要な判断を行う場合は、必ずEDINET原本または企業IR資料をご確認
ください」と免責している点に留意すること。

- **BUY判定に用いる数値・判断の結論を左右する数値は、本サービスの値のみを根拠にしない。**
  EDINET原本・決算短信・企業IRのいずれかで裏取りする（D-025 内容4）。
- WATCH/PASS判定の背景情報・同業比較の相対値は本サービス単独の引用を認めるが、
  出典として「EDINET DB（二次情報源）」である旨を成果物に明記する。

## AI生成コンテンツの使用禁止（D-025 内容3）

本サービスは `/v1/companies/{code}/analysis` でAI所見・ヘルススコア・信用スコアを提供するが、
**当社はこれらを一切使用しない**。他社のAIが生成した分析・評価を事実として成果物に引用する
ことは、絶対制約第2条が禁じるハルシネーションの間接的な混入に当たる。

本ツールは当該エンドポイントを**実装しない**ことでこれを機械的に担保する。さらに、
レスポンスに混入する `credit_score` / `credit_rating` / `ai_*` / `*_insight` 等のフィールドは
`_strip_ai_fields()` で取得後に除去する。採用してよいのはXBRL由来の数値フィールドと
企業マスタ（社名・業種・EDINETコード等）に限る。

## 認証（D-025 評価時に実地確認、2026-08-02）

- `GET /v1/search?q=<クエリ>` は **APIキー無し（匿名100回/日）で動作する**。
  証券コード→社名の同定検証はキー無しで即日運用できる（INC-001の直接的な再発防止策）。
- `/v1/companies/{code}/financials` 等の実データ系エンドポイントはAPIキー必須
  （キー無しでは `{"error":{"code":"auth_required"}}` が返る）。
- キー発行にはGoogle/Microsoft/メールでのアカウント登録が必要で、**登録はCEOが行う必要が
  ある**（EDINET公式APIと同じ制約）。手順は REGISTRATION_HELP 定数を参照。
- キーは環境変数 `EDINETDB_API_KEY` から読み込み、`X-API-Key` ヘッダで送信する。
  URLには含めない（ログ・出典表示への漏洩を構造的に防ぐため）。

## レート制限（D-025 内容6）

無料枠は100回/日。本ツールは1プロセスあたりの呼び出し回数を上限 `--max-calls`
（デフォルト50）で自衛的に打ち切る。100回/日を超える運用は行わない。超過が常態化する
場合は有料プランの要否をCEOが改めて裁定する（エージェントが独断で課金しない）。

## CLIの使い方

    # 証券コード→社名・業種の同定検証（APIキー不要。企業調査部の着手時に必須 — D-025 内容2）
    python3 corp/tools/edinetdb_fetch.py --resolve 5282

    # 上流工程が記載した社名との一致を機械的に検証（不一致なら終了コード2で停止）
    python3 corp/tools/edinetdb_fetch.py --resolve 5282 --expect-name "ジャニス工業"

    # 財務データ（P/L・B/S・CF、最大6期分。APIキー必須）
    python3 corp/tools/edinetdb_fetch.py --financials 4549

    # 財務指標（ROE・営業利益率・自己資本比率等。APIキー必須）
    python3 corp/tools/edinetdb_fetch.py --ratios 4549

    # 企業プロファイル＋直近財務（APIキー必須）
    python3 corp/tools/edinetdb_fetch.py --company 4549

    # 大株主（5%以上）・役員・子会社（APIキー必須）
    python3 corp/tools/edinetdb_fetch.py --shareholders 3923

    # JSON形式で出力（後続のPython処理へ渡す場合）
    python3 corp/tools/edinetdb_fetch.py --financials 4549 --json

絶対制約第2条（数値実在原則）に従い、すべての出力に「取得元URL」「取得日時」および
レスポンスの `data_as_of`（データ基準日）を明示する。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

BASE_URL = "https://edinetdb.jp/v1"
ENV_KEY_NAME = "EDINETDB_API_KEY"
USER_AGENT = "SyntropiaResearch-EdinetDbFetch/1.0 (research tool; contact via CEO)"
DEFAULT_MAX_CALLS = 50
FREE_TIER_DAILY_LIMIT = 100

# D-025 内容3: これらを含むフィールドは第三者AIの生成物・独自スコアであり成果物に取り込まない。
# 前方一致・部分一致の双方で除去する。
AI_FIELD_MARKERS = (
    "ai_",
    "_ai",
    "insight",
    "credit_score",
    "credit_rating",
    "health_score",
    "score",
    "comment",
    "summary_text",
    "analysis",
)

REGISTRATION_HELP = f"""\
EDINET DBの実データ系エンドポイント（財務・指標・スクリーナー等）の利用にはAPIキーが
必要です。キー発行にはアカウント登録（Google / Microsoft / メールアドレス）が必要であり、
自動化エージェントのこのセッション内では完結できません。CEOに以下の手順の実施を
依頼してください。

  1. ブラウザで次のURLにアクセスする:
     https://edinetdb.jp/developers
  2. Googleアカウント・Microsoftアカウント・メールアドレスのいずれかで登録する
     （先方はGoogleアカウントでの登録を推奨と記載）。
  3. 利用目的の選択画面で「AIエージェント連携」または「企業分析」を選ぶ。
  4. 登録完了後、APIキーが**一度だけ**画面に表示される。必ず控えること
     （再表示されない仕様のため）。
  5. 取得したAPIキーを環境変数 {ENV_KEY_NAME} に設定してから本ツールを実行する。
     例:  export {ENV_KEY_NAME}="発行されたキーの文字列"
          python3 corp/tools/edinetdb_fetch.py --financials 4549

なお、証券コード→社名の同定検証（--resolve）はAPIキー無しで動作するため、上記の登録前でも
実行できます（D-025 内容2の再発防止策は即日運用可能）。

参考: 料金プランは無料枠100回/日。D-025は無料枠のみの使用を定めており、エージェントが
独断で有料プランに移行することを禁じています。
"""


class EdinetDbAuthError(RuntimeError):
    """APIキーが未設定、または無効な場合に送出する。"""


class EdinetDbAPIError(RuntimeError):
    """EDINET DB APIがエラーステータス・エラーボディを返した場合に送出する。"""


class RateGuardError(RuntimeError):
    """1プロセスあたりの自衛的な呼び出し上限に達した場合に送出する。"""


_call_count = 0
_max_calls = DEFAULT_MAX_CALLS


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def get_api_key(explicit: Optional[str] = None) -> str:
    key = explicit or os.environ.get(ENV_KEY_NAME)
    if not key:
        raise EdinetDbAuthError(
            f"環境変数 {ENV_KEY_NAME} が未設定です。\n\n" + REGISTRATION_HELP
        )
    return key


def _strip_ai_fields(obj: Any) -> Any:
    """第三者AIの生成物・独自スコアに該当するフィールドを再帰的に除去する（D-025 内容3）。

    絶対制約第2条は出典を示せない数値・記憶ベースの数値の記載を禁じる。第三者のAIが
    生成した所見・スコアは、その算出根拠を当社が検証できないため、事実として成果物に
    取り込めばハルシネーションを間接的に混入させることになる。取得段階で機械的に落とす。
    """
    if isinstance(obj, dict):
        cleaned = {}
        for k, v in obj.items():
            lowered = str(k).lower()
            if any(marker in lowered for marker in AI_FIELD_MARKERS):
                continue
            cleaned[k] = _strip_ai_fields(v)
        return cleaned
    if isinstance(obj, list):
        return [_strip_ai_fields(v) for v in obj]
    return obj


def _request(path: str, params: Optional[dict] = None, api_key: Optional[str] = None) -> dict:
    """EDINET DB APIへGETし、JSONを返す。

    api_key が None の場合は匿名アクセス（/v1/search 等のみ許可される）。
    APIキーは X-API-Key ヘッダで送る。URLには絶対に含めない（第2条の出典記録時に
    キーが漏洩することを構造的に防ぐため）。
    """
    global _call_count
    if _call_count >= _max_calls:
        raise RateGuardError(
            f"1プロセスあたりの呼び出し上限（{_max_calls}回）に達しました。"
            f"EDINET DBの無料枠は{FREE_TIER_DAILY_LIMIT}回/日です（D-025 内容6）。"
            "必要であれば --max-calls で上限を引き上げてください（日次上限は超えないこと）。"
        )

    query = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v is not None})
    url = f"{BASE_URL}{path}" + (f"?{query}" if query else "")

    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key

    req = urllib.request.Request(url, headers=headers)
    _call_count += 1
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        if exc.code in (401, 403):
            raise EdinetDbAuthError(
                f"認証エラー（HTTP {exc.code}）: {url}\n{body}\n\n" + REGISTRATION_HELP
            ) from exc
        if exc.code == 429:
            raise EdinetDbAPIError(
                f"レート制限（HTTP 429）: {url}\n{body}\n"
                f"無料枠は{FREE_TIER_DAILY_LIMIT}回/日です（D-025 内容6）。"
                "本日の実行を停止し、翌日以降に再試行してください。"
            ) from exc
        raise EdinetDbAPIError(f"HTTP {exc.code}: {url}\n{body}") from exc

    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EdinetDbAPIError(f"レスポンスのJSON解析に失敗: {url}") from exc

    # 200で返しつつボディにエラーを載せるケース（認証必須エンドポイントへのキー無しアクセス等）
    if isinstance(data, dict) and "error" in data:
        err = data.get("error") or {}
        code = err.get("code", "")
        message = err.get("message", "")
        if code == "auth_required" or "api key" in str(message).lower():
            raise EdinetDbAuthError(
                f"このエンドポイントはAPIキーが必要です: {url}\n{message}\n\n" + REGISTRATION_HELP
            )
        raise EdinetDbAPIError(f"APIエラー: {url}\ncode={code} message={message}")

    data = _strip_ai_fields(data)
    data["_provenance"] = {
        "source_url": url,
        "fetched_at": _now_iso(),
        "source_kind": "EDINET DB（第三者構造化データAPI・二次情報源、D-025）",
        "note": (
            "BUY判定に用いる数値・結論を左右する数値はEDINET原本/決算短信/企業IRで裏取りすること"
            "（D-025 内容4。先方も名寄せ誤差の可能性を免責表示している）"
        ),
    }
    return data


# ---------------------------------------------------------------------------
# 1. 証券コード → 社名・業種の同定検証（APIキー不要・INC-001の再発防止策）
# ---------------------------------------------------------------------------

def resolve(sec_code: str) -> dict:
    """証券コードから企業マスタを引く（APIキー不要）。

    EDINET DBの sec_code は末尾に0を付した5桁表記（例: 5282 → "52820"）。検索結果には
    部分一致の別会社も混ざるため、5桁表記の完全一致で絞り込む。
    """
    data = _request("/search", {"q": sec_code})
    candidates = data.get("data") or []
    want = f"{sec_code}0"
    exact = [c for c in candidates if str(c.get("sec_code", "")) == want]
    return {
        "sec_code": sec_code,
        "matched": exact[0] if exact else None,
        "other_candidates": [c for c in candidates if str(c.get("sec_code", "")) != want],
        "meta": data.get("meta", {}),
        "_provenance": data["_provenance"],
    }


# ---------------------------------------------------------------------------
# 2. 実データ系（APIキー必須）
#    注: /companies/{code}/analysis はD-025 内容3により意図的に実装しない。
# ---------------------------------------------------------------------------

def company(sec_code: str, api_key: str) -> dict:
    return _request(f"/companies/{sec_code}", api_key=api_key)


def financials(sec_code: str, api_key: str) -> dict:
    return _request(f"/companies/{sec_code}/financials", api_key=api_key)


def ratios(sec_code: str, api_key: str) -> dict:
    return _request(f"/companies/{sec_code}/ratios", api_key=api_key)


def earnings(sec_code: str, api_key: str) -> dict:
    return _request(f"/companies/{sec_code}/earnings", api_key=api_key)


def shareholders(sec_code: str, api_key: str) -> dict:
    return _request(f"/companies/{sec_code}/shareholders", api_key=api_key)


def screener(api_key: str, **params) -> dict:
    return _request("/screener", params or None, api_key=api_key)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_provenance(prov: dict) -> None:
    print("  --- 出典（絶対制約第2条） ---")
    print(f"  取得元URL : {prov.get('source_url')}")
    print(f"  取得日時   : {prov.get('fetched_at')}")
    print(f"  情報源区分 : {prov.get('source_kind')}")
    print(f"  留意       : {prov.get('note')}")


def _print_resolve(result: dict, expect_name: Optional[str]) -> int:
    code = result["sec_code"]
    matched = result["matched"]
    meta = result.get("meta", {})
    print(f"=== 証券コード {code} → 企業マスタ照合（EDINET DB、APIキー不要） ===")
    if not matched:
        print(f"  一致なし: 証券コード {code} に完全一致する企業が見つかりませんでした。")
        if result["other_candidates"]:
            print("  参考（部分一致の別会社。取り違えに注意）:")
            for c in result["other_candidates"][:5]:
                print(f"    - {c.get('sec_code')} {c.get('name_ja')}（{c.get('industry')}）")
        print(f"  データ基準日: {meta.get('data_as_of', '取得不能')}")
        _print_provenance(result["_provenance"])
        return 2

    print(f"  社名       : {matched.get('name_ja')}")
    print(f"  英文社名   : {matched.get('name_en')}")
    print(f"  業種       : {matched.get('industry')}")
    print(f"  EDINETコード: {matched.get('edinet_code')}")
    print(f"  上場状態   : {matched.get('listing_status')}（廃止={matched.get('is_delisted')}）")
    print(f"  データ基準日: {meta.get('data_as_of', '取得不能')}")
    _print_provenance(result["_provenance"])

    if expect_name:
        actual = str(matched.get("name_ja") or "")
        # 「株式会社」「(株)」等の表記ゆれを吸収して比較する
        def _norm(s: str) -> str:
            for noise in ("株式会社", "(株)", "（株）", " ", "　"):
                s = s.replace(noise, "")
            return s
        if _norm(expect_name) and _norm(expect_name) in _norm(actual):
            print(f"\n  [OK] 上流工程の記載社名「{expect_name}」と一致しました。")
            return 0
        print(
            f"\n  [不一致] 上流工程の記載社名「{expect_name}」と、証券コード {code} の"
            f"実体「{actual}」が一致しません。\n"
            "  D-025 内容2に従い、調査を進める前に上流工程（スクリーニング）へ差し戻してください。\n"
            "  （INC-001と同型の事象です。corp/incidents.md を参照）"
        )
        return 2
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    global _max_calls

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--resolve", metavar="CODE", help="証券コード→社名・業種の同定検証（APIキー不要）")
    parser.add_argument("--expect-name", help="--resolveと併用。上流工程が記載した社名との一致を検証し、不一致なら終了コード2")
    parser.add_argument("--company", metavar="CODE", help="企業プロファイル＋直近財務（要APIキー）")
    parser.add_argument("--financials", metavar="CODE", help="財務データ（P/L・B/S・CF、最大6期分。要APIキー）")
    parser.add_argument("--ratios", metavar="CODE", help="財務指標（ROE・利益率・自己資本比率等。要APIキー）")
    parser.add_argument("--earnings", metavar="CODE", help="直近決算サマリ（要APIキー）")
    parser.add_argument("--shareholders", metavar="CODE", help="大株主（5%%以上）（要APIキー）")
    parser.add_argument("--json", action="store_true", help="JSON形式で出力する")
    parser.add_argument("--api-key", help=f"APIキー（省略時は環境変数 {ENV_KEY_NAME} を使用）")
    parser.add_argument(
        "--max-calls",
        type=int,
        default=DEFAULT_MAX_CALLS,
        help=f"1プロセスあたりの呼び出し上限（デフォルト{DEFAULT_MAX_CALLS}。無料枠は{FREE_TIER_DAILY_LIMIT}回/日）",
    )
    args = parser.parse_args(argv)
    _max_calls = args.max_calls

    try:
        if args.resolve:
            result = resolve(args.resolve)
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 0 if result["matched"] else 2
            return _print_resolve(result, args.expect_name)

        keyed = {
            "company": args.company,
            "financials": args.financials,
            "ratios": args.ratios,
            "earnings": args.earnings,
            "shareholders": args.shareholders,
        }
        selected = [(name, code) for name, code in keyed.items() if code]
        if not selected:
            parser.print_help()
            return 1
        if len(selected) > 1:
            print("エラー: 実データ系のオプションは1回につき1つだけ指定してください。", file=sys.stderr)
            return 1

        name, code = selected[0]
        api_key = get_api_key(args.api_key)
        fn = {
            "company": company,
            "financials": financials,
            "ratios": ratios,
            "earnings": earnings,
            "shareholders": shareholders,
        }[name]
        data = fn(code, api_key)

        if args.json:
            print(json.dumps(data, ensure_ascii=False, indent=2))
            return 0

        prov = data.pop("_provenance")
        print(f"=== {name} / 証券コード {code}（EDINET DB） ===")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        _print_provenance(prov)
        print(
            "\n  ※ D-025 内容3により、AI所見・ヘルススコア・信用スコア等の第三者AI生成"
            "フィールドは取得段階で除去済みです（成果物に取り込まないこと）。"
        )
        return 0

    except (EdinetDbAuthError, EdinetDbAPIError, RateGuardError) as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
