"""出图器（含主办方/Sponsor、报名人数、奖金、阶段 四个新列）"""
import html
from datetime import date

TAG_COLORS = {
    "Agents": ("#EEEDFE", "#3C3489"), "AI Coding": ("#E1F5EE", "#085041"),
    "MCP": ("#EEEDFE", "#3C3489"), "DevTools": ("#E6F1FB", "#0C447C"),
    "Infra": ("#FAEEDA", "#854F0B"), "LLM Eng": ("#FBEAF0", "#72243E"),
    "Open Source": ("#EAF3DE", "#27500A"), "Hackathon": ("#FAECE7", "#712B13"),
    "Builders": ("#E6F1FB", "#0C447C"), "Automation": ("#E1F5EE", "#085041"),
}
PRIORITY_STYLE = {"高": ("#E1F5EE", "#085041", "●"), "中": ("#FAEEDA", "#854F0B", "●"),
                  "跳过": ("#F1EFE8", "#888780", "○")}
STATUS_STYLE = {
    "open": ("报名中", "#E1F5EE", "#085041"), "live": ("进行中", "#E1F5EE", "#085041"),
    "ongoing": ("进行中", "#E1F5EE", "#085041"), "upcoming": ("即将开始", "#FAEEDA", "#854F0B"),
    "ended": ("已结束", "#F1EFE8", "#888780"),
}

def _esc(s):
    return html.escape(str(s)) if s not in (None, "") else "—"

def _num(n):
    return f"{int(n):,}" if isinstance(n, (int, float)) else "—"

def _tag_pills(tags):
    out = []
    for t in tags:
        bg, fg = TAG_COLORS.get(t, ("#F1EFE8", "#444441"))
        out.append(f'<span class="pill" style="background:{bg};color:{fg}">{_esc(t)}</span>')
    return "".join(out)

def _priority_badge(p):
    bg, fg, dot = PRIORITY_STYLE.get(p, ("#F1EFE8", "#888780", "○"))
    return f'<span class="badge" style="background:{bg};color:{fg}">{dot} {_esc(p)}</span>'

def _status_badge(s):
    label, bg, fg = STATUS_STYLE.get((s or "upcoming").lower(), ("即将开始", "#FAEEDA", "#854F0B"))
    return f'<span class="badge" style="background:{bg};color:{fg}">{label}</span>'

def build_report(scored_events, today=None):
    today = today or date.today().isoformat()
    total = len(scored_events)
    high = sum(1 for e in scored_events if e["priority"] == "高")
    skipped = sum(1 for e in scored_events if e["priority"] == "跳过")
    new_today = [e for e in scored_events if e.get("date_added") == today and e["priority"] != "跳过"]

    new_cards = ""
    for e in sorted(new_today, key=lambda x: x["score"], reverse=True):
        prize_line = f'<div class="card-prize">🏆 {_esc(e.get("prize"))}</div>' if e.get("prize") else ""
        new_cards += f"""
        <div class="card">
          <div class="card-top"><span class="card-title">{_esc(e['title'])}</span><span class="card-score">{e['score']}</span></div>
          <div class="card-meta">{_esc(e['source'])} · {_esc(e.get('date'))} · {_esc(e.get('location'))} · {_esc(e.get('event_type'))}</div>
          <div class="card-host">主办：{_esc(e.get('host'))}　报名 {_num(e.get('registrations'))}</div>
          {prize_line}
          <div class="pills">{_tag_pills(e['tags'])}</div>
          <a class="card-link" href="{_esc(e['url'])}" target="_blank">查看活动 &rarr;</a>
        </div>"""
    if not new_cards:
        new_cards = '<p class="empty">今天暂时没有新的高优先级活动。明天再来看看。</p>'

    rows = ""
    ordered = sorted(scored_events, key=lambda x: (x.get("date_added", ""), x["score"]), reverse=True)
    for e in ordered:
        is_new = "new" if e.get("date_added") == today else ""
        new_tag = '<span class="newtag">NEW</span>' if is_new else ""
        rows += f"""
        <tr class="{is_new}">
          <td class="t-name"><a href="{_esc(e['url'])}" target="_blank">{_esc(e['title'])}</a>{new_tag}
            <div class="t-loc">{_esc(e.get('location'))}</div>
            <div class="t-tags">{_tag_pills(e['tags'])}</div></td>
          <td class="muted">{_esc(e['source'])}</td>
          <td>{_esc(e.get('host'))}</td>
          <td class="muted nowrap">{_esc(e.get('date'))}</td>
          <td>{_status_badge(e.get('status'))}</td>
          <td class="muted">{_esc(e.get('event_type'))}</td>
          <td class="muted">{_num(e.get('registrations'))}</td>
          <td class="muted">{_esc(e.get('prize'))}</td>
          <td class="score">{e['score']}</td>
          <td>{_priority_badge(e['priority'])}</td>
        </tr>"""

    return TEMPLATE.format(today=_esc(today), total=total, high=high,
                           new_count=len(new_today), skipped=skipped,
                           new_cards=new_cards, rows=rows)

