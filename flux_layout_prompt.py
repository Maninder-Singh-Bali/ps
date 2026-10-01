"""Compact reference roles for plan-derived FLUX.2 Klein views.

Based on BFL's multi-reference, JSON prompting and layout guidance. This is
semantic conditioning, not a bounding-box enforcement or ControlNet layer.
Original plan facts remain in the scene manifest for auditing.
"""
import json, math

SOURCES=[
 'https://docs.bfl.ai/guides/prompting_editing_multi_reference',
 'https://docs.bfl.ai/guides/usecases_editing_controlnets',
 'https://docs.bfl.ai/guides/usecases_t2i_json_prompting',
 'https://docs.bfl.ai/guides/prompting_unified_technical',
]

def compile_prompt(project,room,refs,plan,lighting='',packed=False,projection=None):
    from placement_map import current_layout
    layout=current_layout(room) or room.get('furniture_layout',{});heading=math.radians(layout.get('camera_heading',0))
    from interior_style import camera_for
    camera=camera_for(plan,room)
    if camera:
        dx=(camera['target'][0]-camera['position'][0])*plan['width'];dy=(camera['target'][1]-camera['position'][1])*plan['height']
        heading=math.atan2(dx,-dy)
    items={v['asset_id']:v for v in layout.get('items',[])}
    subjects=[];roles=[{'image':1,'role':'Layout authority: camera view, wall openings, furniture centres, facing and depth ordering.'}]
    for index,ref in enumerate(refs,2):
        if ref.get('surface_target'):
            roles.append({'image':2 if packed else index,'role':f"Finish reference for {ref['surface_target']} only; preserve the layout and all geometry.",**({'product_board_tile':index-1} if packed else {})})
            continue
        item=items[ref['id']];x,y=item['x']-.5,item['y']-.5
        if camera:
            rb=room['bbox'];x=(rb[0]+item['x']*rb[2]-camera['position'][0])*plan['width'];y=(rb[1]+item['y']*rb[3]-camera['position'][1])*plan['height']
            span=max(rb[2]*plan['width'],rb[3]*plan['height']);x/=span;y/=span
        screen_x=x*math.cos(heading)+y*math.sin(heading)
        depth=x*math.sin(heading)-y*math.cos(heading)
        side='left' if screen_x<-.12 else 'right' if screen_x>.12 else 'centre'
        distance='rear' if depth>.18 else 'foreground' if depth<-.18 else 'middle'
        relative=(item['angle']-math.degrees(heading))%360
        facing=('away from the camera','toward the image right','toward the camera','toward the image left')[int((relative+45)//90)%4]
        category=ref.get('category','Furniture')
        if not packed:roles.append({'image':index,'role':f'Product appearance for {category}: silhouette, materials and construction only.'})
        subjects.append({'description':category,'reference_image':2 if packed else index,'count':1,'position':f'{side} {distance}, at the matching placeholder in image 1','facing':facing,**({'product_board_tile':index-1} if packed else {})})
        if item.get('block_id'):subjects[-1].update(block_id=item['block_id'],change_instruction=item.get('instruction',''),section_footprint=item['proportion'])
        if projection is not None and item.get('block_id'):
            projected=next((v for v in projection if v.get('room_id')==room['id'] and v.get('block_id')==item['block_id'] and v.get('asset_id')==ref['id']),None)
            if not projected or not projected.get('visible_pixels'):raise ValueError('Missing visible projection for furniture block '+item['block_id'])
            bbox=projected['guide_bbox_xyxy']
            subjects[-1].update(position='Inside the corresponding projected placeholder in image 1',
                image_1_bounds_percent=[round(bbox[0]/19.2,2),round(bbox[1]/10.88,2),round(bbox[2]/19.2,2),round(bbox[3]/10.88,2)],
                bounds_order='left, top, right, bottom; origin top-left',
                placement_rule='Preserve the placeholder ground contact, facing, scale and occlusion. Fit the product silhouette to this envelope; do not move it to match the product photograph.')
    if packed:roles.append({'image':2,'role':'Numbered product board: each tile supplies appearance only for its corresponding subject. Do not render tile labels or the board.'})
    reviewed=plan.get('plan_reading',{}).get('features',[])
    architecture=[]
    for v in reviewed:
        if v.get('review_status')!='confirmed' or v.get('floor') not in (None,'',room.get('floor')):continue
        if v.get('room_id') and room['id'] not in (v['room_id'],v.get('connection_room_id')):continue
        item={'feature':v.get('label') or v.get('kind'),'description':v.get('notes','')}
        if v['kind']=='furniture':item.update(object_type=v.get('object_type'),seat_count=v.get('seat_count'),full_plan_bounds=v['bbox'],constraint='One distinct object; retain the verified seat count and placement.')
        if v.get('connection_room_id'):
            item.update(shared_feature_id=v['id'],connected_sections=[v['room_id'],v['connection_room_id']],full_plan_bounds=v['bbox'])
            if v['kind']=='space':item['constraint']='Open continuous space: no dividing wall, door or partition. These bounds are not construction lines.'
        architecture.append(item)
    prompt={
      'scene':f"An architectural interior photograph of {room['name']}. Render the layout in image 1 using the real furniture designs from the other images.",
      'reference_roles':roles,'subjects':subjects,
      'composition':'Same perspective and depth ordering as image 1. One instance of each listed product replaces its placeholder. The circulation space remains clear floor. One continuous, full-frame interior photograph.',
      'architecture':architecture,
      'room_direction':room.get('notes',''),
      'style':project.get('style',''),
      'lighting':lighting or 'Soft natural daylight through the planned openings; neutral exposure.',
      'surface_detail':'Natural fabric weave, wood grain, material joints, soft highlights and clean unmarked surfaces.',
    }
    blocks=room.get('block_layout',{}).get('items',[])
    if blocks:
        prompt['furniture_blocks']=[{**v,'constraint':(f"Render {v['chair_modules']['rows']*v['chair_modules']['columns']} separate identical chairs in the specified rows and columns, with 15% of one chair size between chairs. Preserve individual chair proportions and group rotation; never stretch them into one object." if v.get('chair_modules') else 'One distinct furniture object matching this reviewed plain volume.')+' Coordinates are on the full source plan.'} for v in blocks]
        prompt['composition']+=' Retain the reviewed block volumes and their positions.'
    if not refs and not blocks:
        prompt['scene']=f"An architectural photograph of the empty {room['name']} shell. Render the geometry in image 1 with realistic plaster, stone flooring, glazing and door materials."
        prompt['composition']='Same perspective, walls and opening positions as image 1. Clear unfurnished floor throughout. One continuous full-frame photograph.'
    return json.dumps(prompt,ensure_ascii=False,indent=2),{'version':1,'format':'structured reference roles','sources':SOURCES,'scope':'Semantic guidance only; visual plan review is required.'}
