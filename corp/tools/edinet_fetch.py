#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
edinet_fetch.py — EDINET API（金融庁 開示書類閲覧システム）連携ツール

Syntropia Research 企業調査部（RSH）向け。D-012（エッジ仮説: 適時開示・決算イベント駆動）の
中核機能として、WebFetch/curlでは本文取得できないEDINETの適時開示・有価証券報告書・
臨時報告書等を、EDINET公式APIから直接取得する。

## 前提（2026-07-09 調査で確定した事実。すべて実際のcurl/pdftotext検証済み）

- EDINET APIのベースURLは `https://api.edinet-fsa.go.jp/api/v2` であり、このサンドボックス
  環境から到達可能（curlでHTTP 200を確認済み）。
- ただし v2 API は「Subscription-Key」（無料のAPIキー）が必須。キー無し/不正キーの場合は
  HTTPステータス200でボディに `{"StatusCode": 401, "message": "Access denied due to invalid
  subscription key...."}` が返る（EDINET API仕様書 Version 2, 2026年6月, 金融庁 3-3節）。
- APIキーの取得は https://api.edinet-fsa.go.jp/api/auth/index.aspx?mode=1 から行う、
  メール確認コード入力＋SMS/自動音声による多要素認証を要する対話的フローであり、
  自動化エージェントのこのセッション内では完結できない（登録はCEOが行う必要がある。
  詳細は REGISTRATION_HELP 定数、および corp/RUNBOOK.md「既知の技術的制約」節を参照）。
- 一方、証券コード⇔EDINETコードの対応表（EDINETコードリスト）は認証不要の公開ZIPとして
  配布されており（https://disclosure2dl.edinet-fsa.go.jp/searchdocument/codelist/Edinetcode.zip）、
  このツールはAPIキーが無くてもコード解決までは実行できる（実際に9432→E04430等で検証済み）。

## 提供する機能

1. `resolve_edinet_code(sec_code)`      : 証券コード → EDINETコード・提出者名の解決（公開データ、キー不要）
2. `list_documents_by_date(date)`       : 指定日の書類一覧を取得（書類一覧API、キー必須）
3. `search_documents(...)`              : 証券コード/EDINETコード×日付範囲で書類一覧を横断検索（キー必須）
4. `download_document(doc_id, doc_type)`: 書類（XBRL/PDF/CSV等）をダウンロード（書類取得API、キー必須）

## CLIの使い方

    # 証券コード9432（NTT）について直近7日間の書類一覧を検索
    python3 corp/tools/edinet_fetch.py --code 9432 --days 7

    # EDINETコードを直接指定して日付範囲で検索
    python3 corp/tools/edinet_fetch.py --edinet-code E04430 --start-date 2026-07-01 --end-date 2026-07-09

    # 書類IDを指定して書類本体（type=1: 提出本文書+監査報告書+XBRL, 2: PDF, 5: CSV等）をダウンロード
    python3 corp/tools/edinet_fetch.py --doc-id S100XXXX --doc-type 2 --out-dir corp/tools/downloads

    # APIキー無しでも証券コード→EDINETコードの解決だけは確認できる（動作確認用）
    python3 corp/tools/edinet_fetch.py --code 9432 --resolve-only

APIキーは環境変数 `EDINET_API_KEY` から読み込む。未設定の場合、書類一覧・書類取得の
呼び出しは実行前に明確なエラーメッセージ（登録手順つき）で停止する。

絶対制約第2条（数値実在原則）に従い、すべての出力に「取得元URL」と「取得日時」を明示する。
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Iterable, Optional

BASE_URL = "https://api.edinet-fsa.go.jp/api/v2"
CODELIST_URL = "https://disclosure2dl.edinet-fsa.go.jp/searchdocument/codelist/Edinetcode.zip"
TOOL_DIR = Path(__file__).resolve().parent
CACHE_DIR = TOOL_DIR / ".cache"
CODELIST_CACHE_ZIP = CACHE_DIR / "Edinetcode.zip"
DEFAULT_DOWNLOAD_DIR = TOOL_DIR / "downloads"
ENV_KEY_NAME = "EDINET_API_KEY"
USER_AGENT = "SyntropiaResearch-EdinetFetch/1.0 (research tool; contact via CEO)"

