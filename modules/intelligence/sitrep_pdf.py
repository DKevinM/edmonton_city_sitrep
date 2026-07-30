import base64

from weasyprint import HTML

from core.aqhi import eccc_messages
from core.timefmt import format_long, format_short, tz_abbrev
from core.config import ROOT
from modules.weather.codes import label as weather_label

ASSETS = ROOT / 'assets'
LIVE_MAP_URL = 'https://dkevinm.github.io/LiveMap/ACA.html'

RISK_LABEL = {'LOW': 'Low Risk', 'MODERATE': 'Moderate Risk', 'HIGH': 'High Risk', 'EXTREME': 'Very High Risk', 'UNKNOWN': 'Unavailable'}

# Matches the official AEPA/ACA AQHI colour scale used at
# https://dkevinm.github.io/ACA_AQHI/ (getAQHIColor) and the LiveMap legend.
AQHI_VALUE_COLOR = {1: '#01cbff', 2: '#0099cb', 3: '#016797', 4: '#fffe03', 5: '#ffcb00', 6: '#ff9835', 7: '#fd6866', 8: '#fe0002', 9: '#cc0001', 10: '#9a0100'}
AQHI_ABOVE_10_COLOR = '#640100'
AQHI_UNAVAILABLE_COLOR = '#adb5bd'

AQHI_SCALE = [(1, '#01cbff'), (2, '#0099cb'), (3, '#016797'), (4, '#fffe03'), (5, '#ffcb00'), (6, '#ff9835'), (7, '#fd6866'), (8, '#fe0002'), (9, '#cc0001'), (10, '#9a0100'), ('10+', AQHI_ABOVE_10_COLOR)]
AQHI_SCALE_BANDS = [('Low Risk', 3, '#016797'), ('Moderate Risk', 3, '#c98f00'), ('High Risk', 4, '#c81f1f'), ('Very High Risk', 1, AQHI_ABOVE_10_COLOR)]


def _aqhi_color(v):
    if v is None:
        return AQHI_UNAVAILABLE_COLOR
    try:
        n = float(v)
    except (TypeError, ValueError):
        return AQHI_UNAVAILABLE_COLOR
    if n > 10:
        return AQHI_ABOVE_10_COLOR
    return AQHI_VALUE_COLOR.get(round(n), AQHI_UNAVAILABLE_COLOR)


def _fmt_aqhi(v):
    if v is None:
        return '—'
    try:
        n = float(v)
    except (TypeError, ValueError):
        return str(v)
    return '10+' if n > 10 else (str(int(n)) if n == int(n) else f'{n:.1f}')


def _fmt_forecast(v):
    if v in (None, '', 'N/A', 'None'):
        return '—'
    return _fmt_aqhi(v)


def _b64(path):
    return base64.b64encode(path.read_bytes()).decode('ascii')


def _v(x, suffix=''):
    return '—' if x is None else f'{x}{suffix}'


AQHI_SCALE_DARK_BG = {7, 8, 9, 10, '10+'}


def _aqhi_scale_bar():
    cells = ''.join(f"<div class='aqhi-cell' style='background:{color};color:{'#fff' if n in AQHI_SCALE_DARK_BG else '#1a2733'}'>{n}</div>" for n, color in AQHI_SCALE)
    bands = ''.join(f"<div class='aqhi-band' style='flex:{span};color:{color}'>{label}</div>" for label, span, color in AQHI_SCALE_BANDS)
    return f"<div class='aqhi-scale'><div class='aqhi-cells'>{cells}</div><div class='aqhi-bands'>{bands}</div></div>"


