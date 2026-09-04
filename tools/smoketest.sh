#!/usr/bin/env bash
# ARGUS ローカル結合スモークテスト（ワンコマンド版）
#
#   bash tools/smoketest.sh              # PORT=5001 で実行（macOS の AirPlay が 5000 を掴むため）
#   PORT=5003 bash tools/smoketest.sh    # 5001 も塞がっていた場合
#   PYTHON=python3.12 bash tools/smoketest.sh
#
# 実機(Freenove)・マイク・カメラ・OpenAI キーは不要。検証するのはデータ閉ループだけ。
# 終了コード: 0 = 全ステップ緑 / 非0 = どこかで落ちた。

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"

PORT="${PORT:-5001}"
PYTHON="${PYTHON:-python3}"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "✗ $PYTHON が見つからない。PYTHON=... で指定してください（macOS は python ではなく python3）。" >&2
  exit 1
fi

if ! "$PYTHON" -c "import flask, requests" >/dev/null 2>&1; then
  echo "✗ flask / requests が入っていない。次を実行してください：" >&2
  echo "    $PYTHON -m pip install flask requests" >&2
  exit 1
fi

cd "$ROOT"
exec env PORT="$PORT" "$PYTHON" "$HERE/smoketest.py" "$@"
