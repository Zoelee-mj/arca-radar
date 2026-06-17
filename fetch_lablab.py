"""
lablab 抓取器（列表 + 详情页主办方/主题）
=========================================
1) 从首页 RSC 拿活动列表（名称/日期/人数/奖金等）
2) 并发进每个活动详情页，抓主办方（powered by / must use / Speakers 公司）
   和主题（正文关键词总结）
奖金：有金额写金额，非现金写 "Other"，没有留空。
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from sources_common import clean_text, UA
import urllib.request

PRIZE_RE = re.compile(r"(\$[\d,]+(?:\.\d+)?\s*[kKmM]?\+?)")

KNOWN_COMPANIES = [
    "Qualcomm", "Meta", "Samsung", "GitHub", "PyTorch", "AMD", "NVIDIA",
    "Google DeepMind", "Google Cloud", "Google", "Gemini", "AWS", "Microsoft",
    "Azure", "IBM", "OpenAI", "Anthropic", "Claude", "Circle", "Arc",
    "Bright Data", "Vultr", "Kraken", "Deriv", "MindsDB", "Snyk", "Mastercard",
    "CrewAI", "LangChain", "Surge", "ElevenLabs", "Stability AI", "Featherless",
    "Speechmatics", "Band", "Nebius", "Supabase", "Coolify", "NativelyAI", "NEAR",
]

# 主题关键词（命中就作为 topic 显示）
TOPIC_MAP = [
    ("AI Agent", ["ai agent", "agentic", "autonomous agent", "multi-agent"]),
    ("Vibe Coding", ["vibe coding", "ai coding", "cursor", "claude code", "codex", "copilot"]),
    ("MCP", ["mcp", "model context protocol"]),
    ("LLM", ["llm", "fine-tun", "post-training", "rlhf", "rag", "eval"]),
    ("Voice AI", ["voice ai", "voice agent", "speech", "live api"]),
    ("Multimodal", ["multimodal", "image", "video", "vision"]),
    ("Web3/Crypto", ["blockchain", "crypto", "usdc", "web3", "onchain", "wallet"]),
    ("Infra", ["infrastructure", "inference", "gpu", "vector db", "deploy"]),
    ("Open Source", ["open source", "open-source", "oss"]),
    ("Enterprise", ["enterprise", "workflow", "automation"]),
]


def _companies(text):
    if not isinstance(text, str):
        return []
    found = []
    for c in KNOWN_COMPANIES:
        if re.search(r"\b" + re.escape(c) + r"\b", text, re.I) and c not in found:
            found.append(c)
    return found


def _topics(text):
    if not isinstance(text, str):
        return []
    low = text.lower()
    out = []
    for label, words in TOPIC_MAP:
        if any(w in low for w in words):
            out.append(label)
    return out[:4]


def _get(url, rsc):
    headers = {"User-Agent": UA, "Accept": "*/*"}
    if rsc:
        headers["RSC"] = "1"; headers["Next-Router-Prefetch"] = "1"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=12) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _extract_events_array(text):
    i = text.find('"events":')
    if i == -1: return None
    j = text.find("[", i)
    if j == -1: return None
    depth, k, in_str, esc = 0, j, False, False
    while k < len(text):
        c = text[k]
        if in_str:
            if esc: esc = False
            elif c == "\\": esc = True
            elif c == '"': in_str = False
        else:
            if c == '"': in_str = True
            elif c == "[": depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0: return text[j:k+1]
        k += 1
    return None


def _status(ev):
    if ev.get("toBeAnnounced"): return "upcoming"
    end = ev.get("endAt")
    if isinstance(end, str):
        end = end.replace("$D", "")
        try:
            if end[:10] and end[:10] < date.today().isoformat(): return "ended"
        except Exception: pass
    if ev.get("signupActive"): return "open"
    return "upcoming" if ev.get("active") else "ended"


def _date_range(ev):
    s = (ev.get("startAt") or "").replace("$D", "")[:10]
    e = (ev.get("endAt") or "").replace("$D", "")[:10]
    return f"{s} ~ {e}" if s and e else (s or "TBA")


def _reward(desc):
    if isinstance(desc, str):
        m = PRIZE_RE.search(desc)
        if m: return m.group(1)
        if re.search(r"credit|prize|reward|goodies|airpods|swag|token", desc, re.I):
            return "Other"
    return None


def _fetch_detail(slug):
    """进活动详情页，返回 (organizer_str, topics_list)。"""
    url = f"https://lablab.ai/ai-hackathons/{slug}"
    try:
        html = _get(url, rsc=True)
    except Exception:
        try:
            html = _get(url, rsc=False)
        except Exception:
            return "", []
    text = clean_text(html)
    companies = _companies(text)
    topics = _topics(text)
    return " / ".join(companies[:4]), topics


def fetch_lablab_events():
    text = None
    for url, rsc in [("https://lablab.ai/ai-hackathons", True),
                     ("https://lablab.ai/", True),
                     ("https://lablab.ai/ai-hackathons", False)]:
        try:
            t = _get(url, rsc)
            if '"events":' in t:
                print(f"[lablab] 命中：{url}")
                text = t; break
        except Exception as e:
            print(f"[lablab] 请求 {url} 失败：{e}")
    if not text:
        print("[lablab] 未拿到 events"); return []

    arr = _extract_events_array(text)
    if not arr:
        print("[lablab] 截取 events 失败"); return []
    try:
        raw_events = json.loads(arr)
    except Exception as e:
        print(f"[lablab] 解析失败：{e}"); return []

    base = []
    for ev in raw_events:
        if not isinstance(ev, dict) or not ev.get("name"): continue
        if not (ev.get("active") or ev.get("signupActive") or ev.get("toBeAnnounced")): continue
        desc = clean_text(ev.get("description", ""))
        base.append({
            "title": ev.get("name", "(无标题)"), "description": desc, "source": "lablab",
            "event_type": "Hackathon", "date": _date_range(ev),
            "location": (ev.get("eventType") or "ONLINE").title(),
            "url": f"https://lablab.ai/event/{ev.get('slug','')}",
            "slug": ev.get("slug", ""),
            "registrations": (ev.get("_count") or {}).get("participants"),
            "prize": _reward(desc), "status": _status(ev),
            "date_added": date.today().isoformat(),
        })

    # 并发进详情页抓主办方 + 主题
    print(f"[lablab] 开始抓 {len(base)} 个详情页（主办方+主题）…")
    detail = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = {pool.submit(_fetch_detail, e["slug"]): e["slug"] for e in base if e["slug"]}
        for fut in as_completed(futs):
            detail[futs[fut]] = fut.result()

    got = 0
    for e in base:
        org, topics = detail.get(e["slug"], ("", []))
        # 详情页没抓到主办方时，用描述里的公司名兜底
        if not org:
            org = " / ".join(_companies(e["title"] + " " + e["description"])[:4])
        if not topics:
            topics = _topics(e["title"] + " " + e["description"])
        e["host"] = org
        e["topics"] = topics
        e.pop("slug", None)
        if org: got += 1
    print(f"[lablab] 详情页拿到主办方 {got}/{len(base)}")
    print(f"[lablab] 抓到 {len(base)} 个活动")
    return base


if __name__ == "__main__":
    for e in fetch_lablab_events():
        print(e["title"], "| 主办", e["host"], "| 主题", e.get("topics"))
