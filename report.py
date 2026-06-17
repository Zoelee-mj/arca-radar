"""Report builder (English, sectioned, collapsible)."""
import html
from datetime import date

TAG_COLORS = {
    "Agents": ("#EEEDFE", "#3C3489"), "AI Coding": ("#E1F5EE", "#085041"),
    "MCP": ("#EEEDFE", "#3C3489"), "DevTools": ("#E6F1FB", "#0C447C"),
    "Infra": ("#FAEEDA", "#854F0B"), "LLM Eng": ("#FBEAF0", "#72243E"),
    "Open Source": ("#EAF3DE", "#27500A"), "Hackathon": ("#FAECE7", "#712B13"),
    "Builders": ("#E6F1FB", "#0C447C"), "Automation": ("#E1F5EE", "#085041"),
}
PRIORITY_STYLE = {"高": ("#E1F5EE", "#085041", "High"), "中": ("#FAEEDA", "#854F0B", "Medium"),
                  "跳过": ("#F1EFE8", "#888780", "Skip")}
STATUS_STYLE = {
    "open": ("Open", "#E1F5EE", "#085041"), "live": ("Live", "#E1F5EE", "#085041"),
    "ongoing": ("Live", "#E1F5EE", "#085041"), "upcoming": ("Upcoming", "#FAEEDA", "#854F0B"),
    "ended": ("Ended", "#F1EFE8", "#888780"),
}
TOPIC_BG = ("#EEEDFE", "#3C3489")
TOP_N = 10


def _esc(s):
    return html.escape(str(s)) if s not in (None, "") else "—"

def _num(n):
    return f"{int(n):,}" if isinstance(n, (int, float)) else "—"

def _topic_pills(topics):
    if not topics:
        return "—"
    return "".join(f'<span class="pill" style="background:{TOPIC_BG[0]};color:{TOPIC_BG[1]}">{_esc(t)}</span>'
                   for t in topics)

def _priority_badge(p):
    bg, fg, label = PRIORITY_STYLE.get(p, ("#F1EFE8", "#888780", "Skip"))
    return f'<span class="badge" style="background:{bg};color:{fg}">{label}</span>'

def _status_badge(s):
    label, bg, fg = STATUS_STYLE.get((s or "upcoming").lower(), ("Upcoming", "#FAEEDA", "#854F0B"))
    return f'<span class="badge" style="background:{bg};color:{fg}">{label}</span>'

def _reward(e):
    return _esc(e.get("prize"))


def _hack_row(e, today, show_new):
    is_new = "new" if (show_new and e.get("date_added") == today) else ""
    nt = '<span class="newtag">NEW</span>' if is_new else ""
    return f"""<tr class="{is_new}">
      <td class="t-name"><a href="{_esc(e['url'])}" target="_blank">{_esc(e['title'])}</a>{nt}
        <div class="t-loc">{_esc(e.get('location'))}</div></td>
      <td class="muted">{_esc(e['source'])}</td>
      <td>{_esc(e.get('host'))}</td>
      <td class="muted nowrap">{_esc(e.get('date'))}</td>
      <td>{_status_badge(e.get('status'))}</td>
      <td class="muted">{_num(e.get('registrations'))}</td>
      <td class="muted">{_reward(e)}</td>
      <td><div class="t-tags">{_topic_pills(e.get('topics'))}</div></td>
      <td class="score">{e['score']}</td>
      <td>{_priority_badge(e['priority'])}</td>
    </tr>"""


def _luma_row(e, today, show_new):
    is_new = "new" if (show_new and e.get("date_added") == today) else ""
    nt = '<span class="newtag">NEW</span>' if is_new else ""
    return f"""<tr class="{is_new}">
      <td class="t-name"><a href="{_esc(e['url'])}" target="_blank">{_esc(e['title'])}</a>{nt}
        <div class="t-loc">{_esc(e.get('location'))}</div></td>
      <td class="muted">{_esc(e['source'])}</td>
      <td>{_esc(e.get('host'))}</td>
      <td class="muted nowrap">{_esc(e.get('date'))}</td>
      <td>{_status_badge(e.get('status'))}</td>
      <td class="muted">{_esc(e.get('event_type'))}</td>
      <td class="muted">{_num(e.get('registrations'))}</td>
      <td class="score">{e['score']}</td>
      <td>{_priority_badge(e['priority'])}</td>
    </tr>"""


