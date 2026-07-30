import requests

ODATA_URL = "https://data.environment.alberta.ca/EdwServices/aqhi/odata/CommunityAqhis?$format=json"

# Maps our community labels to the AEPA feed's CommunityName values.
COMMUNITY_API_NAME = {
    'Edmonton': 'Edmonton',
    'Strathcona County': 'Strathcona County',
    'St. Albert': 'St. Albert',
    'Enoch': 'Enoch',
    'Leduc': 'Leduc (Sensor)',
}

RISK_MAP = {'low': 'LOW', 'moderate': 'MODERATE', 'high': 'HIGH', 'very high': 'EXTREME'}


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _risk(label):
    return RISK_MAP.get((label or '').strip().lower(), 'UNKNOWN')


def fetch_community_feed(timeout=20):
    r = requests.get(ODATA_URL, timeout=timeout, headers={'User-Agent': 'CityOfEdmontonSitRep/1.0'})
    r.raise_for_status()
    rows = r.json().get('value', [])
    return {row['CommunityName']: row for row in rows}


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
            out.append({'name': name, 'kind': 'unavailable', 'status': 'missing', 'aqhi': None, 'risk': 'UNKNOWN'})
            continue
        out.append({
            'name': name,
            'kind': 'aepa',
            'status': 'ok',
            'aqhi': num(row.get('Aqhi')),
            'forecast_today': row.get('ForecastToday'),
            'forecast_tonight': row.get('ForecastTonight'),
            'forecast_tomorrow': row.get('ForecastTomorrow'),
            'reading_date': row.get('ReadingDate'),
            'risk': _risk(row.get('HealthRisk')),
            'general_message': row.get('GeneralPopulationMessage'),
            'at_risk_message': row.get('AtRiskMessage'),
        })
    return out
