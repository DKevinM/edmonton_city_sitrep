from core.geometry import compass
from core.timefmt import format_short
from modules.weather.metrics import summarize


def f(v, d=0):
    return 'unavailable' if v is None else f'{v:.{d}f}'


def build_weather_bullets(cfg, weather):
    tz = cfg['project'].get('timezone', 'America/Edmonton')
    c = weather.get('current') or {}
    hourly = weather.get('hourly') or []
    bullets = []

    if c.get('temperature_c') is not None:
        bullets.append(
            f"Currently in Edmonton, temperature is {f(c.get('temperature_c'), 1)}°C and feels near {f(c.get('apparent_temperature_c'), 1)}°C. "
            f"Winds are {f(c.get('wind_speed_kmh'))} km/h from the {compass(c.get('wind_direction_deg'))}, gusting near {f(c.get('wind_gust_kmh'))} km/h."
        )
    else:
        bullets.append('Current weather observations were unavailable for this run.')

    if hourly:
        m = summarize(hourly)
        if m.get('thunderstorm_possible'):
            bullets.append(f"Thunderstorm conditions appear in the forecast beginning around {format_short(m.get('first_thunderstorm_hour'), tz)}.")
        elif (m.get('max_precipitation_probability_pct') or 0) >= 40:
            bullets.append(f"Precipitation probability reaches approximately {f(m.get('max_precipitation_probability_pct'))}% over the next {len(hourly)} hours.")
        if (m.get('max_wind_gust_kmh') or 0) >= 45:
            bullets.append(f"Wind gusts up to {f(m.get('max_wind_gust_kmh'))} km/h are expected over the next {len(hourly)} hours.")
        temps = [r['temperature_c'] for r in hourly if r.get('temperature_c') is not None]
        if temps:
            bullets.append(f"Temperatures over the next {len(hourly)} hours are expected to range from {f(min(temps), 1)}°C to {f(max(temps), 1)}°C.")

    return bullets


def pm25_label(v):
    if v is None:
        return 'unavailable'
    if v < 12:
        return 'good'
    if v < 35.4:
        return 'moderate'
    if v < 55.4:
        return 'unhealthy for sensitive groups'
    if v < 150.4:
        return 'unhealthy'
    if v < 250.4:
        return 'very unhealthy'
    return 'hazardous'


def build_wildfire_smoke_bullets(pm25_cell, fire_result):
    bullets = []
    if pm25_cell and pm25_cell.get('pm25') is not None:
        v = pm25_cell['pm25']
        bullets.append(f"Wildfire smoke model (BlueSky Canada) currently estimates PM2.5 of {v:.1f} µg/m³ over Edmonton — {pm25_label(v)} air quality from smoke alone.")
    else:
        bullets.append('Wildfire smoke model data was unavailable for this run.')

    if fire_result and fire_result.get('status') == 'ok':
        nearest = fire_result.get('nearest')
        if nearest:
            bullets.append(
                f"Nearest active fire detection (NASA FIRMS – VIIRS) is {nearest['distance_km']} km {nearest['direction']} of Edmonton, "
                f"detected {nearest.get('acq_date', 'unknown date')} {nearest.get('acq_time', '')} UTC."
            )
            other = fire_result.get('count', 0) - 1
            if other > 0:
                bullets.append(f"{other} additional active fire detection cluster(s) within {300} km of Edmonton.")
        else:
            bullets.append('No active fire detections within 300 km of Edmonton (NASA FIRMS – VIIRS).')
    elif fire_result and fire_result.get('status') == 'missing':
        bullets.append('Active fire detection data was unavailable for this run (FIRMS API key not configured).')
    else:
        bullets.append('Active fire detection data was unavailable for this run.')

    return bullets
