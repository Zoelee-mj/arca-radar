"""
Luma 抓取器
-----------
抓取你提供的各个 Luma 日历页，从页面内嵌 JSON 里提取活动。
用"递归找活动对象"的方式解析，Luma 改版时也比较扛得住。
"""
from sources_common import http_get, extract_next_data, find_event_like, normalize, clean_text

# 你给的 Luma 日历（slug 就是 luma.com/ 后面那段）
LUMA_CALENDARS = [
    "ls", "claw", "ai", "claudecommunity",
    "genai-collective", "bond-london", "genai-sf", "genai-ny",
]


def _location_text(raw):
    geo = raw.get("geo_address_info") or raw.get("location")
    if isinstance(geo, dict):
        return geo.get("city_state") or geo.get("address") or geo.get("city") or "Online"
    return clean_text(geo) if geo else "Online"


def fetch_luma_events():
    events, seen = [], set()
    for slug in LUMA_CALENDARS:
        url = f"https://luma.com/{slug}"
        try:
            html_text = http_get(url)
        except Exception as e:
            print(f"[Luma] {slug} 抓取失败：{e}")
            continue
        data = extract_next_data(html_text)
        if not data:
            print(f"[Luma] {slug} 未找到内嵌数据（可能改版，需调整）")
            continue
        raw_events = find_event_like(data)
        count = 0
        for raw in raw_events:
            ev = normalize(raw, source="Luma", default_type="Event")
            ev["location"] = _location_text(raw)
            link = raw.get("url") or raw.get("api_id") or ev["title"]
            if ev["url"] and not ev["url"].startswith("http"):
                ev["url"] = f"https://luma.com/{ev['url'].lstrip('/')}"
            if not ev["url"]:
                ev["url"] = url
            key = (ev["title"], ev["date"])
            if key in seen:
                continue
            seen.add(key)
            events.append(ev)
            count += 1
        print(f"[Luma] {slug}: {count} 个活动")
    print(f"[Luma] 合计 {len(events)} 个活动")
    return events


if __name__ == "__main__":
    for e in fetch_luma_events():
        print(e["title"], "|", e["date"], "|", e["location"])
