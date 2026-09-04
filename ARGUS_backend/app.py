from flask import Flask, request, jsonify, render_template, redirect, url_for, Response
import sqlite3
from pathlib import Path
from datetime import datetime
import uuid
import time
import threading

try:
    import cv2
except ImportError:
    cv2 = None


# ==================================================
# Flask / 基本設定
# ==================================================
app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "argus.db"
CAMERA_INDEX = 0
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480


# ==================================================
# アクション設定
# ==================================================
ACTIONS = {
    "forward": {
        "label": "前進",
        "amount": 100,
        "description": "ロボットを少し前進させます",
    },
    "turn_left": {
        "label": "左旋回",
        "amount": 100,
        "description": "ロボットを左に旋回させます",
    },
    "turn_right": {
        "label": "右旋回",
        "amount": 100,
        "description": "ロボットを右に旋回させます",
    },
    "bow": {
        "label": "お辞儀",
        "amount": 300,
        "description": "ロボットがお辞儀します",
    },
    "wave": {
        "label": "手を振る",
        "amount": 300,
        "description": "ロボットが手を振る動作をします",
    },
    "search_person": {
        "label": "人を探す",
        "amount": 500,
        "description": "人物検出ミッションを開始します",
    },
}


# ==================================================
# 共通処理
# ==================================================
def now_text():
    """現在時刻をDB保存用の文字列で返す。"""
    return datetime.now().isoformat(timespec="seconds")


def get_connection():
    """SQLiteに接続する。Row指定で row['name'] の形で扱える。"""
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def rows_to_dicts(rows):
    """sqlite3.RowのリストをJSONにしやすいdictのリストへ変換する。"""
    return [dict(row) for row in rows]


# ==================================================
# DB初期化
# ==================================================
def init_db():
    with get_connection() as con:
        cur = con.cursor()

        # AI画像認識の検出履歴
        cur.execute("""
            CREATE TABLE IF NOT EXISTS detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                type TEXT NOT NULL,
                confidence REAL,
                image TEXT,
                created_at TEXT NOT NULL
            )
            """)

        # 投げ銭 / 決済の履歴
        cur.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payment_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                amount INTEGER NOT NULL,
                action TEXT NOT NULL,
                action_label TEXT NOT NULL,
                payer_name TEXT NOT NULL,
                message TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """)

        # ロボットへ送る命令キュー
        cur.execute("""
            CREATE TABLE IF NOT EXISTS command_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id INTEGER,
                action TEXT NOT NULL,
                action_label TEXT NOT NULL,
                source TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                done_at TEXT,
                FOREIGN KEY (transaction_id) REFERENCES transactions(id)
            )
            """)

        con.commit()


# ==================================================
# 模擬決済処理
# 後でStripeなどに差し替え可能
# ==================================================
def process_payment(amount, payer_name):
    payment_id = "dummy_" + uuid.uuid4().hex[:12]

    return {
        "success": True,
        "payment_id": payment_id,
        "status": "paid",
    }


# ==================================================
# カメラ配信処理
# /video_feed でブラウザへリアルタイム映像を流す
# ==================================================
_camera = None
_camera_lock = threading.Lock()


def get_camera():
    """カメラを1回だけ起動して使い回す。"""
    global _camera

    if cv2 is None:
        return None

    if _camera is None:
        camera = cv2.VideoCapture(CAMERA_INDEX)
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)

        if not camera.isOpened():
            camera.release()
            return None

        _camera = camera

    return _camera


def generate_camera_frames():
    """カメラ映像をJPEGの連続データとして返す。"""
    camera = get_camera()

    if camera is None:
        return

    while True:
        with _camera_lock:
            success, frame = camera.read()

        if not success:
            time.sleep(0.1)
            continue

        ok, buffer = cv2.imencode(".jpg", frame)

        if not ok:
            time.sleep(0.1)
            continue

        frame_bytes = buffer.tobytes()

        yield (
            b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
        )


@app.route("/video_feed")
def video_feed():
    if cv2 is None:
        return (
            "OpenCVがインストールされていません。pip install opencv-python を実行してください。",
            500,
        )

    if get_camera() is None:
        return (
            "カメラを起動できませんでした。カメラ接続やCAMERA_INDEXを確認してください。",
            500,
        )

    return Response(
        generate_camera_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store"},
    )


# ==================================================
# 画面表示ルート
# ==================================================
@app.route("/")
def public_page():
    """観客向け公開ページ。投げ銭操作、ライブ映像、ランキングを表示。"""
    with get_connection() as con:
        cur = con.cursor()

        transactions = cur.execute("""
            SELECT *
            FROM transactions
            ORDER BY id DESC
            LIMIT 10
            """).fetchall()

        ranking = cur.execute("""
            SELECT
                payer_name,
                SUM(amount) AS total_amount,
                COUNT(*) AS pay_count
            FROM transactions
            WHERE status = 'paid'
            GROUP BY payer_name
            ORDER BY total_amount DESC
            LIMIT 5
            """).fetchall()

    return render_template(
        "public.html",
        actions=ACTIONS,
        transactions=transactions,
        ranking=ranking,
    )


@app.route("/dashboard")
def dashboard():
    """運営向け管理ダッシュボード。"""
    with get_connection() as con:
        cur = con.cursor()

        detections = cur.execute("""
            SELECT *
            FROM detections
            ORDER BY id DESC
            LIMIT 20
            """).fetchall()

        transactions = cur.execute("""
            SELECT *
            FROM transactions
            ORDER BY id DESC
            LIMIT 20
            """).fetchall()

        commands = cur.execute("""
            SELECT *
            FROM command_queue
            ORDER BY id DESC
            LIMIT 20
            """).fetchall()

        total_sales = cur.execute("""
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM transactions
            WHERE status = 'paid'
            """).fetchone()["total"]

        transaction_count = cur.execute("""
            SELECT COUNT(*) AS count
            FROM transactions
            """).fetchone()["count"]

        pending_count = cur.execute("""
            SELECT COUNT(*) AS count
            FROM command_queue
            WHERE status = 'pending'
            """).fetchone()["count"]

    return render_template(
        "dashboard.html",
        detections=detections,
        transactions=transactions,
        commands=commands,
        total_sales=total_sales,
        transaction_count=transaction_count,
        pending_count=pending_count,
    )


# ==================================================
# API：画像認識 / 検出履歴
# ==================================================
@app.route("/upload", methods=["POST"])
def upload_detection():
    """A担当：AI画像認識結果を保存する。"""
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"ok": False, "error": "JSONデータがありません"}), 400

    detection_type = data.get("type")
    confidence = data.get("confidence")
    image = data.get("image")
    timestamp = data.get("timestamp") or now_text()

    if not detection_type:
        return jsonify({"ok": False, "error": "type が必要です"}), 400

    created_at = now_text()

    with get_connection() as con:
        cur = con.cursor()
        cur.execute(
            """
            INSERT INTO detections (timestamp, type, confidence, image, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (timestamp, detection_type, confidence, image, created_at),
        )
        detection_id = cur.lastrowid
        con.commit()

    return jsonify(
        {
            "ok": True,
            "message": "検出イベントを保存しました",
            "detection_id": detection_id,
        }
    )


