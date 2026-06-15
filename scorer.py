"""
ARCA 打分大脑
-------------
输入一个活动（标题 + 描述 + 形式），输出：
  - score   : 0-100 的 ARCA 相关分
  - tags    : 命中的主题标签（Agents / AI Coding / MCP ...）
  - priority: 高 / 中 / 跳过

逻辑完全基于 ARCA 的关注重点：高密度技术开发者、AI Builder、
Agent / Coding / Infra / LLM 工程 / 开源 / 黑客松 / MCP 生态。
低优先级：AI 绘画、内容创作、营销、入门课、泛社交。
"""

# 加分词：命中就加分，并贴上对应标签。
# 格式: (标签, [关键词...], 该标签的权重)
POSITIVE = [
    ("Agents",      ["ai agent", "agentic", "multi-agent", "autonomous agent", "agent framework",
                     "langchain", "llamaindex", "crewai", "autogen", "langgraph"], 16),
    ("AI Coding",   ["ai coding", "vibe coding", "cursor", "claude code", "codex", "copilot",
                     "windsurf", "code generation", "pair programming", "coding agent"], 16),
    ("MCP",         ["mcp", "model context protocol"], 16),
    ("DevTools",    ["developer tool", "devtools", "dev tools", "sdk", "api", "tooling"], 9),
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

# 减分词：命中就扣分，说明偏离 ARCA 重点。
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

# 活动形式的额外加权：动手做 > 工作坊 > 演讲 > 纯社交
FORMAT_BONUS = {
    "hackathon": 14, "demo day": 12, "build": 12, "buildathon": 14,
    "workshop": 8, "bootcamp": 6, "talk": 2, "conference": 4,
    "meetup": 3, "mixer": -6, "webinar": -4, "panel": 1,
}


def score_event(event):
    """给单个活动打分。event 是一个 dict，至少包含 title 和 description。"""
    text = ((event.get("title", "") + " " + event.get("description", "")
             + " " + event.get("event_type", "")).lower())

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

    # 收口到 0-100
    score = max(0, min(100, score + 30))  # +30 基线，让分数分布更直观

    if score >= 70:
        priority = "高"
    elif score >= 45:
        priority = "中"
    else:
        priority = "跳过"

    event = dict(event)
    event["score"] = score
    event["tags"] = tags[:4]          # 最多展示 4 个标签
    event["priority"] = priority
    return event


def score_all(events):
    """给一批活动打分，并按分数从高到低排序。"""
    return sorted((score_event(e) for e in events),
                  key=lambda e: e["score"], reverse=True)
