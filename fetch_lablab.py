"""
lablab 抓取器（RSC 专用版）
--------------------------
lablab 用 Next.js 的 RSC 格式传数据，活动列表藏在响应里一个
"events":[ ... ] 的 JSON 数组中。本抓取器：
  1) 直接请求 RSC 接口（带 ?_rsc 参数）
  2) 从文本里定位 "events":[...] 并完整截取该数组
  3) 逐个活动归一化（含报名人数、阶段、奖金）
奖金从 description 文字里用正则提取；Sponsor 在图片上，无法获取，留空。
"""
import json
import re
from datetime import date
from sources_common import http_get, clean_text

LABLAB_URL = "https://lablab.ai/ai-hackathons"
# RSC 接口：在正常页面 URL 后面加 ?_rsc 参数即可拿到纯数据
RSC_URL = "https://lablab.ai/ai-hackathons?_rsc=1"

PRIZE_RE = re.compile(r"(\$[\d,]+(?:\.\d+)?\s*[kKmM]?\+?)")


def _extract_events_array(text):
    """从 RSC 文本里把 "events":[ ... ] 这个数组完整、平衡括号地截取出来。"""
    key = '"events":'
    i = text.find(key)
    if i == -1:
        return None
    j = text.find("[", i)
    if j == -1:
        return None
    depth, k, in_str, esc = 0, j, False, False
    while k < len(text):
        c = text[k]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "[":
                depth += 1
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
    # RSC 里日期写成 "$D2026-06-19T..."，去掉前缀 $D
    if isinstance(end, str):
        end = end.replace("$D", "")
        try:
            if end[:10] < date.today().isoformat():
                return "ended"
        except Exception:
            pass
    if ev.get("signupActive"):
        return "open"
    return "upcoming" if ev.get("active") else "ended"


def _date_range(ev):
    s = (ev.get("startAt") or "").replace("$D", "")[:10]
    e = (ev.get("endAt") or "").replace("$D", "")[:10]
    if s and e:
        return f"{s} ~ {e}"
    return s or "待定"


def _prize(desc):
    if not isinstance(desc, str):
        return None
    m = PRIZE_RE.search(desc)
    return m.group(1) if m else None


def fetch_lablab_events():
    text = None
    for url in (RSC_URL, LABLAB_URL):
        try:
            text = http_get(url)
            if '"events":' in text:
                break
        except Exception as e:
            print(f"[lablab] 请求 {url} 失败：{e}")
    if not text or '"events":' not in text:
        print("[lablab] 未找到 events 数据")
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
        # 跳过明显的测试/占位活动
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
            "url": f"https://lablab.ai/event/{slug}" if slug else LABLAB_URL,
            "host": "",  # Sponsor 在缩略图上，文字数据里没有
            "registrations": (ev.get("_count") or {}).get("participants"),
            "prize": _prize(desc),
            "status": _status(ev),
            "date_added": date.today().isoformat(),
        })
    print(f"[lablab] 抓到 {len(events)} 个活动")
    return events


if __name__ == "__main__":
    for e in fetch_lablab_events():
        print(e["title"], "|", e["date"], "| 报名", e["registrations"], "|", e["prize"])
