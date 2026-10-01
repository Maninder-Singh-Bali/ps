"""Local, approximate solar position using NOAA's general solar equations.

No network calls. Longitude is east-positive. Civil time is resolved locally
from coordinates and the selected date; north is clockwise from up.
Reference: https://gml.noaa.gov/grad/solcalc/solareqns.PDF
"""
import math
from datetime import datetime, timedelta
import calendar
from scene_timezone import resolve, local_offset

def number(v, low, high, label):
    if type(v) not in (int,float) or not math.isfinite(v) or not low<=v<=high:
        raise ValueError(f'Enter a valid {label} ({low} to {high}).')
    return float(v)

def clean_site(d):
    if not isinstance(d,dict):raise ValueError('Invalid site settings.')
    out={'north_confirmed':d.get('north_confirmed') is True,'north_angle':number(d.get('north_angle',0),0,360,'north angle')%360,'name':str(d.get('name',''))[:120],'latitude':None,'longitude':None,'sun_enabled':d.get('sun_enabled') is True}
    lat,lon=d.get('latitude'),d.get('longitude')
    if lat is not None or lon is not None:
        out.update(latitude=number(lat,-90,90,'latitude'),longitude=number(lon,-180,180,'longitude'))
    out['utc_offset']=0
    date=str(d.get('date',''));time=str(d.get('time','12:00'))
    try:
        if date:datetime.strptime(date+' '+time,'%Y-%m-%d %H:%M')
        elif out['sun_enabled']:raise ValueError()
    except ValueError:raise ValueError('Choose a scene date and time.')
    out.update(date=date,time=time)
    if out['sun_enabled'] and (lat is None or not out['north_confirmed']):raise ValueError('Set latitude, longitude and the plan’s north direction to use scene sunlight.')
    if lat is not None and date:out.update(resolve(out['latitude'],out['longitude'],date,time))
    if 'model' in d:
        from scene_scale import clean_model
        out['model']=clean_model(d['model'])
    return out

def position(site, local):
    # Fractional year is evaluated at UTC; solar time is derived from local clock.
    offset=local_offset(site['timezone'],local) if site.get('timezone') else site['utc_offset']
    utc=local-timedelta(hours=offset);hour=utc.hour+utc.minute/60+utc.second/3600
    g=2*math.pi/(366 if calendar.isleap(utc.year) else 365)*(utc.timetuple().tm_yday-1+(hour-12)/24)
    eq=229.18*(.000075+.001868*math.cos(g)-.032077*math.sin(g)-.014615*math.cos(2*g)-.040849*math.sin(2*g))
    dec=.006918-.399912*math.cos(g)+.070257*math.sin(g)-.006758*math.cos(2*g)+.000907*math.sin(2*g)-.002697*math.cos(3*g)+.00148*math.sin(3*g)
    tst=(local.hour*60+local.minute+local.second/60+eq+4*site['longitude']-60*offset)%1440
    ha=math.radians(tst/4-180);lat=math.radians(site['latitude'])
    cosz=math.sin(lat)*math.sin(dec)+math.cos(lat)*math.cos(dec)*math.cos(ha)
    elevation=90-math.degrees(math.acos(max(-1,min(1,cosz))))
    az=(math.degrees(math.atan2(math.sin(ha),math.cos(ha)*math.sin(lat)-math.tan(dec)*math.cos(lat)))+180)%360
    return {'azimuth':az,'elevation':elevation,'plan_angle':(az+site['north_angle'])%360}

def solar_summary(site):
    if site.get('latitude') is None or not site.get('date'):return None
    local=datetime.strptime(site['date']+' '+site['time'],'%Y-%m-%d %H:%M');result=position(site,local)
    midnight=local.replace(hour=0,minute=0,second=0);events={'sunrise':None,'sunset':None}
    previous=position(site,midnight)['elevation']+.833
    # Find each event within the actual selected local date, including polar days.
    for minute in range(10,1441,10):
        current=position(site,midnight+timedelta(minutes=minute))['elevation']+.833
        if (previous<0<=current) or (previous>=0>current):
            lo,hi=minute-10,minute;rising=current>previous
            for _ in range(15):
                mid=(lo+hi)/2;v=position(site,midnight+timedelta(minutes=mid))['elevation']+.833
                if (v>=0)==rising:hi=mid
                else:lo=mid
            instant=midnight+timedelta(minutes=(lo+hi)/2)
            # UI has minute precision. Choose the lit side of the event so the
            # sunrise preset does not fall just before the visible sunrise.
            displayed=instant+timedelta(minutes=1) if rising and instant.second else instant
            events['sunrise' if rising else 'sunset']={'time':displayed.strftime('%H:%M'),**position(site,instant)}
        previous=current
    result.update(events);result['daylight']=result['elevation']>-.833
    result['note']='Approximate sun position; terrain, buildings, clouds and atmospheric conditions are not modelled.'
    return result

def lighting_instruction(plan):
    site=plan.get('drawing',{}).get('site',{})
    if not site.get('sun_enabled'):return '',None
    site=clean_site(site)
    solar=solar_summary(site)
    if not solar:return '',None
    text=f"SCENE LIGHTING OVERRIDE: use the saved scene time {site['date']} {site['time']} (UTC{site['utc_offset']:+g}). North points {site['north_angle']:g} degrees clockwise from plan-up. "
    if solar['daylight']:
        text+=f"The sun is at azimuth {solar['azimuth']:.1f} degrees clockwise from true north, elevation {solar['elevation']:.1f} degrees; its position is {solar['plan_angle']:.1f} degrees clockwise from plan-up. Light travels FROM that side through existing openings. "
        text+='Use low-angle warm sunlight and long shadows. ' if solar['elevation']<12 else 'Use natural daylight consistent with that elevation. '
    else:text+='The sun is below the horizon. No direct sunlight or hard sun beams; use twilight/night ambience and plausible interior practical lights. '
    text+='Preserve architecture and openings. Do not add windows to admit light. This supersedes daylight and exposure described in the style or original photo.'
    return text,{'site':site,'solar':solar,'mode':'approximate solar guidance; image model is not a physical daylight simulator'}
