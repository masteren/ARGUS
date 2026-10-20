from flask import Flask, request, jsonify, render_template, redirect, url_for, Response, session
from werkzeug.exceptions import HTTPException
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import secrets
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

# ── 会員登録・ログイン（要件定義書 機能2）────────────────────
# ARGUS_SECRET_KEY : セッション Cookie の署名鍵。未設定なら起動ごとに乱数で作る
#   （その場合 B を再起動すると全員ログアウトになる。展示では1日の中で
#    再起動しても困らないよう、固定値を環境変数で渡しておくとよい）。
# ARGUS_SESSION_IDLE_SEC : サーバ側で見る無操作の上限。公開ページは JS で
#   60秒の無操作を検知して自分でログアウトするが、画面を閉じられた場合などの
#   取りこぼしをここで受け止める。
app.secret_key = os.environ.get("ARGUS_SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)
SESSION_IDLE_SEC = int(os.environ.get("ARGUS_SESSION_IDLE_SEC", "600"))
PIN_LENGTH = 4
AUTH_MIN_INTERVAL_SEC = float(os.environ.get("ARGUS_AUTH_MIN_INTERVAL", "1.0"))  # 同一IPからのログイン・登録の最短間隔
AUTH_MAX_FAILURES = 5             # 同じ名前で続けて PIN を間違えられる回数
AUTH_LOCK_SEC = 60                # 上を超えたらその名前を一時的に止める秒数

_last_auth_at = {}                # client ip -> 最後に受けたログイン・登録の時刻
_last_purchase_at = {}            # client ip -> 最後に受けた購入の時刻
_auth_failures = {}               # name -> (連続失敗回数, 最後に失敗した時刻)
_auth_guard_lock = threading.Lock()

CAMERA_INDEX = 0
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480

# ARGUS_ROBOT_HOST : 設定すると、ローカルの USB カメラではなく
#   Freenove サーバー（Pi）の映像ストリームを使う。＝ロボット一人称視点。
#   C（voice/argus_voice.py）が命令の送信先に使うのと同じ変数なので、
#   「Pi の IP を1つ決めれば B と C の両方がそこを向く」。
#   未設定なら従来どおり CAMERA_INDEX のローカルカメラ（結合試験・単体開発用）。
ROBOT_HOST = os.environ.get("ARGUS_ROBOT_HOST")
ROBOT_VIDEO_PORT = int(os.environ.get("ARGUS_ROBOT_VIDEO_PORT", "8002"))

# ARGUS_STAFF_TOKEN : 運営の直接操作（/control）を別端末から使うための合言葉。
#   未設定なら /control は localhost からのみ。観客と同じLANに置くので、
#   スタッフのスマホから操作したいときだけ設定する。
STAFF_TOKEN = os.environ.get("ARGUS_STAFF_TOKEN")


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
# チケットパック（要件定義書 機能3）
# price は表示用の模擬価格（1チケット＝¥1〈模擬〉）。実際の請求は発生しない。
# ==================================================
TICKET_PACKS = {
    "pack_500": {
        "label": "500チケット",
        "tickets": 500,
        "price": 500,
        "description": "前進5回、または「人を探す」1回ぶん",
    },
    "pack_1000": {
        "label": "1,000チケット",
        "tickets": 1000,
        "price": 1000,
        "description": "いろいろな動きを試したい人向け",
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

        # 会員（要件定義書 機能2）。PIN は平文で持たず、ハッシュだけを保存する。
        # balance はチケット残高。購入で増え、/pay で減る。負にはならない。
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                pin_hash TEXT NOT NULL,
                balance INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0),
                created_at TEXT NOT NULL,
                last_login_at TEXT
            )
            """)

        # チケット購入（模擬決済）の履歴（要件定義書 機能3）
        cur.execute("""
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                payment_id TEXT NOT NULL,
                pack TEXT NOT NULL,
                tickets INTEGER NOT NULL,
                price INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """)

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

        # チケット消費（取引）の履歴。user_id は消費した会員。
        cur.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(id),
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
        # ログイン導入前の DB（transactions に user_id が無い頃のもの）も移行する
        ensure_column(cur, "transactions", "user_id", "INTEGER REFERENCES users(id)")

        con.commit()


# ==================================================
# 模擬決済処理（チケット購入 /purchase から呼ぶ）
# 外部には接続しない。後で決済事業者に差し替えるときはここだけを直す。
# ==================================================
def process_payment(amount, payer_name):
    payment_id = "dummy_" + uuid.uuid4().hex[:12]

    return {
        "success": True,
        "payment_id": payment_id,
        "status": "paid",
    }


# ==================================================
# ログイン状態の扱い
# セッションには user_id と最後に操作した時刻だけを入れる。名前や残高は
# 毎回 DB から読む（セッションに残高を持つと、別タブとずれる）。
# ==================================================
def client_ip():
    return request.remote_addr or "unknown"


def too_fast(table, interval):
    """同一IPからの連打なら True。受理した場合は時刻を記録する。"""
    ip = client_ip()
    now = time.time()
    with _auth_guard_lock:
        if now - table.get(ip, 0.0) < interval:
            return True
        table[ip] = now
    return False


def current_user():
    """ログイン中の会員を返す。未ログイン・無操作で期限切れなら None。"""
    user_id = session.get("user_id")
    if not user_id:
        return None

    if time.time() - session.get("seen_at", 0) > SESSION_IDLE_SEC:
        session.clear()
        return None

    with get_connection() as con:
        user = con.execute(
            "SELECT id, name, balance FROM users WHERE id = ?", (user_id,)
        ).fetchone()

    if user is None:
        session.clear()
        return None

    session["seen_at"] = time.time()
    return user


def user_json(user):
    return {"id": user["id"], "name": user["name"], "balance": user["balance"]}


def login_required_response():
    return jsonify(
        {"ok": False, "error": "ログインしてください", "login_required": True}
    ), 401


def validate_credentials(data):
    """名前と PIN を取り出して検証する。エラーなら (None, None, メッセージ)。"""
    name = clean_text(data.get("name", ""))
    pin = str(data.get("pin", "")).strip()

    if not name:
        return None, None, "名前を入力してください"
    if len(name) > MAX_PAYER_NAME_LEN:
        return None, None, "名前は%d文字までです" % MAX_PAYER_NAME_LEN
    if len(pin) != PIN_LENGTH or not pin.isdigit():
        return None, None, "PINは数字%d桁で入力してください" % PIN_LENGTH
    return name, pin, None


def start_session(user_id):
    session.clear()
    session["user_id"] = user_id
    session["seen_at"] = time.time()


# ==================================================
# カメラ配信処理
# /video_feed でブラウザへリアルタイム映像を流す
# ==================================================
_camera = None
_camera_lock = threading.Lock()        # read() の排他用
_camera_init_lock = threading.Lock()   # 初期化の排他用（下記の理由で必須）


def get_camera():
    """カメラを1回だけ起動して使い回す。

    ARGUS_ROBOT_HOST が設定されていれば Freenove（Pi）の映像＝ロボット一人称視点、
    未設定ならローカルの USB カメラ。どちらも read() の使い方は同じなので、
    呼ぶ側（generate_camera_frames）はカメラの正体を意識しない。
    """
    global _camera

    if cv2 is None:
        return None

    if _camera is not None:          # 速い経路：既に出来ている
        return _camera

    # ここをロックで守るのは必須。Flask はマルチスレッドなので、複数の
    # /video_feed が同時に来ると FreenoveCamera が2つ作られる。Freenove の
    # サーバーは 8002 を一度しか accept しないので2つ目は繋がらず、しかも
    # _camera が上書きされて1つ目が GC される＝ソケットが閉じ、サーバー側が
    # "End transmit" で映像を打ち切ってしまう（実機で発生）。
    with _camera_init_lock:
        if _camera is not None:      # 待っている間に他スレッドが作り終えた
            return _camera

        if ROBOT_HOST:
            from freenove_camera import FreenoveCamera

            camera = FreenoveCamera(ROBOT_HOST, ROBOT_VIDEO_PORT)
            # Pi 側が accept して最初の1枚を流すまで少し待つ。
            # 待たずに返すと isOpened() が False になり /video_feed が 500 を返す。
            if not camera.wait_first_frame(timeout=10.0):
                print(
                    f"[camera] Freenove {ROBOT_HOST}:{ROBOT_VIDEO_PORT} から映像が来ません。"
                    "Pi で main.py が起動しているか、公式クライアント Main.py が"
                    "8002 を先に掴んでいないか確認してください。",
                    flush=True,
                )
                camera.release()
                return None
        else:
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

    # Freenove から来る映像は元から JPEG。read_jpeg() があるならデコード＋再エンコードを
    # 省いてそのまま流す（Pi の負荷と遅延を減らす）。ローカルカメラは従来どおり encode する。
    passthrough = hasattr(camera, "read_jpeg")
    last_seq = None

    while True:
        if passthrough:
            # FreenoveCamera は内部でロック済みなので _camera_lock は要らない。
            # ここで外側のロックを取ると視聴端末が増えたとき互いに待ち合ってしまう。
            #
            # after_seq を渡して「次の新しいフレーム」を待つのが肝。待たずに
            # 最新フレームを取ると、同じ画を CPU 全開で送り続けることになり、
            # 受信側が重複フレームで詰まって実測 0.5fps まで落ちた。
            success, frame_bytes, last_seq = camera.read_jpeg(after_seq=last_seq)

            if not success:
                time.sleep(0.1)
                continue
        else:
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
            "OpenCVがインストールされていません。pip install 'opencv-python<5' を実行してください。",
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
    """観客向け公開ページ。ログイン・チケット購入・操作、ライブ映像、ランキングを表示。"""
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

    user = current_user()

    return render_template(
        "public.html",
        actions=ACTIONS,
        packs=TICKET_PACKS,
        transactions=transactions,
        ranking=ranking,
        user=user_json(user) if user else None,
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

        purchases = cur.execute("""
            SELECT purchases.*, users.name AS user_name
            FROM purchases
            JOIN users ON users.id = purchases.user_id
            ORDER BY purchases.id DESC
            LIMIT 20
            """).fetchall()

        purchase_total = cur.execute("""
            SELECT COALESCE(SUM(price), 0) AS total
            FROM purchases
            WHERE status = 'paid'
            """).fetchone()["total"]

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
        purchases=purchases,
        purchase_total=purchase_total,
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
# ==================================================
# 会員登録・ログイン（要件定義書 機能2）
# 公開ページのパネルから fetch で呼ぶ。ページは遷移させない（MJPEG が切れるため）。
# ==================================================
def auth_guard(name):
    """連打と PIN の総当たりを止める。止めるなら (応答, ステータス) を返す。"""
    if too_fast(_last_auth_at, AUTH_MIN_INTERVAL_SEC):
        return jsonify(
            {"ok": False, "error": "操作が速すぎます。少し待ってからもう一度お願いします"}
        ), 429

    with _auth_guard_lock:
        count, last = _auth_failures.get(name, (0, 0.0))
        if count >= AUTH_MAX_FAILURES and time.time() - last < AUTH_LOCK_SEC:
            return jsonify(
                {"ok": False, "error": "PINを続けて間違えたため、%d秒ほど待ってください" % AUTH_LOCK_SEC}
            ), 429
    return None


def record_auth_failure(name):
    with _auth_guard_lock:
        count, _ = _auth_failures.get(name, (0, 0.0))
        _auth_failures[name] = (count + 1, time.time())


@app.route("/auth/register", methods=["POST"])
def auth_register():
    """観客：名前と PIN で会員登録し、そのままログインする。"""
    data = request.get_json(silent=True) or request.form
    name, pin, error = validate_credentials(data)
    if error:
        return jsonify({"ok": False, "error": error}), 400

    blocked = auth_guard(name)
    if blocked:
        return blocked

    created_at = now_text()
    try:
        with get_connection() as con:
            cur = con.execute(
                """
                INSERT INTO users (name, pin_hash, balance, created_at, last_login_at)
                VALUES (?, ?, 0, ?, ?)
                """,
                (name, generate_password_hash(pin), created_at, created_at),
            )
            user_id = cur.lastrowid
            con.commit()
    except sqlite3.IntegrityError:
        return jsonify(
            {"ok": False, "error": "その名前はすでに使われています。ログインするか別の名前にしてください"}
        ), 409

    start_session(user_id)
    return jsonify(
        {"ok": True, "user": {"id": user_id, "name": name, "balance": 0}}
    )


@app.route("/auth/login", methods=["POST"])
def auth_login():
    """観客：名前と PIN でログインする。"""
    data = request.get_json(silent=True) or request.form
    name, pin, error = validate_credentials(data)
    if error:
        return jsonify({"ok": False, "error": error}), 400

    blocked = auth_guard(name)
    if blocked:
        return blocked

    with get_connection() as con:
        user = con.execute(
            "SELECT id, name, pin_hash, balance FROM users WHERE name = ?", (name,)
        ).fetchone()

        # 名前の有無で文言を変えない（どの名前が登録済みかを探られないように）
        if user is None or not check_password_hash(user["pin_hash"], pin):
            record_auth_failure(name)
            return jsonify({"ok": False, "error": "名前またはPINが違います"}), 401

        con.execute(
            "UPDATE users SET last_login_at = ? WHERE id = ?", (now_text(), user["id"])
        )
        con.commit()

    with _auth_guard_lock:
        _auth_failures.pop(name, None)

    start_session(user["id"])
    return jsonify({"ok": True, "user": user_json(user)})


@app.route("/auth/logout", methods=["POST"])
def auth_logout():
    """観客：「体験を終える」または無操作60秒でログアウトする。"""
    session.clear()
    return jsonify({"ok": True})


@app.route("/me")
def me():
    """ログイン状態と残高。未ログインでも 200 で logged_in=false を返す。"""
    user = current_user()
    if user is None:
        return jsonify({"ok": True, "logged_in": False, "user": None})
    return jsonify({"ok": True, "logged_in": True, "user": user_json(user)})


# ==================================================
# チケット購入（模擬決済 / 要件定義書 機能3）
# 購入記録の追加と残高の加算を同じトランザクションで確定させる。
# ==================================================
@app.route("/purchase", methods=["POST"])
def purchase():
    """観客：チケットパックを模擬決済で購入し、残高に加算する。"""
    user = current_user()
    if user is None:
        return login_required_response()

    data = request.get_json(silent=True) or request.form
    pack_code = str(data.get("pack", "")).strip()
    if pack_code not in TICKET_PACKS:
        return jsonify({"ok": False, "error": "存在しないチケットパックです"}), 400

    if too_fast(_last_purchase_at, PAY_MIN_INTERVAL_SEC):
        return jsonify(
            {"ok": False, "error": "操作が速すぎます。少し待ってからもう一度お願いします"}
        ), 429

    pack = TICKET_PACKS[pack_code]
    payment_result = process_payment(pack["price"], user["name"])
    if not payment_result["success"]:
        return jsonify({"ok": False, "error": "決済に失敗しました"}), 400

    created_at = now_text()
    with get_connection() as con:
        cur = con.cursor()
        cur.execute(
            """
            INSERT INTO purchases
            (user_id, payment_id, pack, tickets, price, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user["id"],
                payment_result["payment_id"],
                pack_code,
                pack["tickets"],
                pack["price"],
                payment_result["status"],
                created_at,
            ),
        )
        purchase_id = cur.lastrowid
        cur.execute(
            "UPDATE users SET balance = balance + ? WHERE id = ?",
            (pack["tickets"], user["id"]),
        )
        balance = cur.execute(
            "SELECT balance FROM users WHERE id = ?", (user["id"],)
        ).fetchone()["balance"]
        con.commit()

    return jsonify(
        {
            "ok": True,
            "message": "%sを追加しました（模擬決済・実際の請求はありません）" % pack["label"],
            "purchase_id": purchase_id,
            "payment_id": payment_result["payment_id"],
            "pack": pack_code,
            "tickets": pack["tickets"],
            "price": pack["price"],
            "balance": balance,
        }
    )


