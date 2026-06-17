"""
Luma 抓取器（详情页：主办方/Cohost + 报名人数 + Type）
====================================================
列表页拿活动 → 并发进详情页，从正文抓：
  - 主办人 + 赞助/合办公司（Thank you / sponsored by / Prize Tracks / credits from）
  - 报名人数（"N 参加" / "N going"）
  - Type：标题含 hackathon→Hackathon，含 workshop→Workshop，其余→Meetup
并发 8 路、每请求 12 秒超时；抓不到的字段留空，不影响其它。
"""
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from sources_common import http_get, extract_next_data, find_event_like, normalize, clean_text

LUMA_CALENDARS = [
    "ls", "claw", "ai", "claudecommunity",
    "genai-collective", "bond-london", "genai-sf", "genai-ny",
]
CAL_NAME_FIX = {"ls": "Latent Space", "claw": "CLAW", "ai": "AI Events Hub",
                "claudecommunity": "Claude Community", "genai-sf": "GenAI SF",
                "genai-ny": "GenAI NY", "genai-collective": "GenAI Collective",
                "bond-london": "Bond London"}

# 报名人数： "67 参加" / "67 going" / "67 Attendees"
REG_RE = re.compile(r"(\d[\d,]*)\s*(?:参加|going|attendees|attending|registered|guests?)", re.I)
# 赞助/合办公司：在这些引导词后面，逐行收集公司名
SPONSOR_CUES = [
    "thank you for making this", "made possible", "sponsored by", "powered by",
    "prize tracks", "thanks to our sponsors", "our sponsors", "credits from",
    "感谢", "赞助",
]


def _location_text(raw):
    geo = raw.get("geo_address_info") or raw.get("location")
    if isinstance(geo, dict):
        return geo.get("city_state") or geo.get("address") or geo.get("city") or "Online"
    return clean_text(geo) if geo else "Online"


def _find_host(node):
    if isinstance(node, dict):
        h = node.get("hosts")
        if isinstance(h, list):
            for it in h:
                if isinstance(it, dict) and it.get("name"):
                    return it["name"]
        for key in ("host", "calendar"):
            v = node.get(key)
            if isinstance(v, dict) and v.get("name"):
                return v["name"]
            if isinstance(v, str) and v.strip():
                return v
        for v in node.values():
            r = _find_host(v)
            if r:
                return r
    elif isinstance(node, list):
        for v in node:
            r = _find_host(v)
            if r:
                return r
    return None


# 公司名候选：大写开头的词组（含 & 和 .），用于在赞助段落里挑出公司
COMPANY_RE = re.compile(r"\b([A-Z][A-Za-z0-9&.]*(?:\s+[A-Z][A-Za-z0-9&.]*){0,3})\b")
STOP_WORDS = {"Prize", "Tracks", "Thank", "You", "Team", "Sizes", "Agenda", "Best",
              "First", "Second", "Third", "Place", "AI", "The", "And", "For", "All",
              "Walk", "Most", "Each", "Voice", "LLM", "AirPods"}


def _extract_sponsors(text):
    """从正文里，定位赞助引导词，收集其后若干行里的公司名。"""
    if not isinstance(text, str):
        return []
    low = text.lower()
    sponsors = []
    for cue in SPONSOR_CUES:
        idx = low.find(cue)
        if idx == -1:
            continue
        chunk = text[idx: idx + 400]  # 引导词后面一小段
        for line in chunk.splitlines()[1:]:
            line = line.strip(" *•\t-")
            if not line or len(line) > 40:
                continue
            m = COMPANY_RE.match(line)
            if m and m.group(1).split()[0] not in STOP_WORDS:
                name = m.group(1).strip()
                if name and name not in sponsors:
                    sponsors.append(name)
            if len(sponsors) >= 8:
                break
    return sponsors[:6]


def _luma_type(title):
    t = (title or "").lower()
    if "hackathon" in t or "buildathon" in t:
        return "Hackathon"
    if "workshop" in t:
        return "Workshop"
    return "Meetup"


def _fetch_detail(url):
    """返回 (host_cohost, registrations, raw_text)。失败返回空。"""
    try:
        html = http_get(url)
    except Exception:
        return None, None, ""
    data = extract_next_data(html)
    host = clean_text(_find_host(data)) if data else None
    # 报名人数：先从 JSON 找 guest_count，再从可见文字兜底
    reg = None
    if data:
        for key in ("guest_count", "guests_count"):
            m = re.search(r'"%s":\s*(\d+)' % key, html)
            if m:
                reg = int(m.group(1)); break
    if reg is None:
        m = REG_RE.search(html)
        if m:
            try: reg = int(m.group(1).replace(",", ""))
            except Exception: pass
    return host, reg, html


def fetch_luma_events():
    events, seen = [], set()
    for slug in LUMA_CALENDARS:
        url = f"https://luma.com/{slug}"
        try:
            data = extract_next_data(http_get(url))
        except Exception as e:
            print(f"[Luma] {slug} 抓取失败：{e}")
            continue
        if not data:
            print(f"[Luma] {slug} 未找到内嵌数据")
            continue
        count = 0
        for raw in find_event_like(data):
            ev = normalize(raw, source="Luma", default_type="Event")
            ev["location"] = _location_text(raw)
            if ev["url"] and not str(ev["url"]).startswith("http"):
                ev["url"] = f"https://luma.com/{str(ev['url']).lstrip('/')}"
            if not ev["url"]:
                ev["url"] = url
            key = (ev["title"], ev["date"])
            if key in seen:
                continue
            seen.add(key)
            ev["_cal_fallback"] = CAL_NAME_FIX.get(slug, slug)
            ev["event_type"] = _luma_type(ev["title"])  # Type 列
            events.append(ev)
            count += 1
        print(f"[Luma] {slug}: {count} 个活动")

    detail_urls = [e["url"] for e in events if str(e.get("url", "")).startswith("http")]
    print(f"[Luma] 开始抓 {len(detail_urls)} 个详情页（主办方+赞助+人数）…")
    results = {}

    def work(u):
        host, reg, text = _fetch_detail(u)
        sponsors = _extract_sponsors(text)
        return u, host, reg, sponsors

    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(work, u) for u in detail_urls]
        for fut in as_completed(futs):
            u, host, reg, sponsors = fut.result()
            results[u] = (host, reg, sponsors)

    host_got = reg_got = 0
    for e in events:
        host, reg, sponsors = results.get(e["url"], (None, None, []))
        organizer = host or e.pop("_cal_fallback", "")
        e.pop("_cal_fallback", None)
        # 合成「主办方/Cohost」一列
        parts = [organizer] if organizer else []
        for s in sponsors:
            if s and s not in parts:
                parts.append(s)
        e["host"] = " / ".join(parts) if parts else ""
        if reg is not None:
            e["registrations"] = reg
            reg_got += 1
        if host:
            host_got += 1
    print(f"[Luma] 详情页：主办方 {host_got}/{len(detail_urls)}，报名人数 {reg_got}/{len(detail_urls)}")
    print(f"[Luma] 合计 {len(events)} 个活动")
    return events


if __name__ == "__main__":
    for e in fetch_luma_events():
        print(e["title"], "|", e["event_type"], "| 报名", e["registrations"], "| 主办", e["host"])