def render_html(cfg, communities, wx_alerts, smoke_bullets, weather, weather_bullets, snapshots, generated_at):
    tz = cfg['project'].get('timezone', 'America/Edmonton')

    edmonton = next((c for c in communities if c['name'] == 'Edmonton'), communities[0])
    known_risk = [c['risk'] for c in communities if c['risk'] != 'UNKNOWN']
    overall_risk = max(known_risk, key=lambda r: {'LOW': 0, 'MODERATE': 1, 'HIGH': 2, 'EXTREME': 3}[r]) if known_risk else 'UNKNOWN'

    if edmonton.get('general_message') and edmonton.get('at_risk_message'):
        msgs = {'general': edmonton['general_message'], 'at_risk': edmonton['at_risk_message']}
    else:
        msgs = eccc_messages(edmonton['risk']) or eccc_messages('LOW')

    logo_b64 = _b64(ASSETS / 'aca_logo.jpg')

    community_rows = ''
    for c in communities:
        if c['status'] != 'ok':
            community_rows += f"<tr><td>{c['name']}</td><td colspan='5' style='color:#6c757d'>data unavailable</td></tr>"
            continue
        community_rows += (
            f"<tr><td>{c['name']}</td>"
            f"<td style='background:{_aqhi_color(c.get('aqhi'))};color:#fff;font-weight:bold;text-align:center'>{_fmt_aqhi(c.get('aqhi'))}</td>"
            f"<td style='font-size:9.5px'>{c.get('reading_date', '—')}</td>"
            f"<td style='background:{_aqhi_color(c.get('forecast_today')) if c.get('forecast_today') not in (None, 'N/A', 'None') else '#fff'};text-align:center'>{_fmt_forecast(c.get('forecast_today'))}</td>"
            f"<td style='background:{_aqhi_color(c.get('forecast_tonight')) if c.get('forecast_tonight') not in (None, 'N/A', 'None') else '#fff'};text-align:center'>{_fmt_forecast(c.get('forecast_tonight'))}</td>"
            f"<td style='background:{_aqhi_color(c.get('forecast_tomorrow')) if c.get('forecast_tomorrow') not in (None, 'N/A', 'None') else '#fff'};text-align:center'>{_fmt_forecast(c.get('forecast_tomorrow'))}</td></tr>"
        )

    if wx_alerts:
        wx_html = ''.join(f"<div class='alert'><b>{x.get('name', '').title()}</b> — {x.get('region', '')}</div>" for x in wx_alerts)
        wx_section = f"<section class='panel alertbox'><h2>Active Environment Canada Alerts</h2>{wx_html}</section>"
    else:
        wx_section = "<section class='panel okbox'><p>No active Environment Canada weather alerts for the Edmonton region.</p></section>"

    smoke_items = ''.join(f'<li>{b}</li>' for b in smoke_bullets)
    firesmoke_img = f"<a href='{LIVE_MAP_URL}'><img class='snapfig' src='data:image/png;base64,{_b64(snapshots['firesmoke_path'])}'/></a>" if snapshots.get('firesmoke_path') else "<p style='color:#6c757d;font-size:10px'>Live smoke map snapshot unavailable for this run.</p>"
    livemap_img = f"<a href='{LIVE_MAP_URL}'><img class='snapfig' src='data:image/png;base64,{_b64(snapshots['livemap_path'])}'/></a>" if snapshots.get('livemap_path') else "<p style='color:#6c757d;font-size:10px'>Live map snapshot unavailable for this run.</p>"

    weather_items = ''.join(f'<li>{b}</li>' for b in weather_bullets)
    tzab = tz_abbrev(tz)
    wx_rows = ''
    for r in (weather.get('hourly') or [])[:6]:
        wx_rows += (
            f"<tr><td>{_v(format_short(r.get('time'), tz))}</td>"
            f"<td>{_v(r.get('temperature_c'), '°C')}</td>"
            f"<td>{_v(r.get('precipitation_probability_pct'), '%')}</td>"
            f"<td>{_v(r.get('precipitation_mm'), ' mm')}</td>"
            f"<td>{_v(r.get('wind_gust_kmh'), ' km/h')}</td>"
            f"<td>{_v(weather_label(r.get('weather_code')))}</td></tr>"
        )

    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
