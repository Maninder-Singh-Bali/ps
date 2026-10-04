"""Invented geometry for an opt-in, isolated browser-local editing scenario."""
import copy,re,base64

def build(pack,plan_drafts,media):
    result=copy.deepcopy(pack);project=result['state']['projects']['synthetic-ui'];project['name']='Synthetic apartment · multi-room · two floors'
    project['rooms']=[];result['docs']={};result['scenes']={};result['footprints']={}
    for level in (1,2):
        prefix=f'm{level}-';aid=f'plan-{level}';base=copy.deepcopy(pack['state']['projects']['synthetic-ui']['rooms'][level-1]);did=f'synthetic-floor-{level}'
        # All coordinates are invented centimetres. Room IDs are floor-specific.
        zones=[('living','Living / dining',(60,460,540,440)),('kitchen','Kitchen',(600,460,300,440)),('bed1','Bedroom 1',(60,60,380,280)),('bed2','Bedroom 2',(440,60,380,280)),('bed3','Bedroom 3',(820,60,380,280)),('hall','Circulation',(60,340,1140,120)),('bath1','Bathroom 1',(900,460,300,220)),('bath2','Bathroom 2',(900,680,300,220))]
        fs=[]
        def wall(key,a,b):
            row={'id':prefix+key,'kind':'wall','points':[a,b],'thickness':16,'height_m':2.8,'junction_ids':[prefix+'j'+str(p[0])+'_'+str(p[1]) for p in (a,b)],'review_note':'Invented synthetic dimensions.'};fs.append(row);return row
        for key,a,b in [('north',[60,60],[1200,60]),('east',[1200,60],[1200,900]),('south',[1200,900],[60,900]),('west',[60,900],[60,60]),('bedline',[60,340],[1200,340]),('hallline',[60,460],[1200,460]),('bed1',[440,60],[440,340]),('bed2',[820,60],[820,340]),('kitchen',[600,460],[600,900]),('baths',[900,460],[900,900]),('bathsplit',[900,680],[1200,680])]:wall(key,a,b)
        # Share exact junction identities, retaining intermediate branch nodes.
        for w in fs:
            a,b=w['points'];nodes={}
            for other in fs:
                for p,j in zip(other['points'],other['junction_ids']):
                    cross=(p[0]-a[0])*(b[1]-a[1])-(p[1]-a[1])*(b[0]-a[0])
                    if p not in w['points'] and cross==0 and min(a[0],b[0])<=p[0]<=max(a[0],b[0]) and min(a[1],b[1])<=p[1]<=max(a[1],b[1]):nodes[j]={'id':j,'point':p}
            if nodes:w['junction_nodes']=list(nodes.values())
        def opening(key,kind,host,t,width):
            w=next(w for w in fs if w['id']==prefix+host);a,b=w['points'];L=sum((a[i]-b[i])**2 for i in (0,1))**.5
            fs.append({'id':prefix+key,'kind':kind,'host_wall_id':w['id'],'points':[[a[i]+(b[i]-a[i])*u/L for i in (0,1)] for u in (t,t+width)],'offset':t,'width':width,'thickness':10,'frame_thickness':6,'head_m':2.4 if kind=='window' else 2.2,('sill_m' if kind=='window' else 'base_m'):.9 if kind=='window' else 0,'flip':False,'dimension_provenance':'demonstration'})
        for n,t in enumerate((120,500,880)):opening('bed-door'+str(n),'door','bedline',t,90);opening('bed-window'+str(n),'window','north',t,120)
        for n,t in enumerate((140,650,940)):opening('hall-door'+str(n),'door','hallline',t,80)
        opening('bath-door','door','baths',280,70);opening('entry','door','west',360,90);opening('living-window','window','south',650,170);opening('kitchen-window','window','south',350,130)
        d=copy.deepcopy(pack['docs'][did]);d.update(width=1260,height=960,wall_height_m=2.8,features=fs,name=f'Synthetic multi-room · Floor {level}',calibration={'points':[[60,60],[1200,60]],'metres':11.4,'method':'Invented synthetic geometry'},review={'issues':[],'view_box':[10,10,1240,940]},surface_design={'version':1,'surfaces':[],'items':[]},notes='Fully synthetic UI fixture, not a surveyed or private apartment.')
        for code,name,b in zones:
            r=copy.deepcopy(base);rid=f'room-{level}' if code=='living' else f'room-{level}-{code}';r.update(id=rid,name=name if level==1 else name+' · upper',bbox=[b[0]/1260,b[1]/960,b[2]/1260,b[3]/960],kind='circulation' if code=='hall' else 'room',block_layout={'items':[],'reviewed':False})
            r['area_polygon']=[[b[0]/1260,b[1]/960],[(b[0]+b[2])/1260,b[1]/960],[(b[0]+b[2])/1260,(b[1]+b[3])/960],[b[0]/1260,(b[1]+b[3])/960]]
            if code!='living':
                r.update(images=[],videos=[],anchor_id=None,approved_image_id=None,approved_video_id=None,camera_views={},view_approvals={})
            r['references']=[]
            for ref in ('sofa','art','tile','lamp'):
                refid=rid+'-'+ref;asset=copy.deepcopy(pack['state']['assets'][f'room-{level}-{ref}']);asset.update(id=refid,room_id=rid);result['state']['assets'][refid]=asset;r['references'].append(refid)
            if code in ('living','bed1','bed2','bed3','kitchen'):
                item={'id':prefix+code+'-chair','preset_id':'chair','label':name+' chair','kind':'chair','shape':'box','x':(b[0]+b[2]/2)/1260,'y':(b[1]+b[3]/2)/960,'width':.6/12.6,'depth':.6/9.6,'height_m':.9,'angle':0,'color':'#7c9891','asset_id':rid+'-sofa','dimension_status':'assumed','host_attachment':{'kind':'floor','floor':f'Floor {level}'}}
                r['block_layout']['items'].append(item)
            for k in ('floor','ceiling'):
                sf={'id':prefix+code+'-'+k,'kind':k,'room_id':rid,'label':r['name']+' · '+k,'boundary':[[b[0],b[1]],[b[0]+b[2],b[1]],[b[0]+b[2],b[1]+b[3]],[b[0],b[1]+b[3]]],'holes':[],'elevation_m':2.8 if k=='ceiling' else 0,'dimension_status':'assumed'}
                if k=='floor':sf['finish']={'kind':'paint','color':'#d8cbb7'}
                d['surface_design']['surfaces'].append(sf)
            if code=='living':
                d['surface_design']['surfaces'].append({'id':prefix+'living-wall','kind':'wall','wall_id':prefix+'west','side':-1,'room_id':rid,'label':'Living · west face'})
                for key,host,kind,x,y,wide,high,depth,drop in [('art','living-wall','painting',2,1.5,.6,.8,.04,0),('lamp','living-ceiling','pendant',2.7,2.2,.45,.45,.2,.5)]:
                    d['surface_design']['items'].append({'id':prefix+key,'surface_id':prefix+host,'kind':kind,'x':x,'y':y,'width':wide,'height':high,'depth':depth,'drop':drop,'rotation':0,'reference':{'image':'data:image/png;base64,'+base64.b64encode((media/(('art' if key=='art' else 'lamp')+'.png')).read_bytes()).decode(),'dimension_status':'assumed','aspect_locked':True}})
            project['rooms'].append(r)
        d=plan_drafts.validate(d,d);d['opening_attachment_revision']=1;result['docs'][did]=d;result['scenes'][did]=plan_drafts.preview(d);result['footprints'][did]=plan_drafts.footprint(d)
        asset=result['state']['assets'][aid];asset.update(width=1260,height=960,manual_document=d,name=f'Multi-room · Floor {level}',display_name=f'Multi-room · Floor {level}')
    result['scenario']='multi-room';return result