def _collapsible_table(events, head_html, row_fn, today, show_new=True):
    if not events:
        return '<p class="empty">No events in this section.</p>'
    first = events[:TOP_N]
    rest = events[TOP_N:]
    rows_first = "".join(row_fn(e, today, show_new) for e in first)
    block = f'<div class="table-wrap"><table>{head_html}<tbody>{rows_first}'
    if rest:
        rows_rest = "".join(row_fn(e, today, show_new) for e in rest)
        block += f'</tbody></table></div>'
        block += (f'<details class="more"><summary>Show all {len(events)} '
                  f'(+{len(rest)} more)</summary>'
                  f'<div class="table-wrap"><table>{head_html}<tbody>{rows_rest}</tbody></table></div></details>')
    else:
        block += '</tbody></table></div>'
    return block


HACK_HEAD = """<thead><tr>
  <th>Activity</th><th>Source</th><th>Organizer</th><th>Date</th><th>Status</th>
  <th>Registrations</th><th>Reward</th><th>Topics</th><th>ARCA Score</th><th>Priority</th>
</tr></thead>"""

LUMA_HEAD = """<thead><tr>
  <th>Activity</th><th>Source</th><th>Organizer / Cohost</th><th>Date</th><th>Status</th>
  <th>Type</th><th>Registrations</th><th>ARCA Score</th><th>Priority</th>
</tr></thead>"""


def build_report(scored_events, today=None):
    today = today or date.today().isoformat()
    ended = [e for e in scored_events if (e.get("status") or "").lower() == "ended"]
    active = [e for e in scored_events if (e.get("status") or "").lower() != "ended"]
    hackathons = sorted([e for e in active if e.get("track") == "hackathon"],
                        key=lambda x: x["score"], reverse=True)
    meetups = sorted([e for e in active if e.get("track") != "hackathon"],
                     key=lambda x: x["score"], reverse=True)
    ended = sorted(ended, key=lambda x: x.get("date", ""), reverse=True)
    new_today = [e for e in active if e.get("date_added") == today and e["priority"] != "跳过"]

    total = len(scored_events)
    high = sum(1 for e in active if e["priority"] == "高")

    new_cards = ""
    for e in sorted(new_today, key=lambda x: x["score"], reverse=True):
        reward = f'<div class="card-prize">🏆 {_esc(e.get("prize"))}</div>' if e.get("prize") else ""
        cls = "Hackathon" if e.get("track") == "hackathon" else "Event"
        new_cards += f"""<div class="card">
          <div class="card-top"><span class="card-title">{_esc(e['title'])}</span><span class="card-score">{e['score']}</span></div>
          <div class="card-meta">{cls} · {_esc(e['source'])} · {_esc(e.get('date'))} · {_esc(e.get('location'))}</div>
          <div class="card-host">Organizer: {_esc(e.get('host'))}　Reg {_num(e.get('registrations'))}</div>
          {reward}
          <a class="card-link" href="{_esc(e['url'])}" target="_blank">View event &rarr;</a>
        </div>"""
    if not new_cards:
        new_cards = '<p class="empty">No new high-priority events discovered today. Check back tomorrow.</p>'

    return TEMPLATE.format(
        today=_esc(today), total=total, high=high,
        hack_count=len(hackathons), meet_count=len(meetups), ended_count=len(ended),
        new_count=len(new_today), new_cards=new_cards,
        hack_table=_collapsible_table(hackathons, HACK_HEAD, _hack_row, today),
        luma_table=_collapsible_table(meetups, LUMA_HEAD, _luma_row, today),
        ended_table=_collapsible_table(ended, HACK_HEAD, _hack_row, today, show_new=False),
    )


TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ARCA Event Radar · {today}</title>
<style>
  :root {{ --bg:#faf9f5; --surface:#fff; --line:rgba(0,0,0,0.10);
    --text:#1d1c1a; --muted:#6b6a65; --faint:#9b9a94; --info:#185fa5; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--text);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif;
    line-height:1.6; -webkit-font-smoothing:antialiased; }}
  .wrap {{ max-width:1240px; margin:0 auto; padding:40px 24px 80px; }}
  .head {{ display:flex; align-items:center; gap:10px; }}
  .head h1 {{ font-size:24px; font-weight:600; margin:0; }}
  .sub {{ color:var(--muted); font-size:13px; margin:4px 0 28px; }}
  .stats {{ display:grid; grid-template-columns:repeat(5,1fr); gap:12px; margin-bottom:36px; }}
  @media(max-width:680px){{ .stats{{grid-template-columns:repeat(2,1fr);}} }}
  .stat {{ background:#f1efe8; border-radius:10px; padding:14px; }}
  .stat .label {{ font-size:12px; color:var(--muted); }}
  .stat .num {{ font-size:24px; font-weight:600; margin-top:2px; }}
  .num.green {{ color:#0f6e56; }} .num.info {{ color:var(--info); }} .num.faint {{ color:var(--faint); }}
  .sec {{ font-size:17px; font-weight:600; margin:34px 0 6px; }}
  .sec-desc {{ font-size:12px; color:var(--muted); margin:0 0 14px; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:14px; margin-bottom:10px; }}
  .card {{ background:var(--surface); border:1px solid var(--line); border-radius:12px; padding:16px 18px; }}
  .card-top {{ display:flex; justify-content:space-between; gap:8px; align-items:start; }}
  .card-title {{ font-size:15px; font-weight:600; }}
  .card-score {{ font-size:13px; font-weight:600; color:#0f6e56; }}
  .card-meta {{ font-size:12px; color:var(--muted); margin:6px 0 4px; }}
  .card-host {{ font-size:12px; color:var(--text); margin-bottom:6px; }}
  .card-prize {{ font-size:12px; color:#854f0b; margin-bottom:8px; }}
  .pill {{ font-size:11px; padding:2px 8px; border-radius:7px; margin:0 4px 4px 0; display:inline-block; }}
  .card-link {{ display:inline-block; margin-top:10px; font-size:13px; color:var(--info); text-decoration:none; }}
  .empty {{ color:var(--muted); font-size:14px; background:var(--surface); border:1px dashed var(--line); border-radius:12px; padding:18px; }}
  .table-wrap {{ background:var(--surface); border:1px solid var(--line); border-radius:12px; overflow-x:auto; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; min-width:980px; }}
  thead tr {{ background:#f1efe8; color:var(--muted); text-align:left; }}
  th {{ padding:11px 12px; font-weight:500; white-space:nowrap; }}
  td {{ padding:12px; border-top:1px solid var(--line); vertical-align:top; }}
  tr.new {{ background:#fbfdf4; }}
  .t-name a {{ color:var(--text); font-weight:600; text-decoration:none; }}
  .t-name a:hover {{ color:var(--info); }}
  .t-loc {{ font-size:11px; color:var(--faint); margin-top:2px; }}
  .t-tags {{ max-width:200px; }}
  .newtag {{ font-size:10px; font-weight:700; color:#0f6e56; background:#e1f5ee; padding:1px 6px; border-radius:6px; margin-left:8px; }}
  .muted {{ color:var(--muted); }} .nowrap {{ white-space:nowrap; }}
  .score {{ font-weight:600; }}
  .badge {{ font-size:11px; padding:2px 10px; border-radius:8px; white-space:nowrap; }}
  details.more {{ margin-top:8px; }}
  details.more summary {{ cursor:pointer; color:var(--info); font-size:13px; padding:8px 0; font-weight:500; }}
  .foot {{ color:var(--faint); font-size:12px; margin-top:26px; }}
</style></head>
<body><div class="wrap">
  <div class="head"><span style="font-size:22px;">&#128225;</span><h1>ARCA Event Radar</h1></div>
  <div class="sub">Sources: Luma + lablab + Devpost · Auto-scored by ARCA criteria · Generated {today}</div>
  <div class="stats">
    <div class="stat"><div class="label">Total events</div><div class="num">{total}</div></div>
    <div class="stat"><div class="label">High priority</div><div class="num green">{high}</div></div>
    <div class="stat"><div class="label">Hackathons (active)</div><div class="num">{hack_count}</div></div>
    <div class="stat"><div class="label">Luma events</div><div class="num">{meet_count}</div></div>
    <div class="stat"><div class="label">Ended</div><div class="num faint">{ended_count}</div></div>
  </div>

  <div class="sec">&#128293; Discovered Today · Worth Attention</div>
  <div class="sec-desc">Events first seen today with high/medium priority</div>
  <div class="cards">{new_cards}</div>

  <div class="sec">&#127942; Hackathons (Devpost + lablab)</div>
  <div class="sec-desc">Scored by topics + reward + registrations · newest first · showing top 10</div>
  {hack_table}

  <div class="sec">&#129309; Luma Events</div>
  <div class="sec-desc">Meetup / Workshop / Hackathon · scored by topics + format · showing top 10</div>
  {luma_table}

  <div class="sec">&#128451; Ended</div>
  <div class="sec-desc">Past events, for reference</div>
  <details class="more"><summary>Show {ended_count} ended events</summary>{ended_table}</details>

  <div class="foot">Auto-regenerated daily. Registrations count toward scoring for hackathons only.</div>
</div></body></html>"""
