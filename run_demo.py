import logging
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo

from core.config import load_config, ROOT
from core.io import write_json
from modules.air_quality.service import load_all_communities
from modules.alerts.service import load_weather_alerts
from modules.intelligence.sitrep_pdf import build_pdf


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
        now = datetime.now(ZoneInfo(cfg['project']['timezone'])).isoformat(timespec='seconds')

        write_json(out / 'sitrep_data.json', {'generated_at': now, 'communities': communities, 'wx_alerts': wx_alerts_result})
        build_pdf(cfg, communities, wx_alerts, now, out / 'sitrep.pdf')

        print(f"Sit rep PDF: {out / 'sitrep.pdf'}")
        return 0
    except Exception:
        log.error(traceback.format_exc())
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
