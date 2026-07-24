#!/usr/bin/env python3
"""Syntropia Research 開発部（DEV） — ダッシュボードビルドスクリプト。

corp/data/price-history.json と corp/data/shadow-price-history.json を
テンプレート（corp/dev/dashboard.template.html）に埋め込み、
自己完結型HTML corp/dev/dashboard.html を生成する。

- 決定論的な定型作業（絶対制約第4条: 下位モデル/Haiku で実行可）。
- データの数値は一切加工しない（絶対制約第2条: JSONの内容をそのまま埋め込む。
  損益率等の導出値は閲覧時にJS側で固定式により計算される）。
- 外部リクエストは行わない・生成物にも含めない（playbooks/dev.md）。

使い方:
    python3 corp/dev/build_dashboard.py
    （リポジトリルート以外から実行してもパスはスクリプト位置から解決される）
"""

import json
import sys
from pathlib import Path

DEV_DIR = Path(__file__).resolve().parent          # corp/dev
CORP_DIR = DEV_DIR.parent                          # corp
TEMPLATE = DEV_DIR / "dashboard.template.html"
OUTPUT = DEV_DIR / "dashboard.html"
PORTFOLIO_JSON = CORP_DIR / "data" / "price-history.json"
SHADOW_JSON = CORP_DIR / "data" / "shadow-price-history.json"
# テンプレート冒頭のコメントにも同じ語が登場するため、置換対象は代入行そのものに限定する
PLACEHOLDER = "var DATA = __EMBED_DATA_JSON__;"


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    portfolio = load(PORTFOLIO_JSON)
    shadow = load(SHADOW_JSON)

    data = {"portfolio": portfolio, "shadow": shadow}
    # </script> 早期終了を防ぐエスケープ（数値・文字列の内容自体は不変）
    embedded = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")

    template = TEMPLATE.read_text(encoding="utf-8")
    if PLACEHOLDER not in template:
        print(f"ERROR: テンプレートにプレースホルダ {PLACEHOLDER} がありません", file=sys.stderr)
        return 1
    html = template.replace(PLACEHOLDER, "var DATA = " + embedded + ";", 1)
    if "var DATA = __EMBED_DATA_JSON__;" in html:
        print("ERROR: プレースホルダの置換に失敗しました", file=sys.stderr)
        return 1

    OUTPUT.write_text(html, encoding="utf-8")
    n_real = len(portfolio.get("positions", {}))
    n_shadow = len(shadow.get("positions", {}))
    print(f"OK: {OUTPUT} を生成しました（保有 {n_real}件 / シャドー {n_shadow}件, "
          f"as_of: 保有={portfolio.get('as_of')} シャドー={shadow.get('as_of')}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
