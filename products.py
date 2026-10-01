"""Real retailer discovery. Public metadata only; no purchase or visual-match claims."""
from pathlib import Path
from html.parser import HTMLParser
from html import unescape
from urllib.parse import urljoin,urlsplit,urlencode
from concurrent.futures import ThreadPoolExecutor
import hashlib, io, json, re, threading, time
from web_image import public_target,PinnedHTTP,PinnedHTTPS,fetch_public_image
from PIL import Image

ROOT=Path(__file__).resolve().parent
RETAILERS=[{'name':'Dekor Company','base':'https://www.dekorcompany.com','market':'IN','currency':'INR'},
           {'name':'Olive + Wild','base':'https://oliveandwild.com','market':'international','currency':'CAD'}]
CACHE_LOCK=threading.Lock()

def fetch_document(url):
    for _ in range(4):
        parsed,host,port,ip=public_target(url);conn=(PinnedHTTPS if parsed.scheme=='https' else PinnedHTTP)(host,port,ip,12)
        try:
            target=parsed.path or '/'
            if parsed.query:target+='?'+parsed.query
            conn.request('GET',target,headers={'User-Agent':'Mozilla/5.0 (compatible; PixeloidStudio/1.0)','Accept':'text/html,application/xhtml+xml,application/json;q=0.8','Connection':'close'})
            response=conn.getresponse()
            if response.status in (301,302,303,307,308):url=urljoin(url,response.getheader('Location',''));continue
            if response.status!=200:raise ValueError('The website did not make this listing available. Open its product page in your browser.')
            data=response.read(8*1024*1024+1)
            if len(data)>8*1024*1024:raise ValueError('Listing is too large to inspect safely.')
            return data.decode('utf8',errors='replace'),url
        finally:conn.close()
    raise ValueError('The product link redirects too many times.')

class ListingParser(HTMLParser):
    def __init__(self):super().__init__();self.capture=False;self.text=[];self.blocks=[];self.meta={}
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='script' and a.get('type','').lower()=='application/ld+json':self.capture=True;self.text=[]
        if tag=='meta':self.meta[a.get('property') or a.get('name')]=a.get('content','')
    def handle_data(self,text):
        if self.capture:self.text.append(text)
    def handle_endtag(self,tag):
        if tag=='script' and self.capture:
            try:self.blocks.append(json.loads(''.join(self.text)))
            except ValueError:pass
            self.capture=False

def nodes(value):
    if isinstance(value,list):
        for v in value:yield from nodes(v)
    elif isinstance(value,dict):
        yield value
        for key in ('@graph','mainEntity','hasVariant'):
            if key in value:yield from nodes(value[key])

def clean_text(value,limit=450):return re.sub(r'\s+',' ',unescape(re.sub('<[^>]*>',' ',str(value or '')))).strip()[:limit]
def safe_link(value,base):
    if not value:return ''
    u=urljoin(base,str(value or ''));p=urlsplit(u)
    return u if p.scheme in ('https','http') and p.hostname and not p.username and not p.password else ''

