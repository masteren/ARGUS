# fake_backend.py —— 假装是 B 的后端，只为让 C 能独立开发。
# 集成时删掉它，把地址换成真 B 即可。
from flask import Flask, jsonify
import time

app = Flask(__name__)

# 假的课金命令队列：模拟"观众付费 → B 生成的动作"
fake_commands = [
    {"id": 1, "action": "forward",    "payer_name": "太郎", "amount": 100},
    {"id": 2, "action": "turn_left",  "payer_name": "花子", "amount": 100},
    {"id": 3, "action": "bow",        "payer_name": "次郎", "amount": 300},
]

@app.route("/commands")
def get_commands():
    # 第一次返回全部，之后返回空（模拟"取走就没了"）
    global fake_commands
    out = fake_commands
    fake_commands = []
    return jsonify(out)

@app.route("/commands/<int:cid>/done", methods=["POST"])
def mark_done(cid):
    print(f"  ✔ B 收到完成报告: command {cid}")
    return jsonify({"ok": True})

# 假的检测数据：模拟"A 检测到的东西"，给"看到了什么"用
@app.route("/events")
def get_events():
    return jsonify([
        {"timestamp": "2026-08-01T14:23:01", "type": "person", "confidence": 0.92},
        {"timestamp": "2026-08-01T14:23:05", "type": "bottle", "confidence": 0.78},
    ])

if __name__ == "__main__":
    print("=== 假后端(伪B) 起動 http://localhost:5001 ===")
    app.run(port=5001)
