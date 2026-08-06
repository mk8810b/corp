# tanshin_verify.py の再現テストデータ（D-026）

`corp/tools/tanshin_verify.py` が**実際に発生した誤りを捕捉できること**、および
**正しい転記を誤検知しないこと**を確認するための入力データ。
ツールを改修した際は必ず下記を再実行し、期待どおりの終了コードになることを確認すること。

| ファイル | 内容 | 期待する結果 |
|---|---|---|
| `5411-20260805-miscolumn.json` | 2026-08-06の朝スキャンで担当SCR-H19が実際に報告した5411 JFEの数値。IFRS短信の連結経営成績表（6欄）の列を横にずらして読み、事業利益の前年同期として当期の四半期包括利益（46,131）を、親会社帰属四半期利益として四半期利益（32,267）を転記していた | **exit 2**（FAIL 3件: 増減率の整合2件＋増減率の原本照合1件、WARN 1件: 転記の網羅性） |
| `8386-20260805-split-not-applied.json` | 同日の8386 百十四銀行。2026-04-01付の1株→4株の株式分割をEPSには適用しながら配当には適用せず、「年間配当234円→35円の大幅減少」と誤読していた | **exit 2**（FAIL 1件: 株式分割の基準統一） |
| `5411-20260805-correct.json` | 同じ5411を原本どおり正しく転記したもの（親セッションが `pdftotext -layout` で原本を再抽出して確認） | **exit 0**（FAIL 0件・WARN 0件＝偽陽性なし） |

## 実行方法

PDFは開示当日のTDnetから取得する（`source_url` に記載）。ローカルに保存済みのPDFを
`--pdf` に渡してもよい。

    python3 corp/tools/tanshin_verify.py --json corp/tools/testdata/5411-20260805-miscolumn.json --pdf <5411の短信PDF>
    python3 corp/tools/tanshin_verify.py --json corp/tools/testdata/8386-20260805-split-not-applied.json --pdf <8386の短信PDF>
    python3 corp/tools/tanshin_verify.py --json corp/tools/testdata/5411-20260805-correct.json --pdf <5411の短信PDF>

**注意**: 検査6（増減率の原本照合）と検査3（株式分割の基準統一）は `--pdf` が無いと働かない。
`--pdf` なしで実行すると 5411-miscolumn は FAIL 2件（原本照合が効かない分だけ減る）、
8386 は FAIL 0件（分割注記を検出できない）になる。**必ず `--pdf` つきで実行すること。**
