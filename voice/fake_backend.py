# fake_backend.py —— B のバックエンドを模した偽サーバー。C が単独で開発できるようにするためのもの。
# 統合時にはこれを削除し、アドレスを本物の B に差し替えればよい。
from flask import Flask, jsonify
import time

app = Flask(__name__)

# 偽の課金コマンドキュー：「視聴者が課金 → B が生成した動作」を模擬する
fake_commands = [
    {"id": 1, "action": "forward",    "payer_name": "太郎", "amount": 100},
    {"id": 2, "action": "turn_left",  "payer_name": "花子", "amount": 100},
    {"id": 3, "action": "bow",        "payer_name": "次郎", "amount": 300},
]

@app.route("/commands")
def get_commands():
    # 初回は全件返し、以降は空を返す（「取り出したらなくなる」を模擬）
    global fake_commands
    out = fake_commands
    fake_commands = []
    return jsonify(out)

@app.route("/commands/<int:cid>/done", methods=["POST"])
def mark_done(cid):
    print(f"  ✔ B が完了報告を受信: command {cid}")
    return jsonify({"ok": True})

# 偽の検出データ：「A が検出したもの」を模擬し、「何が見える」の応答に使う
@app.route("/events")
def get_events():
    return jsonify([
        {"timestamp": "2026-08-01T14:23:01", "type": "person", "confidence": 0.92},
        {"timestamp": "2026-08-01T14:23:05", "type": "bottle", "confidence": 0.78},
    ])

if __name__ == "__main__":
    print("=== 偽バックエンド(擬似B) 起動 http://localhost:5001 ===")
    app.run(port=5001)
