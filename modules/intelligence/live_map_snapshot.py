from playwright.sync_api import sync_playwright

LIVEMAP_URL = 'https://dkevinm.github.io/LiveMap/ACA.html'
HIDE_CSS = '''
#search-box, #header-right, #clear-btn, .leaflet-control-layers { display: none !important; }
'''


def _capture(page, path, center, zoom, enable_layer=None):
    page.goto(LIVEMAP_URL, wait_until='networkidle', timeout=45000)
    page.wait_for_timeout(3500)
    page.evaluate('([lat, lon, z]) => window.map.setView([lat, lon], z)', [center[0], center[1], zoom])
    page.wait_for_timeout(500)
    if enable_layer:
        page.get_by_text(enable_layer, exact=True).click()
        page.wait_for_timeout(3000)
    page.evaluate('() => { if (window.clearSelection) window.clearSelection(); }')
    page.mouse.move(2, 2)
    page.wait_for_timeout(500)
    page.add_style_tag(content=HIDE_CSS)
    page.wait_for_timeout(300)
    page.screenshot(path=str(path))


def capture_snapshots(city, out_dir, zoom=9):
    center = (float(city['latitude']), float(city['longitude']))
    small_map_path = out_dir / 'livemap_snapshot.png'
    firesmoke_path = out_dir / 'firesmoke_snapshot.png'
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1000, 'height': 700})
        try:
            _capture(page, small_map_path, center, zoom)
            _capture(page, firesmoke_path, center, zoom, enable_layer='FireSmoke Now')
            status = 'ok'
        except Exception as ex:
            status = f'error: {type(ex).__name__}: {ex}'
        finally:
            browser.close()
    return {
        'status': status,
        'livemap_path': small_map_path if small_map_path.exists() else None,
        'firesmoke_path': firesmoke_path if firesmoke_path.exists() else None,
    }
