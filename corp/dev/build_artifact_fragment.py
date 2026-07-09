#!/usr/bin/env python3
"""
corp/dev/dashboard.html（完全なHTML文書、正本）から <title>/<style>/<body> の中身だけを
抽出し、Artifact公開用の断片ファイルを生成する。

Artifact機能は独自に <!doctype>/<html>/<head>/<body> を付与するため、完全なHTML文書を
そのまま渡すとタグが二重になる。ビルド済みの dashboard.html を直接編集せず、常にこの
スクリプトで断片を再生成すること（`playbooks/dev.md` 6-1参照）。

使い方:
    python3 corp/dev/build_artifact_fragment.py
出力:
    corp/dev/dashboard-artifact-fragment.html
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "dashboard.html"
OUT = HERE / "dashboard-artifact-fragment.html"


def main():
    html = SRC.read_text(encoding="utf-8")

    title_m = re.search(r"<title>(.*?)</title>", html, re.S)
    style_m = re.search(r"<style>(.*?)</style>", html, re.S)
    body_m = re.search(r"<body[^>]*>(.*?)</body>", html, re.S)
    if not (title_m and style_m and body_m):
        sys.exit("ERROR: dashboard.html から <title>/<style>/<body> を抽出できませんでした。"
                  "テンプレート構造が変わっていないか確認してください。")

    fragment = (
        f"<title>{title_m.group(1)}</title>\n"
        f"<style>{style_m.group(1)}</style>\n"
        f"{body_m.group(1)}\n"
    )
    OUT.write_text(fragment, encoding="utf-8")
    print(f"OK: {OUT} を生成しました（Artifact公開用、file_path指定で同一URLへ再デプロイすること）")


if __name__ == "__main__":
    main()
