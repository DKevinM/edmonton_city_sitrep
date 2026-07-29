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
