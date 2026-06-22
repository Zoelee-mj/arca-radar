"""
Luma 抓取器（纯接口版：游标翻页 + 接口字段直取）
===============================================
用 get-items 接口游标翻页抓全部活动；主办方/人数/Type/状态全部
直接从接口返回字段提取（hosts / guest_count / tags / end_at），
不再进详情页 —— 又快又准又全。
"""
import json
import re
import urllib.request
import urllib.parse
from datetime import date, datetime, timezone
from sources_common import extract_next_data, http_get, clean_text, UA

LUMA_CALENDARS = [
    "ls", "claw", "ai", "claudecommunity",
    "genai-collective", "bond-london", "genai-sf", "genai-ny",
]
CAL_NAME_FIX = {"ls": "Latent Space", "claw": "CLAW", "ai": "AI Events Hub",
                "claudecommunity": "Claude Community", "genai-sf": "GenAI SF",
                "genai-ny": "GenAI NY", "genai-collective": "GenAI Collective",
                "bond-london": "Bond London"}
GET_ITEMS = "https://api.luma.com/calendar/get-items?calendar_api_id={cid}&pagination_limit=50&period=future"


def _api_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _calendar_id(slug):
    try:
        data = extract_next_data(http_get(f"https://luma.com/{slug}"))
    except Exception:
        return None
    found = []

    def walk(n):
        if isinstance(n, dict):
            v = n.get("api_id")
            if isinstance(v, str) and v.startswith("cal-"):
                found.append(v)
            for x in n.values():
                walk(x)
        elif isinstance(n, list):
            for x in n:
                walk(x)
    walk(data)
    # 取出现最多的那个 cal- id（日历主体），避免拿到某个活动所属的别的日历
    if not found:
        return None
    from collections import Counter
    return Counter(found).most_common(1)[0][0]


def _items_for_calendar(cid):
    items, cursor, pages = [], None, 0
    while pages < 15:
        url = GET_ITEMS.format(cid=cid)
        if cursor:
            url += "&pagination_cursor=" + urllib.parse.quote(cursor)
        try:
            data = _api_json(url)
        except Exception as e:
            print(f"[Luma] {cid} 第{pages+1}页失败：{e}")
            break
        entries = data.get("entries") or []
        items.extend(entries)
        cursor = data.get("next_cursor")
        pages += 1
        if not data.get("has_more") or not cursor or not entries:
            break
    return items


def _luma_type(title, tags):
    for t in tags or []:
        if isinstance(t, dict) and "hackathon" in (t.get("name", "").lower()):
            return "Hackathon"
    low = (title or "").lower()
    if "hackathon" in low or "buildathon" in low:
        return "Hackathon"
    if "workshop" in low:
        return "Workshop"
    return "Meetup"


def _status(end_at):
    if not end_at:
        return "upcoming"
    try:
        end = datetime.fromisoformat(end_at.replace("Z", "+00:00"))
        return "ended" if end < datetime.now(timezone.utc) else "upcoming"
    except Exception:
        return "upcoming"


def _entry_to_event(entry):
    ev = entry.get("event") or {}
    if not ev.get("name"):
        return None
    hosts = entry.get("hosts") or []
    host_names = [h.get("name") for h in hosts if isinstance(h, dict) and h.get("name")]
    geo = ev.get("geo_address_info") or {}
    loc = (geo.get("city_state") or geo.get("city") or "Online") if isinstance(geo, dict) else "Online"
    if ev.get("location_type") == "virtual":
        loc = "Online"
    short = ev.get("url") or ev.get("api_id") or ""
    url = f"https://luma.com/{short}" if short and not str(short).startswith("http") else short
    tags = entry.get("tags") or []
    return {
        "title": ev.get("name"), "description": "", "source": "Luma",
        "event_type": _luma_type(ev.get("name"), tags),
        "date": str(ev.get("start_at") or "")[:10] or "TBA",
        "location": loc, "url": url,
        "host": " / ".join(host_names[:4]),
        "registrations": entry.get("guest_count"),
        "prize": None, "status": _status(ev.get("end_at")),
        "date_added": date.today().isoformat(),
    }


def fetch_luma_events():
    events, seen = [], set()
    for slug in LUMA_CALENDARS:
        cid = _calendar_id(slug)
        if not cid:
            print(f"[Luma] {slug}: 未取到日历ID，跳过")
            continue
        count = 0
        for entry in _items_for_calendar(cid):
            e = _entry_to_event(entry)
            if not e:
                continue
            key = (e["title"], e["date"])
            if key in seen:
                continue
            seen.add(key)
            if not e["host"]:
                e["host"] = CAL_NAME_FIX.get(slug, slug)
            events.append(e)
            count += 1
        print(f"[Luma] {slug}: {count} 个活动")

    host_got = sum(1 for e in events if e["host"])
    reg_got = sum(1 for e in events if e.get("registrations") is not None)
    print(f"[Luma] 主办方 {host_got}/{len(events)}，报名人数 {reg_got}/{len(events)}（接口直取）")
    print(f"[Luma] 合计 {len(events)} 个活动")
    return events


if __name__ == "__main__":
    for e in fetch_luma_events():
        print(e["title"], "|", e["event_type"], "| reg", e["registrations"], "| host", e["host"])
