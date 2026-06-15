"""公共抓取工具（多策略解析版）"""
import json
import re
import socket
import urllib.request
from datetime import date

# 全局兜底：任何网络操作最多等 15 秒，绝不无限挂起
socket.setdefaulttimeout(15)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def http_get(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def extract_next_data(html_text):
    """策略1：取 <script id="__NEXT_DATA__"> 里的 JSON。"""
    m = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', html_text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


def extract_jsonld(html_text):
    """策略2：取所有 <script type="application/ld+json"> 里的 JSON（最标准、最稳）。"""
    blobs = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
                       html_text, re.S)
    out = []
    for b in blobs:
        try:
            data = json.loads(b.strip())
            out.append(data)
        except Exception:
            continue
    return out


def extract_all_script_json(html_text):
    """策略3：扫描所有 <script> 块，凡是能解析成 JSON 的都收集起来。"""
    out = []
    for b in re.findall(r'<script[^>]*>(.*?)</script>', html_text, re.S):
        b = b.strip()
        if not (b.startswith("{") or b.startswith("[")):
            continue
        try:
            out.append(json.loads(b))
        except Exception:
            continue
    return out


NAME_KEYS = ("name", "title")
DATE_KEYS = ("start_at", "start_time", "starts_at", "start_date", "startDate",
             "date", "submission_period_dates")


def find_event_like(node, found=None):
    """递归遍历 JSON，收集同时含有名字字段和日期字段的对象。"""
    if found is None:
        found = []
    if isinstance(node, dict):
        has_name = any(k in node and isinstance(node[k], str) for k in NAME_KEYS)
        has_date = any(k in node for k in DATE_KEYS)
        if has_name and has_date:
            found.append(node)
        for v in node.values():
            find_event_like(v, found)
    elif isinstance(node, list):
        for v in node:
            find_event_like(v, found)
    return found


def _first(d, keys, default=None):
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return default


def normalize(raw, source, default_type="Event"):
    return {
        "title": _first(raw, NAME_KEYS, "(无标题)"),
        "description": _first(raw, ("description", "summary", "tagline", "subtitle"), ""),
        "source": source,
        "event_type": _first(raw, ("event_type", "type", "category"), default_type),
        "date": str(_first(raw, DATE_KEYS, ""))[:40],
        "location": _first(raw, ("location", "city", "geo_address_info", "displayed_location"), ""),
        "url": _first(raw, ("url", "permalink", "link"), ""),
        "host": _first(raw, ("host", "organization_name", "calendar_name", "organizer", "hosts"), ""),
        "registrations": _first(raw, ("registrations_count", "guest_count", "attendees", "registered"), None),
        "prize": _first(raw, ("prize", "prize_amount", "prizes"), None),
        "status": _first(raw, ("status", "open_state", "state"), "upcoming"),
        "date_added": date.today().isoformat(),
    }


def clean_text(s):
    if not isinstance(s, str):
        return s
    return re.sub(r"<[^>]+>", "", s).strip()
