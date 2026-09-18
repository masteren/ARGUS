# 設計書（課題No06）の作り直し手順

提出物3点（`ER図_ARGUS.png` / `画面遷移図_ARGUS.png` / `画面設計書_ARGUS.pdf`）は
実際に動いている画面から作っている。修正するときはここのファイルを直して作り直す。

## 必要なもの
- Google Chrome（`/Applications/Google Chrome.app`）
- `npm i puppeteer-core`、`pip install pillow pymupdf`

## 1. ER図 / 画面遷移図
`er.html` `flow.html` の mermaid 記述を直してから：

```
node render_diag.js "$PWD/er.html"   "$PWD/er.png"   1700 1450
node render_diag.js "$PWD/flow.html" "$PWD/flow.png" 1900 1750
```

## 2. 画面キャプチャ
`run_app.py` は本番DBを触らずに一時DBでアプリを起動し、カメラの代わりに
静止フレームを返す（実機・カメラなしで撮影できる）。

```
python3 run_app.py &            # http://127.0.0.1:5077
node shoot.js                   # 3画面のキャプチャ → shots/
node shoot2.js                  # 入力中／受付／エラーの3状態 → shots/
python3 make_crops.py           # スライド用に切り出し → doc/img/
node boxes.js                   # 注釈ピン用に要素座標を採取 → boxes.json
```

撮影用のデータ（取引・検出）は `/pay` と `/upload` を叩いて作る。

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
