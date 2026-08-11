import os
import requests

from core.aqhi import risk_from_aqhi,pm25_to_eaqhi,compute_aqhi
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


def _nearest_purpleair_pm25(cfg, lat, lon, n=3):
    """Shared by load_purpleair_eaqhi_estimate and load_mds_direct_estimate:
    average the n nearest PurpleAir sensors' PM2.5. Returns the raw average
    (not yet converted to an AQHI number) plus the sensor detail, or
    {'status':'missing'} if nothing usable is within radius."""
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
    return {'status': 'ok', 'pm25_avg': round(avg_pm, 1), 'n_sensors': len(nearest), 'sensor_names': [x[1].get('name') for x in nearest], 'max_distance_km': round(nearest[-1][0], 2)}


def load_purpleair_eaqhi_estimate(cfg, lat, lon, n=3):
    """Last-resort fail-safe for a community missing from the AEP feed:
    average the n nearest PurpleAir sensors' PM2.5 and convert to an eAQHI
    proxy via the same breakpoints SK_datapull already uses elsewhere. Only
    used when load_mds_direct_estimate also has nothing — this is a lower-
    confidence estimate, not a real reading."""
    pm = _nearest_purpleair_pm25(cfg, lat, lon, n)
    if pm.get('status') != 'ok':
        return pm
    return {'status': 'ok', 'aqhi': pm25_to_eaqhi(pm['pm25_avg']), **pm}


def load_mds_direct_estimate(cfg, lat, lon, hours_back=3):
    """Second-tier fail-safe, tried before the PurpleAir-only estimate: a
    real reading from the airshed's own MDS telemetry (ACA_data_pipe /
    WCAS_data_pipe -> Supabase measurements), read via the api_measurements
    view. Independent pipe from the AEP feed this module normally uses, so
    a community can still get a real reading here even during an AEP
    outage. Only borrows PM2.5 from PurpleAir if the nearest MDS station
    itself has no PM2.5 sensor."""
    url = os.environ.get('SUPABASE_URL')
    key = os.environ.get('SUPABASE_SERVICE_KEY')
    if not url or not key:
        return {'status': 'missing'}

    from datetime import datetime,timedelta,timezone
    since = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).isoformat()
    radius = float(cfg['air_quality'].get('search_radius_km', 30))
    try:
        r = requests.get(
            f"{url.rstrip('/')}/rest/v1/api_measurements",
            headers={'apikey': key, 'Authorization': f'Bearer {key}'},
            params={
                'parameter_code': 'in.(NO2,O3,PM25)',
                'reading_time': f'gte.{since}',
                'select': 'StationName,Latitude,Longitude,parameter_code,value,reading_time',
                'limit': '10000',
            },
            timeout=20,
        )
        r.raise_for_status()
        rows = r.json()
    except Exception as ex:
        return {'status': 'error', 'error': f'{type(ex).__name__}: {ex}'}
    if not rows:
        return {'status': 'missing'}

    by_station = {}
    for row in rows:
        name = row.get('StationName')
        la, lo = row.get('Latitude'), row.get('Longitude')
        if name is None or la is None or lo is None:
            continue
        st = by_station.setdefault(name, {'lat': la, 'lon': lo, 'vals': {}})
        p = row.get('parameter_code'); v = num(row.get('value'))
        if p and v is not None:
            st['vals'].setdefault(p, []).append(v)

    cand = [(haversine_km(lat, lon, s['lat'], s['lon']), name, s) for name, s in by_station.items() if s['vals'].get('NO2') and s['vals'].get('O3')]
    cand = [c for c in cand if c[0] <= radius]
    if not cand:
        return {'status': 'missing'}
    d, station_name, s = min(cand, key=lambda x: x[0])

    o3_ppb = sum(s['vals']['O3']) / len(s['vals']['O3'])
    no2_ppb = sum(s['vals']['NO2']) / len(s['vals']['NO2'])

    if s['vals'].get('PM25'):
        pm25 = sum(s['vals']['PM25']) / len(s['vals']['PM25'])
        pm25_source = 'MDS'
        pa = None
    else:
        pa = _nearest_purpleair_pm25(cfg, s['lat'], s['lon'])
        if pa.get('status') != 'ok':
            return {'status': 'missing'}
        pm25 = pa['pm25_avg']
        pm25_source = 'PurpleAir'

    aqhi = compute_aqhi(o3_ppb, no2_ppb, pm25)
    result = {'status': 'ok', 'aqhi': aqhi, 'station_name': station_name, 'distance_km': round(d, 2), 'pm25_source': pm25_source, 'pm25_avg': round(pm25, 2), 'o3_avg': round(o3_ppb, 1), 'no2_avg': round(no2_ppb, 1)}
    if pa is not None:
        result['n_sensors'] = pa['n_sensors']
        result['sensor_names'] = pa['sensor_names']
    return result


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
            if lat is None or lon is None:
                out.append({'name': name, 'kind': 'unavailable', 'status': 'missing', 'aqhi': None, 'risk': 'UNKNOWN'})
                continue
            mds = load_mds_direct_estimate(cfg, lat, lon)
            if mds.get('status') == 'ok':
                out.append({'name': name, 'kind': 'mds_direct', 'status': 'mds_direct', 'aqhi': mds['aqhi'], 'risk': risk_from_aqhi(mds['aqhi']), 'estimate': mds})
                continue
            est = load_purpleair_eaqhi_estimate(cfg, lat, lon)
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
