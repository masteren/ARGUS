# detection_lite.py —— 依存ゼロの軽量検出。画面に「枠」を出すためのもの。
#
# なぜこれがあるか：
#   本命の detection_webcam.py は YOLO（ultralytics）を使う。精度は高いが
#   PyTorch を引き込むので 2〜3GB あり、環境によっては入らない。
#   「展示で枠が出ればいい」だけなら OpenCV 内蔵の検出器で足りる。
#   こちらは **opencv-python と requests だけ**で動く。
#
# B から見た口は detection_webcam.py と同じ（GET /video_feed → POST /upload）。
# したがって公開ページの HUD（templates/public.html の <canvas id="hud">）は
# 何も変えずにそのまま枠を描く。search_person ミッションにも対応する。
#
# 検出方式（ARGUS_DETECTOR で選ぶ）：
#   hog    : OpenCV 内蔵の HOG 歩行者検出。人だと分かって検出するが、
#            6脚ロボットの低い視点では人の全身が入らず外しやすい。
#   motion : 背景差分で「動いたもの」を囲む。視点を選ばず必ず何か出る。
#            ただしロボット自身が歩くと画面全体が動くので、その間は止める。
#   auto   : 既定。hog を試し、取れなければ motion で拾う。
#
# 使い方：
#   python3 detection_lite.py
#   ARGUS_DETECTOR=motion python3 detection_lite.py

import os
import time

import cv2
import numpy as np
import requests

# ── B への接続（detection_webcam.py と同じ規約）──────────────
B_PORT = os.environ.get("PORT", "5000")
# localhost だと Windows で IPv6 先行解決のため1回あたり約2秒待たされる
# （実測 7ms → 2050ms）。検出ループが止まるので明示的に IPv4 を使う。
B_HOST = os.environ.get("ARGUS_B_HOST", "127.0.0.1")
B_URL = "http://%s:%s" % (B_HOST, B_PORT)
UPLOAD_URL = f"{B_URL}/upload"
MISSION_URL = f"{B_URL}/mission/active"
CAMERA_SOURCE = f"{B_URL}/video_feed"

DETECTOR = os.environ.get("ARGUS_DETECTOR", "auto").lower()
POST_INTERVAL = float(os.environ.get("ARGUS_POST_INTERVAL", "1.0"))
MIN_AREA_RATIO = float(os.environ.get("ARGUS_MIN_AREA", "0.02"))   # 画面比。小さすぎる枠は捨てる
MISSION_TYPE = "mission_person"
MISSION_POLL = 2.0

# ミッション成功を「動いた塊」でも認めるか。既定は認めない（人だけ）。
# 低い視点で HOG がどうしても人を取れず、展示で search_person が
# 一度も成功しない…という場合の逃げ道として用意してあるが、
# 有効にすると人が居なくてもミッションが完了しうることは承知の上で使うこと。
MISSION_ACCEPT_MOTION = os.environ.get("ARGUS_MISSION_ACCEPT_MOTION") == "1"

_last_post = 0.0
_mission_active = False
_mission_reported = False
_last_mission_poll = 0.0


# ── 検出器 ────────────────────────────────────────────────
hog = cv2.HOGDescriptor()
hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

# history を短めにして、ロボットが止まった直後から使えるようにする
bg = cv2.createBackgroundSubtractorMOG2(history=200, varThreshold=40,
                                        detectShadows=False)


def detect_hog(frame):
    """OpenCV 内蔵の歩行者検出。(bbox, confidence) か None。"""
    # 検出は縮小画像で行う（そのままだと遅い）。座標は後で戻す。
    scale = 320 / frame.shape[1]
    small = cv2.resize(frame, None, fx=scale, fy=scale)
    rects, weights = hog.detectMultiScale(small, winStride=(8, 8),
                                          padding=(8, 8), scale=1.05)
    if len(rects) == 0:
        return None

    best = int(np.argmax(weights))
    x, y, w, h = (int(v / scale) for v in rects[best])
    conf = float(min(1.0, max(0.0, weights[best][0] / 2.0)))
    return [x, y, x + w, y + h], conf


def detect_motion(frame):
    """背景差分で動いた塊を囲む。(bbox, confidence) か None。"""
    mask = bg.apply(frame)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    mask = cv2.dilate(mask, np.ones((9, 9), np.uint8), iterations=2)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    frame_area = frame.shape[0] * frame.shape[1]
    biggest = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(biggest)

    # 小さすぎるノイズは無視。大きすぎる＝画面全体が動いた（ロボットが歩いた）
    # ときも枠にする意味が無いので捨てる。
    ratio = area / frame_area
    if ratio < MIN_AREA_RATIO or ratio > 0.8:
        return None

    x, y, w, h = cv2.boundingRect(biggest)
    return [x, y, x + w, y + h], float(min(1.0, ratio * 4))