# 書類取得APIの type パラメータ（EDINET API仕様書 3-2-1節）
DOC_TYPE_NAMES = {
    "1": "提出本文書及び監査報告書（ZIP, XBRL含む）",
    "2": "PDF",
    "3": "代替書面・添付文書（ZIP）",
    "4": "英文ファイル（ZIP）",
    "5": "CSV（ZIP）",
}

# 書類種別コード（抜粋。EDINET API仕様書 別紙「書類種別コード」より、調査で使う頻度が高いもの）
DOC_TYPE_CODE_NAMES = {
    "030": "有価証券届出書",
    "120": "有価証券報告書",
    "130": "訂正有価証券報告書",
    "140": "四半期報告書",
    "150": "訂正四半期報告書",
    "160": "半期報告書",
    "180": "臨時報告書",
    "190": "訂正臨時報告書",
    "220": "自己株券買付状況報告書",
    "235": "内部統制報告書",
    "350": "大量保有報告書",
}

REGISTRATION_HELP = """\
EDINET APIの利用には無料の「Subscription-Key」（APIキー）の取得が必要です。
このキー登録はメール確認コード入力＋SMS/自動音声による多要素認証を要する対話的フローで
あり、自動化エージェントのこのセッション内では完結できません。CEOに以下の手順の実施を
依頼してください。

  1. ブラウザで次のURLにアクセスする:
     https://api.edinet-fsa.go.jp/api/auth/index.aspx?mode=1
     （Microsoft Azure AD B2C の認証画面にリダイレクトされます。動作確認済み: 2026-07-09）
  2. メールアドレスを登録し、届いた確認コードを入力する。
  3. パスワードを設定する（12〜256文字。英大文字・小文字・数字・記号のうち3種類以上）。
  4. 多要素認証として電話番号を登録し、SMSまたは自動音声で本人確認する
     （携帯番号が080/090始まりの場合、国番号は+81を選び、電話番号欄には先頭の0を除いた
     番号を入力する）。
  5. 認証完了後に表示される画面で連絡先情報を入力し「連絡先登録」をクリックすると、
     画面上にAPIキー（Subscription-Key）が表示される。
  6. 取得したAPIキーを環境変数 EDINET_API_KEY に設定してから本ツールを実行する。
     例:  export EDINET_API_KEY="発行されたキーの文字列"
          python3 corp/tools/edinet_fetch.py --code 9432 --days 7

参考資料: EDINET API仕様書（Version 2, 2026年6月, 金融庁企画市場局企業開示課）
  https://disclosure2dl.edinet-fsa.go.jp/guide/static/disclosure/download/ESE140206.pdf
"""


class EdinetAuthError(RuntimeError):
    """APIキーが未設定、または無効な場合に送出する。"""


class EdinetAPIError(RuntimeError):
    """EDINET APIがエラーステータス（400/404/429/500等）を返した場合に送出する。"""


def _now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def get_api_key(explicit: Optional[str] = None) -> str:
    key = explicit or os.environ.get(ENV_KEY_NAME)
    if not key:
        raise EdinetAuthError(
            f"環境変数 {ENV_KEY_NAME} が未設定です（EDINET APIの利用にはAPIキーが必須）。\n\n"
            + REGISTRATION_HELP
        )
    return key


def _http_get_bytes(url: str, timeout: int = 30) -> tuple[bytes, dict]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
        headers = dict(resp.headers.items())
    return body, headers


def _build_url(path: str, params: dict) -> str:
    query = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
    return f"{BASE_URL}{path}?{query}" if query else f"{BASE_URL}{path}"


# ---------------------------------------------------------------------------
# 1. 証券コード ⇔ EDINETコードの解決（EDINETコードリスト、認証不要・公開データ）
# ---------------------------------------------------------------------------

