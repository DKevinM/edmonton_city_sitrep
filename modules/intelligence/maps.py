import base64
import io
from math import cos, radians

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Circle
from matplotlib.collections import PatchCollection

PM25_BANDS = [
    (12, '#2f9e44', '0–11.9 (good)'),
    (35.4, '#e0a800', '12–35.3 (moderate)'),
    (55.4, '#e8590c', '35.4–55.3 (unhealthy for sensitive groups)'),
    (150.4, '#c92a2a', '55.4–150.3 (unhealthy)'),
    (250.4, '#862e9c', '150.4–250.3 (very unhealthy)'),
    (float('inf'), '#5c0000', '250.4+ (hazardous)'),
]


def _pm25_color(v):
    if v is None:
        return '#6c757d'
    for limit, color, _ in PM25_BANDS:
        if v < limit:
            return color
    return PM25_BANDS[-1][1]


def render_regional_map(cells, communities, fire_hotspots, city, half_lat, half_lon, risk_color, timestamp_label):
    lat0, lon0 = float(city['latitude']), float(city['longitude'])
    fig, ax = plt.subplots(figsize=(6.4, 5.4), dpi=150)

    patches, colors = [], []
    for c in cells:
        ring = c['geometry']['coordinates'][0]
        patches.append(Polygon([(p[0], p[1]) for p in ring], closed=True))
        colors.append(_pm25_color(c.get('pm25')))
    if patches:
        pc = PatchCollection(patches, facecolor=colors, edgecolor='none', linewidths=0)
        ax.add_collection(pc)

    for f in fire_hotspots:
        ax.scatter(f['lon'], f['lat'], marker='*', s=160, color='#ff6b35', edgecolor='white', linewidths=0.8, zorder=5)

    label_offsets = {'Edmonton': (-8, 8, 'right'), 'Strathcona County': (8, -10, 'left')}
    for c in communities:
        color = risk_color.get(c.get('risk'), '#6c757d')
        ax.add_patch(Circle((c['longitude'], c['latitude']), radius=half_lon * 0.028, facecolor=color, edgecolor='white', linewidth=0.8, zorder=6))
        dx, dy, ha = label_offsets.get(c['name'], (7, 6, 'left'))
        ax.annotate(c['name'], (c['longitude'], c['latitude']), textcoords='offset points', xytext=(dx, dy), fontsize=8.5, color='#1a2733', zorder=7, weight='bold', ha=ha)

    ax.set_xlim(lon0 - half_lon, lon0 + half_lon)
    ax.set_ylim(lat0 - half_lat, lat0 + half_lat)
    ax.set_aspect(1 / max(cos(radians(lat0)), 0.01))
    ax.set_facecolor('#eef3f7')
    ax.tick_params(labelsize=7, colors='#4a5a68')
    for spine in ax.spines.values():
        spine.set_color('#c6d2dc')
    ax.set_xlabel('Longitude', fontsize=7.5, color='#4a5a68')
    ax.set_ylabel('Latitude', fontsize=7.5, color='#4a5a68')
    ax.set_title(f'Wildfire Smoke (PM2.5) and Community AQHI — {timestamp_label}', fontsize=10, color='#0f6cbd', loc='left')

    handles = [plt.Line2D([0], [0], marker='s', linestyle='', markerfacecolor=color, markeredgecolor='none', markersize=9, label=label) for _, color, label in PM25_BANDS]
    handles.append(plt.Line2D([0], [0], marker='*', linestyle='', markerfacecolor='#ff6b35', markeredgecolor='white', markersize=11, label='Active fire detection (NASA FIRMS)'))
    ax.legend(handles=handles, loc='upper center', bbox_to_anchor=(0.5, -0.14), ncol=2, fontsize=6.8, frameon=False)

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')
