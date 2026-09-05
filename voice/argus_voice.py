import os
import threading
import requests
from openai import OpenAI
from robot_bridge import MockBridge, FreenoveBridge
from paid_poller import poll_paid_commands, B_URL
import sounddevice as sd
import soundfile as sf
import numpy as np

client = OpenAI()
# 実機（Pi）に繋ぐときは環境変数だけで切り替える。コードの編集は不要。
#   ARGUS_ROBOT_HOST=192.168.0.50 python3 argus_voice.py
# 未設定なら MockBridge（ログ出力のみ）で、実機なしでも通しで動く。
ROBOT_HOST = os.environ.get("ARGUS_ROBOT_HOST")
bridge = FreenoveBridge(ROBOT_HOST) if ROBOT_HOST else MockBridge()
print("🦿 bridge =", "FreenoveBridge(%s)" % ROBOT_HOST if ROBOT_HOST else "MockBridge（実機なし）")

SAMPLE_RATE = 16000

SYSTEM_PROMPT = """あなたは「ARGUS（アーガス）」という6脚の相棒ロボットです。
- 一人称は「ARGUS」。簡潔に、少しメカっぽく、フレンドリーに話す。
- 返事は1〜2文の短さ。長く喋らない。
- 日本語で答える。"""

# 動作が確定したときの定型返事
ACTION_REPLIES = {
    "forward": "了解、前進します。",
    "back": "後退します。",
    "turn_left": "左に曲がります。",
    "turn_right": "右に曲がります。",
    "stop": "停止します。",
}

# キーワード → 動作。これらの語を聞き取ったら対応する動作を発火させる。
def detect_intent(text):
    if any(w in text for w in ["前進", "進んで", "すすめ"]):
        return "forward"
    if any(w in text for w in ["後退", "後ろ", "下がっ", "バック"]):
        return "back"
    if "左" in text:
        return "turn_left"
    if "右" in text:
        return "turn_right"
    if any(w in text for w in ["止ま", "停止", "ストップ", "停"]):
        return "stop"
    return None

# 「何が見えているか」を尋ねているかどうかを判定する
def is_vision_question(text):
    keywords = ["何が見える", "何見える", "見えてる", "見える",
                "周り", "周囲",
                "what do you see", "what can you see"]
    return any(k in text for k in keywords)

# B から最新の検出結果を読み取り、一文にまとめて LLM の参考にする
def get_detections():
    try:
        # ── 統合時の変更点 ──
        # B の /events は {"ok": true, "events": [...]} を返す（偽サーバーは裸のリストだった）。
        # どちらの形でも動くよう吸収する。
        payload = requests.get(f"{B_URL}/events", timeout=3).json()
        if isinstance(payload, dict):
            events = payload.get("events", [])
        else:
            events = payload
        if not events:
            return "今は特に何も検出していません。"
        items = [f"{e['type']}(信頼度{e.get('confidence', '?')})" for e in events]
        return "検出したもの: " + "、".join(items)
    except Exception as e:
        print("[events]", e)
        return "検出データが取得できませんでした。"

def record(filename="input.wav"):
    """録音して filename に保存。取り消された場合は False を返す。"""
    input("\n▶ Enter を押して録音開始...")            # 1回目の Enter で録音スタート
    print("● 録音中... 話し終わったら Enter / 言い間違えたら r+Enter で取り消し")
    frames = []
    # マイク入力をコールバックで frames にためていく。長さは話者が Enter を押すまで可変
    stream = sd.InputStream(
        samplerate=SAMPLE_RATE, channels=1,
        callback=lambda indata, n, t, status: frames.append(indata.copy()),
    )
    with stream:
        cmd = input()                                  # 2回目の入力で録音停止。'r' なら取り消し
    if cmd.strip().lower() == "r":
        print("↺ 取り消しました。もう一度どうぞ")
        return False
    if not frames:
        sf.write(filename, np.zeros(1, dtype="float32"), SAMPLE_RATE)
        return True
    audio = np.concatenate(frames, axis=0)
    sf.write(filename, audio, SAMPLE_RATE)
    return True

def transcribe(filename="input.wav"):
    with open(filename, "rb") as f:
        res = client.audio.transcriptions.create(
            model="gpt-4o-transcribe", file=f, language="ja"
        )
    return res.text

def ask_argus(user_text):
    res = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
    )
    return res.choices[0].message.content

def speak(text, filename="reply.wav"):
    with client.audio.speech.with_streaming_response.create(
        model="gpt-4o-mini-tts", voice="alloy", input=text
    ) as response:
        response.stream_to_file(filename)
    data, fs = sf.read(filename)
    sd.play(data, fs)
    sd.wait()

# ───────── メインループ（音声スレッド）─────────
def voice_loop():
    while True:
        if not record():   # 1回目Enterで録音開始→2回目Enterで停止。r+Enterでこの録音を破棄
            continue
        user_text = transcribe()
        print("🧑 あなた:", user_text)

        if not user_text.strip():
            print("（聞き取れませんでした）")
            continue

        action = detect_intent(user_text)
        if action:
            # 動作指令の場合：歩行ブリッジを発火 + 即座に定型確認を返す（LLMは通さない）
            bridge.send(action)
            reply = ACTION_REPLIES.get(action, "了解。")
        elif is_vision_question(user_text):
            # 「何が見える」の場合：検出データを読み、それを使って LLM に答えさせる
            detections = get_detections()
            reply = ask_argus(f"{user_text}\n\n（参考：{detections}）")
        else:
            # 通常の対話
            reply = ask_argus(user_text)

        print("🤖 ARGUS:", reply)
        speak(reply)

# ───────── 起動 ─────────
if __name__ == "__main__":
    print("=== ARGUS 音声対話 + チケット命令 起動。Ctrl+C で終了 ===")

    # チケット命令のポーリングはバックグラウンドスレッドで実行（daemon=メインプログラム終了時に自動終了）
    paid_thread = threading.Thread(
        target=poll_paid_commands, args=(bridge,), daemon=True
    )
    paid_thread.start()

    # 音声はメインスレッドで実行
    voice_loop()
