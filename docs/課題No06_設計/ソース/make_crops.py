# -*- coding: utf-8 -*-
"""shots/ のキャプチャを設計書スライド用に切り出す（doc/img/ へ出力）。"""
import os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(HERE, "shots")
O = os.path.join(HERE, "doc", "img")
os.makedirs(O, exist_ok=True)

# gen_doc.py の CROPS と同じ範囲を使う（変えるときは両方直す）
CROPS = [
    ("public_pc.png",     "public_pc",  (0.0,   0.0,   1.0,  1.0)),
    ("ranking_pc.png",    "ranking_pc", (0.0,   0.0,   1.0,  1.0)),
    ("public_pc.png",     "hud_zoom",   (0.205, 0.10,  0.762, 0.685)),
    ("public_sp.png",     "sp_top",     (0.0,   0.0,   1.0,  0.50)),
    ("public_sp.png",     "sp_bottom",  (0.0,   0.50,  1.0,  1.0)),
    ("dashboard_pc.png",  "dash_top",   (0.0,   0.0,   1.0,  0.38)),
    ("dashboard_pc.png",  "dash_tx",    (0.10,  0.383, 0.90, 0.565)),
    ("dashboard_pc.png",  "dash_det",   (0.10,  0.652, 0.90, 0.842)),
    ("public_sp_input.png",  "sp_input",  (0.0, 0.30, 1.0, 0.58)),
    ("public_sp_result.png", "sp_result", (0.0, 0.30, 1.0, 0.58)),
    ("public_sp_error.png",  "sp_error",  (0.0, 0.30, 1.0, 0.58)),
]

for src, name, (l, t, r, b) in CROPS:
    im = Image.open(os.path.join(S, src))
    W, H = im.size
    c = im.crop((int(l * W), int(t * H), int(r * W), int(b * H))).convert("RGB")
    # PDFが重くならないようJPEGで保存する
    c.save(os.path.join(O, name + ".jpg"), quality=88, optimize=True, progressive=True)
    print(name, c.size)

# 画面遷移図はスライドでは題字と注記を落として大きく載せる
flow = os.path.join(HERE, "flow.png")
if os.path.exists(flow):
    im = Image.open(flow); W, H = im.size
    im.crop((int(0.015 * W), int(0.095 * H), int(0.945 * W), int(0.85 * H))).save(os.path.join(O, "flow.png"))
    print("flow.png")
