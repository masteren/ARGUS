import sounddevice as sd
import soundfile as sf

SAMPLE_RATE = 16000   # 16kHz，STT 喜欢这个采样率
DURATION = 5          # 录 5 秒

print("3 秒后开始，请准备说话...")
sd.sleep(3000)

print("● 录音中...（5 秒）")
audio = sd.rec(int(DURATION * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1)
sd.wait()
sf.write("test.wav", audio, SAMPLE_RATE)
print("✔ 已保存 test.wav")

print("▶ 回放...")
data, fs = sf.read("test.wav")
sd.play(data, fs)
sd.wait()
print("✔ 完成")

