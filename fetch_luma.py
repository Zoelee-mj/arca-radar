"""
Luma 抓取器（带详情页主办方）
----------------------------
1) 抓每个日历页，拿到活动列表
2) 并发进每个活动详情页，抓真实主办方(host)
3) 抓不到 host 时，用日历名兜底（如 genai-sf -> GenAI SF）
并发 8 路、每请求 12 秒超时，慢但不卡死；抓不到的留空不影响其它。
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from sources_common import http_get, extract_next_data, find_event_like, normalize, clean_text

LUMA_CALENDARS = [
    "ls", "claw", "ai", "claudecommunity",
    "genai-collective", "bond-london", "genai-sf", "genai-ny",
]

# 日历名兜底（抓不到详情页 host 时用）
CAL_NAME_FIX = {"ls": "Latent Space", "claw": "CLAW", "ai": "AI Events Hub",
                "claudecommunity": "Claude Community", "genai-sf": "GenAI SF",
                "genai-ny": "GenAI NY", "genai-collective": "GenAI Collective",
                "bond-london": "Bond London"}


def _location_text(raw):
    geo = raw.get("geo_address_info") or raw.get("location")
    if isinstance(geo, dict):
        return geo.get("city_state") or geo.get("address") or geo.get("city") or "Online"
    return clean_text(geo) if geo else "Online"


def _find_host(node):
    """在详情页 JSON 里递归找主办方名字。"""
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


def _fetch_host(url):
    """抓单个活动详情页的 host。失败返回 None。"""
    try:
        data = extract_next_data(http_get(url))
        return clean_text(_find_host(data)) if data else None
    except Exception:
        return None


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
            events.append(ev)
            count += 1
        print(f"[Luma] {slug}: {count} 个活动")

    # 并发抓详情页 host
    detail_urls = [e["url"] for e in events if str(e.get("url", "")).startswith("http")]
    host_map = {}
    print(f"[Luma] 开始抓 {len(detail_urls)} 个详情页的主办方…")
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(_fetch_host, u): u for u in detail_urls}
        for fut in as_completed(futs):
            host_map[futs[fut]] = fut.result()
    got = sum(1 for v in host_map.values() if v)
    print(f"[Luma] 详情页拿到主办方 {got}/{len(detail_urls)} 个（其余用日历名兜底）")

    for e in events:
        e["host"] = host_map.get(e["url"]) or e.pop("_cal_fallback", "") 
        e.pop("_cal_fallback", None)

    print(f"[Luma] 合计 {len(events)} 个活动")
    return events


if __name__ == "__main__":
    for e in fetch_luma_events():
        print(e["title"], "| host:", e["host"])
