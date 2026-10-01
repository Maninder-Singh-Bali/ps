"""Resolve user-pasted Google Maps links without reading unrelated page content."""
import re,math
from urllib.parse import urlsplit,urljoin,parse_qs,unquote
from web_image import public_target,PinnedHTTPS

def allowed(url):
    p=urlsplit(url)
    if p.scheme!='https' or p.username or p.password or p.port not in (None,443):raise ValueError('Paste an HTTPS Google Maps link.')
    if p.hostname=='maps.app.goo.gl':return p
    if p.hostname in ('google.com','www.google.com','maps.google.com','google.co.in','www.google.co.in') and (p.path.startswith('/maps') or p.hostname=='maps.google.com'):return p
    if p.hostname=='goo.gl' and p.path.startswith('/maps/'):return p
    raise ValueError('Use a Google Maps place or shared location link.')

def extract(url):
    p=allowed(url);text=unquote(url)
    if '/dir/' in p.path:raise ValueError('Use a single place pin, not a directions route.')
    matches=re.findall(r'!3d([-+\d.]+)!4d([-+\d.]+)',text)
    source='place_pin'
    if len(set(matches))>1:raise ValueError('This link contains several places. Share one place pin.')
    pair=matches[0] if matches else None
    if not pair:
        for key in ('query','q','ll'):
            v=parse_qs(p.query).get(key,[''])[0]
            m=re.fullmatch(r'\s*([-+\d.]+)\s*,\s*([-+\d.]+)\s*',v)
            if m:pair=m.groups();source='map_centre' if key=='ll' else 'coordinate_pin';break
    if not pair:
        m=re.search(r'@([-+\d.]+),([-+\d.]+)',text)
        if m:pair=m.groups();source='map_centre'
    if not pair:return None
    try:lat,lon=map(float,pair)
    except ValueError:raise ValueError('Invalid coordinates in this link.')
    if not all(math.isfinite(v) for v in (lat,lon)) or not -90<=lat<=90 or not -180<=lon<=180:raise ValueError('Invalid coordinates in this link.')
    return {'latitude':lat,'longitude':lon,'source':source,'warning':'This is the map viewing centre, not a verified place pin. Check it before using it.' if source=='map_centre' else ''}

def resolve(url):
    url=str(url).strip()
    # Accept links pasted as Markdown as well as plain URLs.
    m=re.fullmatch(r'\[[^\]]*\]\((https://[^\s]+)\)',url)
    if m:url=m[1]
    for _ in range(5):
        allowed(url);result=extract(url)
        if result:return result
        p,host,port,ip=public_target(url);conn=PinnedHTTPS(host,port,ip,10)
        try:
            conn.request('GET',p.path+('?' + p.query if p.query else ''),headers={'User-Agent':'Mozilla/5.0','Connection':'close'})
            response=conn.getresponse()
            if response.status not in (301,302,303,307,308):raise ValueError('This link does not expose coordinates. Share a place pin or paste latitude, longitude.')
            target=response.getheader('Location')
            if not target:raise ValueError('The Maps redirect is incomplete.')
            url=urljoin(url,target)
        finally:conn.close()
    raise ValueError('Too many Maps redirects. Paste the full place link.')