def _download_codelist(refresh: bool = False) -> Path:
    """EDINETコードリスト（公開ZIP、APIキー不要）をダウンロード・キャッシュする。"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if CODELIST_CACHE_ZIP.exists() and not refresh:
        age_hours = (time.time() - CODELIST_CACHE_ZIP.stat().st_mtime) / 3600
        if age_hours < 24:
            return CODELIST_CACHE_ZIP
    body, _ = _http_get_bytes(CODELIST_URL, timeout=60)
    CODELIST_CACHE_ZIP.write_bytes(body)
    return CODELIST_CACHE_ZIP


def load_edinet_code_map(refresh: bool = False) -> list[dict]:
    """EDINETコードリストCSVを読み込み、行のリスト（dict）を返す。

    各行: {edinet_code, filer_name, sec_code, source_url, fetched_at}
    証券コード（sec_code）はEDINET側では末尾にチェックデジット"0"等が付いた5桁表記
    （例: 9432 → "94320"）であることが多い。解決時は先頭一致で照合する。
    """
    zip_path = _download_codelist(refresh=refresh)
    fetched_at = _now_iso()
    rows: list[dict] = []
    with zipfile.ZipFile(zip_path) as zf:
        csv_name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
        with zf.open(csv_name) as raw:
            text = io.TextIOWrapper(raw, encoding="cp932", errors="replace")
            lines = text.readlines()
    # 先頭2行はヘッダ情報（ダウンロード実行日、列名）。3行目からデータ。
    reader = csv.reader(lines[2:])
    for row in reader:
        if len(row) < 12:
            continue
        edinet_code = row[0].strip('"').strip()
        filer_name = row[6].strip('"').strip()
        sec_code = row[11].strip('"').strip()
        if not edinet_code:
            continue
        rows.append(
            {
                "edinet_code": edinet_code,
                "filer_name": filer_name,
                "sec_code": sec_code,
                "source_url": CODELIST_URL,
                "fetched_at": fetched_at,
            }
        )
    return rows


def resolve_edinet_code(sec_code: str, refresh: bool = False) -> Optional[dict]:
    """証券コード（例: "9432", "285A"）からEDINETコードを解決する。複数一致時は先頭を返す。"""
    rows = load_edinet_code_map(refresh=refresh)
    sec_code = sec_code.strip().upper()
    matches = [r for r in rows if r["sec_code"].upper().startswith(sec_code) and r["sec_code"]]
    return matches[0] if matches else None


# ---------------------------------------------------------------------------
# 2. 書類一覧API（documents.json） — APIキー必須
# ---------------------------------------------------------------------------

def list_documents_by_date(date: str, doc_type: int = 2, api_key: Optional[str] = None) -> dict:
    """指定した『ファイル日付』（YYYY-MM-DD）の書類一覧を取得する（書類一覧API）。

    doc_type: 1=メタデータのみ, 2=提出書類一覧及びメタデータ（デフォルト）
    """
    key = get_api_key(api_key)
    url = _build_url("/documents.json", {"date": date, "type": doc_type, "Subscription-Key": key})
    fetched_at = _now_iso()
    body, headers = _http_get_bytes(url)
    data = json.loads(body.decode("utf-8"))

    # EDINET APIはエラー時もHTTP 200を返し、ボディで判別する（仕様書3-3節）。
    meta = data.get("metadata", {})
    status = meta.get("status") or str(data.get("StatusCode", ""))
    if status and status != "200":
        message = meta.get("message") or data.get("message") or "不明なエラー"
        if status == "401":
            raise EdinetAuthError(
                f"EDINET APIキーが無効です（HTTPボディ: status={status}, message={message}）。\n\n"
                + REGISTRATION_HELP
            )
        raise EdinetAPIError(
            f"EDINET API（書類一覧API）がエラーを返しました: status={status}, message={message} "
            f"(取得元: {url}, 取得日時: {fetched_at})"
        )

    data["_source_url"] = url
    data["_fetched_at"] = fetched_at
    return data


def _daterange(start: dt.date, end: dt.date) -> Iterable[dt.date]:
    days = (end - start).days
    for i in range(days + 1):
        yield start + dt.timedelta(days=i)


def search_documents(
    sec_code: Optional[str] = None,
    edinet_code: Optional[str] = None,
    days: int = 7,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    api_key: Optional[str] = None,
    sleep_sec: float = 0.3,
) -> list[dict]:
    """証券コード/EDINETコード×日付範囲で書類一覧を横断検索する。

    書類一覧API（documents.json）は「1日分」の全書類一覧しか返さないため
    （EDINET API仕様書3-1節: dateパラメータは単一日のみ）、日付範囲分だけAPIを繰り返し
    呼び出し、結果をクライアント側で証券コード/EDINETコードによりフィルタする。
    """
    if not sec_code and not edinet_code:
        raise ValueError("sec_code または edinet_code のいずれかを指定してください。")

    resolved_edinet_code = edinet_code
    resolved_from = None
    if sec_code and not edinet_code:
        resolved = resolve_edinet_code(sec_code)
        if not resolved:
            raise ValueError(f"証券コード {sec_code} に対応するEDINETコードが見つかりませんでした。")
        resolved_edinet_code = resolved["edinet_code"]
        resolved_from = resolved

    if start_date and end_date:
        start = dt.date.fromisoformat(start_date)
        end = dt.date.fromisoformat(end_date)
    else:
        end = dt.date.today()
        start = end - dt.timedelta(days=days - 1)

    matches: list[dict] = []
    for i, d in enumerate(_daterange(start, end)):
        date_str = d.isoformat()
        try:
            resp = list_documents_by_date(date_str, doc_type=2, api_key=api_key)
        except EdinetAPIError as e:
            # 404（当日の一覧未生成等）はスキップしてよいが、それ以外は伝播させる。
            if "status=404" in str(e):
                continue
            raise
        for res in resp.get("results", []) or []:
            if resolved_edinet_code and res.get("edinetCode") != resolved_edinet_code:
                continue
            if sec_code and not resolved_edinet_code:
                if not (res.get("secCode") or "").upper().startswith(sec_code.upper()):
                    continue
            res["_query_date"] = date_str
            res["_source_url"] = resp["_source_url"]
            res["_fetched_at"] = resp["_fetched_at"]
            matches.append(res)
        if i < (end - start).days:
            time.sleep(sleep_sec)  # 連続リクエストを避ける（429対策、仕様書3-3節）

    if resolved_from:
        for m in matches:
            m["_resolved_from"] = resolved_from
    return matches


# ---------------------------------------------------------------------------
# 3. 書類取得API（documents/{docID}） — APIキー必須
# ---------------------------------------------------------------------------

def download_document(
    doc_id: str,
    doc_type: str = "1",
    out_dir: Optional[Path] = None,
    api_key: Optional[str] = None,
) -> dict:
    """書類ID（例: S100XXXX）を指定して書類本体をダウンロードする（書類取得API）。

    doc_type: "1"=提出本文書+監査報告書+XBRL(ZIP), "2"=PDF, "3"=代替書面・添付文書(ZIP),
              "4"=英文ファイル(ZIP), "5"=CSV(ZIP)
    """
    key = get_api_key(api_key)
    url = _build_url(f"/documents/{doc_id}", {"type": doc_type, "Subscription-Key": key})
    fetched_at = _now_iso()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        content_type = resp.headers.get("Content-Type", "")
        body = resp.read()

    if content_type.startswith("application/json"):
        # 失敗時（仕様書3-2-2節: 成功時はoctet-stream/pdf、失敗時のみjson）
        data = json.loads(body.decode("utf-8"))
        message = data.get("message") or data.get("metadata", {}).get("message") or "不明なエラー"
        status = str(data.get("StatusCode") or data.get("metadata", {}).get("status") or "")
        if status == "401":
            raise EdinetAuthError(
                f"EDINET APIキーが無効です（message={message}）。\n\n" + REGISTRATION_HELP
            )
        raise EdinetAPIError(
            f"EDINET API（書類取得API）がエラーを返しました: doc_id={doc_id}, type={doc_type}, "
            f"message={message} (取得元: {url}, 取得日時: {fetched_at})"
        )

    ext = ".pdf" if content_type.startswith("application/pdf") else ".zip"
    out_dir = Path(out_dir) if out_dir else DEFAULT_DOWNLOAD_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{doc_id}_type{doc_type}{ext}"
    out_path.write_bytes(body)

    return {
        "doc_id": doc_id,
        "doc_type": doc_type,
        "doc_type_name": DOC_TYPE_NAMES.get(doc_type, "不明"),
        "content_type": content_type,
        "size_bytes": len(body),
        "out_path": str(out_path),
        "source_url": url,
        "fetched_at": fetched_at,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_header(title: str) -> None:
    print(f"\n=== {title} ===")


def _print_provenance(source_url: str, fetched_at: str) -> None:
    print(f"  取得元: {source_url}")
    print(f"  取得日時: {fetched_at}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="EDINET API連携ツール（Syntropia Research 企業調査部, D-012）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=REGISTRATION_HELP,
    )
    parser.add_argument("--code", help="証券コード（例: 9432, 285A）")
    parser.add_argument("--edinet-code", help="EDINETコードを直接指定（例: E04430）")
    parser.add_argument("--days", type=int, default=7, help="今日から遡って検索する日数（デフォルト7日）")
    parser.add_argument("--start-date", help="検索開始日 YYYY-MM-DD（--end-dateと併用）")
    parser.add_argument("--end-date", help="検索終了日 YYYY-MM-DD（--start-dateと併用）")
    parser.add_argument("--resolve-only", action="store_true", help="証券コード→EDINETコードの解決のみ行う（APIキー不要・動作確認用）")
    parser.add_argument("--refresh-codelist", action="store_true", help="EDINETコードリストのキャッシュを強制更新する")
    parser.add_argument("--doc-id", help="書類ID（例: S100XXXX）を指定して書類本体をダウンロードする")
    parser.add_argument(
        "--doc-type",
        default="1",
        choices=list(DOC_TYPE_NAMES.keys()),
        help="書類取得APIのtype（1=提出本文書+監査報告書+XBRL, 2=PDF, 3=代替書面・添付文書, 4=英文, 5=CSV）",
    )
    parser.add_argument("--out-dir", help=f"ダウンロード先ディレクトリ（デフォルト: {DEFAULT_DOWNLOAD_DIR}）")
    parser.add_argument("--api-key", help="EDINET APIキー（省略時は環境変数 EDINET_API_KEY を使用）")
    args = parser.parse_args(argv)

    try:
        if args.resolve_only:
            if not args.code:
                print("エラー: --resolve-only には --code の指定が必要です。", file=sys.stderr)
                return 2
            _print_header(f"証券コード {args.code} → EDINETコード解決")
            resolved = resolve_edinet_code(args.code, refresh=args.refresh_codelist)
            if not resolved:
                print(f"  該当なし（証券コード {args.code} に対応するEDINETコードが見つかりません）")
                return 1
            print(f"  EDINETコード: {resolved['edinet_code']}")
            print(f"  提出者名: {resolved['filer_name']}")
            print(f"  証券コード（EDINET表記）: {resolved['sec_code']}")
            _print_provenance(resolved["source_url"], resolved["fetched_at"])
            return 0

        if args.doc_id:
            _print_header(f"書類取得API: {args.doc_id} (type={args.doc_type}: {DOC_TYPE_NAMES.get(args.doc_type)})")
            result = download_document(
                args.doc_id,
                doc_type=args.doc_type,
                out_dir=Path(args.out_dir) if args.out_dir else None,
                api_key=args.api_key,
            )
            print(f"  保存先: {result['out_path']}")
            print(f"  Content-Type: {result['content_type']}")
            print(f"  サイズ: {result['size_bytes']:,} bytes")
            _print_provenance(result["source_url"], result["fetched_at"])
            return 0

        if args.code or args.edinet_code:
            label = args.code or args.edinet_code
            _print_header(f"書類一覧検索: {label}")
            docs = search_documents(
                sec_code=args.code,
                edinet_code=args.edinet_code,
                days=args.days,
                start_date=args.start_date,
                end_date=args.end_date,
                api_key=args.api_key,
            )
            if not docs:
                print("  該当書類なし（指定期間内に提出書類が見つかりませんでした）")
                return 0
            for d in docs:
                docname = DOC_TYPE_CODE_NAMES.get(d.get("docTypeCode", ""), d.get("docTypeCode", ""))
                print(
                    f"  [{d.get('_query_date')}] docID={d.get('docID')} "
                    f"種別={docname} 提出者={d.get('filerName')} "
                    f"提出日時={d.get('submitDateTime')} "
                    f"概要={d.get('docDescription')}"
                )
                print(
                    f"      XBRL={d.get('xbrlFlag')} PDF={d.get('pdfFlag')} "
                    f"CSV={d.get('csvFlag')} 添付={d.get('attachDocFlag')}"
                )
                _print_provenance(d["_source_url"], d["_fetched_at"])
            return 0

        parser.print_help()
        return 2

    except EdinetAuthError as e:
        print(f"\n[APIキーエラー]\n{e}", file=sys.stderr)
        return 3
    except (EdinetAPIError, ValueError) as e:
        print(f"\n[エラー] {e}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"\n[通信エラー] EDINETへの到達に失敗しました: {e}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    sys.exit(main())
