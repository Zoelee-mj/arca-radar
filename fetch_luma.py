"""
Luma 抓取器（接口游标翻页 + 详情页主办方/赞助/人数）
===================================================
1) 每个日历：从页面拿 calendar_api_id，再用 get-items 接口游标翻页抓全部活动
   （解决之前每个日历只抓前 20 个的问题）
2) 并发进每个活动详情页，抓 主办方/Cohost + 报名人数 + Type
并发 8 路、每请求 12 秒超时；任一步失败留空，不影响其它。
"""
import json
import re
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from sources_common import http_get, extract_next_data, normalize, clean_text, UA

LUMA_CALENDARS = [
    "ls", "claw", "ai", "claudecommunity",
    "genai-collective", "bond-london", "genai-sf", "genai-ny",
]
CAL_NAME_FIX = {"ls": "Latent Space", "claw": "CLAW", "ai": "AI Events Hub",
                "claudecommunity": "Claude Community", "genai-sf": "GenAI SF",
                "genai-ny": "GenAI NY", "genai-collective": "GenAI Collective",
                "bond-london": "Bond London"}

GET_ITEMS = "https://api.luma.com/calendar/get-items?calendar_api_id={cid}&pagination_limit=50&period=future"
REG_RE = re.compile(r"(\d[\d,]*)\s*(?:参加|going|attendees|attending|registered|guests?)", re.I)
SPONSOR_CUES = ["thank you for making this", "made possible", "sponsored by", "powered by",
                "prize tracks", "our sponsors", "credits from", "感谢", "赞助"]
COMPANY_RE = re.compile(r"\b([A-Z][A-Za-z0-9&.]*(?:\s+[A-Z][A-Za-z0-9&.]*){0,3})\b")
STOP_WORDS = {"Prize", "Tracks", "Thank", "You", "Team", "Sizes", "Agenda", "Best",
              "First", "Second", "Third", "Place", "AI", "The", "And", "For", "All",
              "Walk", "Most", "Each", "Voice", "LLM", "AirPods"}


def _api_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _calendar_id(slug):
    """从日历页 __NEXT_DATA__ 里找 calendar 的 api_id（形如 cal-xxx）。"""
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
    return found[0] if found else None


def _items_for_calendar(cid):
    """用 get-items 接口游标翻页，抓某日历的全部活动对象。"""
    items, cursor, pages = [], None, 0
    while pages < 15:  # 上限保护：最多 15 页（约 750 个）
        url = GET_ITEMS.format(cid=cid)
        if cursor:
            url += "&pagination_cursor=" + urllib.parse.quote(cursor)
        try:
            data = _api_json(url)
        except Exception as e:
            print(f"[Luma] {cid} 第{pages+1}页失败：{e}")
            break
        entries = data.get("entries") or data.get("items") or []
        for en in entries:
            ev = en.get("event") if isinstance(en, dict) and "event" in en else en
            if isinstance(ev, dict):
                items.append(ev)
        cursor = data.get("next_cursor") or data.get("pagination_cursor")
        pages += 1
        if not data.get("has_more") and not cursor:
            break
        if not entries:
            break
    return items


def _ev_from_item(ev, slug):
    """把接口返回的活动对象转成统一字段。"""
    name = ev.get("name") or ev.get("title") or "(无标题)"
    api_id = ev.get("api_id") or ev.get("url") or ""
    url = f"https://luma.com/{api_id}" if api_id and not str(api_id).startswith("http") else (api_id or f"https://luma.com/{slug}")
    geo = ev.get("geo_address_info") or {}
    loc = (geo.get("city_state") or geo.get("address") or geo.get("city")
           if isinstance(geo, dict) else None) or "Online"
    start = str(ev.get("start_at") or "")[:10]
    return {
        "title": name, "description": clean_text(ev.get("description") or ""),
        "source": "Luma", "event_type": _luma_type(name), "date": start or "TBA",
        "location": loc, "url": url,
        "registrations": ev.get("guest_count"),
        "prize": None, "status": "upcoming",
        "date_added": __import__("datetime").date.today().isoformat(),
    }


def _luma_type(title):
    t = (title or "").lower()
    if "hackathon" in t or "buildathon" in t:
        return "Hackathon"
    if "workshop" in t:
        return "Workshop"
    return "Meetup"


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


def _extract_sponsors(text):
    if not isinstance(text, str):
        return []
    low = text.lower()
    sponsors = []
    for cue in SPONSOR_CUES:
        idx = low.find(cue)
        if idx == -1:
            continue
        for line in text[idx: idx + 400].splitlines()[1:]:
            line = line.strip(" *•\t-")
            if not line or len(line) > 40:
                continue
            m = COMPANY_RE.match(line)
            if m and m.group(1).split()[0] not in STOP_WORDS:
                nm = m.group(1).strip()
                if nm and nm not in sponsors:
                    sponsors.append(nm)
            if len(sponsors) >= 8:
                break
    return sponsors[:6]


def _fetch_detail(url):
    try:
        html = http_get(url)
    except Exception:
        return None, None, []
    data = extract_next_data(html)
    host = clean_text(_find_host(data)) if data else None
    reg = None
    m = re.search(r'"guest_count":\s*(\d+)', html)
    if m:
        reg = int(m.group(1))
    else:
        m2 = REG_RE.search(html)
        if m2:
            try: reg = int(m2.group(1).replace(",", ""))
            except Exception: pass
    return host, reg, _extract_sponsors(clean_text(html))


def fetch_luma_events():
    events, seen = [], set()
    for slug in LUMA_CALENDARS:
        cid = _calendar_id(slug)
        if not cid:
            print(f"[Luma] {slug}: 未取到日历ID，跳过")
            continue
        items = _items_for_calendar(cid)
        count = 0
        for ev in items:
            e = _ev_from_item(ev, slug)
            key = (e["title"], e["date"])
            if key in seen:
                continue
            seen.add(key)
            e["_cal_fallback"] = CAL_NAME_FIX.get(slug, slug)
            events.append(e)
            count += 1
        print(f"[Luma] {slug}: {count} 个活动")

    detail_urls = [e["url"] for e in events if str(e.get("url", "")).startswith("http")]
    print(f"[Luma] 开始抓 {len(detail_urls)} 个详情页（主办方+赞助+人数）…")
    results = {}

    def work(u):
        h, r, sp = _fetch_detail(u)
        return u, h, r, sp

    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(work, u) for u in detail_urls]
        for fut in as_completed(futs):
            u, h, r, sp = fut.result()
            results[u] = (h, r, sp)

    host_got = reg_got = 0
    for e in events:
        h, r, sp = results.get(e["url"], (None, None, []))
        organizer = h or e.pop("_cal_fallback", "")
        e.pop("_cal_fallback", None)
        parts = [organizer] if organizer else []
        for s in sp:
            if s and s not in parts:
                parts.append(s)
        e["host"] = " / ".join(parts) if parts else ""
        if r is not None:
            e["registrations"] = r
        if e.get("registrations") is not None:
            reg_got += 1
        if h:
            host_got += 1
    print(f"[Luma] 详情页：主办方 {host_got}/{len(detail_urls)}，报名人数 {reg_got}/{len(detail_urls)}")
    print(f"[Luma] 合计 {len(events)} 个活动")
    return events


if __name__ == "__main__":
    for e in fetch_luma_events():
        print(e["title"], "|", e["event_type"], "| reg", e["registrations"])
