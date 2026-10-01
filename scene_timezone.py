"""Offline coordinate lookup and date-aware civil time for scene lighting."""
from datetime import datetime, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo
import tzfpy

@lru_cache(maxsize=512)
def zone_at(latitude, longitude):
    names = tzfpy.get_tzs(longitude, latitude)
    if len(names) != 1:
        raise ValueError('The timezone at this location is unclear. Check the coordinates.')
    return names[0]

def local_offset(zone, local, validate=False):
    tz = ZoneInfo(zone)
    aware = local.replace(tzinfo=tz)
    if validate:
        restored = aware.astimezone(timezone.utc).astimezone(tz).replace(tzinfo=None)
        if restored != local:
            raise ValueError('This time is skipped by the daylight-saving change. Choose another scene time.')
        if aware.utcoffset() != local.replace(tzinfo=tz, fold=1).utcoffset():
            raise ValueError('This time occurs twice during the daylight-saving change. Choose another scene time.')
    return aware.utcoffset().total_seconds()/3600

def resolve(latitude, longitude, date, time):
    zone = zone_at(latitude, longitude)
    offset = local_offset(zone, datetime.strptime(date+' '+time, '%Y-%m-%d %H:%M'), True)
    return {'timezone': zone, 'utc_offset': offset, 'timezone_source': 'offline coordinates and scene date'}
