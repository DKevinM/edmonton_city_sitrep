from core.config import resolve_path
from core.geometry import haversine_km
from core.io import read_structured_source

AK = ('AQHI', 'aqhi', 'value', 'Value', 'current_aqhi')
LAT = ('latitude', 'lat', 'Latitude', 'LAT')
LON = ('longitude', 'lon', 'lng', 'Longitude', 'LON')
STATION = ('station_name', 'name', 'station', 'StationName')
TIME = ('timestamp', 'datetime', 'time', 'observed_at', 'ReadingDate')
F3H = ('aqhi_3h', 'AQHI_3H', 'aqhi_future_3h', 'forecast_3h', 'AQHI_forecast_3h', 'aqhi_forecast_3h')


def first(d, ks):
    for k in ks:
        if d.get(k) not in (None, ''):
            return d[k]


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def records(data):
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict) and data.get('type') == 'FeatureCollection':
        out = []
        for f in data.get('features', []):
            p = dict(f.get('properties') or {})
            g = f.get('geometry') or {}
            c = g.get('coordinates') or []
            if g.get('type') == 'Point' and len(c) > 1:
                p.setdefault('longitude', c[0])
                p.setdefault('latitude', c[1])
            out.append(p)
        return out
    return [data] if isinstance(data, dict) else []


def _load(cfg, key, fallback):
    src = cfg['air_quality'].get(key, '')
    mode = cfg.get('data_mode', 'auto')
    if src and mode != 'sample':
        try:
            s = src if src.startswith(('http://', 'https://')) else str(resolve_path(cfg, src))
            return read_structured_source(s), s, False
        except Exception:
            if mode == 'live':
                raise
    s = str(resolve_path(cfg, fallback))
    return read_structured_source(s), s, True


def _nearest_station(cfg, lat, lon, radius_km):
    aq = cfg['air_quality']
    data, src, fb = _load(cfg, 'current_source', aq['fallback_current_file'])
    cand = []
    for r in records(data):
        v = num(first(r, AK))
        la = num(first(r, LAT))
        lo = num(first(r, LON))
        if v is not None and la is not None and lo is not None:
            d = haversine_km(lat, lon, la, lo)
            if d <= radius_km:
                cand.append((d, r, v))
    if not cand:
        return None
    d, r, v = min(cand, key=lambda x: x[0])
    plus3 = num(first(r, F3H))
    return {
        'status': 'ok',
        'source': src,
        'fallback': fb,
        'aqhi': round(v, 1),
        'station_name': first(r, STATION) or 'Nearest AQHI station',
        'timestamp': first(r, TIME),
        'distance_km': round(d, 2),
        'plus_3h': round(plus3, 1) if plus3 is not None else None,
    }


def _blend_estimate(cfg, lat, lon):
    path = cfg['air_quality'].get('blend_grid_file')
    if not path:
        return None
    try:
        data = read_structured_source(str(resolve_path(cfg, path)))
    except Exception as ex:
        return {'status': 'error', 'error': f'{type(ex).__name__}: {ex}'}
    for f in data.get('features', []):
        g = f.get('geometry') or {}
        if g.get('type') != 'Polygon':
            continue
        ring = g['coordinates'][0]
        lons = [c[0] for c in ring]
        lats = [c[1] for c in ring]
        if min(lons) <= lon <= max(lons) and min(lats) <= lat <= max(lats):
            p = f.get('properties') or {}
            v = num(p.get('value'))
            return {
                'status': 'ok' if v is not None else 'no_data',
                'value': v,
                'confidence': p.get('confidence'),
                'timestamp': p.get('timestamp'),
            }
    return {'status': 'missing'}


def load_community_aqhi(cfg, community):
    """Official station within search_radius_km if one exists, else a labeled
    gridded blend estimate at the community's coordinates."""
    lat, lon = float(community['latitude']), float(community['longitude'])
    radius = float(cfg['air_quality'].get('search_radius_km', 15))
    base = {'name': community['name'], 'latitude': lat, 'longitude': lon}
    station = _nearest_station(cfg, lat, lon, radius)
    if station:
        return {**base, 'kind': 'station', **station}
    blend = _blend_estimate(cfg, lat, lon)
    if blend and blend.get('status') == 'ok':
        return {
            **base,
            'kind': 'estimate',
            'status': 'ok',
            'aqhi': round(blend['value'], 1) if blend['value'] is not None else None,
            'plus_3h': None,
            'confidence': blend.get('confidence'),
            'timestamp': blend.get('timestamp'),
        }
    return {**base, 'kind': 'unavailable', 'status': 'missing', 'aqhi': None, 'plus_3h': None}


def load_all_communities(cfg):
    return [load_community_aqhi(cfg, c) for c in cfg['communities']]
