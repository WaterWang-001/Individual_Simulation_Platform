"""
从档案文本推断每个智能体的性别，写回 student_profiles.json。
使用 DeepSeek API（与仿真后端共用同一配置）。
"""
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).parent.parent / ".env")

API_KEY  = os.environ["LLM_API_KEY"]
API_BASE = os.environ.get("LLM_API_BASE", "https://api.deepseek.com")
MODEL    = os.environ.get("LLM_MODEL", "deepseek/deepseek-chat").split("/")[-1]  # "deepseek-chat"

client = OpenAI(api_key=API_KEY, base_url=API_BASE)

PROFILES_PATH = Path(__file__).parent / "student_profiles.json"


def build_prompt(profile: dict) -> str:
    parts = []
    if profile.get("bio"):
        parts.append(f"个人简介：{profile['bio']}")
    if profile.get("personality"):
        parts.append(f"性格描述：{profile['personality']}")
    posts = profile.get("sample_posts", [])[:2]
    for p in posts:
        if p.get("content"):
            parts.append(f"帖子内容（节选）：{p['content'][:200]}")
    return "\n".join(parts)


def infer_gender(profile: dict) -> str:
    text = build_prompt(profile)
    if not text.strip():
        return "unknown"

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是一个性别推断助手。根据用户提供的中文社交媒体档案内容，"
                    "推断该用户的性别。只输出以下三个词之一：male / female / unknown。"
                    "不要输出任何其他内容。"
                    "判断依据：自称词（我这个女生/男生/女孩/男孩）、"
                    "性别代词（她/他）、外貌描述、体型数据（如160/50kg通常为女性）等。"
                    "若线索不足或无法确定，输出 unknown。"
                ),
            },
            {"role": "user", "content": text},
        ],
        max_tokens=5,
        temperature=0,
    )
    result = resp.choices[0].message.content.strip().lower()
    if result not in ("male", "female"):
        return "unknown"
    return result


def main():
    with open(PROFILES_PATH, encoding="utf-8") as f:
        profiles = json.load(f)

    counts = {"male": 0, "female": 0, "unknown": 0}
    for i, p in enumerate(profiles):
        gender = infer_gender(p)
        p["gender"] = gender
        counts[gender] += 1
        print(f"[{i+1:02d}/{len(profiles)}] {p['name']:<20} → {gender}")

    with open(PROFILES_PATH, "w", encoding="utf-8") as f:
        json.dump(profiles, f, ensure_ascii=False, indent=2)

    print(f"\n完成：male={counts['male']}, female={counts['female']}, unknown={counts['unknown']}")
    print(f"已写回 {PROFILES_PATH}")


if __name__ == "__main__":
    main()