def detect(frame):
    """設定に従って検出する。戻り値は (bbox, confidence, ラベル) か None。"""
    if DETECTOR in ("hog", "auto"):
        found = detect_hog(frame)
        if found:
            return found[0], found[1], "person"
        if DETECTOR == "hog":
            return None

    if DETECTOR in ("motion", "auto"):
        found = detect_motion(frame)
        if found:
            # ラベルは "motion"。これは「動いた」だけで人とは限らないので、
            # 呼び出し側はミッション成功の判定に使ってはいけない（main 参照）。
            return found[0], found[1], "motion"

    return None


# ── B への送信（detection_webcam.py と同じ契約）──────────────
def send_detection(frame, kind, confidence, bbox):
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
    if not ok:
        return False

    import base64
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "type": kind,
        "confidence": round(float(confidence), 2),
        "image": base64.b64encode(buf.tobytes()).decode("ascii"),
        "bbox": [int(v) for v in bbox],
        "frame_wh": [int(frame.shape[1]), int(frame.shape[0])],
    }
    try:
        r = requests.post(UPLOAD_URL, json=payload, timeout=3)
        body = r.json()
        if body.get("mission_success"):
            print("🎯 ミッション成功！", flush=True)
        return r.status_code == 200 and body.get("ok")
    except Exception as e:
        print("[upload]", e, flush=True)
        return False


def poll_mission():
    """ミッションが走っているかを B に聞く。"""
    global _mission_active, _mission_reported, _last_mission_poll

    now = time.time()
    if now - _last_mission_poll < MISSION_POLL:
        return
    _last_mission_poll = now

    try:
        active = bool(requests.get(MISSION_URL, timeout=3).json().get("active"))
    except Exception:
        return

    if active and not _mission_active:
        print("🎫 search_person ミッション開始 → 検出を狙う", flush=True)
        _mission_reported = False
    _mission_active = active


def main():
    global _last_post, _mission_reported

    print(f"[detection_lite] 検出方式 = {DETECTOR}", flush=True)
    print(f"[detection_lite] 映像 = {CAMERA_SOURCE}", flush=True)
    if MISSION_ACCEPT_MOTION:
        print("[detection_lite] ※ 動体でもミッション成功を認める設定です"
              "（人が居なくても完了しえます）", flush=True)
    elif DETECTOR == "motion":
        print("[detection_lite] ※ motion のみのため search_person は自動成功しません。"
              "人物判定が要るなら DETECTOR=auto/hog、または "
              "ARGUS_MISSION_ACCEPT_MOTION=1", flush=True)

    cap = cv2.VideoCapture(CAMERA_SOURCE)
    if not cap.isOpened():
        print("！ B の映像に繋げません。B が起動しているか確認してください。",
              flush=True)
        return

    print("[detection_lite] 開始。Ctrl+C で終了", flush=True)
    last_log = 0.0
    frames = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            time.sleep(0.1)
            continue

        frames += 1
        now = time.time()
        poll_mission()

        found = detect(frame)
        if found:
            bbox, conf, label = found

            # ミッション成功にできるのは「人」と判定できたときだけ。
            # motion（動いた塊）はカメラの揺れやロボット自身の移動でも出るので、
            # それで成功にすると人が居なくても ¥500 のミッションが完了してしまう。
            # B は type が mission_ で始まる /upload を無条件で成功扱いにするため、
            # ここで絞らないと歯止めが無い。
            mission_ok = label == "person" or MISSION_ACCEPT_MOTION

            if _mission_active and not _mission_reported and mission_ok:
                # ミッション中は throttle せず即送る。成功したときだけ
                # 「報告済み」にする（失敗したら次のフレームで再挑戦）。
                _mission_reported = send_detection(frame, MISSION_TYPE, conf, bbox)
                _last_post = now
            elif now - _last_post >= POST_INTERVAL:
                send_detection(frame, label, conf, bbox)
                _last_post = now

        if now - last_log >= 10:
            state = "MISSION" if _mission_active else "NORMAL"
            print(f"[detection_lite] {frames/10:.1f} fps | {state}", flush=True)
            frames = 0
            last_log = now


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n終了します")
