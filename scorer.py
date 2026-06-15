"""
ARCA 打分大脑（分两类 + 报名人数加分版）
=========================================
两类活动分开打分，用不同的尺子：
  A 类 · 黑客松 (track="hackathon")：来源 Devpost / lablab，或形式是 hackathon/demo day/build
        —— 看 技术主题 + 奖金 + 报名人数（人越多越高，0 人重罚）
  B 类 · 活动/Meetup (track="meetup")：来源 Luma
        —— 看 技术主题 + 形式（不看报名人数，因为 Luma 常拿不到）

输出：score(0-100)、tags、priority(高/中/跳过)、track(hackathon/meetup)
已结束(status=ended)的活动照常打分，但在报告里单独成区。

★ 想改规则，主要动下面三块：POSITIVE(加分词)、NEGATIVE(减分词)、
  以及 HACKATHON_REG_TIERS(报名人数加分档)。
"""

POSITIVE = [
    ("Agents",      ["ai agent", "agentic", "multi-agent", "autonomous agent", "agent framework",
                     "langchain", "llamaindex", "crewai", "autogen", "langgraph"], 16),
    ("AI Coding",   ["ai coding", "vibe coding", "cursor", "claude code", "codex", "copilot",
                     "windsurf", "code generation", "pair programming", "coding agent"], 16),
    ("MCP",         ["mcp", "model context protocol"], 16),
    ("DevTools",    ["developer tool", "devtools", "dev tools", "sdk", "tooling"], 9),
    ("Infra",       ["infrastructure", "infra", "inference", "gpu", "serving", "vector db",
                     "vector database", "orchestration"], 11),
    ("LLM Eng",     ["llm", "fine-tun", "fine tun", "post-training", "post training", "rlhf",
                     "reinforcement learning", "evals", "eval", "rag", "prompt engineering",
                     "training data", "trajectory"], 13),
    ("Open Source", ["open source", "open-source", "oss"], 9),
    ("Hackathon",   ["hackathon", "hack night", "buildathon", "build weekend", "demo day",
                     "build day", "jam"], 14),
    ("Builders",    ["builder", "build with", "ship", "power user", "engineer", "developer"], 8),
    ("Automation",  ["automation", "workflow", "agentic workflow", "n8n", "zapier"], 7),
]

NEGATIVE = [
    (["ai art", "generative art", "midjourney", "image generation", "stable diffusion",
      "text-to-image", "ai drawing", "design tool"], 22),
    (["content creation", "content creator", "copywriting", "writing with ai",
      "ai writing", "newsletter"], 18),
    (["marketing", "growth hacking", "seo", "social media", "ads ", "advertis"], 20),
    (["intro to", "beginner", "getting started", "101", "no-code for", "for marketers",
      "for beginners", "fundamentals", "crash course"], 18),
    (["networking", "mixer", "happy hour", "social event", "meet and greet"], 12),
    (["webinar", "thought leadership", "fireside chat"], 8),
    (["nft", "crypto trading", "memecoin"], 14),
]

FORMAT_BONUS = {
    "hackathon": 14, "demo day": 12, "build": 12, "buildathon": 14,
    "workshop": 8, "bootcamp": 6, "talk": 2, "conference": 4,
    "meetup": 3, "mixer": -6, "webinar": -4, "panel": 1,
}

# 黑客松报名人数加分档（人越多分越高；0 人或极少重罚）
# 格式: (报名人数下限, 加分)。从高到低匹配，命中第一个。
HACKATHON_REG_TIERS = [
    (2000, 16),
    (1000, 12),
    (500,   8),
    (100,   4),
    (10,    0),
    (1,   -12),   # 1-9 人：基本没人参加，重扣
    (0,   -20),   # 0 人：重罚，绝不会进高优先级
]


def _track(event):
    """判断属于哪一类。"""
    src = (event.get("source") or "").lower()
    fmt = (event.get("event_type") or "").lower()
    if src in ("devpost", "lablab"):
        return "hackathon"
    if any(k in fmt for k in ("hackathon", "demo day", "build", "buildathon")):
        return "hackathon"
    return "meetup"


def _registration_bonus(reg):
    if not isinstance(reg, (int, float)):
        return 0  # 拿不到人数就不加不减
    for floor, bonus in HACKATHON_REG_TIERS:
        if reg >= floor:
            return bonus
    return 0


def score_event(event):
    text = ((event.get("title", "") + " " + event.get("description", "")
             + " " + event.get("event_type", "")).lower())
    track = _track(event)

    score = 0
    tags = []
    for tag, words, weight in POSITIVE:
        if any(w in text for w in words):
            score += weight
            tags.append(tag)
    for words, penalty in NEGATIVE:
        if any(w in text for w in words):
            score -= penalty

    fmt = (event.get("event_type", "") or "").lower()
    for key, bonus in FORMAT_BONUS.items():
        if key in fmt or key in text:
            score += bonus
            break

    if track == "hackathon":
        # 奖金加分（有奖金 +6）
        if event.get("prize"):
            score += 6
        # 报名人数加分（只对黑客松）
        score += _registration_bonus(event.get("registrations"))

    score = max(0, min(100, score + 30))  # +30 基线

    if score >= 70:
        priority = "高"
    elif score >= 45:
        priority = "中"
    else:
        priority = "跳过"

    event = dict(event)
    event["score"] = score
    event["tags"] = tags[:4]
    event["priority"] = priority
    event["track"] = track
    return event


def score_all(events):
    return sorted((score_event(e) for e in events),
                  key=lambda e: e["score"], reverse=True)
