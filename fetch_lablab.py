"""
lablab 抓取器（RSC header 版）
-----------------------------
lablab 用 Next.js RSC 传数据，活动列表在响应里的 "events":[...] 数组。
直接加 ?_rsc=固定值 会被服务器忽略，所以改用「带 RSC 请求头」的方式，
并尝试多个候选地址 + 普通网页保底，把命中过程打到日志。
奖金从描述文字里正则提取；Sponsor 在图片上，无法获取，留空。
"""
import json
import re
import urllib.request
from datetime import date
from sources_common import clean_text, UA

PRIZE_RE = re.compile(r"(\$[\d,]+(?:\.\d+)?\s*[kKmM]?\+?)")

# 候选请求：(地址, 是否带 RSC 头)。依次尝试，命中即用。
CANDIDATES = [
    ("https://lablab.ai/ai-hackathons", True),
    ("https://lablab.ai/", True),
    ("https://lablab.ai/ai-hackathons", False),
]


def _get(url, rsc_header):
    headers = {"User-Agent": UA, "Accept": "*/*"}
    if rsc_header:
        # Next.js 用这些头来返回 RSC 数据而不是整页 HTML
        headers["RSC"] = "1"
        headers["Next-Router-Prefetch"] = "1"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=12) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _extract_events_array(text):
    i = text.find('"events":')
    if i == -1:
        return None
    j = text.find("[", i)
    if j == -1:
        return None
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
                if depth == 0:
                    return text[j:k + 1]
        k += 1
    return None


def _status(ev):
    if ev.get("toBeAnnounced"):
        return "upcoming"
    end = ev.get("endAt")
    if isinstance(end, str):
        end = end.replace("$D", "")
        try:
            if end[:10] and end[:10] < date.today().isoformat():
                return "ended"
        except Exception:
            pass
    if ev.get("signupActive"):
        return "open"
    return "upcoming" if ev.get("active") else "ended"


def _date_range(ev):
    s = (ev.get("startAt") or "").replace("$D", "")[:10]
    e = (ev.get("endAt") or "").replace("$D", "")[:10]
    return f"{s} ~ {e}" if s and e else (s or "待定")


def _prize(desc):
    if not isinstance(desc, str):
        return None
    m = PRIZE_RE.search(desc)
    return m.group(1) if m else None


def fetch_lablab_events():
    text = None
    for url, rsc in CANDIDATES:
        try:
            t = _get(url, rsc)
            tag = "带RSC头" if rsc else "普通"
            if '"events":' in t:
                print(f"[lablab] 命中：{url} ({tag})")
                text = t
                break
            else:
                print(f"[lablab] {url} ({tag}) 无 events，继续尝试")
        except Exception as e:
            print(f"[lablab] 请求 {url} 失败：{e}")
    if not text:
        print("[lablab] 所有方式都没拿到 events 数据")
        return []

    arr_text = _extract_events_array(text)
    if not arr_text:
        print("[lablab] 定位到 events 但截取失败")
        return []
    try:
        raw_events = json.loads(arr_text)
    except Exception as e:
        print(f"[lablab] events 解析失败：{e}")
        return []

    events = []
    for ev in raw_events:
        if not isinstance(ev, dict) or not ev.get("name"):
            continue
        if not (ev.get("active") or ev.get("signupActive") or ev.get("toBeAnnounced")):
            continue
        desc = clean_text(ev.get("description", ""))
        slug = ev.get("slug", "")
        events.append({
            "title": ev.get("name", "(无标题)"),
            "description": desc,
            "source": "lablab",
            "event_type": (ev.get("type") or "Hackathon").title(),
            "date": _date_range(ev),
            "location": (ev.get("eventType") or "ONLINE").title(),
            "url": f"https://lablab.ai/event/{slug}" if slug else "https://lablab.ai/ai-hackathons",
            "host": "",
            "registrations": (ev.get("_count") or {}).get("participants"),
            "prize": _prize(desc),
            "status": _status(ev),
            "date_added": date.today().isoformat(),
        })
    print(f"[lablab] 抓到 {len(events)} 个活动")
    return events


if __name__ == "__main__":
    fetch_lablab_events()
