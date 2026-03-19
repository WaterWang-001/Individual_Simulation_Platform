"""
生成智能体之间的关系网络，写入 relationships.json。

流程：
  1. 随机筛选候选对（~12% 概率）
  2. LLM 批量分类（10对/次）
  3. 有向关系方向判断
  4. 性别合法性校验
  5. 写入 relationships.json
"""
import json
import random
import os
from itertools import combinations
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# ── 配置 ─────────────────────────────────────────────────────
load_dotenv(Path(__file__).parent.parent / ".env")

API_KEY  = os.environ["LLM_API_KEY"]
API_BASE = os.environ.get("LLM_API_BASE", "https://api.deepseek.com")
MODEL    = os.environ.get("LLM_MODEL", "deepseek/deepseek-chat").split("/")[-1]

client = OpenAI(api_key=API_KEY, base_url=API_BASE)

PROFILES_PATH      = Path(__file__).parent / "student_profiles.json"
RELATIONSHIPS_PATH = Path(__file__).parent / "relationships.json"

RANDOM_SEED        = 42
CANDIDATE_PROB     = 0.22   # 每对被选为候选的概率

RELATION_TYPES = [
    "同班同学", "室友", "导师-学生", "学长-学弟妹", "课题组成员",
    "学习小组", "好友", "普通朋友", "前任", "社团成员",
    "社团干部-普通成员", "学生会成员", "志愿者队友",
    "竞争者", "矛盾/冲突", "恋人", "兼职同事",
]

DIRECTED_TYPES = {"导师-学生", "学长-学弟妹", "社团干部-普通成员"}

# 需要同性的关系
SAME_GENDER_TYPES = {"室友"}
# 优先异性的关系（同性时退化）
OPPOSITE_GENDER_TYPES = {"恋人", "前任"}


# ── 工具函数 ─────────────────────────────────────────────────
def occ_level(p: dict) -> int:
    """学历层次：本科=1，研究生=2，博士=3，其他=1"""
    occ = p.get("occupation", "")
    if "博士" in occ:
        return 3
    if "研究生" in occ or "硕士" in occ:
        return 2
    return 1


def profile_summary(p: dict) -> str:
    interests = "、".join(p.get("interests", [])[:4])
    pers = p.get("personality", "")[:60]
    return (
        f"姓名={p['name']} 性别={p['gender']} 年龄={p['age']} "
        f"身份={p['occupation']} 专业={p['major']} "
        f"兴趣=[{interests}] 性格={pers}"
    )


def batch_classify(pairs: list[tuple[dict, dict]]) -> list[str]:
    """
    发送一批人物对给 LLM，返回每对对应的关系类型（或'无关系'）。
    pairs: list of (profileA, profileB)
    returns: list of str, len == len(pairs)
    """
    lines = []
    for i, (a, b) in enumerate(pairs):
        lines.append(f"对{i+1}:\n  A: {profile_summary(a)}\n  B: {profile_summary(b)}")

    rel_list = "、".join(RELATION_TYPES)
    prompt = f"""你是一个社会关系分析助手，负责为复旦大学校园仿真构建关系网络。
给定以下 {len(pairs)} 对复旦大学学生，请为每对判断最合适的关系类型。

可选关系类型：{rel_list}、无关系

判断标准（宽松）：
- 同专业或相近专业 → 优先考虑同班同学、学长-学弟妹、课题组成员
- 有共同兴趣爱好（≥1个）→ 优先考虑社团成员、好友、志愿者队友
- 学历差距明显（博士 vs 本科/硕士）→ 考虑导师-学生
- 两人完全没有交集才输出"无关系"，请尽量找到合适的关系
- 目标：约 50-60% 的候选对有关系，其余输出"无关系"
- 室友必须同性别；恋人/前任优先异性
- 请以 JSON 数组格式返回，例如：["好友", "无关系", "室友", ...]
- 只输出 JSON 数组，不要任何其他文字

学生信息：
{chr(10).join(lines)}
"""
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0.3,
    )
    raw = resp.choices[0].message.content.strip()
    # 提取 JSON 数组
    start = raw.find("[")
    end   = raw.rfind("]") + 1
    try:
        results = json.loads(raw[start:end])
        if len(results) == len(pairs):
            return results
    except Exception:
        pass
    # 解析失败则全部标为无关系
    print(f"  [warn] JSON parse failed: {raw[:100]}")
    return ["无关系"] * len(pairs)