def measured(value):
    """Only explicit positive dimensions with a known unit; never infer missing axes."""
    if isinstance(value,dict):value=str(value.get('value',''))+' '+str(value.get('unitText') or value.get('unitCode') or '')
    text=clean_text(value,150)
    m=re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*(mm|cm|m|in|inch|inches|ft|feet|millimeters?|centimeters?|metres?|meters?|CMT|MMT|MTR|INH|FOT|["\u2033])\s*',text,re.I)
    if not m:return None
    unit=m[2].lower();factor=.001 if unit in ('mm','mmt') or unit.startswith('millimeter') else .01 if unit in ('cm','cmt') or unit.startswith('centimeter') else .3048 if unit in ('ft','feet','fot') else .0254 if unit in ('in','inch','inches','inh','"','\u2033') else 1
    metres=float(m[1])*factor
    return {'metres':metres,'published':text} if 0<metres<100 else None

def dimensions_from(product):
    found={};raw=[]
    properties=product.get('additionalProperty') or []
    if isinstance(properties,dict):properties=[properties]
    for name in ('width','depth','height'):
        value=product.get(name)
        if value is None:value=next((v.get('value') for v in properties if isinstance(v,dict) and str(v.get('name','')).strip().lower()==name),None)
        converted=measured(value)
        if converted:found[name]=converted
    text=clean_text(product.get('description'),15000)
    for name in ('width','depth','height'):
        if name in found:continue
        matches=re.findall(r'\b'+name+r'\s*[:=-]?\s*(\d+(?:\.\d+)?\s*(?:mm|cm|inches|inch|in|ft|feet|metres?|meters?|m))\b',text,re.I)
        # Conflicting variant dimensions are left unresolved.
        values=[measured(v) for v in matches];values=[v for v in values if v]
        if values and len({v['metres'] for v in values})==1:found[name]=values[0]
    for p in properties:
        if isinstance(p,dict) and any(t in str(p.get('name','')).lower() for t in ('dimension','size','width','depth','height','length')):raw.append(clean_text(p.get('name'),60)+': '+clean_text(p.get('value'),180))
    return found,raw

def retailer_embedded_product(text,url):
    """Read data only from the retailer's embedded product record; never execute JS."""
    if (urlsplit(url).hostname or '').lower() not in ('westelm.in','www.westelm.in'):return None
    start=re.search(r'window\.APP_DATA\s*=\s*',text)
    if not start:return None
    data=text[start.end():];match=re.search(r'"product_details"\s*:\s*',data)
    if not match:return None
    try:record,_=json.JSONDecoder().raw_decode(data[match.end():])
    except ValueError:return None
    if not isinstance(record,dict) or record.get('slug')!=urlsplit(url).path.rstrip('/').split('/')[-1]:return None
    attrs=record.get('attributes',{});sizes=record.get('sizes',{});price=sizes.get('price',{}).get('effective',{});details=sizes.get('size_details',[])
    product={'@type':'Product','name':record.get('name'),'url':url,'image':[m.get('url') for m in record.get('media',[]) if m.get('type')=='image'],
             'description':attrs.get('product_details') or record.get('description'),'brand':record.get('brand'),
             'offers':{'price':price.get('min'),'priceCurrency':price.get('currency_code'),'availability':'InStock' if sizes.get('sellable') else 'OutOfStock'}}
    notes=[];published={}
    if len(details)==1:
        dimension=details[0].get('dimension',{});unit=dimension.get('unit','')
        for axis in ('length','width','height'):
            value=measured({'value':dimension.get(axis),'unitText':unit})
            if value:published[axis]=value
        notes.append('Retailer size metadata: '+', '.join(k+' '+v['published'] for k,v in published.items())+'. Confirm orientation and whether these are assembled product dimensions.')
    elif details:notes.append('Multiple size variants are published. Select the correct variant and enter its measurements.')
    title=record.get('name','');inch=re.search(r'(\d+(?:\.\d+)?)\s*["\u2033]',title)
    if inch and published.get('length') and abs(float(inch[1])*.0254-published['length']['metres'])>.05:
        notes.append('Dimension discrepancy: the inch measurement in the product title differs from the length in retailer metadata. Verify before applying size.')
    if 'chaise' in url.lower() and 'wedge' in title.lower():notes.append('Variant discrepancy: the URL says chaise while the retailer product record says wedge. Check the intended sofa configuration.')
    product['_published_dimensions']=published;product['_dimension_notes']=notes
    return product

def parse_listing(text,url):
    parser=ListingParser();parser.feed(text)
    product=next((n for b in parser.blocks for n in nodes(b) if 'Product' in ([n.get('@type')] if isinstance(n.get('@type'),str) else (n.get('@type') or []))),None)
    if not product:product=retailer_embedded_product(text,url)
    if not product:raise ValueError('No verifiable product listing was found. Pinterest and inspiration pages need a retailer product link.')
    offers=product.get('offers') or [];offers=[offers] if isinstance(offers,dict) else offers
    offers=[o for o in offers if isinstance(o,dict)];offer=offers[0] if offers else {}
    picture=product.get('image') or parser.meta.get('og:image','')
    pictures=picture if isinstance(picture,list) else [picture]
    images=list(dict.fromkeys(u for v in pictures if (u:=safe_link((v.get('contentUrl') or v.get('url','')) if isinstance(v,dict) else v,url))))[:8]
    if isinstance(picture,list):picture=picture[0] if picture else ''
    if isinstance(picture,dict):picture=picture.get('contentUrl') or picture.get('url','')
    brand=product.get('brand') or ''
    if isinstance(brand,dict):brand=brand.get('name','')
    availability=str(offer.get('availability','')).split('/')[-1]
    price=offer.get('price',offer.get('lowPrice'));currency=offer.get('priceCurrency') or parser.meta.get('product:price:currency')
    try:price=float(price);price=price if price>=0 and price<1e10 else None
    except (ValueError,TypeError):price=None
    measurements=[]
    for name in ('width','depth','height'):
        v=product.get(name)
        if isinstance(v,dict):v=str(v.get('value',''))+' '+str(v.get('unitText') or v.get('unitCode') or '')
        if v:measurements.append(name+': '+clean_text(v,70))
    canonical=safe_link(product.get('url') or url,url)
    # Keep purchase link on the inspected retailer, not an arbitrary offer redirect.
    if urlsplit(canonical).hostname!=urlsplit(url).hostname:canonical=url
    metric,raw_dimensions=dimensions_from(product)
    if product.get('_published_dimensions'):metric=product['_published_dimensions']
    raw_dimensions.extend(product.get('_dimension_notes',[]))
    return {'id':hashlib.sha256(canonical.encode()).hexdigest()[:24],'title':clean_text(product.get('name') or parser.meta.get('og:title'),180),'url':canonical,'image':safe_link(picture,url),'images':images,'dimensions_m':metric,'dimension_notes':raw_dimensions,'retailer':urlsplit(url).hostname,'brand':clean_text(brand,100),'price':price,'currency':str(currency or '')[:8],'availability':availability or 'Not supplied','description':clean_text(product.get('description')),'dimensions':'; '.join(measurements),'checked':time.time(),'verified_listing':bool(offers),'market':'IN' if currency=='INR' else 'international'}

def cache_path():return ROOT/'cache'/'products'/'index.json'
def read_cache():
    try:return json.loads(cache_path().read_text(encoding='utf8'))
    except (FileNotFoundError,ValueError):return {}
def save_product(product):
    with CACHE_LOCK:
        data=read_cache();data[product['id']]=product;path=cache_path();path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2),encoding='utf8');tmp.replace(path)
    return product
