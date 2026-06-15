"""
lablab 抓取器（多策略版）
------------------------
依次尝试多种解析方式，命中哪种用哪种：
  1) __NEXT_DATA__   2) JSON-LD（schema.org Event）   3) 扫描全部 script JSON
并把每种策略的命中数打到日志，方便判断 lablab 当前用的是哪种结构。
"""
from sources_common import (http_get, extract_next_data, extract_jsonld,
                            extract_all_script_json, find_event_like,
                            normalize, clean_text)

LABLAB_URL = "https://lablab.ai/ai-hackathons"


def _from_jsonld(blobs):
    """JSON-LD 里挑出 Event / Hackathon 类型的对象。"""
    found = []
    for data in blobs:
        items = data if isinstance(data, list) else [data]
        for it in items:
            if not isinstance(it, dict):
                continue
            t = str(it.get("@type", "")).lower()
            if "event" in t or "hackathon" in t or it.get("name"):
                found.append(it)
            graph = it.get("@graph")
            if isinstance(graph, list):
                found += [g for g in graph if isinstance(g, dict) and g.get("name")]
    return found


def _finalize(ev):
    if ev["url"] and not str(ev["url"]).startswith("http"):
        ev["url"] = f"https://lablab.ai/{str(ev['url']).lstrip('/')}"
    if not ev["url"]:
        ev["url"] = LABLAB_URL
    ev["location"] = clean_text(ev.get("location")) or "Online"
    return ev


def fetch_lablab_events():
    try:
        html_text = http_get(LABLAB_URL)
    except Exception as e:
        print(f"[lablab] 抓取失败：{e}")
        return []

    raw = []
    nd = extract_next_data(html_text)
    if nd:
        hits = find_event_like(nd)
        print(f"[lablab] 策略1 __NEXT_DATA__：{len(hits)} 个")
        raw += hits
    ld = _from_jsonld(extract_jsonld(html_text))
    if ld:
        print(f"[lablab] 策略2 JSON-LD：{len(ld)} 个")
        raw += ld
    if not raw:
        for blob in extract_all_script_json(html_text):
            raw += find_event_like(blob)
        print(f"[lablab] 策略3 全脚本扫描：{len(raw)} 个")

    events, seen = [], set()
    for r in raw:
        ev = _finalize(normalize(r, source="lablab", default_type="Hackathon"))
        key = (ev["title"], ev["date"])
        if ev["title"] == "(无标题)" or key in seen:
            continue
        seen.add(key)
        events.append(ev)

    if not events:
        print("[lablab] 三种策略都没拿到，页面结构可能较特殊，需要看一下源码再调。")
    print(f"[lablab] 抓到 {len(events)} 个活动")
    return events


if __name__ == "__main__":
    fetch_lablab_events()
