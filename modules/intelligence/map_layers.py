from math import cos, radians

from core.config import resolve_path
from core.geometry import haversine_km
from core.io import read_structured_source


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def half_degrees(lat0, half_width_km):
    half_lat = half_width_km / 111.0
    half_lon = half_width_km / (111.0 * max(cos(radians(lat0)), 0.01))
    return half_lat, half_lon


def in_bbox(ring, lat, lon, half_lat, half_lon):
    lons = [c[0] for c in ring]
    lats = [c[1] for c in ring]
    return max(lons) >= lon - half_lon and min(lons) <= lon + half_lon and max(lats) >= lat - half_lat and min(lats) <= lat + half_lat


def load_firesmoke(cfg):
    path = cfg.get('air_quality', {}).get('firesmoke_current_file')
    if not path:
        return None
    try:
        data = read_structured_source(str(resolve_path(cfg, path)))
    except Exception:
        return None
    c = cfg['city']
    lat, lon = float(c['latitude']), float(c['longitude'])
    half_width_km = float(cfg.get('map', {}).get('half_width_km', 55))
    half_lat, half_lon = half_degrees(lat, half_width_km)
    out = []
    for f in data.get('features', []):
        g = f.get('geometry') or {}
        if g.get('type') != 'Polygon':
            continue
        if in_bbox(g['coordinates'][0], lat, lon, half_lat, half_lon):
            p = f.get('properties') or {}
            out.append({'geometry': g, 'pm25': num(p.get('pm25')), 'timestamp': p.get('timestamp')})
    return out


def nearest_pm25(cells, lat, lon):
    if not cells:
        return None
    best = None
    best_d = None
    for c in cells:
        ring = c['geometry']['coordinates'][0]
        clat = sum(p[1] for p in ring) / len(ring)
        clon = sum(p[0] for p in ring) / len(ring)
        d = haversine_km(lat, lon, clat, clon)
        if best_d is None or d < best_d:
            best_d, best = d, c
    return best