def get_product(key):
    if not re.fullmatch('[a-f0-9]{24}',str(key)):raise ValueError('Choose a product from discovery.')
    item=read_cache().get(key)
    if not item:raise ValueError('Product lookup expired. Search again.')
    return item
def lookup(url,require_offer=True):
    if 'pinterest.' in (urlsplit(str(url)).hostname or ''):raise ValueError('Pinterest is an inspiration source. Open the pin’s retailer link and paste that product page to verify its price and availability.')
    text,final=fetch_document(url);product=parse_listing(text,final)
    if require_offer and not product['verified_listing']:raise ValueError('This page identifies a product but supplies no retailer offer. Its price and availability could not be verified.')
    return save_product(product)

def search_retailer(retailer,query):
    qs=urlencode({'q':query,'resources[type]':'product','resources[limit]':5})
    raw,_=fetch_document(retailer['base']+'/search/suggest.json?'+qs)
    products=json.loads(raw).get('resources',{}).get('results',{}).get('products',[])
    return [safe_link(p['url'],retailer['base']) for p in products if p.get('url')]

def search(query,market='IN',context='',area=None):
    query=clean_text(query,180)
    if len(query)<2:raise ValueError('Describe a furniture piece or look to search for.')
    if market not in ('IN','international','both'):raise ValueError('Select India, International or Both.')
    shops=[r for r in RETAILERS if market=='both' or r['market']==market];links=[];warnings=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        for shop,result in zip(shops,pool.map(lambda r:_capture(lambda:search_retailer(r,query)),shops)):
            if isinstance(result,Exception):warnings.append(shop['name']+': '+str(result))
            else:links.extend(result)
        values=list(pool.map(lambda link:_capture(lambda:lookup(link)),links[:10]))
    products=[v for v in values if not isinstance(v,Exception)]
    failures=sum(isinstance(v,Exception) for v in values)
    if failures:warnings.append(f'{failures} listings could not be verified and were omitted.')
    vocabulary={'walnut','oak','teak','ash','wood','brass','bronze','marble','stone','boucle','linen','leather','velvet','cream','ivory','white','beige','green','blue','black','brown','rattan','sculptural','minimal','classic','contemporary','rustic','mid-century','organic'}
    terms={w.lower() for w in re.findall('[a-zA-Z-]{3,}',context)}&vocabulary
    for p in products:
        matches=sorted(t for t in terms if t in (p['title']+' '+p['description']).lower())[:5]
        p['match_note']='Matches your saved direction: '+', '.join(matches) if matches else 'Matches the retailer search. Compare the photo, material and size with your room.'
        p['match_score']=len(matches)
        domestic=bool(area and area.get('country_code')=='IN' and p['market']=='IN')
        p['local_priority']=domestic
        p['local_note']=('Indian retailer; ' if domestic else '')+'delivery to '+area['city']+' is not confirmed.' if area and area.get('city') else 'Delivery location not confirmed.'
    products.sort(key=lambda p:(p['availability']=='InStock',p['local_priority'],p['match_score']),reverse=True)
    return {'items':products,'warnings':warnings,'market':market,'query':query,'coverage':[s['name'] for s in shops],'note':'Live retailer listings, ranked by saved text direction. Not visual similarity or a guaranteed dimensional fit. Stock, delivery and final price must be confirmed with the seller.','pinterest_url':'https://www.pinterest.com/search/pins/?'+urlencode({'q':query+' interior furniture'})}

def _capture(fn):
    try:return fn()
    except Exception as e:return e

def product_image(product,index=0):
    photos=product.get('images') or [product.get('image')]
    if type(index)!=int or not 0<=index<len(photos) or not photos[index]:raise ValueError('Choose an available product image.')
    return photos[index]

def thumbnail(key,index=0):
    p=get_product(key);source=product_image(p,index);out=ROOT/'cache'/'products'/(key+'-'+str(index)+'.jpg')
    if out.exists():return out
    if not p['image']:raise ValueError('This listing has no product photo.')
    raw,_=fetch_public_image(source)
    with Image.open(io.BytesIO(raw)) as image:
        image=image.convert('RGB');image.thumbnail((720,720));image.save(out,'JPEG',quality=90)
    return out
