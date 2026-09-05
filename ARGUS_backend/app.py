from flask import Flask, request, jsonify, render_template, redirect, url_for, Response
from werkzeug.exceptions import HTTPException
import sqlite3
from pathlib import Path
from datetime import datetime
import uuid
import time
import threading
import json
import os

try:
    import cv2
except ImportError:
    cv2 = None


# ==================================================
# Flask / 基本設定
# ==================================================
app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent

# ── 環境変数で上書きできる設定（既定値は契約どおり）───────────────
# PORT     : macOS の AirPlay Receiver が 5000 を掴むため、ローカル結合試験は
#            PORT=5001 で逃がす。未設定なら 5000（正本の既定値）。
# ARGUS_DB : 結合試験が本番の argus.db を壊さないよう、使い捨てDBを指せる。
PORT = int(os.environ.get("PORT", "5000"))
DB_PATH = Path(os.environ.get("ARGUS_DB") or (BASE_DIR / "argus.db"))

# ARGUS_DEBUG : 既定は OFF。展示は同一LANに観客の端末が居るため、debug=True の
#               ままだと Werkzeug のデバッガ（＝任意コード実行）が誰にでも開く。
#               開発中だけ ARGUS_DEBUG=1 で有効化する。
DEBUG = os.environ.get("ARGUS_DEBUG", "0") == "1"

# ── 入力検証・連打への備え（要件定義書 NFR）──────────────────
# 展示端末は共用（1台を観客が順番に使う）ため、IPで強く絞ると端末ごと止まる。
# 防ぎたいのは「連打で命令キューが溢れ、ロボットが数分間詰まる」ことなので、
#   ① 同一IPからの最短間隔  ② 未実行コマンドの上限
# の2段で受け止める。
PAY_MIN_INTERVAL_SEC = float(os.environ.get("ARGUS_PAY_MIN_INTERVAL", "1.5"))
PENDING_COMMAND_LIMIT = 10
MAX_PAYER_NAME_LEN = 24
MAX_MESSAGE_LEN = 100

_last_pay_at = {}                 # client ip -> 最後に受理した時刻
_pay_guard_lock = threading.Lock()

CAMERA_INDEX = 0
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480


# ==================================================
# アクション設定
# amount は体験チケット（模擬通貨）の枚数。実際の金銭は動かさない。
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


# ミッション（¥500 の目玉 / CONTRACT.md ①）
# search_person を課金すると missions に active 行が立ち、A から
# type が "mission_" で始まる検出が届いた時点で success になる。
MISSION_ACTIONS = {"search_person"}
MISSION_DETECTION_PREFIX = "mission_"


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


def clean_text(value):
    """観客が入力した文字列を整える。制御文字を落として前後の空白を取る。"""
    if not isinstance(value, str):
        return ""
    return "".join(ch for ch in value if ch.isprintable()).strip()


def rows_to_dicts(rows):
    """sqlite3.RowのリストをJSONにしやすいdictのリストへ変換する。"""
    return [dict(row) for row in rows]


def dump_json_field(value):
    """bbox / frame_wh のようなリストをTEXT列へ保存する。Noneはそのまま。"""
    return None if value is None else json.dumps(value)


def load_json_field(text):
    """TEXT列に入れた bbox / frame_wh を読み戻す。壊れていたら None。"""
    if not text:
        return None
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return None


