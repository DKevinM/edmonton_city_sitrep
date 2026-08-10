import requests

from core.aqhi import risk_from_aqhi,pm25_to_eaqhi
from core.geometry import haversine_km
from core.io import read_structured_source

ODATA_URL = "https://data.environment.alberta.ca/EdwServices/aqhi/odata/CommunityAqhis?$format=json"

# Maps our community labels to the AEPA feed's CommunityName values.
COMMUNITY_API_NAME = {
    'Edmonton': 'Edmonton',
    'Strathcona County': 'Strathcona County',
    'St. Albert': 'St. Albert',
    'Enoch': 'Enoch',
    'Leduc': 'Leduc (Sensor)',
}


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def fetch_community_feed(timeout=20):
    r = requests.get(ODATA_URL, timeout=timeout, headers={'User-Agent': 'CityOfEdmontonSitRep/1.0'})
    r.raise_for_status()
    rows = r.json().get('value', [])
    return {row['CommunityName']: row for row in rows}


def load_purpleair_eaqhi_estimate(cfg, lat, lon, n=3):
    """Fail-safe for a community missing from the AEP feed (e.g. an outage):
    average the n nearest PurpleAir sensors' PM2.5 and convert to an eAQHI
    proxy via the same breakpoints SK_datapull already uses elsewhere. A
    lower-confidence estimate, not an official reading."""
    path = cfg['air_quality'].get('purpleair_source')
    if not path:
        return {'status': 'missing'}
    try:
        rows = read_structured_source(path)
    except Exception as ex:
        return {'status': 'error', 'error': f'{type(ex).__name__}: {ex}'}
    radius = float(cfg['air_quality'].get('search_radius_km', 30))
    cand = []
    for r in rows:
        if not r.get('use_for_map'):
            continue
        la, lo = r.get('latitude'), r.get('longitude')
        if la is None or lo is None:
            continue
        pm = r.get('pm_corr') if r.get('pm_corr') is not None else r.get('pm2.5_atm')
        if pm is None:
            continue
        d = haversine_km(lat, lon, la, lo)
        if d <= radius:
            cand.append((d, r, pm))
    if not cand:
        return {'status': 'missing'}
    nearest = sorted(cand, key=lambda x: x[0])[:n]
    avg_pm = sum(x[2] for x in nearest) / len(nearest)
    return {'status': 'ok', 'aqhi': pm25_to_eaqhi(avg_pm), 'pm25_avg': round(avg_pm, 1), 'n_sensors': len(nearest), 'sensor_names': [x[1].get('name') for x in nearest], 'max_distance_km': round(nearest[-1][0], 2)}


def load_all_communities(cfg):
    try:
        feed = fetch_community_feed()
    except Exception as ex:
        return [{'name': name, 'kind': 'unavailable', 'status': 'error', 'error': f'{type(ex).__name__}: {ex}', 'aqhi': None, 'risk': 'UNKNOWN'} for name in cfg['communities']]

    out = []
    for community in cfg['communities']:
        name = community['name'] if isinstance(community, dict) else community
        api_name = COMMUNITY_API_NAME.get(name, name)
        row = feed.get(api_name)
        if not row:
            lat = community.get('latitude') if isinstance(community, dict) else None
            lon = community.get('longitude') if isinstance(community, dict) else None
            est = load_purpleair_eaqhi_estimate(cfg, lat, lon) if lat is not None and lon is not None else {'status': 'missing'}
            if est.get('status') == 'ok':
                out.append({'name': name, 'kind': 'estimated', 'status': 'estimated', 'aqhi': est['aqhi'], 'risk': risk_from_aqhi(est['aqhi']), 'estimate': est})
            else:
                out.append({'name': name, 'kind': 'unavailable', 'status': 'missing', 'aqhi': None, 'risk': 'UNKNOWN'})
            continue
        aqhi = num(row.get('Aqhi'))
        out.append({
            'name': name,
            'kind': 'aepa',
            'status': 'ok',
            'aqhi': aqhi,
            'forecast_today': row.get('ForecastToday'),
            'forecast_tonight': row.get('ForecastTonight'),
            'forecast_tomorrow': row.get('ForecastTomorrow'),
            'reading_date': row.get('ReadingDate'),
            # Classified from the numeric AQHI ourselves — the feed's own
            # HealthRisk/message fields have been observed not matching its
            # own Aqhi number (e.g. HealthRisk "Low" at Aqhi 4-5).
            'risk': risk_from_aqhi(aqhi),
        })
    return out
