"""
lablab 抓取器
-------------
抓取 lablab.ai 的 AI 黑客松列表页，从内嵌 JSON 提取活动。
"""
from sources_common import http_get, extract_next_data, find_event_like, normalize

LABLAB_URL = "https://lablab.ai/ai-hackathons"


def fetch_lablab_events():
    events = []
    try:
        html_text = http_get(LABLAB_URL)
    except Exception as e:
        print(f"[lablab] 抓取失败：{e}")
        return events
    data = extract_next_data(html_text)
    if not data:
        print("[lablab] 未找到内嵌数据（可能改版，需调整）")
        return events
    for raw in find_event_like(data):
        ev = normalize(raw, source="lablab", default_type="Hackathon")
        if ev["url"] and not ev["url"].startswith("http"):
            ev["url"] = f"https://lablab.ai/{ev['url'].lstrip('/')}"
        if not ev["url"]:
            ev["url"] = LABLAB_URL
        events.append(ev)
    print(f"[lablab] 抓到 {len(events)} 个活动")
    return events


if __name__ == "__main__":
    for e in fetch_lablab_events():
        print(e["title"], "|", e["date"])