@app.route("/events")
def get_events():
    """検出履歴をJSONで取得する。"""
    limit = request.args.get("limit", 20, type=int)

    with get_connection() as con:
        cur = con.cursor()
        rows = cur.execute(
            """
            SELECT *
            FROM detections
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return jsonify({"ok": True, "events": rows_to_dicts(rows)})


# ==================================================
# API：投げ銭 / ロボット操作命令
# ==================================================
@app.route("/pay", methods=["POST"])
def pay():
    """観客：投げ銭をしてロボット操作命令を登録する。"""
    data = request.get_json(silent=True) or request.form

    payer_name = data.get("payer_name", "").strip() or "匿名"
    action = data.get("action", "").strip()
    message = data.get("message", "").strip()

    if action not in ACTIONS:
        return jsonify({"ok": False, "error": "存在しないアクションです"}), 400

    amount = ACTIONS[action]["amount"]
    action_label = ACTIONS[action]["label"]

    payment_result = process_payment(amount, payer_name)

    if not payment_result["success"]:
        return jsonify({"ok": False, "error": "決済に失敗しました"}), 400

    created_at = now_text()

    with get_connection() as con:
        cur = con.cursor()

        # 1. 取引履歴を保存
        cur.execute(
            """
            INSERT INTO transactions
            (payment_id, timestamp, amount, action, action_label, payer_name, message, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payment_result["payment_id"],
                created_at,
                amount,
                action,
                action_label,
                payer_name,
                message,
                payment_result["status"],
                created_at,
            ),
        )
        transaction_id = cur.lastrowid

        # 2. ロボット操作命令をキューに登録
        cur.execute(
            """
            INSERT INTO command_queue
            (transaction_id, action, action_label, source, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (transaction_id, action, action_label, "paid", "pending", created_at),
        )
        command_id = cur.lastrowid

        con.commit()

    return jsonify(
        {
            "ok": True,
            "message": "決済が完了し、ロボット命令を登録しました",
            "transaction_id": transaction_id,
            "command_id": command_id,
            "amount": amount,
            "action": action,
            "action_label": action_label,
            "payer_name": payer_name,
            "payment_id": payment_result["payment_id"],
        }
    )


@app.route("/commands")
def get_commands():
    """ロボット側：未実行コマンドを取得する。"""
    status = request.args.get("status", "pending")

    with get_connection() as con:
        cur = con.cursor()
        rows = cur.execute(
            """
            SELECT *
            FROM command_queue
            WHERE status = ?
            ORDER BY id ASC
            """,
            (status,),
        ).fetchall()

    return jsonify({"ok": True, "commands": rows_to_dicts(rows)})


@app.route("/commands/<int:command_id>/done", methods=["POST"])
def command_done(command_id):
    """ロボット側：実行したコマンドを完了済みにする。"""
    done_at = now_text()

    with get_connection() as con:
        cur = con.cursor()
        cur.execute(
            """
            UPDATE command_queue
            SET status = 'done',
                done_at = ?
            WHERE id = ?
            """,
            (done_at, command_id),
        )

        if cur.rowcount == 0:
            return (
                jsonify({"ok": False, "error": "指定されたコマンドが見つかりません"}),
                404,
            )

        con.commit()

    return jsonify(
        {
            "ok": True,
            "message": "コマンドを完了にしました",
            "command_id": command_id,
        }
    )


# ==================================================
# ランキング画面
# ==================================================
@app.route("/ranking")
def ranking_page():
    """投げ銭ランキング画面を表示する。"""
    today_prefix = datetime.now().date().isoformat() + "%"

    with get_connection() as con:
        cur = con.cursor()

        ranking = cur.execute("""
            SELECT
                payer_name,
                SUM(amount) AS total_amount,
                COUNT(*) AS pay_count
            FROM transactions
            WHERE status = 'paid'
            GROUP BY payer_name
            ORDER BY total_amount DESC, payer_name ASC
            LIMIT 10
            """).fetchall()

        total_donation = cur.execute("""
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM transactions
            WHERE status = 'paid'
            """).fetchone()["total"]

        today_command_count = cur.execute(
            """
            SELECT COUNT(*) AS count
            FROM command_queue
            WHERE created_at LIKE ?
            """,
            (today_prefix,),
        ).fetchone()["count"]

        active_users = cur.execute("""
            SELECT COUNT(DISTINCT payer_name) AS count
            FROM transactions
            WHERE status = 'paid'
            """).fetchone()["count"]

        latest_support = cur.execute("""
            SELECT
                payer_name,
                amount,
                action_label,
                timestamp
            FROM transactions
            WHERE status = 'paid'
            ORDER BY id DESC
            LIMIT 1
            """).fetchone()

    return render_template(
        "ranking.html",
        ranking=ranking,
        total_donation=total_donation,
        today_command_count=today_command_count,
        active_users=active_users,
        latest_support=latest_support,
    )


# ==================================================
# API：ランキングデータ
# ==================================================
@app.route("/api/ranking")
def get_ranking():
    """投げ銭ランキングをJSONで取得する。"""
    with get_connection() as con:
        cur = con.cursor()

        rows = cur.execute("""
            SELECT
                payer_name,
                SUM(amount) AS total_amount,
                COUNT(*) AS pay_count
            FROM transactions
            WHERE status = 'paid'
            GROUP BY payer_name
            ORDER BY total_amount DESC, payer_name ASC
            LIMIT 10
            """).fetchall()

    return jsonify(
        {
            "ok": True,
            "ranking": rows_to_dicts(rows),
        }
    )


# ==================================================
# テスト用ルート
# ==================================================
@app.route("/dummy/detection")
def dummy_detection():
    """管理画面テスト用：ダミー検出履歴を1件追加する。"""
    created_at = now_text()

    with get_connection() as con:
        cur = con.cursor()
        cur.execute(
            """
            INSERT INTO detections (timestamp, type, confidence, image, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (created_at, "person", 0.92, "detections/sample.jpg", created_at),
        )
        con.commit()

    return redirect(url_for("dashboard"))


@app.route("/health")
def health():
    """動作確認用。"""
    return jsonify({"ok": True, "message": "ARGUS server is running"})


# ==================================================
# 起動処理
# ==================================================
if __name__ == "__main__":
    init_db()
    app.run(
        debug=True,
        host="0.0.0.0",
        port=5000,
        use_reloader=False,
    )
