from openai import OpenAI
import sounddevice as sd
import soundfile as sf

client = OpenAI()

def speak(text, filename="reply.wav"):
    # 文字 → 语音文件
    res = client.audio.speech.create(
        model="gpt-4o-mini-tts",   # OpenAI 的语音合成模型
        voice="alloy",             # 声音；可换 echo / fable / onyx / nova / shimmer
        input=text,
    )
    res.stream_to_file(filename)

    # 播放出来
    data, fs = sf.read(filename)
    sd.play(data, fs)
    sd.wait()

if __name__ == "__main__":
    speak("もちろん、前進するよ。進行中。")
    print("✔ 再生完了")
