# -*- coding: utf-8 -*-
"""スライドに載せる切り出し範囲。make_crops.py（画像を切る）と gen_doc.py（注釈ピンを置く）の両方が使う。

範囲は撮影時の要素座標（boxes.json）から計算する。画面の行数（取引件数など）が
変わっても、切り出しが表やパネルの途中で途切れないようにするため。
値は (元画像名, 左, 上, 右, 下)。いずれも元画像に対する割合（0.0〜1.0）。
"""
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
BOXES = json.load(open(os.path.join(BASE, "boxes.json"), encoding="utf-8"))


def _box(page, selector, idx=0):
    r = BOXES[page]["els"][selector][idx]
    return r["l"] / 100.0, r["t"] / 100.0, (r["l"] + r["rw"]) / 100.0, (r["t"] + r["rh"]) / 100.0


def _pad(page, px):
    """縦方向の余白 px を、その画面の高さに対する割合に直す。"""
    return px / float(BOXES[page]["H"])


# ── 公開ページ（スマホ）：映像＋操作パネル ／ ボード＋ロボット紹介 ──
_, _, _, pay_b = _box("public_sp", ".payment-panel")
_, board_t, _, _ = _box("public_sp", ".board-panel")
SP_SPLIT_TOP = min(1.0, pay_b + _pad("public_sp", 8))
SP_SPLIT_BOTTOM = max(0.0, board_t - _pad("public_sp", 8))

# ── 管理ダッシュボード：上部（サマリ・直接操作・命令キューの先頭）／ 各履歴 ──
_, q_t, _, q_b = _box("dashboard_pc", ".card", 1)          # ロボット命令キュー
_, pur_t, _, pur_b = _box("dashboard_pc", ".card", 2)      # 購入履歴
_, tx_t, _, tx_b = _box("dashboard_pc", ".card", 3)        # 取引履歴
_, det_t, _, det_b = _box("dashboard_pc", ".card", 4)      # AI検出履歴
_p = _pad("dashboard_pc", 6)

CROPS = {
    "public_pc":  ("public_pc",    0.0,   0.0,   1.0,   1.0),
    "hud_zoom":   ("public_pc",    0.205, 0.10,  0.762, 0.685),
    "sp_top":     ("public_sp",    0.0,   0.0,   1.0,   SP_SPLIT_TOP),
    "sp_bottom":  ("public_sp",    0.0,   SP_SPLIT_BOTTOM, 1.0, 1.0),
    "ranking_pc": ("ranking_pc",   0.0,   0.0,   1.0,   1.0),
    # 命令キューは先頭の数行まで見せる（以降は同じ形の行が続くだけ）
    "dash_top":   ("dashboard_pc", 0.0,   0.0,   1.0,   q_t + (q_b - q_t) * 0.32),
    "dash_pur":   ("dashboard_pc", 0.10,  pur_t - _p, 0.90, pur_b + _p),
    # 取引履歴は先頭の約8行まで
    "dash_tx":    ("dashboard_pc", 0.10,  tx_t - _p,  0.90, tx_t + (tx_b - tx_t) * 0.42),
    "dash_det":   ("dashboard_pc", 0.10,  det_t - _p, 0.90, min(1.0, det_b + _p)),
}