# ==================================================
# チケット消費（要件定義書 機能4）
# 残高の減算・取引・命令・ミッションを1つのトランザクションで確定させる。
# 減算は「残高が足りるときだけ減らす」UPDATE なので、同時に押されても負にならない。
# ==================================================
@app.route("/pay", methods=["POST"])
def pay():
    """観客：チケットを消費してロボット操作命令を登録する。"""
    user = current_user()
    if user is None:
        return login_required_response()

    data = request.get_json(silent=True) or request.form

    # 名前はログイン中の会員名を使う（本文の payer_name は見ない）
    payer_name = user["name"]
    action = str(data.get("action", "")).strip()
    message = clean_text(data.get("message", ""))

    if action not in ACTIONS:
        return jsonify({"ok": False, "error": "存在しないアクションです"}), 400

    if len(message) > MAX_MESSAGE_LEN:
        return jsonify(
            {"ok": False, "error": "メッセージは%d文字までです" % MAX_MESSAGE_LEN}
        ), 400

    # 連打の受け止め（同一端末からの最短間隔）
    ip = client_ip()
    now = time.time()

    with _pay_guard_lock:
        if now - _last_pay_at.get(ip, 0.0) < PAY_MIN_INTERVAL_SEC:
            return jsonify(
                {"ok": False, "error": "操作が速すぎます。少し待ってからもう一度お願いします"}
            ), 429
        _last_pay_at[ip] = now

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
    payment_id = "ticket_" + uuid.uuid4().hex[:12]
    created_at = now_text()

    with get_connection() as con:
        cur = con.cursor()

        # 0. 残高から減算（足りなければ何も書かずに 402）
        cur.execute(
            "UPDATE users SET balance = balance - ? WHERE id = ? AND balance >= ?",
            (amount, user["id"], amount),
        )
        if cur.rowcount != 1:
            con.rollback()
            balance = con.execute(
                "SELECT balance FROM users WHERE id = ?", (user["id"],)
            ).fetchone()["balance"]
            return jsonify(
                {
                    "ok": False,
                    "error": "チケットが足りません（必要 %d / 残高 %d）" % (amount, balance),
                    "insufficient": True,
                    "required": amount,
                    "balance": balance,
                }
            ), 402

        # 1. 取引履歴を保存
        cur.execute(
            """
            INSERT INTO transactions
            (user_id, payment_id, timestamp, amount, action, action_label, payer_name, message, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user["id"],
                payment_id,
                created_at,
                amount,
                action,
                action_label,
                payer_name,
                message,
                "paid",
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

        # 3. ミッションなら missions に active 行を立てる
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

        balance = cur.execute(
            "SELECT balance FROM users WHERE id = ?", (user["id"],)
        ).fetchone()["balance"]
        con.commit()

    return jsonify(
        {
            "ok": True,
            "message": "チケットを使い、ロボット命令を登録しました",
            "transaction_id": transaction_id,
            "command_id": command_id,
            "mission_id": mission_id,
            "amount": amount,
            "action": action,
            "action_label": action_label,
            "payer_name": payer_name,
            "payment_id": payment_id,
            "balance": balance,
        }
    )


# ==================================================
# 運営用：直接操作（展示の現場でスタッフが使う）
# /pay と違って課金・ランキング・取引履歴を汚さずにロボットを動かす。
# 観客メニューに無い stop / back / relax もここからは使える
# （robot_bridge.py に実装済みのものだけを並べてある）。
# ==================================================
STAFF_ACTIONS = {
    "forward": "前進",
    "back": "後退",
    "turn_left": "左旋回",
    "turn_right": "右旋回",
    "stop": "停止",
    "relax": "脱力",
    "bow": "お辞儀",
    "wave": "手を振る",
    # カメラ（頭）の上下。低い視点だと人の全身が入らないので現場で合わせる。
    "head_up": "カメラ↑",
    "head_down": "カメラ↓",
}


def staff_is_allowed():
    """運営操作を許すかどうか。

    **B を動かしている端末（localhost）は常に許可する。** 運営が操作するのは
    そこなので、ここを塞ぐとダッシュボードのボタンが全部 403 になる。
    （以前はトークンを設定した途端 localhost にもヘッダを要求していて、
    ブラウザの fetch はそれを送らないため運営 UI が使えなくなっていた。）

    別の端末からの操作は ARGUS_STAFF_TOKEN を設定したときだけ開く。
    観客と同じ LAN に置く以上、誰でも叩ける経路にはしない。
    """
    if request.remote_addr in ("127.0.0.1", "::1"):
        return True
    return bool(STAFF_TOKEN) and request.headers.get("X-Staff-Token") == STAFF_TOKEN


@app.route("/control", methods=["POST"])
def control():
    if not staff_is_allowed():
        return jsonify(
            {"ok": False, "error": "権限がありません（運営端末から操作してください）"}
        ), 403

    data = request.get_json(silent=True) or {}
    action = clean_text(data.get("action"))

    if action not in STAFF_ACTIONS:
        return jsonify({"ok": False, "error": "未定義の操作です: %s" % action}), 400

    created_at = now_text()
    flushed = 0

    with get_connection() as con:
        cur = con.cursor()

        # 「停止」は溜まった命令を片付けてから止める。そうしないとキューに
        # 残った前進などが後から実行され、止めたはずのロボットが動き出す。
        if action == "stop":
            cur.execute(
                "UPDATE command_queue SET status = 'done', done_at = ? "
                "WHERE status = 'pending'",
                (created_at,),
            )
            flushed = cur.rowcount

        cur.execute(
            """
            INSERT INTO command_queue
            (transaction_id, action, action_label, source, status, created_at)
            VALUES (NULL, ?, ?, 'staff', 'pending', ?)
            """,
            (action, STAFF_ACTIONS[action], created_at),
        )
        command_id = cur.lastrowid

    return jsonify(
        {
            "ok": True,
            "command_id": command_id,
            "action": action,
            "action_label": STAFF_ACTIONS[action],
            "flushed": flushed,      # stop のとき、消した未実行命令の数
        }
    )


# ==================================================
# バッテリー残量
# ロボットの電圧は C だけが知れる（5002 の TCP を握っているのが C のため）。
# C が定期的に CMD_POWER を投げて POST /battery で置いていき、
# 公開ページとダッシュボードは GET /battery で読む。
# 瞬時値なので DB には残さずメモリに最新値だけ持つ。
# ==================================================
_battery = {"load": None, "pi": None, "at": None}
_battery_lock = threading.Lock()

# 2セルのリチウム電池（満充電 8.4V / 公称 7.4V / 下限 6.0V）を前提に割合を出す。
BATTERY_FULL_V = 8.4
BATTERY_EMPTY_V = 6.0
# Freenove の server.py は 負荷側<5.5V または Pi側<6V でブザーを鳴らす。
# 展示中に止まると困るので、それより手前で警告を出す。
BATTERY_LOW_V = 7.2
BATTERY_CRITICAL_V = 6.6


def battery_level(volts):
    """電圧から残量（0-100）をざっくり出す。"""
    if volts is None:
        return None
    ratio = (volts - BATTERY_EMPTY_V) / (BATTERY_FULL_V - BATTERY_EMPTY_V)
    return int(max(0.0, min(1.0, ratio)) * 100)


@app.route("/battery", methods=["POST"])
def put_battery():
    """C からの電圧報告を受ける。"""
    data = request.get_json(silent=True) or {}
    try:
        load_v = float(data["load"])
        pi_v = float(data["pi"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"ok": False, "error": "load と pi が必要です"}), 400

    with _battery_lock:
        _battery["load"] = load_v
        _battery["pi"] = pi_v
        _battery["at"] = time.time()

    return jsonify({"ok": True})


@app.route("/battery")
def get_battery():
    """公開ページ・ダッシュボードが読む。"""
    with _battery_lock:
        load_v, pi_v, at = _battery["load"], _battery["pi"], _battery["at"]

    if at is None:
        # まだ一度も報告が無い（C が繋がっていない / 実機なし）
        return jsonify({"ok": True, "available": False, "status": "unknown"})

    age = time.time() - at
    lowest = min(load_v, pi_v)

    if lowest < BATTERY_CRITICAL_V:
        status = "critical"
    elif lowest < BATTERY_LOW_V:
        status = "low"
    else:
        status = "good"

    return jsonify(
        {
            "ok": True,
            "available": True,
            "load": round(load_v, 2),       # サーボ側
            "pi": round(pi_v, 2),           # ラズパイ側
            "level": battery_level(lowest),  # 0-100
            "status": status,
            "age_sec": round(age, 1),       # 古い値かどうかの判断用
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
