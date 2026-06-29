from openai import OpenAI

client = OpenAI()   # 自动读取环境变量 OPENAI_API_KEY

print("● 识别 test.wav 中...")
with open("test.wav", "rb") as f:
    result = client.audio.transcriptions.create(
        model="gpt-4o-transcribe",   # OpenAI 的语音识别模型
        file=f,
        language="zh",               # 日语；中文测试改成 "zh"
    )

print("📝 识别结果:", result.text)
