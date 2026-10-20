# 設計書（課題No06）の作り直し手順

提出物3点（`ER図_ARGUS.png` / `画面遷移図_ARGUS.png` / `画面設計書_ARGUS.pdf`）は
実際に動いている画面から作っている。修正するときはここのファイルを直して作り直す。

## 必要なもの
- Google Chrome（`/Applications/Google Chrome.app`。別の場所なら `CHROME=` で指定）
- `npm i puppeteer-core`、`pip install pillow pymupdf`

## まとめて作り直す（推奨）

```
bash build.sh
```

一時DBでアプリを起動 → 撮影用データを投入 → 画面を撮影 → 図とPDFを生成 → 1つ上の
フォルダの提出物3点を上書きする。各段階を個別に回したいときは下の手順を見る。

## 1. ER図 / 画面遷移図
`er.html` `flow.html` の mermaid 記述を直してから：

```
node render_diag.js "$PWD/er.html"   "$PWD/er.png"   1700 1450
node render_diag.js "$PWD/flow.html" "$PWD/flow.png" 1900 1750
```

## 2. 画面キャプチャ
`run_app.py` は本番DBを触らずに一時DB（`design.db`）でアプリを起動し、カメラの代わりに
静止フレームを返す（実機・カメラなしで撮影できる）。撮影用データは `seed.py` が
本番と同じ API（会員登録 → 購入 → チケット消費 → 実行完了）を叩いて作る。

**順番に意味がある。** `shoot.js` と `boxes.js` は `seed.py` 直後の同じデータで撮る
（注釈ピンの座標がずれないように）。`shoot2.js` は購入・操作を実際に行ってデータを
変えるので、必ず最後に撮る。

```
rm -f design.db
python3 run_app.py &            # http://127.0.0.1:5077
python3 seed.py                 # 会員8人・購入・取引・検出を作る
node shoot.js                   # 4画面のキャプチャ（公開ページは「ゆい」でログイン中）→ shots/
node boxes.js                   # 注釈ピン用に要素座標を採取 → boxes.json
node shoot2.js                  # ログイン・購入パネルと操作パネルの各状態 → shots/
python3 make_crops.py           # スライド用に切り出し → doc/img/
```

切り出し範囲は `crops.py` が `boxes.json` の要素座標から計算する（表の行数が
変わっても途中で切れないように）。`make_crops.py` と `gen_doc.py` の両方がこれを使う。

## 3. 画面設計書PDF
`gen_doc.py` がスライドHTMLを組み立てる。注釈ピンは `boxes.json` の要素座標を
切り出し範囲に合わせて変換して置いているので、画面のCSSを変えたら `boxes.js` から採り直す。

```
python3 gen_doc.py              # → doc/design.html
node topdf.js "$PWD/doc/design.html" "$PWD/doc/画面設計書_ARGUS.pdf"
```

`topdf.js` は各ページの中身がスライド枠からはみ出していないかを確認し、
`overflow: []` 以外が出たらレイアウトを直す。

## 直すことが多い場所
- 日付・チーム名・改訂番号：`gen_doc.py` 冒頭の `DATE` / `TEAM` / `REV`
- ページ構成：`gen_doc.py` の `slide(...)` の並び
- 撮影用の会員・購入・操作：`seed.py` の `VISITORS`
