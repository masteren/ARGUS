import threading
from openai import OpenAI
from robot_bridge import MockBridge
from paid_poller import poll_paid_commands
import sounddevice as sd
import soundfile as sf

client = OpenAI()
bridge = MockBridge()   # 开发期只打印；实机后换成 FreenoveBridge

SAMPLE_RATE = 16000
DURATION = 5   # 每次录 5 秒

SYSTEM_PROMPT = """あなたは「ARGUS（アーガス）」という6脚の監視ロボットです。
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

# 关键词 → 动作。听到这些词就触发对应动作。
def detect_intent(text):
    if any(w in text for w in ["前進", "前进", "進んで", "すすめ"]):
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

def record(filename="input.wav"):
    print("● 録音中...（5秒、話してください）")
    audio = sd.rec(int(DURATION * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1)
    sd.wait()
    sf.write(filename, audio, SAMPLE_RATE)

def transcribe(filename="input.wav"):
    with open(filename, "rb") as f:
        res = client.audio.transcriptions.create(
            model="gpt-4o-transcribe", file=f, language="zh"   # 正式 demo 改回 "ja"
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

# ───────── メインループ（语音线）─────────
def voice_loop():
    while True:
        input("\n▶ Enter を押して話しかける...")   # 按回车再开始录,避免抢话
        record()
        user_text = transcribe()
        print("🧑 あなた:", user_text)

        if not user_text.strip():
            print("（聞き取れませんでした）")
            continue

        action = detect_intent(user_text)
        if action:
            # 是动作指令：触发行走桥 + 利落确认（不走 LLM）
            bridge.send(action)
            reply = ACTION_REPLIES.get(action, "了解。")
        else:
            # 不是动作指令：交给 LLM 对话
            reply = ask_argus(user_text)

        print("🤖 ARGUS:", reply)
        speak(reply)

# ───────── 起動 ─────────
if __name__ == "__main__":
    print("=== ARGUS 音声対話 + 課金 起動。Ctrl+C で終了 ===")

    # 课金轮询放后台线程（daemon=主程序退出时它自动结束）
    paid_thread = threading.Thread(
        target=poll_paid_commands, args=(bridge,), daemon=True
    )
    paid_thread.start()

    # 语音在主线程跑
    voice_loop()
