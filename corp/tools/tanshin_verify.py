#!/usr/bin/env python3
"""tanshin_verify.py — 決算短信の転記に対する機械的自己検算ツール（D-026、2026-08-06新設）

Syntropia Research スクリーニング部（SCR）・企業調査部（RSH）・投資判断部（JDG）共用。

## なぜ必要か（設計の根拠）

`corp/incidents.md` に記録された誤りを機序で分類すると、**最大の分類は「表のセル・行・基準の
取り違え」**である（INC-001の3405〔PBR欄に有利子負債倍率〕・6548〔日付1週間ずれ〕、
2026-08-05の3964〔前日比が前営業日の行〕、2026-08-06の5411〔IFRS短信の列が4つずれ〕・
8386〔株式分割を配当に未適用〕）。この分類は**毎営業日のように再発している**一方、
機械ゲートを導入した分類（D-025の証券コード↔社名照合）は導入後の再発がゼロである。

**決算短信は「値」と「増減率」の両方を印刷しており、検算に必要な冗長性が原本の中にある。**
本ツールはその冗長性を機械的に突き合わせる。判定基準（D-012のBUY基準等）・リスク上限
（D-002/D-011/D-015/D-019）・データソース（D-003）には**一切触れない**。誤りを検出するだけで
あり、何を買うか・何をWATCHするかの判断には関与しない。

## 検査する項目

1. **増減率の整合（check_growth）**
   転記した (当期値, 前年同期値, 短信記載の増減率) の3つ組について
   `|(当期/前年-1)*100 - 記載増減率| <= 許容幅` を検査する。既定の許容幅は0.15pt
   （短信は小数第1位で丸めるため、丸め差のみを許容する幅）。
   → 2026-08-06の5411で、担当エージェントが自分の報告書に「PDF記載+315.0%」と
     「検算+210.9%」を並記したまま提出した事象を、その場で停止させる。

2. **列の相互汚染（check_cross_contamination）**
   ある項目の「前年同期値」として転記した数値が、**別項目の「当期値」と一致**する場合に
   FAILとする。表の列を横にずらして読むと必ずこの形になる。
   → 5411では、事業利益の前年同期として46,131（実際は当期の四半期包括利益の欄）を
     転記していた。本検査で捕捉できる。

3. **株式分割の基準統一（check_split_basis）**
   PDFテキストに株式分割の注記が見つかった場合、1株当たり項目（EPS・配当）について
   `split_adjusted` の明示を必須とする。未指定なら FAIL。
   → 2026-08-06の8386（1株→4株の分割を EPS には適用したが配当には適用せず
     「234円→35円の大幅減配」と誤読）を捕捉する。
     2026-08-04の3673・2026-08-05の3964（分割の未記載）も同型。

4. **増減率が定義不能なケース（check_growth 内）**
   前年同期が0以下（赤字・ゼロ）の場合、増減率は定義できない。短信も「－」と表示する。
   にもかかわらず数値の増減率が転記されていれば FAIL とする。

5. **当期値の重複（check_duplicate_current）**
   複数の項目に同一の当期値が転記されている場合に WARN（同額はありうるため FAIL にはしない）。

6. **増減率の原本照合（check_stated_pct_in_document）— 本ツールの中核**
   転記した増減率が、**実際に開示本文へ印刷されているか**を照合する。
   検査1は転記者が増減率を自分で計算した場合に空回りする（誤った前年同期値から計算した
   増減率は、その誤った値と必ず整合するため）。実際、2026-08-06の5411では事業利益について
   「当期32,313／前年46,131／△30.0%」という**内部整合した誤り**が報告され、検査1では
   捕捉できなかった（短信が印刷していたのは +98.7%）。本検査はこの穴を塞ぐ。
   → `--pdf` の指定が必須。未指定なら WARN を出す。

7. **転記の網羅性（check_completeness）**
   `summary_columns` に連結経営成績の欄数を申告させ、転記項目数がそれを下回れば WARN。
   検査2は比較相手が転記されて初めて機能する。5411ではずれの原因となった
   「四半期包括利益合計額」が転記されておらず検査2が発火しなかった。

## 使い方

    # 自己検算のみ（PDFなし）
    python3 corp/tools/tanshin_verify.py --json items.json

    # PDF本文も併せて検査（株式分割の注記検出）
    python3 corp/tools/tanshin_verify.py --json items.json --pdf https://www.release.tdnet.info/inbs/XXXX.pdf
    python3 corp/tools/tanshin_verify.py --json items.json --pdf /path/to/local.pdf

    # 許容幅を変える（既定0.15pt）
    python3 corp/tools/tanshin_verify.py --json items.json --tol 0.2

終了コード: 0=全検査通過 / 2=FAILあり（転記をやり直すこと） / 1=実行エラー

## 入力JSONの形式

    {
      "code": "5411",
      "name": "JFEホールディングス株式会社",
      "source_url": "https://www.release.tdnet.info/inbs/140120260804508994.pdf",
      "fetched_at": "2026-08-05T23:00:00Z",
      "period": "2027年3月期第1四半期",
      "summary_columns": 6,
      "items": [
        {"label": "売上収益",   "current": 1161178, "prior": 1115313, "stated_pct": 4.1},
        {"label": "事業利益",   "current": 32313,   "prior": 16261,   "stated_pct": 98.7},
        {"label": "四半期利益", "current": 32267,   "prior": 7775,    "stated_pct": 315.0}
      ],
      "per_share": [
        {"label": "基本的1株当たり四半期利益", "current": 49.09, "prior": 11.21,
         "split_adjusted": true}
      ],
      "dividend": [
        {"label": "年間配当", "current": 80.00, "prior": 80.00, "split_adjusted": true}
      ]
    }

`stated_pct` は**短信が印刷している増減率をそのまま転記する**こと。
**自分で計算した値を入れてはならない**（検査6が空回りし、本ツールの意味が失われる）。
短信が「－」を表示している場合は null を入れる。
`summary_columns` は連結経営成績サマリー表の欄数（IFRSは通常6、日本基準は通常4〜5）。
`per_share` / `dividend` は省略可。`split_adjusted` は株式分割の注記がある場合に必須。

絶対制約第2条に従い、本ツールは**入力された数値の出所を検証しない**（出所の記録は
成果物側の責任）。本ツールが保証するのは「転記された数値どうしが内部整合しているか」だけ
である。内部整合していても原本と違う値を転記していれば検出できない点に注意すること
（ただし増減率まで含めて整合的に間違えるのは、単なる列ずれでは起こりにくい）。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")

DEFAULT_TOL = 0.15  # 増減率の許容差（パーセントポイント）。短信の小数第1位丸めを吸収する

# 株式分割の注記を検出する正規表現。短信の注記文の実例に合わせている:
#   「2026年４月１日付で普通株式１株を４株に分割する株式分割を行いました」
#   「普通株式１株につき２株の割合で株式分割を実施いたしました」
SPLIT_PAT = re.compile(
    r"(株式分割|１株につき[０-９0-9]+株|1株につき[0-9]+株|１株を[０-９0-9]+株|1株を[0-9]+株)"
)


class Finding:
    """検査結果の1件。level は 'FAIL' か 'WARN'。"""

    def __init__(self, level: str, check: str, message: str):
        self.level = level
        self.check = check
        self.message = message

    def __str__(self) -> str:
        mark = "[FAIL]" if self.level == "FAIL" else "[WARN]"
        return f"  {mark} {self.check}: {self.message}"


def _fmt(x: float) -> str:
    """数値を桁区切りで表示する（整数は小数点を出さない）。"""
    if isinstance(x, float) and abs(x - round(x)) < 1e-9:
        return f"{int(round(x)):,}"
    return f"{x:,}"


def check_growth(items: list[dict], tol: float) -> list[Finding]:
    """増減率の整合を検査する（検査1・検査4）。"""
    out: list[Finding] = []
    for it in items:
        label = it.get("label", "(無名項目)")
        cur, pri = it.get("current"), it.get("prior")
        stated = it.get("stated_pct", None)

        if cur is None or pri is None:
            out.append(Finding("WARN", "増減率の整合",
                               f"{label}: current/prior のいずれかが未入力のため検算不能"))
            continue

        # 前年同期が0以下なら増減率は定義できない（短信も「－」を印刷する）
        if pri <= 0:
            if stated is not None:
                out.append(Finding(
                    "FAIL", "増減率の定義可能性",
                    f"{label}: 前年同期が {_fmt(pri)}（0以下）のため増減率は定義できないが、"
                    f"stated_pct={stated} が転記されている。"
                    f"短信は「－」を印刷しているはずであり、別欄の値を拾った可能性が高い"))
            continue

        calc = (cur / pri - 1.0) * 100.0
        if stated is None:
            out.append(Finding("WARN", "増減率の整合",
                               f"{label}: stated_pct が null。再計算値 {calc:+.2f}% の"
                               f"検証相手が無いため、短信記載の増減率を転記すること"))
            continue

        diff = abs(calc - stated)

        # 【2026-08-07改良】短信は「百万円未満切捨て」で表示するため、転記した整数値の
        # 背後にある真値は [x, x+1) の幅を持つ。絶対額が小さい項目ではこの丸めだけで
        # 増減率が数pt〜数百pt動くため、固定許容幅 tol では構造的に誤検出（偽陽性）となる。
        # 実例（5491、2026-08-07）: 純利益 当期263／前年9 は、真値のとりうる増減率が
        # +2,530.0%〜+2,833.3% の幅を持ち、短信記載の +2,817.1% はその内側にある。
        # そこで **切捨て前の真値がとりうる増減率レンジ** を計算し、stated がその内側に
        # あれば整合とみなす（レンジは丸めの数学的帰結であり、検出力を落とす緩和ではない）。
        lo_rate = (cur / (pri + 1.0) - 1.0) * 100.0 if pri + 1.0 > 0 else None
        hi_rate = ((cur + 1.0) / pri - 1.0) * 100.0
        in_trunc_range = (lo_rate is not None
                          and lo_rate - tol <= stated <= hi_rate + tol)

        if diff > tol and not in_trunc_range:
            out.append(Finding(
                "FAIL", "増減率の整合",
                f"{label}: 当期 {_fmt(cur)} ÷ 前年 {_fmt(pri)} = {calc:+.2f}% だが、"
                f"短信記載は {stated:+.2f}%（差 {diff:.2f}pt > 許容 {tol}pt）。"
                f"切捨て前の真値を考慮したレンジ [{lo_rate:+.2f}%, {hi_rate:+.2f}%] からも外れる。"
                f"転記した当期値・前年同期値・増減率のいずれかが別の欄の値である"))
        elif diff > tol:
            out.append(Finding(
                "WARN", "増減率の整合",
                f"{label}: 再計算 {calc:+.2f}% と短信記載 {stated:+.2f}% の差 {diff:.2f}pt は"
                f"許容 {tol}pt を超えるが、百万円未満切捨てによる真値のレンジ "
                f"[{lo_rate:+.2f}%, {hi_rate:+.2f}%] の内側にあるため整合とみなす"
                f"（絶対額が小さい項目では丸めの影響が大きい）"))
    return out


def check_cross_contamination(items: list[dict], corroborated: set | None = None) -> list[Finding]:
    """列の相互汚染を検査する（検査2）。

    ある項目の prior が、別項目の current と一致する場合を疑う。表の列を横にずらして読むと
    必ずこの形になるためである。

    **【2026-08-07改良】偶然の一致による偽陽性の抑制。** 2営業日で3件の偽陽性が確認された
    （8111ゴールドウイン: 前回予想の営業利益7,000と修正後の経常利益7,000／5408中山製鋼所／
    4613関西ペイント。いずれも原本で確認したところ列ずれではなく同額の偶然の一致だった）。
    そこで、**当該2項目の双方について検査6（増減率の原本照合）が通っている場合は WARN へ
    降格する**。検査6が通っているとは「転記した増減率が開示本文に実際に印刷されている」
    ということであり、その増減率は当期値と前年同期値の組を独立に裏づける。列をずらして
    読んでいれば、ずれた組に対応する増減率が原本に印刷されている可能性は極めて低い。
    検査6が通っていない項目（`--pdf` 未指定の場合を含む）については従来どおり FAIL とする。
    """
    out: list[Finding] = []
    corroborated = corroborated if corroborated is not None else set()
    cur_by_label = {it.get("label"): it.get("current")
                    for it in items if it.get("current") is not None}
    for it in items:
        label, pri = it.get("label"), it.get("prior")
        if pri is None:
            continue
        for other_label, other_cur in cur_by_label.items():
            if other_label == label:
                continue
            if other_cur == pri:
                both_ok = label in corroborated and other_label in corroborated
                if both_ok:
                    out.append(Finding(
                        "WARN", "列の相互汚染",
                        f"「{label}」の前年同期値 {_fmt(pri)} が「{other_label}」の当期値と"
                        f"一致しているが、**両項目とも検査6（増減率の原本照合）が通っている**ため"
                        f"偶然の同額とみなす（列ずれであれば原本に対応する増減率は印刷されない）"))
                else:
                    out.append(Finding(
                        "FAIL", "列の相互汚染",
                        f"「{label}」の前年同期値 {_fmt(pri)} が、"
                        f"「{other_label}」の当期値と一致している。"
                        f"表の列を横にずらして読んだ可能性が高い（前年同期の行を読み直すこと）"))
    return out


def _corroborated_labels(items: list[dict], text: str | None) -> set:
    """検査6（増減率の原本照合）が通った項目のラベル集合を返す（検査2の降格判定に使う）。"""
    if text is None:
        return set()
    ok = set()
    for it in items:
        stated = it.get("stated_pct", None)
        if stated is None:
            continue
        if any(v in text for v in _pct_variants(float(stated))):
            ok.add(it.get("label"))
    return ok


def _pct_variants(pct: float) -> list[str]:
    """増減率が短信本文にどう印刷されうるかの表記ゆれを列挙する。

    短信は小数第1位まで印刷し、負値は「△」または「-」で表す。全角数字は使わない
    （数値部分は半角）が、記号は和文フォントのことがあるため両方を候補にする。
    """
    a = abs(pct)
    # 【2026-08-07追加】1,000%以上の増減率は短信が桁区切りカンマ付きで印刷する
    # （実例: 5491の親会社株主帰属四半期純利益「（2,817.1％）」）。カンマ無しの表記しか
    # 探していなかったため、正しい転記に対して検査6が誤ってFAILを出していた。
    bodies = [f"{a:.1f}"]
    if a >= 1000:
        bodies.append(f"{a:,.1f}")
    if pct < 0:
        out: list[str] = []
        for b in bodies:
            out += [f"△{b}", f"△ {b}", f"-{b}", f"−{b}", f"▲{b}"]
        return out
    return bodies


def check_stated_pct_in_document(items: list[dict], text: str | None) -> list[Finding]:
    """転記した増減率が、実際に開示本文へ印刷されているかを検査する（検査6）。

    **本検査が本ツールの中核である。** 検査1（増減率の整合）は、転記者が増減率を自分で
    計算して書いた場合には空回りする——誤った前年同期値から計算した増減率は、その誤った値と
    必ず整合してしまうためである。実際、2026-08-06の5411では事業利益について
    「当期32,313／前年46,131／△30.0%」という**内部整合した誤り**が報告されており、
    検査1だけでは捕捉できなかった（短信が実際に印刷していたのは +98.7%）。

    そこで本検査は「短信が印刷している増減率」を原本テキストに対して照合する。
    転記した増減率が本文のどこにも存在しなければ、それは転記者が自分で計算した値であり、
    原本の値ではない。
    """
    out: list[Finding] = []
    if text is None:
        out.append(Finding(
            "WARN", "増減率の原本照合",
            "--pdf が未指定のため、転記した増減率が原本に印刷されているかを照合できない。"
            "**転記者が自分で計算した増減率は検査1を素通りする**ため、"
            "決算短信の検算では --pdf の指定を強く推奨する"))
        return out

    for it in items:
        label = it.get("label", "(無名項目)")
        stated = it.get("stated_pct", None)
        if stated is None:
            continue
        variants = _pct_variants(float(stated))
        if not any(v in text for v in variants):
            out.append(Finding(
                "FAIL", "増減率の原本照合",
                f"{label}: 転記された増減率 {stated:+.1f}% が開示本文に見当たらない"
                f"（探した表記: {' / '.join(variants)}）。"
                f"**短信が印刷している増減率ではなく、転記者が自分で計算した値の可能性が高い。**"
                f"原本の増減率欄を読み直すこと"))
    return out


def check_completeness(items: list[dict], expected: int | None) -> list[Finding]:
    """連結経営成績の欄を全て転記しているかを検査する（検査7）。

    検査2（列の相互汚染）は、比較相手となる項目が転記されていて初めて機能する。
    2026-08-06の5411では、ずれの原因となった「四半期包括利益合計額」が転記されて
    いなかったため検査2が発火しなかった。**サマリー表の欄は飛ばさず全て転記すること**を
    促すための検査である。

    **空転記の遮断（INC-009、2026-08-10）**: 転記が0項目のときは全検査が空回りし、
    それでも終了コード0が返っていた。実際に「空のJSONを渡してEXIT_CODE 0を得て
    『検証済み』と報告する」事故が発生したため、**転記0項目はFAIL（終了コード2）**とする。
    ゲートは「実行したこと」ではなく「中身を検査したこと」を保証しなければならない。
    """
    out: list[Finding] = []
    if not items:
        out.append(Finding(
            "FAIL", "空転記の遮断",
            "連結経営成績の転記が0項目である。転記が空だと検査1〜6のすべてが空回りし、"
            "本ツールは何も検証していない。**空の入力で終了コード0を得て『検算済み』と"
            "報告してはならない**（INC-009）。サマリー表の欄を実際に転記して再実行すること"))
        return out
    if expected is None:
        return out
    if len(items) < expected:
        out.append(Finding(
            "WARN", "転記の網羅性",
            f"連結経営成績の欄は {expected}項目と申告されているが、転記は {len(items)}項目。"
            f"**欄を飛ばすと検査2（列の相互汚染）が機能しなくなる**ため、"
            f"サマリー表の欄は全て転記すること"))
    return out


def check_duplicate_current(items: list[dict]) -> list[Finding]:
    """複数項目に同一の当期値が転記されていれば WARN（検査5）。"""
    out: list[Finding] = []
    seen: dict[float, list[str]] = {}
    for it in items:
        cur = it.get("current")
        if cur is None:
            continue
        seen.setdefault(cur, []).append(it.get("label", "(無名項目)"))
    for val, labels in seen.items():
        if len(labels) > 1:
            out.append(Finding(
                "WARN", "当期値の重複",
                f"当期値 {_fmt(val)} が {len(labels)}項目（{'・'.join(labels)}）に"
                f"転記されている。同額はありうるが、列の取り違えでも同じ形になる"))
    return out


def check_split_basis(per_share: list[dict], dividend: list[dict],
                      split_notes: list[str] | None) -> list[Finding]:
    """株式分割がある場合、1株当たり項目の基準統一を強制する（検査3）。"""
    out: list[Finding] = []
    if not split_notes:
        return out

    note_preview = split_notes[0][:80]
    for group_name, group in (("per_share", per_share), ("dividend", dividend)):
        for it in group or []:
            label = it.get("label", "(無名項目)")
            if "split_adjusted" not in it:
                out.append(Finding(
                    "FAIL", "株式分割の基準統一",
                    f"{group_name}「{label}」に split_adjusted が未指定。"
                    f"本開示には株式分割の注記がある（「{note_preview}…」）ため、"
                    f"当期値と前年同期値が同一の基準（分割調整の有無）かを明示すること"))
            elif it.get("split_adjusted") is False:
                out.append(Finding(
                    "FAIL", "株式分割の基準統一",
                    f"{group_name}「{label}」が split_adjusted=false。"
                    f"分割前後の値をそのまま比較すると増減を誤読する"
                    f"（分割後換算に統一してから比較すること）"))
    return out


def extract_pdf_text(pdf: str) -> str:
    """PDFのURLまたはローカルパスからテキストを抽出する。

    `corp/RUNBOOK.md`「既知の技術的制約」節に従い、URLの取得は curl（UA指定）で行う。
    """
    with tempfile.TemporaryDirectory() as td:
        if pdf.startswith("http://") or pdf.startswith("https://"):
            local = Path(td) / "doc.pdf"
            r = subprocess.run(["curl", "-sS", "-A", UA, "-o", str(local), pdf],
                               capture_output=True, text=True)
            if r.returncode != 0 or not local.exists() or local.stat().st_size == 0:
                raise RuntimeError(f"PDFの取得に失敗しました: {pdf}\n{r.stderr.strip()}")
        else:
            local = Path(pdf)
            if not local.exists():
                raise RuntimeError(f"PDFが見つかりません: {pdf}")

        r = subprocess.run(["pdftotext", "-layout", str(local), "-"],
                           capture_output=True, text=True)
        # pdftotext は壊れたPDFでも部分的なテキストを返すことがあるため、
        # 空でなければ採用する（第2条: 取得できた範囲を正直に扱う）
        if not r.stdout.strip():
            raise RuntimeError(
                f"PDFからテキストを抽出できませんでした: {pdf}\n"
                f"（画像のみのPDF、またはToUnicode CMapを欠くフォントの可能性。"
                f"この場合は該当項目を「取得不能」として扱うこと）")
        return r.stdout


def find_split_notes(text: str) -> list[str]:
    """PDFテキストから株式分割の注記を抽出する。"""
    notes: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if s and SPLIT_PAT.search(s):
            notes.append(re.sub(r"\s+", " ", s))
    return notes


def verify(payload: dict, tol: float = DEFAULT_TOL,
           pdf: str | None = None) -> tuple[list[Finding], list[str]]:
    """全検査を実行し、(検出結果, 株式分割の注記) を返す。"""
    items = payload.get("items", []) or []
    per_share = payload.get("per_share", []) or []
    dividend = payload.get("dividend", []) or []

    split_notes: list[str] = []
    text: str | None = None
    if pdf:
        text = extract_pdf_text(pdf)
        split_notes = find_split_notes(text)

    findings: list[Finding] = []
    findings += check_growth(items, tol)
    findings += check_stated_pct_in_document(items, text)
    findings += check_cross_contamination(items, _corroborated_labels(items, text))
    findings += check_completeness(items, payload.get("summary_columns"))
    findings += check_duplicate_current(items)
    findings += check_split_basis(per_share, dividend, split_notes)
    return findings, split_notes


def main() -> int:
    ap = argparse.ArgumentParser(
        description="決算短信の転記に対する機械的自己検算（D-026）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    ap.add_argument("--json", required=True,
                    help="転記した数値のJSONファイル（形式はモジュールのdocstring参照）")
    ap.add_argument("--pdf", default=None,
                    help="開示PDFのURLまたはローカルパス。指定すると株式分割の注記を検出する")
    ap.add_argument("--tol", type=float, default=DEFAULT_TOL,
                    help=f"増減率の許容差（パーセントポイント、既定 {DEFAULT_TOL}）")
    args = ap.parse_args()

    try:
        payload = json.loads(Path(args.json).read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001 — 入力不備は利用者に読める形で返す
        print(f"[ERROR] JSONの読み込みに失敗しました: {e}", file=sys.stderr)
        return 1

    try:
        findings, split_notes = verify(payload, tol=args.tol, pdf=args.pdf)
    except RuntimeError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1

    code = payload.get("code", "?")
    name = payload.get("name", "?")
    period = payload.get("period", "")
    print(f"=== 決算短信 転記自己検算（D-026）: {code} {name} {period} ===")
    if payload.get("source_url"):
        print(f"  出典: {payload['source_url']}")
    if payload.get("fetched_at"):
        print(f"  取得日時: {payload['fetched_at']}")
    print(f"  検査対象: items {len(payload.get('items', []) or [])}項目"
          f" / per_share {len(payload.get('per_share', []) or [])}項目"
          f" / dividend {len(payload.get('dividend', []) or [])}項目"
          f" / 許容差 {args.tol}pt")

    if args.pdf:
        if split_notes:
            print(f"  **株式分割の注記を検出（{len(split_notes)}行）**:")
            for n in split_notes[:3]:
                print(f"    - {n[:110]}")
        else:
            print("  株式分割の注記: 検出されず")

    fails = [f for f in findings if f.level == "FAIL"]
    warns = [f for f in findings if f.level == "WARN"]

    if findings:
        print("\n--- 検出 ---")
        for f in fails:
            print(f)
        for f in warns:
            print(f)

    print()
    if fails:
        print(f"[NG] FAIL {len(fails)}件 / WARN {len(warns)}件。"
              f"**転記をやり直すこと。**原本の該当行・該当列を読み直し、"
              f"解消できない場合は当該項目を「取得不能」と明記すること（絶対制約第2条）。")
        return 2

    print(f"[OK] FAIL 0件 / WARN {len(warns)}件。転記の内部整合性を確認しました。")
    print("  注意: 本ツールは転記どうしの整合のみを保証します。"
          "内部整合したまま原本と異なる値を転記していれば検出できません。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
