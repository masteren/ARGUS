# -*- coding: utf-8 -*-
"""shots/ のキャプチャを設計書スライド用に切り出す（doc/img/ へ出力）。

画面全体のキャプチャは crops.py の範囲で切る（gen_doc.py の注釈ピンと同じ範囲）。
パネル・操作パネルの状態は shoot2.js が要素ごとに撮っているので、そのまま縮小して使う。
"""
import os
from PIL import Image

from crops import CROPS

HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(HERE, "shots")
O = os.path.join(HERE, "doc", "img")
os.makedirs(O, exist_ok=True)


def save(im, name):
    # PDFが重くならないようJPEGで保存する
    im.convert("RGB").save(os.path.join(O, name + ".jpg"), quality=88, optimize=True, progressive=True)
    print(name, im.size)


for name, (src, l, t, r, b) in CROPS.items():
    im = Image.open(os.path.join(S, src + ".png"))
    W, H = im.size
    save(im.crop((int(l * W), int(t * H), int(r * W), int(b * H))), name)

# shoot2.js が撮った状態ごとの画像（すでに必要な範囲だけになっている）
STATES = [
    "st_guest", "st_ready", "st_result", "st_error",
    "auth_login", "auth_register", "auth_error",
    "shop_short", "shop_select", "shop_confirm", "shop_done",
]
for name in STATES:
    save(Image.open(os.path.join(S, name + ".png")), name)

# 画面遷移図はスライドでは題字と注記を落として大きく載せる
flow = os.path.join(HERE, "flow.png")
if os.path.exists(flow):
    im = Image.open(flow); W, H = im.size
    im.crop((int(0.012 * W), int(0.072 * H), int(0.94 * W), int(0.885 * H))).save(os.path.join(O, "flow.png"))
    print("flow.png")