# ==================================================
# DB初期化
# ==================================================
def ensure_column(cur, table, column, decl):
    """既存DBを作り直さずに済むよう、後から足した列を必要なときだけ追加する。"""
    existing = {row["name"] for row in cur.execute("PRAGMA table_info(%s)" % table)}
    if column not in existing:
        cur.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, column, decl))


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
                bbox TEXT,
                frame_wh TEXT,
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

        # search_person ミッションの状態（CONTRACT.md ①）
        cur.execute("""
            CREATE TABLE IF NOT EXISTS missions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id INTEGER,
                command_id INTEGER,
                action TEXT NOT NULL,
                action_label TEXT NOT NULL,
                payer_name TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                success_at TEXT,
                detection_id INTEGER,
                FOREIGN KEY (transaction_id) REFERENCES transactions(id)
            )
            """)

        # 既存DB（bbox列が無い頃のもの）を壊さずに移行する
        ensure_column(cur, "detections", "bbox", "TEXT")
        ensure_column(cur, "detections", "frame_wh", "TEXT")

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
    bbox = data.get("bbox")          # 任意：[x1,y1,x2,y2]（ピクセル）
    frame_wh = data.get("frame_wh")  # 任意：[w,h]（ピクセル）

    if not detection_type:
        return jsonify({"ok": False, "error": "type が必要です"}), 400

    created_at = now_text()
    mission_success = False
    mission_id = None

    with get_connection() as con:
        cur = con.cursor()
        cur.execute(
            """
            INSERT INTO detections
            (timestamp, type, confidence, image, bbox, frame_wh, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                timestamp,
                detection_type,
                confidence,
                image,
                dump_json_field(bbox),
                dump_json_field(frame_wh),
                created_at,
            ),
        )
        detection_id = cur.lastrowid

        # type が "mission_" で始まる検出は、進行中ミッションの成功報告として扱う
        if detection_type.startswith(MISSION_DETECTION_PREFIX):
            active = cur.execute("""
                SELECT id
                FROM missions
                WHERE status = 'active'
                ORDER BY id DESC
                LIMIT 1
                """).fetchone()

            if active is not None:
                cur.execute(
                    """
                    UPDATE missions
                    SET status = 'success',
                        success_at = ?,
                        detection_id = ?
                    WHERE id = ?
                    """,
                    (created_at, detection_id, active["id"]),
                )
                mission_success = True
                mission_id = active["id"]

        con.commit()

    return jsonify(
        {
            "ok": True,
            "message": "検出イベントを保存しました",
            "detection_id": detection_id,
            "mission_success": mission_success,
            "mission_id": mission_id,
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

    events = rows_to_dicts(rows)

    # bbox / frame_wh はTEXT列なので、JSONとして返す前にリストへ戻す
    for event in events:
        event["bbox"] = load_json_field(event.get("bbox"))
        event["frame_wh"] = load_json_field(event.get("frame_wh"))

    return jsonify({"ok": True, "events": events})


# ==================================================
# API：投げ銭 / ロボット操作命令
# ==================================================
@app.route("/pay", methods=["POST"])
def pay():
    """観客：投げ銭をしてロボット操作命令を登録する。"""
    data = request.get_json(silent=True) or request.form

    payer_name = clean_text(data.get("payer_name", "")) or "匿名"
    action = data.get("action", "").strip()
    message = clean_text(data.get("message", ""))

    if action not in ACTIONS:
        return jsonify({"ok": False, "error": "存在しないアクションです"}), 400

    if len(payer_name) > MAX_PAYER_NAME_LEN:
        return jsonify(
            {"ok": False, "error": "名前は%d文字までです" % MAX_PAYER_NAME_LEN}
        ), 400

    if len(message) > MAX_MESSAGE_LEN:
        return jsonify(
            {"ok": False, "error": "メッセージは%d文字までです" % MAX_MESSAGE_LEN}
        ), 400

    # 連打の受け止め（同一端末からの最短間隔）
    client_ip = request.remote_addr or "unknown"
    now = time.time()

    with _pay_guard_lock:
        if now - _last_pay_at.get(client_ip, 0.0) < PAY_MIN_INTERVAL_SEC:
            return jsonify(
                {"ok": False, "error": "操作が速すぎます。少し待ってからもう一度お願いします"}
            ), 429
        _last_pay_at[client_ip] = now

    # ロボットが捌ける以上に命令を溜めない
    with get_connection() as con:
        pending = con.execute(
            "SELECT COUNT(*) AS count FROM command_queue WHERE status = 'pending'"
        ).fetchone()["count"]

    if pending >= PENDING_COMMAND_LIMIT:
        return jsonify(
            {"ok": False, "error": "ARGUS が混み合っています。少し待ってからお試しください"}
        ), 429

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

        # 3. ミッション課金なら missions に active 行を立てる
        #    （成功判定は A からの mission_* 検出を受ける /upload 側）
        mission_id = None

        if action in MISSION_ACTIONS:
            cur.execute(
                """
                INSERT INTO missions
                (transaction_id, command_id, action, action_label, payer_name, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    transaction_id,
                    command_id,
                    action,
                    action_label,
                    payer_name,
                    "active",
                    created_at,
                ),
            )
            mission_id = cur.lastrowid

        con.commit()

    return jsonify(
        {
            "ok": True,
            "message": "決済が完了し、ロボット命令を登録しました",
            "transaction_id": transaction_id,
            "command_id": command_id,
            "mission_id": mission_id,
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
# API：ミッション状態（CONTRACT.md ①）
# ==================================================
@app.route("/mission/active")
def mission_active():
    """進行中（active）のミッションを返す。無ければ active=false。"""
    with get_connection() as con:
        cur = con.cursor()
        row = cur.execute("""
            SELECT *
            FROM missions
            WHERE status = 'active'
            ORDER BY id DESC
            LIMIT 1
            """).fetchone()

    return jsonify(
        {
            "ok": True,
            "active": row is not None,
            "mission": dict(row) if row is not None else None,
        }
    )


@app.route("/mission/latest")
def mission_latest():
    """最後に登録されたミッションを状態つきで返す（公開ページの成功演出用）。"""
    with get_connection() as con:
        cur = con.cursor()
        row = cur.execute("""
            SELECT *
            FROM missions
            ORDER BY id DESC
            LIMIT 1
            """).fetchone()

    return jsonify(
        {
            "ok": True,
            "mission": dict(row) if row is not None else None,
            "status": row["status"] if row is not None else None,
        }
    )


# ==================================================
# API：HUDオーバーレイ（CONTRACT.md ②）
# 公開ページが /video_feed の上に描く「最新の bbox」を返す
# ==================================================
def overlay_age_sec(created_at):
    """描画側が古い枠を消せるよう、検出からの経過秒を返す。"""
    try:
        return round(
            (datetime.now() - datetime.fromisoformat(created_at)).total_seconds(), 2
        )
    except (TypeError, ValueError):
        return None


@app.route("/overlay")
def overlay():
    with get_connection() as con:
        cur = con.cursor()
        row = cur.execute("""
            SELECT id, timestamp, type, confidence, bbox, frame_wh, created_at
            FROM detections
            WHERE bbox IS NOT NULL
            ORDER BY id DESC
            LIMIT 1
            """).fetchone()

    if row is None:
        return jsonify(
            {"ok": True, "bbox": None, "frame_wh": None, "detection": None}
        )

    detection = dict(row)
    detection["bbox"] = load_json_field(row["bbox"])
    detection["frame_wh"] = load_json_field(row["frame_wh"])

    return jsonify(
        {
            "ok": True,
            "bbox": detection["bbox"],
            "frame_wh": detection["frame_wh"],
            "type": detection["type"],
            "confidence": detection["confidence"],
            "age_sec": overlay_age_sec(detection["created_at"]),
            "detection": detection,
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


@app.route("/api/transactions")
def get_transactions():
    """直近の取引をJSONで返す（公開ページのフィードが定期的に読む）。"""
    limit = request.args.get("limit", 5, type=int)
    limit = max(1, min(limit, 50))

    with get_connection() as con:
        cur = con.cursor()
        rows = cur.execute(
            """
            SELECT id, timestamp, amount, action, action_label, payer_name, status
            FROM transactions
            WHERE status = 'paid'
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return jsonify({"ok": True, "transactions": rows_to_dicts(rows)})


# ==================================================
# エラー応答の統一（要件定義書 NFR）
# debug を切ると未捕捉の例外は既定でHTMLの500ページになり、
# fetch().json() 側が落ちる。APIと同じ形に揃えておく。
# ==================================================
@app.errorhandler(404)
def handle_404(error):
    if request.path.startswith("/api/") or request.is_json:
        return jsonify({"ok": False, "error": "存在しないパスです"}), 404
    return error, 404


@app.errorhandler(Exception)
def handle_unexpected(error):
    # HTTPException（404など）はそのまま通し、それ以外だけJSONに包む
    if isinstance(error, HTTPException):
        return error

    app.logger.exception("未捕捉の例外: %s", error)
    return jsonify({"ok": False, "error": "サーバ内部でエラーが発生しました"}), 500


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
        debug=DEBUG,
        host="0.0.0.0",
        port=PORT,
        use_reloader=False,
    )
