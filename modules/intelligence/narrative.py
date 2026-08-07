import math

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


def _circular_mean_deg(degrees):
    """Mean of a list of compass bearings — a plain average is wrong at the
    0/360 wraparound (e.g. mean of 350 and 10 should be 0, not 180)."""
    if not degrees:
        return None
    sin_sum = sum(math.sin(math.radians(d)) for d in degrees)
    cos_sum = sum(math.cos(math.radians(d)) for d in degrees)
    return math.degrees(math.atan2(sin_sum, cos_sum)) % 360


_COMPASS_DEG = {'N': 0, 'NE': 45, 'E': 90, 'SE': 135, 'S': 180, 'SW': 225, 'W': 270, 'NW': 315}
CALM_WIND_KMH = 5  # below this, direction is essentially noise — can't claim a transport direction


def build_wind_fire_bullets(fire_result, weather):
    """Ties current + forecast surface wind direction to where active fire
    detections are clustered — a lightweight, no-model proxy for 'is smoke
    transport toward Edmonton plausible', without running the full HRDPS
    back-trajectory particle simulation the venue sit-reps use."""
    if not fire_result or fire_result.get('status') != 'ok':
        return []
    hotspots = fire_result.get('hotspots') or []
    if not hotspots:
        return []

    c = (weather or {}).get('current') or {}
    wind_dir = c.get('wind_direction_deg')
    wind_speed = c.get('wind_speed_kmh')
    if wind_dir is None:
        return []

    counts = {}
    for h in hotspots:
        d = h.get('direction')
        if d:
            counts[d] = counts.get(d, 0) + 1
    if not counts:
        return []
    dominant_dir, dominant_count = max(counts.items(), key=lambda kv: kv[1])
    fire_bearing = _COMPASS_DEG.get(dominant_dir)

    plural = dominant_count != 1
    calm = wind_speed is None or wind_speed < CALM_WIND_KMH

    if calm:
        bullets = [
            f"{dominant_count} active fire detection{'s' if plural else ''} {'are' if plural else 'is'} to the {dominant_dir} of Edmonton. "
            f"Surface winds are currently calm ({f(wind_speed)} km/h), so current wind direction doesn't provide a reliable read on smoke transport toward the city."
        ]
    else:
        wind_from = compass(wind_dir)
        wind_toward = compass((wind_dir + 180) % 360)
        bullets = [
            f"{dominant_count} active fire detection{'s' if plural else ''} {'are' if plural else 'is'} to the {dominant_dir} of Edmonton. "
            f"Surface winds are currently {f(wind_speed)} km/h from the {wind_from}, moving toward the {wind_toward}."
        ]
        if fire_bearing is not None:
            diff = abs(fire_bearing - wind_dir) % 360
            diff = min(diff, 360 - diff)
            if diff <= 45:
                bullets.append(f"This is roughly aligned with the fires to the {dominant_dir}, so smoke transport toward Edmonton from that direction is plausible based on surface winds.")
            else:
                bullets.append(f"Current surface winds are not aligned with transport from the {dominant_dir}, so smoke reaching Edmonton from these fires is less likely right now based on surface winds alone.")

    hourly = (weather or {}).get('hourly') or []
    mean_forecast_dir = _circular_mean_deg([h.get('wind_direction_deg') for h in hourly if h.get('wind_direction_deg') is not None])
    if mean_forecast_dir is not None:
        diff = abs(mean_forecast_dir - wind_dir) % 360
        diff = min(diff, 360 - diff)
        forecast_from = compass(mean_forecast_dir)
        if diff <= 30:
            bullets.append(f"Forecast winds over the next {len(hourly)} hours remain predominantly from the {forecast_from}, similar to current conditions.")
        else:
            bullets.append(f"Forecast winds over the next {len(hourly)} hours shift to predominantly from the {forecast_from}, a change from the current {wind_from}.")

    return bullets


def build_wildfire_smoke_bullets(pm25_cell, fire_result, weather=None):
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
            bullets.extend(build_wind_fire_bullets(fire_result, weather))
        else:
            bullets.append('No active fire detections within 300 km of Edmonton (NASA FIRMS – VIIRS).')
    elif fire_result and fire_result.get('status') == 'missing':
        bullets.append('Active fire detection data was unavailable for this run (FIRMS API key not configured).')
    else:
        bullets.append('Active fire detection data was unavailable for this run.')

    return bullets
