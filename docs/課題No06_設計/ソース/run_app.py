import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("ARGUS_DB", os.path.join(HERE, "design.db"))  # 本番の argus.db は触らない
os.environ["ARGUS_PAY_MIN_INTERVAL"] = "0"
os.environ["PORT"] = "5077"

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "ARGUS_backend"))
import app as argus
from flask import Response
from PIL import Image, ImageDraw

# カメラ実機の代わりに、展示会場を模した静止フレームを返す（撮影用）
def _frame():
    im = Image.new("RGB", (640, 480), (18, 24, 34))
    d = ImageDraw.Draw(im)
    for y in range(480):
        c = int(18 + y * 0.06)
        d.line([(0, y), (640, y)], fill=(c, c + 6, c + 14))
    d.rectangle([0, 360, 640, 480], fill=(26, 32, 44))
    # 人物シルエット（検出対象）
    d.ellipse([250, 150, 330, 230], fill=(70, 82, 100))
    d.rounded_rectangle([230, 235, 350, 420], 18, fill=(70, 82, 100))
    d.text((16, 16), "CAM-01  640x480  30fps", fill=(140, 160, 185))
    return im

_img = _frame()
import io
_buf = io.BytesIO()
_img.save(_buf, format="JPEG", quality=85)
JPEG = _buf.getvalue()

def fake_feed():
    return Response(JPEG, mimetype="image/jpeg")

argus.app.view_functions["video_feed"] = fake_feed

argus.init_db()
argus.app.run(host="127.0.0.1", port=5077, debug=False, threaded=True)