def resolve_direction(rel_type: str, a: dict, b: dict) -> tuple[dict, dict]:
    """
    对有向关系，返回 (agent1=主导方, agent2=从属方)。
    导师-学生：学历高/年龄大的为导师
    学长-学弟妹：年龄大的为学长
    社团干部-普通成员：学历高/年龄大的为干部
    """
    a_level = occ_level(a)
    b_level = occ_level(b)
    if a_level != b_level:
        return (a, b) if a_level > b_level else (b, a)
    # 学历相同则年龄大的为主导
    return (a, b) if a.get("age", 0) >= b.get("age", 0) else (b, a)


def gender_valid(rel_type: str, a: dict, b: dict) -> bool | str:
    """
    检查性别合法性。
    返回 True（合法）、False（丢弃）或新的关系类型（降级）。
    """
    ga, gb = a.get("gender"), b.get("gender")
    if rel_type in SAME_GENDER_TYPES:
        if ga != "unknown" and gb != "unknown" and ga != gb:
            return "普通朋友"   # 降级
    if rel_type in OPPOSITE_GENDER_TYPES:
        if ga != "unknown" and gb != "unknown" and ga == gb:
            return "好友"       # 降级
    return True


# ── 主流程 ───────────────────────────────────────────────────
def main():
    with open(PROFILES_PATH, encoding="utf-8") as f:
        profiles = json.load(f)

    uid_map = {p["user_id"]: p for p in profiles}
    all_pairs = list(combinations(profiles, 2))
    print(f"总对数: {len(all_pairs)}")

    # Step 1: 随机筛选候选对
    random.seed(RANDOM_SEED)
    candidates = [pair for pair in all_pairs if random.random() < CANDIDATE_PROB]
    print(f"候选对数: {len(candidates)}（概率 {CANDIDATE_PROB}）")

    # Step 2: LLM 批量分类（10对/批）
    BATCH = 10
    rel_results: list[tuple[dict, dict, str]] = []  # (a, b, rel_type)

    for i in range(0, len(candidates), BATCH):
        batch = candidates[i:i + BATCH]
        print(f"  LLM 分类 batch {i//BATCH + 1}/{(len(candidates)-1)//BATCH + 1} ...")
        labels = batch_classify(batch)
        for (a, b), label in zip(batch, labels):
            rel_results.append((a, b, label.strip()))

    # Step 3 & 4: 过滤 + 方向判断 + 性别校验
    relationships = []
    for a, b, rel_type in rel_results:
        if rel_type == "无关系":
            continue

        # 性别校验
        validity = gender_valid(rel_type, a, b)
        if validity is False:
            continue
        if isinstance(validity, str):
            rel_type = validity   # 降级

        # 有向关系：确定方向
        directed = rel_type in DIRECTED_TYPES
        if directed:
            agent1, agent2 = resolve_direction(rel_type, a, b)
        else:
            agent1, agent2 = a, b

        relationships.append({
            "agent1":   agent1["user_id"],
            "agent2":   agent2["user_id"],
            "type":     rel_type,
            "directed": directed,
        })

    # 统计
    from collections import Counter
    type_counts = Counter(r["type"] for r in relationships)
    print(f"\n生成关系数: {len(relationships)}")
    for t, c in type_counts.most_common():
        print(f"  {t}: {c}")

    # 写入文件
    output = {"relationships": relationships}
    with open(RELATIONSHIPS_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n已写入 {RELATIONSHIPS_PATH}")


if __name__ == "__main__":
    main()
