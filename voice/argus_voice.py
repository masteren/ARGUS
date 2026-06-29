from openai import OpenAI
import sounddevice as sd
import soundfile as sf

client = OpenAI()
SAMPLE_RATE = 16000
DURATION = 5   # 每次录 5 秒

SYSTEM_PROMPT = """あなたは「ARGUS（アーガス）」という6脚の監視ロボットです。
- 一人称は「ARGUS」。簡潔に、少しメカっぽく、フレンドリーに話す。
- 返事は1〜2文の短さ。長く喋らない。
- 日本語で答える。"""

def record(filename="input.wav"):
    print("● 録音中...（5秒、話してください）")
    audio = sd.rec(int(DURATION * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1)
    sd.wait()
    sf.write(filename, audio, SAMPLE_RATE)

def transcribe(filename="input.wav"):
    with open(filename, "rb") as f:
        res = client.audio.transcriptions.create(
            model="gpt-4o-transcribe", file=f, language="zh"
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
# ───────── メインループ ─────────
if __name__ == "__main__":
    print("=== ARGUS 音声対話 起動。Ctrl+C で終了 ===")
    while True:
        input("\n▶ Enter を押して話しかける...")   # 按回车再开始录,避免抢话
        record()
        user_text = transcribe()
        print("🧑 あなた:", user_text)

        if not user_text.strip():
            print("（聞き取れませんでした）")
            continue

        reply = ask_argus(user_text)
        print("🤖 ARGUS:", reply)
        speak(reply)
