from openai import OpenAI

client = OpenAI()

# ARGUS 的人设。机器人怎么"说话",全靠这段定。以后可自由改。
SYSTEM_PROMPT = """あなたは「ARGUS（アーガス）」という6脚の監視ロボットです。
- 一人称は「ARGUS」。簡潔に、少しメカっぽく、フレンドリーに話す。
- 返事は1〜2文の短さ。長く喋らない。
- 日本語で答える。"""

def ask_argus(user_text):
    res = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
    )
    return res.choices[0].message.content

# テスト：固定の文章を投げてみる
if __name__ == "__main__":
    text = "こんにちは、前進してくれる？"
    print("🧑 あなた:", text)
    print("🤖 ARGUS:", ask_argus(text))
