from datetime import datetime
from zoneinfo import ZoneInfo
def localize(value,tz_name):
    if not value:return None
    try:dt=datetime.fromisoformat(value)
    except ValueError:return None
    return dt.replace(tzinfo=ZoneInfo(tz_name)) if dt.tzinfo is None else dt.astimezone(ZoneInfo(tz_name))
def format_long(value,tz_name):
    dt=localize(value,tz_name); return dt.strftime('%a, %b %-d, %Y · %-I:%M %p %Z') if dt else 'unavailable'
def format_short(value,tz_name):
    dt=localize(value,tz_name); return dt.strftime('%a %-I:%M %p') if dt else None
def tz_abbrev(tz_name):
    return datetime.now(ZoneInfo(tz_name)).strftime('%Z')
def nominal_run_time(now,tz_name,target_hours=(5,12,17)):
    local=now.astimezone(ZoneInfo(tz_name))
    candidates=[local.replace(hour=h,minute=0,second=0,microsecond=0) for h in target_hours]
    return min(candidates,key=lambda c:abs((c-local).total_seconds()))
