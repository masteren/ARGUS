#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARGUS ローカル結合スモークテスト — 三モジュールのデータ閉ループだけを検証する。

    観客 --POST /pay--> B --GET /commands--> C(paid_poller の実コード) --> bridge
                          <--POST /commands/{id}/done-- C
    B(missions: active) <--POST /upload type=mission_person-- A
    B --> /mission/latest = success, /overlay = bbox

実機(Freenove)・マイク・カメラ・OpenAI キーは一切要らない。音声 STT/TTS は対象外。

C は書き直したコピーではなく voice/paid_poller.py の poll_paid_commands を
そのまま import してスレッドで回す。したがって「本物のエンドポイント」を叩いている。
bridge は MockBridge を継承した RecordingBridge で、受け取った action を記録するだけ。

使い方:  bash tools/smoketest.sh          （PORT=5001 で起動。PORT= で上書き可）
"""

import base64
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import traceback
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")  # urllib3 の LibreSSL 警告など、判定に無関係な雑音を消す

import requests

# ==================================================
# 設定
# ==================================================
ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "ARGUS_backend"
VOICE_DIR = ROOT / "voice"

# macOS の AirPlay Receiver が 5000 を掴むので、既定は 5001 で逃がす。
PORT = int(os.environ.get("PORT", "5001"))
BASE_URL = "http://127.0.0.1:%d" % PORT

# 本番の argus.db を絶対に触らないよう、使い捨てDBを別名で作る（最後に消す）。
DB_PATH = BACKEND_DIR / "argus.smoketest.db"
LOG_PATH = BACKEND_DIR / "argus.smoketest.log"

BOOT_TIMEOUT = 25.0     # B が /health を返すまで待つ上限（秒）
POLL_INTERVAL = 0.3     # 実 poller のポーリング間隔。既定の 2 秒だとテストが遅いので詰める
STEP_TIMEOUT = 15.0     # 「C が受け取るまで」「done になるまで」の待ち上限（秒）

MISSION_BBOX = [100, 80, 220, 400]
MISSION_FRAME_WH = [640, 480]


# B の PAY_MIN_INTERVAL_SEC と同じ既定値。B 側を変えたらここも合わせる。
PAY_MIN_INTERVAL = float(os.environ.get("ARGUS_PAY_MIN_INTERVAL", "1.5"))


class SmokeFailure(Exception):
    """1ステップでも落ちたらこれを投げ、全体を非0終了させる。"""


# ==================================================
# 表示 / 判定ヘルパ
# ==================================================
def section(title):
    print("\n%s" % title, flush=True)


def ok(label):
    print("  ✓ %s" % label, flush=True)


def check(label, condition, detail=""):
    if condition:
        ok(label)
        return
    print("  ✗ %s" % label, flush=True)
    if detail:
        print("      → %s" % detail, flush=True)
    raise SmokeFailure(label)


def wait_until(predicate, timeout=STEP_TIMEOUT, interval=0.2):
    """predicate() が真を返すまで待つ。返り値は最後の predicate() の結果。"""
    deadline = time.time() + timeout
    result = False
    while time.time() < deadline:
        try:
            result = predicate()
        except Exception:
            result = False
        if result:
            return result
        time.sleep(interval)
    return result


def get_json(path, **params):
    resp = requests.get(BASE_URL + path, params=params or None, timeout=5)
    return resp.status_code, resp.json()


def post_json(path, payload):
    resp = requests.post(BASE_URL + path, json=payload, timeout=5)
    return resp.status_code, resp.json()


# ==================================================
# B（バックエンド）の起動 / 停止
# ==================================================
def port_is_busy(port):
    sock = socket.socket()
    sock.settimeout(0.5)
    try:
        sock.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def start_backend():
    """PORT と ARGUS_DB を環境変数で渡して app.py を別プロセスで起動する。"""
    env = os.environ.copy()
    env["PORT"] = str(PORT)
    env["ARGUS_DB"] = str(DB_PATH)
    env["PYTHONUNBUFFERED"] = "1"

    log_file = LOG_PATH.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=str(BACKEND_DIR),
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,   # プロセスグループごと確実に落とせるようにする
    )
    return proc, log_file


def wait_for_health(proc):
    deadline = time.time() + BOOT_TIMEOUT
    while time.time() < deadline:
        if proc.poll() is not None:
            return False
        try:
            status, body = get_json("/health")
            if status == 200 and body.get("ok"):
                return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


def stop_backend(proc, log_file):
    if log_file is not None and not log_file.closed:
        log_file.close()

    if proc is None or proc.poll() is not None:
        return

    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(os.getpgid(proc.pid), sig)
        except OSError:
            try:
                proc.kill()
            except OSError:
                pass
        try:
            proc.wait(timeout=5)
            return
        except subprocess.TimeoutExpired:
            continue


def dump_backend_log():
    if not LOG_PATH.exists():
        return
    text = LOG_PATH.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return
    print("\n---- B のログ（末尾30行）" + "-" * 30, flush=True)
    for line in text.splitlines()[-30:]:
        print("   " + line, flush=True)
    print("-" * 54, flush=True)


def remove_temp_files():
    removed = []
    for path in (DB_PATH, Path(str(DB_PATH) + "-wal"), Path(str(DB_PATH) + "-shm"), LOG_PATH):
        if path.exists():
            path.unlink()
            removed.append(path.name)
    return removed


# ==================================================
# C：本物の paid_poller をロードする
# ==================================================
class RecordingBridge(object):
    """MockBridge を継承し、C の実コードが送ってきた action を記録する。

    MockBridge のログ出力はそのまま残すので、ターミナルには実機と同じ
    「🦿 [MOCK] robot <- forward ...」が流れる。"""

    def __init__(self, mock_cls):
        self._mock = mock_cls()
        self._lock = threading.Lock()
        self.actions = []

    def send(self, action, **kwargs):
        with self._lock:
            self.actions.append(action)
        self._mock.send(action, **kwargs)

    def has(self, action):
        with self._lock:
            return action in self.actions

    def snapshot(self):
        with self._lock:
            return list(self.actions)


def load_real_poller():
    """voice/ を import パスに足して、C の実コードをそのまま読み込む。

    argus_voice.py は openai / sounddevice を import するので触らない。
    ここで要るのは paid_poller と robot_bridge だけ。"""
    os.environ["PORT"] = str(PORT)          # module 読み込み時に B_URL が確定するので先に入れる
    sys.path.insert(0, str(VOICE_DIR))
    import robot_bridge
    import paid_poller
    return paid_poller, robot_bridge


# ==================================================
# 本体
# ==================================================
def run_checks():
    # ── 前提 ────────────────────────────────────────
    section("[0] 前提")
    check(
        "ポート %d が空いている" % PORT,
        not port_is_busy(PORT),
        "誰かが %d を使っている。macOS なら システム設定 > 一般 > AirDrop と Handoff > "
        "AirPlay レシーバー を切るか、PORT=5003 bash tools/smoketest.sh で逃がす" % PORT,
    )

    proc, log_file = start_backend()
    globals()["_PROC"] = proc
    globals()["_LOG_FILE"] = log_file

    check(
        "B が起動して /health を返す (PORT=%d)" % PORT,
        wait_for_health(proc),
        "%.0f 秒待っても応答なし。B のログを確認" % BOOT_TIMEOUT,
    )

    paid_poller, robot_bridge = load_real_poller()
    check(
        "C の paid_poller が PORT を見ている (B_URL=%s)" % paid_poller.B_URL,
        paid_poller.B_URL.endswith(":%d" % PORT),
        "paid_poller.B_URL = %r（PORT が効いていない）" % paid_poller.B_URL,
    )

    bridge = RecordingBridge(robot_bridge.MockBridge)
    threading.Thread(
        target=paid_poller.poll_paid_commands,
        args=(bridge,),
        kwargs={"interval": POLL_INTERVAL},
        daemon=True,
    ).start()
    ok("C の poll_paid_commands（実コード）をスレッドで起動")

    # ── 契約の封筒 ──────────────────────────────────
    section("[1] 契約：レスポンスの封筒 {\"ok\":true, ...}")
    status, body = get_json("/commands")
    check(
        "/commands が {\"ok\":true,\"commands\":[...]} を返す",
        status == 200 and body.get("ok") is True and isinstance(body.get("commands"), list),
        "status=%s body=%r" % (status, body),
    )
    status, body = get_json("/events")
    check(
        "/events が {\"ok\":true,\"events\":[...]} を返す",
        status == 200 and body.get("ok") is True and isinstance(body.get("events"), list),
        "status=%s body=%r" % (status, body),
    )

    # ── 課金 → C → bridge → done ────────────────────
    section("[2] 観客 → B(/pay) → C(実 poller) → bridge → B(/commands/{id}/done)")
    status, pay = post_json("/pay", {"payer_name": "smoke_taro", "action": "forward"})
    check(
        "POST /pay action=forward が受理された",
        status == 200 and pay.get("ok") is True and pay.get("command_id"),
        "status=%s body=%r" % (status, pay),
    )
    forward_command_id = pay["command_id"]

    check(
        "C の RecordingBridge が forward を受け取った",
        wait_until(lambda: bridge.has("forward")),
        "%.0f 秒以内に届かず。bridge が受けた action = %r" % (STEP_TIMEOUT, bridge.snapshot()),
    )

    def forward_is_done():
        _, done = get_json("/commands", status="done")
        return forward_command_id in [c["id"] for c in done.get("commands", [])]

    check(
        "B 側でコマンド id=%d が done になった" % forward_command_id,
        wait_until(forward_is_done),
        "%.0f 秒待っても pending のまま" % STEP_TIMEOUT,
    )

    # ── 連打への備え（要件定義書 NFR）───────────────
    # 展示端末は共用なので、連打だけを弾いて端末ごと締め出さないこと。
    status, blocked = post_json("/pay", {"payer_name": "smoke_taro", "action": "forward"})
    check(
        "連打（%.1f秒以内の再送）は 429 で弾かれる" % PAY_MIN_INTERVAL,
        status == 429 and blocked.get("ok") is False,
        "status=%s body=%r" % (status, blocked),
    )

    status, bad = post_json("/pay", {"payer_name": "x" * 100, "action": "forward"})
    check(
        "長すぎる名前は 400 で弾かれる",
        status == 400 and bad.get("ok") is False,
        "status=%s body=%r" % (status, bad),
    )

    # 間隔を空ければ通常どおり受理される（＝締め出しではない）
    time.sleep(PAY_MIN_INTERVAL + 0.1)

    # ── ミッション開始 ──────────────────────────────
    section("[3] 課金 search_person → ミッションが active になる")
    status, pay = post_json("/pay", {"payer_name": "smoke_hanako", "action": "search_person"})
    check(
        "POST /pay action=search_person が受理された",
        status == 200 and pay.get("ok") is True,
        "status=%s body=%r" % (status, pay),
    )

    status, body = get_json("/mission/active")
    check(
        "/mission/active が active=true を返す",
        status == 200 and body.get("ok") is True and body.get("active") is True,
        "status=%s body=%r" % (status, body),
    )

    check(
        "C の RecordingBridge が search_person（巡回モーション）も受け取った",
        wait_until(lambda: bridge.has("search_person")),
        "bridge が受けた action = %r" % (bridge.snapshot(),),
    )

    # ── A の検出でミッション成功 ────────────────────
    section("[4] A(/upload type=mission_person + bbox) → ミッション成功 + HUD オーバーレイ")
    fake_jpeg_b64 = base64.b64encode(b"smoketest-dummy-frame-not-a-real-jpeg").decode("ascii")
    status, up = post_json(
        "/upload",
        {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "type": "mission_person",
            "confidence": 0.91,
            "image": fake_jpeg_b64,
            "bbox": MISSION_BBOX,
            "frame_wh": MISSION_FRAME_WH,
        },
    )
    check(
        "POST /upload が mission_success=true を返す",
        status == 200 and up.get("ok") is True and up.get("mission_success") is True,
        "status=%s body=%r" % (status, up),
    )

    status, body = get_json("/mission/latest")
    mission = body.get("mission") or {}
    check(
        "/mission/latest の状態が success に変わった",
        status == 200 and mission.get("status") == "success",
        "status=%s body=%r" % (status, body),
    )
    check(
        "/mission/active が active=false に戻った",
        get_json("/mission/active")[1].get("active") is False,
        "まだ active のまま",
    )

    status, body = get_json("/overlay")
    check(
        "/overlay に bbox=%r と frame_wh=%r が載っている" % (MISSION_BBOX, MISSION_FRAME_WH),
        status == 200
        and body.get("bbox") == MISSION_BBOX
        and body.get("frame_wh") == MISSION_FRAME_WH,
        "status=%s body=%r" % (status, body),
    )

    status, body = get_json("/events", limit=5)
    latest = (body.get("events") or [{}])[0]
    check(
        "/events からも mission_person が bbox 付きで読める",
        latest.get("type") == "mission_person" and latest.get("bbox") == MISSION_BBOX,
        "先頭イベント = %r" % (latest,),
    )

    # ── 決済台帳 ────────────────────────────────────
    section("[5] transactions の状態が paid（/api/ranking で間接確認）")
    status, body = get_json("/api/ranking")
    ranking = body.get("ranking") or []
    totals = {r["payer_name"]: r["total_amount"] for r in ranking}
    check(
        "/api/ranking（status='paid' のみ集計）に2件の課金が載っている",
        status == 200 and body.get("ok") is True and len(ranking) >= 2,
        "status=%s body=%r" % (status, body),
    )
    status, feed = get_json("/api/transactions", limit=5)
    check(
        "/api/transactions が直近の取引を返す（公開ページのフィード用）",
        status == 200
        and feed.get("ok") is True
        and [t["payer_name"] for t in feed.get("transactions", [])][:2]
        == ["smoke_hanako", "smoke_taro"],
        "status=%s body=%r" % (status, feed),
    )

    check(
        "内訳が正しい: smoke_taro=100(forward), smoke_hanako=500(search_person)",
        totals.get("smoke_taro") == 100 and totals.get("smoke_hanako") == 500,
        "集計 = %r" % (totals,),
    )


def main():
    print("=" * 62, flush=True)
    print("ARGUS 結合スモークテスト  (PORT=%d, DB=%s)" % (PORT, DB_PATH.name), flush=True)
    print("実機・マイク・カメラ・OpenAI キーは不要。データ閉ループのみを検証する。", flush=True)
    print("=" * 62, flush=True)

    exit_code = 0
    try:
        run_checks()
    except SmokeFailure as failure:
        print("\n✗ 失敗したステップ: %s" % failure, flush=True)
        dump_backend_log()
        exit_code = 1
    except Exception:
        print("\n✗ スモークテスト自体が例外で落ちた:", flush=True)
        traceback.print_exc()
        dump_backend_log()
        exit_code = 1
    finally:
        stop_backend(globals().get("_PROC"), globals().get("_LOG_FILE"))
        removed = remove_temp_files()

    print("", flush=True)
    print("後片付け: B を停止し、一時ファイルを削除 (%s)" % (", ".join(removed) if removed else "なし"), flush=True)
    print("=" * 62, flush=True)
    if exit_code == 0:
        print("✓ ALL GREEN — 三モジュールのデータ閉ループは通っている。", flush=True)
    else:
        print("✗ FAILED — 上の ✗ を参照。", flush=True)
    print("=" * 62, flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
