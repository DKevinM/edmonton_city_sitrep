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

# LiveMap's js/map.js now draws its own FireSmoke legend automatically
# whenever a FireSmoke layer is toggled on (left-middle of the map) - this
# used to hand-draw a duplicate one here to compensate for the app not
# having one, but that left two legends stacked in this snapshot once the
# app grew its own.


def _capture(page, path, center, zoom, toggle_off=(), toggle_on=()):
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
            _capture(page, firesmoke_path, center, zoom, toggle_off=[DEFAULT_ON_LAYER], toggle_on=[FIRESMOKE_LAYER])
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
