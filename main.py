"""
ARCA 活动雷达 · 主程序
运行：python main.py
流程：抓 Luma + lablab + Devpost → ARCA 打分 → 生成 report.html
任一来源失败都会跳过并继续，保证一定能出报告。
"""
import json
from datetime import date
from scorer import score_all
from report import build_report

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


def main():
    events, status = collect_events()
    scored = score_all(events)
    html_out = build_report(scored, today=date.today().isoformat())
    with open("report.html", "w", encoding="utf-8") as f:
        f.write(html_out)
    print("各来源结果：", status)
    print(f"完成！共处理 {len(scored)} 个活动，已生成 report.html")


if __name__ == "__main__":
    main()
