"""
Devpost 抓取器
--------------
Devpost 有公开 JSON 接口，能直接拿到奖金、报名人数、阶段、主办方，
是四个新列数据最全的来源。
"""
import json
from sources_common import http_get, clean_text
from datetime import date

# 抓 AI 相关、状态为 open / upcoming 的黑客松
API = ("https://devpost.com/api/hackathons"
       "?search=ai&status[]=upcoming&status[]=open&page={page}")

STATUS_MAP = {"open": "open", "upcoming": "upcoming", "ended": "ended"}


def fetch_devpost_events(max_pages=2):
    events = []
    for page in range(1, max_pages + 1):
        try:
            data = json.loads(http_get(API.format(page=page)))
        except Exception as e:
            print(f"[Devpost] 第 {page} 页抓取失败：{e}")
            break
        items = data.get("hackathons", []) if isinstance(data, dict) else []
        if not items:
            break
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
                "date_added": date.today().isoformat(),
            })
    print(f"[Devpost] 抓到 {len(events)} 个活动")
    return events


if __name__ == "__main__":
    for e in fetch_devpost_events():
        print(e["score"] if "score" in e else "", e["title"])
