"""
Devpost 抓取器
--------------
用 Devpost 公开 JSON 接口抓 AI 黑客松。一直翻页到没有为止，
所以能把全部进行中/即将开始的活动都抓回来（不再只有 18 个）。
"""
import json
import urllib.request
from sources_common import UA
from sources_common import http_get, clean_text
from fetch_lablab import _topics
from datetime import date

API = ("https://devpost.com/api/hackathons"
       "?search=ai&status[]=upcoming&status[]=open&page={page}")
STATUS_MAP = {"open": "open", "upcoming": "upcoming", "ended": "ended"}


def fetch_devpost_events(max_pages=12):
    events = []
    for page in range(1, max_pages + 1):
        try:
            req = urllib.request.Request(API.format(page=page), headers={
                "User-Agent": UA, "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest", "Referer": "https://devpost.com/hackathons"})
            with urllib.request.urlopen(req, timeout=12) as r:
                data = json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:
            print(f"[Devpost] 第 {page} 页抓取失败：{e}")
            break
        items = data.get("hackathons", []) if isinstance(data, dict) else []
        if not items:
            break  # 没有更多了，停止翻页
        for h in items:
            loc = h.get("displayed_location") or {}
            events.append({
                "title": h.get("title", "(无标题)"),
                "description": " ".join(t.get("name", "") for t in h.get("themes", [])),
                "source": "Devpost",
                "event_type": "Hackathon",
                "date": h.get("submission_period_dates", ""),
                "location": loc.get("location", "Online") if isinstance(loc, dict) else "Online",
                "url": h.get("url", ""),
                "host": h.get("organization_name", ""),
                "registrations": h.get("registrations_count"),
                "prize": clean_text(h.get("prize_amount")) or None,
                "status": STATUS_MAP.get(h.get("open_state", ""), "upcoming"),
                "topics": _topics(h.get("title","") + " " + " ".join(t.get("name","") for t in h.get("themes",[]))),
                "date_added": date.today().isoformat(),
            })
        print(f"[Devpost] 第 {page} 页：{len(items)} 个")
    print(f"[Devpost] 抓到 {len(events)} 个活动")
    return events


if __name__ == "__main__":
    fetch_devpost_events()
