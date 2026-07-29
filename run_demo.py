import logging
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo

from core.config import load_config, ROOT
from core.io import write_json
from core.timefmt import format_long
from modules.air_quality.service import load_all_communities
from modules.alerts.service import load_weather_alerts
from modules.intelligence import map_layers
from modules.intelligence.map_layers import half_degrees
from modules.intelligence.maps import render_regional_map
from modules.intelligence.narrative import build_wildfire_smoke_bullets
from modules.intelligence.sitrep_pdf import build_pdf
from modules.fire.service import load_hotspots


def main():
    cfg = load_config()
    out = ROOT / 'output'
    out.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s',
        handlers=[logging.FileHandler(out / 'run.log'), logging.StreamHandler()],
    )
    log = logging.getLogger()
    try:
        communities = load_all_communities(cfg)
        wx_alerts_result = load_weather_alerts(cfg)
        wx_alerts = wx_alerts_result.get('alerts') or [] if wx_alerts_result.get('status') == 'ok' else []

        city = cfg['city']
        firesmoke_cells = map_layers.load_firesmoke(cfg) or []
        pm25_here = map_layers.nearest_pm25(firesmoke_cells, float(city['latitude']), float(city['longitude']))
        fire_result = load_hotspots(cfg)
        smoke_bullets = build_wildfire_smoke_bullets(pm25_here, fire_result)

        now = datetime.now(ZoneInfo(cfg['project']['timezone'])).isoformat(timespec='seconds')
        tz = cfg['project']['timezone']

        risk_color = {'LOW': '#0f6cbd', 'MODERATE': '#e0a800', 'HIGH': '#e8590c', 'EXTREME': '#7d1935', 'UNKNOWN': '#6c757d'}
        t = cfg['thresholds']['aqhi']
        for c in communities:
            v = c.get('aqhi')
            if v is None:
                c['risk'] = 'UNKNOWN'
            elif v >= t['extreme']:
                c['risk'] = 'EXTREME'
            elif v >= t['high']:
                c['risk'] = 'HIGH'
            elif v >= t['moderate']:
                c['risk'] = 'MODERATE'
            else:
                c['risk'] = 'LOW'

        fire_hotspots = (fire_result.get('hotspots') or []) if fire_result.get('status') == 'ok' else []
        half_width_km = float(cfg.get('map', {}).get('half_width_km', 55))
        half_lat, half_lon = half_degrees(float(city['latitude']), half_width_km)
        map_hotspots = [h for h in fire_hotspots if abs(h['lat'] - float(city['latitude'])) <= half_lat and abs(h['lon'] - float(city['longitude'])) <= half_lon]
        map_data_uri = render_regional_map(firesmoke_cells, communities, map_hotspots, city, half_lat, half_lon, risk_color, format_long(now, tz))

        write_json(out / 'sitrep_data.json', {'generated_at': now, 'communities': communities, 'wx_alerts': wx_alerts_result, 'pm25_here': pm25_here, 'fire': fire_result})
        build_pdf(cfg, communities, wx_alerts, smoke_bullets, map_data_uri, now, out / 'sitrep.pdf')

        print(f"Sit rep PDF: {out / 'sitrep.pdf'}")
        return 0
    except Exception:
        log.error(traceback.format_exc())
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
