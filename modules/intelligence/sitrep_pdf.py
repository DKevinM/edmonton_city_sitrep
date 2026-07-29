import base64

from weasyprint import HTML

from core.aqhi import cap as cap_aqhi
from core.aqhi import eccc_messages
from core.timefmt import format_long
from core.config import ROOT

ASSETS = ROOT / 'assets'
LIVE_MAP_URL = 'https://capitalairshed.ca/live-air-data-map/'

RISK_LABEL = {'LOW': 'Low Risk', 'MODERATE': 'Moderate Risk', 'HIGH': 'High Risk', 'EXTREME': 'Very High Risk', 'UNKNOWN': 'Unavailable'}
RISK_COLOR = {'LOW': '#0f6cbd', 'MODERATE': '#e0a800', 'HIGH': '#e8590c', 'EXTREME': '#7d1935', 'UNKNOWN': '#6c757d'}


def _risk(v, thresholds):
    if v is None:
        return 'UNKNOWN'
    if v >= thresholds['extreme']:
        return 'EXTREME'
    if v >= thresholds['high']:
        return 'HIGH'
    if v >= thresholds['moderate']:
        return 'MODERATE'
    return 'LOW'


def _b64(path):
    return base64.b64encode(path.read_bytes()).decode('ascii')


def _v(x, suffix=''):
    return '—' if x is None else f'{x}{suffix}'


def render_html(cfg, communities, wx_alerts, generated_at, contact):
    tz = cfg['project'].get('timezone', 'America/Edmonton')
    t = cfg['thresholds']['aqhi']

    for c in communities:
        c['risk'] = _risk(c.get('aqhi'), t)

    edmonton = next((c for c in communities if c['name'] == 'Edmonton'), communities[0])
    overall_risk = max(communities, key=lambda c: {'LOW': 0, 'MODERATE': 1, 'HIGH': 2, 'EXTREME': 3, 'UNKNOWN': -1}[c['risk']])['risk']
    msgs = eccc_messages(edmonton['risk']) or eccc_messages('LOW')

    logo_b64 = _b64(ASSETS / 'aca_logo.jpg')

    rows = ''
    for c in communities:
        source_note = {
            'station': f"{c.get('station_name', '')} · {_v(c.get('distance_km'), ' km')}",
            'estimate': f"gridded estimate (confidence {c.get('confidence', '—')})",
            'unavailable': 'unavailable',
        }[c['kind']]
        rows += (
            f"<tr><td>{c['name']}</td>"
            f"<td style='color:{RISK_COLOR.get(c['risk'], '#6c757d')};font-weight:bold'>{_v(cap_aqhi(c.get('aqhi')))}</td>"
            f"<td>{_v(cap_aqhi(c.get('plus_3h')))}</td>"
            f"<td style='font-size:9.5px;color:#4a5a68'>{source_note}</td></tr>"
        )

    if wx_alerts:
        wx_html = ''.join(f"<div class='alert'><b>{x.get('name', '').title()}</b> — {x.get('region', '')}</div>" for x in wx_alerts)
        wx_section = f"<section class='panel alertbox'><h2>Active Environment Canada Alerts</h2>{wx_html}</section>"
    else:
        wx_section = "<section class='panel okbox'><p>No active Environment Canada weather alerts for the Edmonton region.</p></section>"

    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