@page {{ size: Letter; margin: 15mm 16mm; }}
body {{ font-family: Arial, Helvetica, sans-serif; color:#1a2733; font-size:11.5px; }}
h1 {{ font-size:20px; margin:0 0 2px; color:#0f6cbd; }}
h2 {{ font-size:13.5px; margin:0 0 8px; color:#0f6cbd; border-bottom:2px solid #0f6cbd; padding-bottom:3px; }}
header {{ display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:10px; }}
header .title {{ flex:1; margin-left:16px; }}
header img.logo {{ height:52px; }}
header .meta {{ text-align:right; font-size:12px; color:#4a5a68; }}
section.panel {{ margin-bottom:11px; }}
.current-aqhi {{ display:flex; align-items:center; gap:16px; background:#f2f6fa; border-radius:8px; padding:10px 14px; margin-bottom:8px; }}
.current-aqhi .big {{ font-size:34px; font-weight:bold; color:{_aqhi_color(edmonton.get('aqhi'))}; }}
.current-aqhi .lbl {{ font-size:11px; color:#4a5a68; }}
table.msg, table.detail, table.comm, table.wx {{ width:100%; border-collapse:collapse; font-size:10.5px; margin-bottom:2px;}}
table.msg th, table.msg td, table.detail th, table.detail td, table.comm th, table.comm td, table.wx th, table.wx td {{ border:1px solid #c6d2dc; padding:6px 8px; text-align:left; vertical-align:top; }}
table.msg th, table.detail th, table.comm th, table.wx th {{ background:#eaf1f8; }}
table.msg tr.active td {{ background:#fff3cd; font-weight:bold; }}
table.detail {{ margin-bottom:10px; }}
.alertbox {{ border:1.5px solid #e8590c; border-radius:6px; padding:8px 10px; }}
.alertbox h2 {{ border-color:#e8590c; color:#e8590c; }}
.okbox {{ border:1.5px solid #2f9e44; border-radius:6px; padding:8px 10px; color:#2f9e44; }}
.alert {{ margin-bottom:4px; }}
.aqhi-scale {{ margin-top:2px; margin-bottom:10px; }}
.aqhi-cells {{ display:flex; }}
.aqhi-cell {{ flex:1; text-align:center; color:#1a2733; font-size:10px; font-weight:bold; padding:4px 0; }}
.aqhi-bands {{ display:flex; margin-top:2px; }}
.aqhi-band {{ text-align:center; font-size:8.5px; font-weight:bold; }}
ul {{ margin:4px 0 0; padding-left:16px; }}
li {{ margin-bottom:3px; }}
.snaprow {{ display:flex; justify-content:center; margin-top:6px; }}
.snapfig {{ max-width:60%; border-radius:8px; display:block; }}
.snapcaption {{ text-align:center; font-size:9px; color:#4a5a68; margin-top:3px; }}
a {{ text-decoration:none; color:inherit; }}
footer {{ border-top:1px solid #c6d2dc; padding-top:5px; margin-top:4px; font-size:9.5px; color:#4a5a68; }}
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
  </div>
</header>

<section class="panel">
  <h2>Air Quality Health Index (AQHI) — Edmonton</h2>
  <div class="current-aqhi">
    <div class="big">{_fmt_aqhi(edmonton.get('aqhi'))}</div>
    <div>
      <div class="lbl">Current AQHI</div>
    </div>
  </div>
  {_aqhi_scale_bar()}
  <table class="detail">
    <tr><th>Reading Date/Time</th><th>Current AQHI</th><th>Forecast Today</th><th>Forecast Tonight</th><th>Forecast Tomorrow</th></tr>
    <tr>
      <td>{_v(edmonton.get('reading_date'))}</td>
      <td style="background:{_aqhi_color(edmonton.get('aqhi'))};color:#fff;font-weight:bold;text-align:center">{_fmt_aqhi(edmonton.get('aqhi'))}</td>
      <td style="text-align:center">{_fmt_forecast(edmonton.get('forecast_today'))}</td>
      <td style="text-align:center">{_fmt_forecast(edmonton.get('forecast_tonight'))}</td>
      <td style="text-align:center">{_fmt_forecast(edmonton.get('forecast_tomorrow'))}</td>
    </tr>
  </table>
  <table class="msg">
    <tr><th>Health Risk</th><th>AQHI</th><th>At-Risk Population</th><th>General Population</th></tr>
    <tr class="active"><td>{RISK_LABEL.get(edmonton['risk'], edmonton['risk'])}</td><td>{_fmt_aqhi(edmonton.get('aqhi'))}</td><td>{msgs['at_risk']}</td><td>{msgs['general']}</td></tr>
  </table>
</section>

{wx_section}

<section class="panel">
  <h2>Wildfire Smoke</h2>
  <ul>{smoke_items}</ul>
  <div class="snaprow">{firesmoke_img}</div>
  <div class="snapcaption">Click the map to open the live interactive version.</div>
</section>

<section class="panel">
  <h2>AQHI by Community — Overall Regional Risk: {RISK_LABEL.get(overall_risk, overall_risk)}</h2>
  <table class="comm">
    <tr><th>Community</th><th>Current AQHI</th><th>Last Updated</th><th>Forecast Today</th><th>Forecast Tonight</th><th>Forecast Tomorrow</th></tr>
    {community_rows}
  </table>
</section>

<section class="panel">
  <h2>Weather Forecast <small style="font-weight:normal">(next 6 hours, {tzab})</small></h2>
  <ul>{weather_items}</ul>
  <table class="wx">
    <tr><th>Time</th><th>Temp</th><th>Precip chance</th><th>Precip</th><th>Gust</th><th>Sky</th></tr>
    {wx_rows}
  </table>
</section>

<section class="panel">
  <h2>Edmonton AQHI Map</h2>
  <div class="snaprow">{livemap_img}</div>
  <div class="snapcaption">Click the map to open the live interactive version.</div>
</section>

<footer>
  Prepared by Alberta Capital Airshed. Beta decision-support product. For the live interactive map, visit {LIVE_MAP_URL}
</footer>
</body></html>'''


def build_pdf(cfg, communities, wx_alerts, smoke_bullets, weather, weather_bullets, snapshots, generated_at, out_path):
    html = render_html(cfg, communities, wx_alerts, smoke_bullets, weather, weather_bullets, snapshots, generated_at)
    HTML(string=html, base_url=str(ROOT)).write_pdf(out_path)
    return out_path
