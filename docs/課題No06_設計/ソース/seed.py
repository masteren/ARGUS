# -*- coding: utf-8 -*-
"""撮影用のデータを作る。run_app.py（http://127.0.0.1:5077）を起動してから実行する。

本番と同じ API（/auth/register → /purchase → /pay → /commands/{id}/done）を叩くので、
画面に出る数値はすべてアプリが実際に計算したもの。何度実行しても同じ結果にするため、
先に design.db を消してから run_app.py を起動すること。
"""
import requests

B = "http://127.0.0.1:5077"

# (名前, PIN, 買うパック, 使うアクション)
VISITORS = [
    ("はると", "1111", ["pack_1000"], ["search_person", "bow", "forward"]),
    ("Ken",    "2222", ["pack_1000"], ["search_person", "turn_left", "bow"]),
    ("さくら", "3333", ["pack_500"],  ["wave", "forward"]),
    ("そうた", "4444", ["pack_500"],  ["bow", "turn_right"]),
    ("みお",   "5555", ["pack_500"],  ["forward", "turn_left", "forward"]),
    ("リン",   "6666", ["pack_500"],  ["wave"]),
    ("たいが", "7777", ["pack_500"],  ["forward"]),
    ("ゆい",   "1234", ["pack_1000"], ["forward", "wave"]),
]


def finish_pending():
    """C の代わりに、溜まった命令を実行済みにする（未実行10件で受付が止まるため）。"""
    for c in requests.get(B + "/commands").json()["commands"]:
        requests.post(B + "/commands/%d/done" % c["id"])


for name, pin, packs, actions in VISITORS:
    s = requests.Session()
    r = s.post(B + "/auth/register", json={"name": name, "pin": pin}).json()
    assert r["ok"], r
    for pack in packs:
        r = s.post(B + "/purchase", json={"pack": pack}).json()
        assert r["ok"], r
    for action in actions:
        r = s.post(B + "/pay", json={"action": action}).json()
        assert r["ok"], r
        finish_pending()
    print(name, "残高", s.get(B + "/me").json()["user"]["balance"])

# ミッション1件を成功させ、AI検出履歴に person / mission_person を残す
for i, (t, conf) in enumerate((("person", 0.88), ("mission_person", 0.92), ("person", 0.91)), 1):
    requests.post(B + "/upload", json={
        "type": t, "confidence": conf, "image": "detections/capture_%02d.jpg" % i,
        "bbox": [232, 142, 350, 424], "frame_wh": [640, 480],
    })
print("ok")
