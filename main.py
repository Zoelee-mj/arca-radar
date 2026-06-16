"""
ARCA 活动雷达 · 主程序（带"记忆"）
=================================
流程：抓 Luma + lablab + Devpost → 对比历史名单标记真正的新活动
      → ARCA 打分 → 生成 report.html
"记忆"机制：seen.json 存所有见过的活动(ID→首次发现日期)。
每天只有名单里没有的活动，才会被标成"今日新发现"。
任一来源失败都会跳过并继续。
"""
import json
import os
from datetime import date
from scorer import score_all
from report import build_report

SEEN_FILE = "seen.json"

SOURCES = []
for name, modname, funcname in [
    ("Luma", "fetch_luma", "fetch_luma_events"),
    ("lablab", "fetch_lablab", "fetch_lablab_events"),
    ("Devpost", "fetch_devpost", "fetch_devpost_events"),
]:
    try:
        mod = __import__(modname)
        SOURCES.append((name, getattr(mod, funcname)))
    except Exception as e:
        print(f"[{name}] 模块加载失败：{e}")


def collect_events():
    events, status = [], {}
    for name, fn in SOURCES:
        try:
            got = fn()
            events += got
            status[name] = len(got)
        except Exception as e:
            print(f"[{name}] 运行出错：{e}")
            status[name] = "失败"
    if not events:
        print(">>> 三个来源都没拿到数据，改用示例数据生成演示报告。")
        with open("sample_events.json", encoding="utf-8") as f:
            events = json.load(f)
    return events, status


def _event_id(e):
    """活动的稳定身份：优先用链接，没有就用 来源|标题|日期。"""
    url = str(e.get("url") or "")
    if url.startswith("http"):
        return url
    return f"{e.get('source')}|{e.get('title')}|{e.get('date')}"


def load_seen():
    if not os.path.exists(SEEN_FILE):
        return {}
    try:
        with open(SEEN_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=0)


def apply_memory(events, today):
    """用历史名单标记每个活动真正的首次发现日期。"""
    seen = load_seen()
    new_count = 0
    for e in events:
        eid = _event_id(e)
        if eid in seen:
            e["date_added"] = seen[eid]          # 以前见过：沿用首次日期
        else:
            e["date_added"] = today              # 第一次见：今天才是新发现
            seen[eid] = today
            new_count += 1
    save_seen(seen)
    first_run = new_count == len(events) and len(events) > 0
    print(f"[记忆] 名单里新增 {new_count} 个活动"
          + ("（首次运行，全部算新，属正常）" if first_run else ""))
    return events


def main():
    today = date.today().isoformat()
    events, status = collect_events()
    events = apply_memory(events, today)
    scored = score_all(events)
    html_out = build_report(scored, today=today)
    with open("report.html", "w", encoding="utf-8") as f:
        f.write(html_out)
    print("各来源结果：", status)
    print(f"完成！共处理 {len(scored)} 个活动，已生成 report.html")


if __name__ == "__main__":
    main()