TEMPLATE = """<!DOCTYPE html>
<html lang="zh"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ARCA 活动雷达 · {today}</title>
<style>
  :root {{ --bg:#faf9f5; --surface:#fff; --line:rgba(0,0,0,0.10);
    --text:#1d1c1a; --muted:#6b6a65; --faint:#9b9a94; --info:#185fa5; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--text);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
    line-height:1.6; -webkit-font-smoothing:antialiased; }}
  .wrap {{ max-width:1200px; margin:0 auto; padding:40px 24px 80px; }}
  .head {{ display:flex; align-items:center; gap:10px; }}
  .head h1 {{ font-size:24px; font-weight:600; margin:0; }}
  .sub {{ color:var(--muted); font-size:13px; margin:4px 0 28px; }}
  .stats {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:36px; }}
  @media(max-width:680px){{ .stats{{grid-template-columns:repeat(2,1fr);}} }}
  .stat {{ background:#f1efe8; border-radius:10px; padding:16px; }}
  .stat .label {{ font-size:13px; color:var(--muted); }}
  .stat .num {{ font-size:26px; font-weight:600; margin-top:2px; }}
  .num.green {{ color:#0f6e56; }} .num.info {{ color:var(--info); }} .num.faint {{ color:var(--faint); }}
  .sec {{ font-size:17px; font-weight:600; margin:0 0 14px; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:14px; margin-bottom:40px; }}
  .card {{ background:var(--surface); border:1px solid var(--line); border-radius:12px; padding:16px 18px; }}
  .card-top {{ display:flex; justify-content:space-between; gap:8px; align-items:start; }}
  .card-title {{ font-size:15px; font-weight:600; }}
  .card-score {{ font-size:13px; font-weight:600; color:#0f6e56; }}
  .card-meta {{ font-size:12px; color:var(--muted); margin:6px 0 4px; }}
  .card-host {{ font-size:12px; color:var(--text); margin-bottom:6px; }}
  .card-prize {{ font-size:12px; color:#854f0b; margin-bottom:8px; }}
  .pills {{ display:flex; flex-wrap:wrap; gap:6px; }}
  .pill {{ font-size:11px; padding:2px 9px; border-radius:8px; }}
  .card-link {{ display:inline-block; margin-top:12px; font-size:13px; color:var(--info); text-decoration:none; }}
  .empty {{ color:var(--muted); font-size:14px; background:var(--surface); border:1px dashed var(--line); border-radius:12px; padding:20px; }}
  .table-wrap {{ background:var(--surface); border:1px solid var(--line); border-radius:12px; overflow-x:auto; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; min-width:980px; }}
  thead tr {{ background:#f1efe8; color:var(--muted); text-align:left; }}
  th {{ padding:11px 12px; font-weight:500; white-space:nowrap; }}
  td {{ padding:12px; border-top:1px solid var(--line); vertical-align:top; }}
  tr.new {{ background:#fbfdf4; }}
  .t-name a {{ color:var(--text); font-weight:600; text-decoration:none; }}
  .t-name a:hover {{ color:var(--info); }}
  .t-loc {{ font-size:11px; color:var(--faint); margin-top:2px; }}
  .t-tags {{ display:flex; flex-wrap:wrap; gap:5px; margin-top:6px; }}
  .newtag {{ font-size:10px; font-weight:700; color:#0f6e56; background:#e1f5ee; padding:1px 6px; border-radius:6px; margin-left:8px; }}
  .muted {{ color:var(--muted); }} .nowrap {{ white-space:nowrap; }}
  .score {{ font-weight:600; }}
  .badge {{ font-size:11px; padding:2px 10px; border-radius:8px; white-space:nowrap; }}
  .foot {{ color:var(--faint); font-size:12px; margin-top:22px; }}
</style></head>
<body><div class="wrap">
  <div class="head"><span style="font-size:22px;">&#128225;</span><h1>ARCA 活动雷达</h1></div>
  <div class="sub">数据来源：Luma + lablab + Devpost · 按 ARCA 标准自动打分筛选 · 生成于 {today}</div>
  <div class="stats">
    <div class="stat"><div class="label">收录活动</div><div class="num">{total}</div></div>
    <div class="stat"><div class="label">高优先级</div><div class="num green">{high}</div></div>
    <div class="stat"><div class="label">今日新发现</div><div class="num info">{new_count}</div></div>
    <div class="stat"><div class="label">已过滤掉</div><div class="num faint">{skipped}</div></div>
  </div>
  <div class="sec">&#128293; 今日新发现 · 值得关注</div>
  <div class="cards">{new_cards}</div>
  <div class="sec">&#128203; 全部活动（新增的排在最前面 · 左右可滑动看全部列）</div>
  <div class="table-wrap"><table>
    <thead><tr>
      <th>活动</th><th>来源</th><th>主办方 / Sponsor</th><th>日期</th><th>阶段</th>
      <th>形式</th><th>报名人数</th><th>奖金 / 积分</th><th>ARCA分</th><th>优先级</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table></div>
  <div class="foot">每天自动重新生成。报名人数 / 奖金等字段以数据源公开信息为准，缺失时显示 &mdash;。</div>
</div></body></html>"""
