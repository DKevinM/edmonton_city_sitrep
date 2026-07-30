import logging
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo

from core.config import load_config, ROOT
from core.io import write_json
from core.timefmt import nominal_run_time
from modules.air_quality.service import load_all_communities
from modules.alerts.service import load_weather_alerts
from modules.fire.service import load_hotspots
from modules.intelligence import map_layers
from modules.intelligence.live_map_snapshot import capture_snapshots
from modules.intelligence.narrative import build_wildfire_smoke_bullets, build_weather_bullets
from modules.intelligence.sitrep_pdf import build_pdf
from modules.weather.service import load_weather


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
        tz = cfg['project']['timezone']
        city = cfg['city']

        communities = load_all_communities(cfg)
        wx_alerts_result = load_weather_alerts(cfg)
        wx_alerts = wx_alerts_result.get('alerts') or [] if wx_alerts_result.get('status') == 'ok' else []
        weather = load_weather(cfg)
        weather_bullets = build_weather_bullets(cfg, weather)

        firesmoke_cells = map_layers.load_firesmoke(cfg) or []
        pm25_here = map_layers.nearest_pm25(firesmoke_cells, float(city['latitude']), float(city['longitude']))
        fire_result = load_hotspots(cfg)
        smoke_bullets = build_wildfire_smoke_bullets(pm25_here, fire_result)

        try:
            snapshots = capture_snapshots(city, out)
        except Exception:
            log.error('live map snapshot capture failed:\n' + traceback.format_exc())
            snapshots = {'status': 'error', 'livemap_path': None, 'firesmoke_path': None}

        now = datetime.now(ZoneInfo(tz))
        nominal = nominal_run_time(now, tz)
        generated_at = nominal.isoformat(timespec='seconds')

        write_json(out / 'sitrep_data.json', {'generated_at': generated_at, 'actual_run_at': now.isoformat(timespec='seconds'), 'communities': communities, 'wx_alerts': wx_alerts_result, 'pm25_here': pm25_here, 'fire': fire_result, 'snapshots': {k: str(v) if v else None for k, v in snapshots.items() if k != 'status'}})
        build_pdf(cfg, communities, wx_alerts, smoke_bullets, weather, weather_bullets, snapshots, generated_at, out / 'sitrep.pdf')

        print(f"Sit rep PDF: {out / 'sitrep.pdf'}")
        return 0
    except Exception:
        log.error(traceback.format_exc())
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
