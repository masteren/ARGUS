# freenove_camera.py
# Freenove サーバー（Code/Server/server.py）の映像を cv2.VideoCapture 互換で読むアダプタ。
#
# なぜ要るか：
#   Freenove の 8002 番ポートは MJPEG ではなく独自形式で流している。
#       [4バイト little-endian の長さ][その長さぶんの JPEG]  …の繰り返し
#   （server.py の transmit_video が struct.pack('<I', frame_length) を書いている）
#   したがって cv2.VideoCapture("http://<pi>:8002") では開けない。ここで復号して
#   ndarray にし、B の get_camera() が返す「カメラ」として差し込む。
#
# 設計：
#   ・受信は専用スレッド。最新フレームだけを持つ（遅延を溜めない＝展示で操作が重くならない）。
#   ・切れたら自動再接続。展示中に Pi を再起動しても B は落ちない。
#   ・read() は cv2.VideoCapture と同じ (bool, ndarray) を返すので app.py はカメラの正体を
#     意識しない。read_jpeg() を使えば JPEG のまま取り出せる（再エンコードを1回省ける）。
#
# 注意：Freenove サーバーは 8002 を一度しか accept しない。公式クライアント Main.py が
#       先に繋いでいるとこちらは映像を受け取れない。展示時は Main.py を閉じること。

import socket
import struct
import threading
import time

try:
    import cv2
    import numpy as np
except ImportError:      # B 本体と同じく、cv2 が無い環境でも import だけは通す
    cv2 = None
    np = None


class FreenoveCamera:
    """Freenove の映像ストリームを cv2.VideoCapture のふりをして返す。"""

    RECONNECT_WAIT_SEC = 2.0     # 切断後の再接続間隔
    SOCKET_TIMEOUT_SEC = 5.0     # 相手が黙ったままになるのを防ぐ

    def __init__(self, host, port=8002):
        self.host = host
        self.port = port

        self._frame = None            # 最新フレーム（ndarray）
        self._jpeg = None             # 同じものの JPEG バイト列
        self._seq = 0                 # フレーム通し番号。「新しいのが来たか」の判定用
        self._lock = threading.Lock()
        self._new_frame = threading.Condition(self._lock)
        self._running = True
        self._connected = False

        self._thread = threading.Thread(target=self._receive_loop, daemon=True)
        self._thread.start()

    # ── 受信スレッド ──────────────────────────────
    def _receive_loop(self):
        while self._running:
            sock = None
            stream = None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.SOCKET_TIMEOUT_SEC)
                sock.connect((self.host, self.port))
                stream = sock.makefile("rb")
                self._connected = True
                print(f"[freenove_camera] connected to {self.host}:{self.port}", flush=True)

                while self._running:
                    # 長さ4バイト → その長さぶんの JPEG。公式 Client.py と同じ読み方。
                    header = stream.read(4)
                    if len(header) < 4:
                        raise ConnectionError("stream closed")

                    length = struct.unpack("<I", header)[0]
                    if length == 0 or length > 10 * 1024 * 1024:
                        raise ValueError(f"suspicious frame length: {length}")

                    jpeg = stream.read(length)
                    if len(jpeg) < length:
                        raise ConnectionError("truncated frame")

                    if cv2 is None:
                        continue

                    frame = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
                    if frame is None:
                        continue      # 壊れたフレームは捨てて次へ

                    with self._new_frame:
                        self._frame = frame
                        self._jpeg = jpeg
                        self._seq += 1
                        self._new_frame.notify_all()   # 待っている配信側を起こす

            except Exception as e:
                if self._running:
                    print(f"[freenove_camera] disconnected ({e}) — retrying", flush=True)
            finally:
                self._connected = False
                for closeable in (stream, sock):
                    try:
                        if closeable is not None:
                            closeable.close()
                    except Exception:
                        pass

            if self._running:
                time.sleep(self.RECONNECT_WAIT_SEC)

    # ── cv2.VideoCapture 互換インターフェース ────────────────
    def wait_first_frame(self, timeout=10.0):
        """最初の1枚が届くまで待つ。VideoCapture(...) が開くのを待つのと同じ意味。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                if self._frame is not None:
                    return True
            time.sleep(0.1)
        return False

    def isOpened(self):
        with self._lock:
            return self._frame is not None

    def read(self):
        with self._lock:
            if self._frame is None:
                return False, None
            return True, self._frame.copy()

    def read_jpeg(self, after_seq=None, timeout=2.0):
        """JPEG のまま取り出す。B の /video_feed はこれをそのまま流せば再エンコード不要。

        after_seq を渡すと「その番号より新しいフレームが来るまで待つ」。
        これが無いと配信側は同じフレームを CPU 全開で送り続けてしまい、
        帯域と CPU を食い潰した上に受信側（A の VideoCapture や
        ブラウザ）が重複フレームの山で詰まる。実測で 0.5fps まで落ちた。

        戻り値は (成功したか, JPEGバイト列, そのフレームの通し番号)。
        """
        with self._new_frame:
            if after_seq is not None:
                self._new_frame.wait_for(lambda: self._seq != after_seq,
                                         timeout=timeout)
            if self._jpeg is None:
                return False, None, 0
            return True, self._jpeg, self._seq

    def set(self, *args, **kwargs):
        # 解像度は Pi 側（camera.py の stream_size）が決める。ここでは無視する。
        return False

    def release(self):
        self._running = False
        try:
            self._thread.join(timeout=2.0)
        except Exception:
            pass