@page {{ size: Letter; margin: 15mm 16mm; }}
body {{ font-family: Arial, Helvetica, sans-serif; color:#1a2733; font-size:11.5px; }}
h1 {{ font-size:20px; margin:0 0 2px; color:#0f6cbd; }}
h2 {{ font-size:13.5px; margin:0 0 8px; color:#0f6cbd; border-bottom:2px solid #0f6cbd; padding-bottom:3px; }}
header {{ display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:10px; }}
header .title {{ flex:1; margin-left:16px; }}
header img.logo {{ height:52px; }}
header .meta {{ text-align:right; font-size:11px; color:#4a5a68; }}
.contact {{ font-size:10px; color:#4a5a68; font-style:italic; margin-top:2px; }}
section.panel {{ margin-bottom:11px; }}
.current-aqhi {{ display:flex; align-items:center; gap:16px; background:#f2f6fa; border-radius:8px; padding:10px 14px; margin-bottom:8px; }}
.current-aqhi .big {{ font-size:34px; font-weight:bold; color:{RISK_COLOR.get(edmonton['risk'], '#0f6cbd')}; }}
.current-aqhi .lbl {{ font-size:11px; color:#4a5a68; }}
table.msg {{ width:100%; border-collapse:collapse; font-size:10.5px; margin-bottom:2px;}}
table.msg th, table.msg td {{ border:1px solid #c6d2dc; padding:6px 8px; text-align:left; vertical-align:top; }}
table.msg th {{ background:#eaf1f8; }}
table.msg tr.active td {{ background:#fff3cd; font-weight:bold; }}
table.comm {{ width:100%; border-collapse:collapse; font-size:11px; }}
table.comm th, table.comm td {{ border:1px solid #c6d2dc; padding:6px 8px; text-align:left; }}
table.comm th {{ background:#eaf1f8; }}
.alertbox {{ border:1.5px solid #e8590c; border-radius:6px; padding:8px 10px; }}
.alertbox h2 {{ border-color:#e8590c; color:#e8590c; }}
.okbox {{ border:1.5px solid #2f9e44; border-radius:6px; padding:8px 10px; color:#2f9e44; }}
.alert {{ margin-bottom:4px; }}
footer {{ border-top:1px solid #c6d2dc; padding-top:8px; margin-top:8px; font-size:9.5px; color:#4a5a68; }}
</style></head>
<body>
<header>
  <img class="logo" src="data:image/jpeg;base64,{logo_b64}"/>
  <div class="title">
    <h1>Air Quality Situation Report</h1>
    <div>City of Edmonton</div>
  </div>
  <div class="meta">
    <div><b>{format_long(generated_at, tz)}</b></div>
    <div class="contact">For more information, contact {contact['name']} at {contact['phone']}</div>
  </div>
</header>

<section class="panel">
  <h2>Air Quality Health Index (AQHI) — Edmonton</h2>
  <div class="current-aqhi">
    <div class="big">{_v(cap_aqhi(edmonton.get('aqhi')))}</div>
    <div>
      <div class="lbl">Current AQHI — City of Edmonton</div>
      <div class="lbl">+3h forecast: <b>{_v(cap_aqhi(edmonton.get('plus_3h')))}</b></div>
    </div>
  </div>
  <table class="msg">
    <tr><th>Health Risk</th><th>AQHI</th><th>At-Risk Population</th><th>General Population</th></tr>
    <tr class="active"><td>{RISK_LABEL.get(edmonton['risk'], edmonton['risk'])}</td><td>{_v(cap_aqhi(edmonton.get('aqhi')))}</td><td>{msgs['at_risk']}</td><td>{msgs['general']}</td></tr>
  </table>
</section>

{wx_section}

<section class="panel">
  <h2>AQHI by Community — Overall Regional Risk: {RISK_LABEL.get(overall_risk, overall_risk)}</h2>
  <table class="comm">
    <tr><th>Community</th><th>Current AQHI</th><th>+3h Forecast</th><th>Source</th></tr>
    {rows}
  </table>
</section>

<footer>
  Prepared by Alberta Capital Airshed. Beta decision-support product — communities without an official AQHI monitor show a gridded estimate blending official and community sensors, noted in the Source column. For the live interactive map, visit {LIVE_MAP_URL}
</footer>
</body></html>'''


def build_pdf(cfg, communities, wx_alerts, generated_at, out_path, contact=None):
    contact = contact or (cfg.get('contact') or {'name': 'Gary Redmond, ACA Executive Director', 'phone': '780.935.4279'})
    html = render_html(cfg, communities, wx_alerts, generated_at, contact)
    HTML(string=html, base_url=str(ROOT)).write_pdf(out_path)
    return out_path
