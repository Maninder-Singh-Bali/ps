"""Approximate nearby city from bundled public data. Never sends coordinates out."""
from pathlib import Path
from functools import lru_cache
import gzip,json,math

@lru_cache(maxsize=1)
def places():
    with gzip.open(Path(__file__).resolve().parent/'resources'/'places.json.gz','rt',encoding='utf8') as f:return json.load(f)

def nearest(latitude,longitude):
    lat=float(latitude);lon=float(longitude)
    if not math.isfinite(lat) or not math.isfinite(lon) or not -90<=lat<=90 or not -180<=lon<=180:raise ValueError('Invalid coordinates.')
    def distance(p):
        a,b=map(math.radians,(lat,p[1]));dl=math.radians(p[2]-lon);dp=b-a
        return 6371*2*math.asin(min(1,math.sqrt(math.sin(dp/2)**2+math.cos(a)*math.cos(b)*math.sin(dl/2)**2)))
    data=places();city=min(data,key=distance);km=distance(city)
    return {'city':city[0],'country_code':city[3],'region':city[4],'timezone':city[5],'distance_km':round(km,1),'approximate':True,'label':f'Near {city[0]}, {city[4]} ({city[3]}) · approximately {km:.0f} km from the named city','source':'GeoNames · CC BY 4.0','coordinates_shared':False,'delivery_verified':False}

def for_room(store,room):
    plan=store.db['assets'].get(room.get('plan_id'),{});site=plan.get('drawing',{}).get('site',{})
    if site.get('latitude') is None or site.get('longitude') is None:return {'label':'No site coordinates saved for this room’s plan. Add them in Refine drawing → Site & sunlight.','coordinates_shared':False,'delivery_verified':False}
    try:return nearest(site['latitude'],site['longitude'])
    except FileNotFoundError:return {'label':'Offline area database is missing. Restore resources/ from the application package.','coordinates_shared':False,'delivery_verified':False}
