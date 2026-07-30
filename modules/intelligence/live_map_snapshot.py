from playwright.sync_api import sync_playwright

LIVEMAP_URL = 'https://dkevinm.github.io/LiveMap/ACA.html'
HIDE_CSS = '''
#search-box, #header-right, #clear-btn, .leaflet-control-layers { display: none !important; }
'''

# On load the app auto-enables the wide ACA-region grid; for city-scoped PDF
# maps we turn that off and use the finer Edmonton-only grid instead.
DEFAULT_ON_LAYER = 'AQHI Grid ACA Stations+Sensors'
EDMONTON_AQHI_LAYER = 'AQHI Grid Edmonton Stations+Sensors'
FIRESMOKE_LAYER = 'FireSmoke Now'

# Matches getSmokeColor() in LiveMap's js/render.js — that app renders the
# FireSmoke Now layer with these bands but never shows a legend for them
# (only the AQHI legend is on-screen), so we draw our own to match exactly.
SMOKE_BANDS = [
    ('< 1', '#f2e8b3'), ('1–9.9', '#e8c95c'), ('10–27.9', '#f5a623'),
    ('28–59.9', '#f57c00'), ('60–119.9', '#cc5500'), ('120+', '#662200'),
]

_LEGEND_JS = '''(bands) => {
  const div = document.createElement('div');
  div.style.cssText = 'position:absolute;left:10px;bottom:10px;z-index:1000;background:#fff;padding:8px 10px;border-radius:4px;box-shadow:0 1px 5px rgba(0,0,0,0.4);font:12px Arial,sans-serif;color:#333;';
  let html = '<div style="font-weight:bold;margin-bottom:4px">Smoke PM2.5 (µg/m³)</div>';
  for (const [label, color] of bands) {
    html += `<div style="display:flex;align-items:center;margin-bottom:2px"><span style="width:14px;height:14px;background:${color};display:inline-block;margin-right:6px;border:1px solid #0002"></span>${label}</div>`;
  }
  div.innerHTML = html;
  div.id = '__smoke_legend';
  document.getElementById('app').appendChild(div);
}'''


def _capture(page, path, center, zoom, toggle_off=(), toggle_on=(), add_smoke_legend=False):
    page.goto(LIVEMAP_URL, wait_until='networkidle', timeout=45000)
    page.wait_for_timeout(3500)
    page.evaluate('([lat, lon, z]) => window.map.setView([lat, lon], z)', [center[0], center[1], zoom])
    page.wait_for_timeout(500)
    for label in toggle_off:
        page.get_by_text(label, exact=True).click()
        page.wait_for_timeout(1500)
    for label in toggle_on:
        page.get_by_text(label, exact=True).click()
        page.wait_for_timeout(2500)
    page.evaluate('() => { if (window.clearSelection) window.clearSelection(); }')
    page.mouse.move(2, 2)
    page.wait_for_timeout(500)
    page.add_style_tag(content=HIDE_CSS)
    if add_smoke_legend:
        page.evaluate(_LEGEND_JS, SMOKE_BANDS)
    page.wait_for_timeout(300)
    page.screenshot(path=str(path))


def capture_snapshots(city, out_dir, zoom=11):
    center = (float(city['latitude']), float(city['longitude']))
    aqhi_path = out_dir / 'livemap_snapshot.png'
    firesmoke_path = out_dir / 'firesmoke_snapshot.png'
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1000, 'height': 700})
        try:
            _capture(page, aqhi_path, center, zoom, toggle_off=[DEFAULT_ON_LAYER], toggle_on=[EDMONTON_AQHI_LAYER])
            _capture(page, firesmoke_path, center, zoom, toggle_off=[DEFAULT_ON_LAYER], toggle_on=[FIRESMOKE_LAYER], add_smoke_legend=True)
            status = 'ok'
        except Exception as ex:
            status = f'error: {type(ex).__name__}: {ex}'
        finally:
            browser.close()
    return {
        'status': status,
        'livemap_path': aqhi_path if aqhi_path.exists() else None,
        'firesmoke_path': firesmoke_path if firesmoke_path.exists() else None,
    }
