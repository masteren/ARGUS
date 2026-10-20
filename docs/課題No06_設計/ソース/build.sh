#!/usr/bin/env bash
# 課題No06 の提出物3点（ER図・画面遷移図・画面設計書）を、いま動いているアプリから作り直す。
#
#   bash build.sh
#
# 必要なもの：Google Chrome、node（npm i puppeteer-core）、python3（pip install pillow）
# Chrome の場所が違うときは CHROME=/path/to/chrome bash build.sh
#
# 順番に意味がある：
#   shoot.js と boxes.js は seed.py 直後の同じデータで撮る（注釈ピンの座標がずれないように）。
#   shoot2.js は購入・操作を実際に行ってデータを変えるので、必ず最後に撮る。

set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
PYTHON="${PYTHON:-python3}"

rm -f design.db
mkdir -p shots doc/img

"$PYTHON" run_app.py > run_app.log 2>&1 &
APP_PID=$!
trap 'kill $APP_PID 2>/dev/null || true' EXIT

for _ in $(seq 1 50); do
  curl -s -o /dev/null http://127.0.0.1:5077/health && break
  sleep 0.2
done

"$PYTHON" seed.py
node shoot.js
node boxes.js
node shoot2.js

node render_diag.js "$PWD/er.html"   "$PWD/er.png"   1700 1450
node render_diag.js "$PWD/flow.html" "$PWD/flow.png" 1900 1750
cp er.png   ../ER図_ARGUS.png
cp flow.png ../画面遷移図_ARGUS.png

"$PYTHON" make_crops.py
"$PYTHON" gen_doc.py
node topdf.js "$PWD/doc/design.html" "$PWD/../画面設計書_ARGUS.pdf"
echo "done: ../ER図_ARGUS.png ../画面遷移図_ARGUS.png ../画面設計書_ARGUS.pdf"
