"""Additive scene/provenance projection; original editable records remain authoritative."""
import copy,hashlib,json
VERSION=1
LIGHT_ASSETS={"pendant-light","wall-light","ceiling-light","floor-lamp","table-lamp","lamp-floor","lamp-table","light-pendant","light-ceiling","light-wall","chandelier","spotlight"}

def from_plan(plan,rooms=(),architecture=()):
    rooms=[r for r in rooms if r.get('plan_id',plan['id'])==plan['id']]
    report=plan.get('vision_report') or {};elements=[]
    source={'asset_id':plan['id'],'sha256':plan.get('sha256'),'page':plan.get('plan_source',{}).get('page',1)}
    for f in plan.get('plan_reading',{}).get('features',[]):
        elements.append({'id':f.get('id') or 'legacy'+hashlib.sha256(json.dumps(f,sort_keys=True).encode()).hexdigest()[:20],'source':copy.deepcopy(source),'floor':f.get('floor'),
            'category':f.get('kind','unknown'),'subtype':f.get('object_type'),'original_location':f.get('bbox'),
            'geometry':{'type':f.get('shape','unspecified'),'bbox':f.get('bbox'),'points':copy.deepcopy(f.get('points'))},
            'classification_uncertainty':f.get('confidence','unknown'),'geometry_uncertainty':'unverified' if f.get('shape','unspecified')=='unspecified' else 'user supplied',
            'dimension_provenance':'unknown','relationships':{'room_id':f.get('room_id'),'connection_room_id':f.get('connection_room_id')},
            'review_state':f.get('review_status','pending'),'pipeline_version':report.get('pipeline_version','legacy'),
            'manual_history':copy.deepcopy(f.get('history',[])),'origin':'observation'})
    for f in plan.get('drawing',{}).get('features',[]):
        elements.append({'id':f.get('id') or 'legacy'+hashlib.sha256(json.dumps(f,sort_keys=True).encode()).hexdigest()[:20],'source':copy.deepcopy(source),'category':f['kind'],
                         'geometry':copy.deepcopy(f),'origin':'manual_geometry','review_state':'user_supplied',
                         'dimension_provenance':'drawing units; project calibration applies'})
    by_id={f['id']:f for f in elements}
    for part in architecture:
        key=part.get('source_id',part.get('id'))
        if key not in by_id:
            entry={'id':key,'source':{**source,'native_entity_id':part.get('native_source_id')},
                   'category':part['kind'],'geometry':{'type':'source_path','svg':part.get('source_geometry'),'units':'plan pixels'},
                   'origin':'classified_source_geometry','review_state':'classification_requires_review',
                   'dimension_provenance':'source strokes; thickness and building scale require validation','manual_history':[]}
            elements.append(entry);by_id[key]=entry
        by_id[key].setdefault('resolved_segments',[]).append({'points':copy.deepcopy(part['points']),
            'thickness':part.get('thickness'),'tolerance_px':part.get('curve_tolerance_px',0)})
    for room in rooms:
        for item in room.get('block_layout',{}).get('items',[]):
            key=room['id']+':'+item['id']
            elements.append({'id':key,'source':copy.deepcopy(source),'floor':room.get('floor'),
                'category':item.get('kind','furniture'),'subtype':item.get('preset_id'),'origin':'editable_proxy',
                'position':[item.get('x'),item.get('y')],'orientation_degrees':item.get('angle',0),
                'geometry':{'type':'library_proxy','units':'normalized plan x/y; elevation in metres','width':item.get('width'),'depth':item.get('depth'),'height_m':item.get('height_m'),'elevation_m':item.get('elevation_m',0)},
                'dimensions':copy.deepcopy(item.get('physical_size')),'dimension_provenance':'explicit furniture dimensions' if item.get('physical_size') else 'library estimate',
                'relationships':{'room_id':room['id'],'product_asset_id':item.get('asset_id'),'host_attachment':copy.deepcopy(item.get('host_attachment'))},
                'review_state':'user_reviewed' if room.get('block_layout',{}).get('reviewed') else 'draft',
                'lighting_origin':('user_design' if item.get('preset_id') in LIGHT_ASSETS else None),
                'proxy':copy.deepcopy(item),'manual_history':copy.deepcopy(item.get('history',[]))})
    from surface_inputs import identity
    design=identity(plan)
    if design:
        for category in ('surfaces','items'):
            elements.extend({'id':'design:'+category+':'+v['id'],'origin':'surface_design','category':v['kind'],'design':v,'floor':plan.get('drawing',{}).get('surface_design_floor')} for v in design[category])
    lighting=[f for f in report.get('features',[]) if f.get('suggested_asset_id','') in
              ('pendant-light','wall-light','ceiling-light','floor-lamp','table-lamp','lamp-floor','lamp-table','light-pendant','light-ceiling','light-wall','chandelier','spotlight')
              or f.get('object_type','').lower() in ('lamp','pendant','chandelier','light','wall light','ceiling light')]
    revision=hashlib.sha256(json.dumps([source,elements,rooms,plan.get('drawing',{}).get('revision')],sort_keys=True).encode()).hexdigest()
    return {'schema_version':VERSION,'scene_revision':revision,'coordinate_system':'original plan pixels and normalized bounds; z in metres',
            'source':source,'source_metadata':copy.deepcopy(plan.get('plan_source',{})),
            'elements':elements,'observations':copy.deepcopy(report.get('features',[])),
            'design_proposals':copy.deepcopy(plan.get('design_proposals',[])),
            'lighting_status':'Possible lighting symbols — verify against source' if lighting else 'No lighting detected; verify against the source' if report.get('coverage_complete') else 'Lighting evidence not established'}

def migrate(plan,rooms=()):
    result=copy.deepcopy(plan)
    if 'scene_document' not in result:result['scene_document']=from_plan(result,rooms)
    return result

def rollback(migrated):
    result=copy.deepcopy(migrated);result.pop('scene_document',None);return result
