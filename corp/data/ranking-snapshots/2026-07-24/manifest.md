# 発掘条件5軸ランキング スナップショット（2026-07-24）

- 取得日時: 2026-07-24 15:45頃 JST（東証大引け後）
- 取得手段: `curl`（ブラウザ相当UA指定、`corp/RUNBOOK.md`「既知の技術的制約」節のワークアラウンド）
- 位置づけ: D-022により、土日実施の週次ルーチン（D-005）における軸A/Bのセッション依存問題
  （休場日にランキングページが空データを返す）への対策として、金曜（週次ルーチン前の最終営業日）の
  大引け後に保存する一次ソース（`playbooks/screening.md` 2-1参照）。

## 取得ページ一覧

| 軸 | 内容 | 取得元URL | 保存ファイル | ファイルサイズ |
|---|---|---|---|---|
| A | 値上がり率（本日、株価上昇率ランキング） | https://kabutan.jp/warning/?mode=2_1 | axisA_gainers.html | 64,217 bytes |
| B | 値下がり率（本日、株価下落率ランキング） | https://kabutan.jp/warning/?mode=2_2 | axisB_losers.html | 64,285 bytes |
| C | 出来高急増率 | https://kabutan.jp/tansaku/?mode=2_0311 | axisC_volume_surge.html | 69,692 bytes |
| D | 低PBR（実績） | https://finance.yahoo.co.jp/stocks/ranking/lowPbr | axisD_low_pbr.html | 224,797 bytes |
| E | 出来高（流動性上位） | https://finance.yahoo.co.jp/stocks/ranking/volume | axisE_volume_top.html | 237,187 bytes |

## 取得確認

各ファイルの`<title>`タグで正常なランキングページであることを確認済み（エラーページ・
bot対策ブロックページではない）。

## 注記

- 本スナップショットは今週末（2026-07-25予定）の週次ルーチンで軸A/Bの一次ソースとして使用する
  （D-022）。生HTMLをそのまま保存しており、個別候補の抽出・パースは週次ルーチン実行時に行う。
