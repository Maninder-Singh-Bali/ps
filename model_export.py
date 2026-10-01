"""GLB export of the same saved mesh used by the shared viewer and guides."""
import json,struct,math

def glb(scene):
    groups={}
    for surface in scene['surfaces']:
        if surface['kind']=='floor_estimate':continue  # bounds are not a building slab
        key=surface.get('object_key') or surface.get('source_id') or surface['kind']
        groups.setdefault(key,[]).append(surface)
    binary=bytearray();views=[];accessors=[];meshes=[];nodes=[]
    def buffer(values,kind,components):
        while len(binary)%4:binary.append(0)
        offset=len(binary);flat=[v for row in values for v in row]
        raw=struct.pack('<'+'f'*len(flat),*flat);binary.extend(raw)
        views.append({'buffer':0,'byteOffset':offset,'byteLength':len(raw)})
        accessors.append({'bufferView':len(views)-1,'componentType':5126,'count':len(values),'type':kind,
                          'min':[min(r[i] for r in values) for i in range(components)],'max':[max(r[i] for r in values) for i in range(components)]})
        return len(accessors)-1
    for key,faces in groups.items():
        points=[];colors=[]
        for face in faces:
            p=face['points']
            for i in range(1,len(p)-1):
                tri=[p[0],p[i],p[i+1]]
                if not all(math.isfinite(v) for q in tri for v in q):raise ValueError('Non-finite model geometry.')
                points.extend([[q[0],q[2],-q[1]] for q in tri]);colors.extend([[v/255 for v in face['color']]]*3)
        if not points:continue
        meshes.append({'name':key,'primitives':[{'attributes':{'POSITION':buffer(points,'VEC3',3),'COLOR_0':buffer(colors,'VEC3',3)},'mode':4}]})
        nodes.append({'name':key,'mesh':len(meshes)-1,'extras':{'stable_element_id':key}})
    if not nodes:raise ValueError('No supported geometry to export yet. Review the plan first.')
    document={'asset':{'version':'2.0','generator':'Pixeloid Studio'},'scene':0,'scenes':[{'nodes':list(range(len(nodes)))}],
        'nodes':nodes,'meshes':meshes,'buffers':[{'byteLength':len(binary)}],'bufferViews':views,'accessors':accessors,
        'extras':{'geometry_hash':scene['geometry_hash'],'plan_id':scene['plan_id'],'floor':scene['floor'],'units':'metres',
                  'scale_measured':scene['calibrated'],'partial':bool(scene.get('partial') or scene['unresolved_architecture']),
                  'geometry_validated':bool(scene.get('geometry_validated')),'limitations':scene['limits'],'unresolved_architecture':scene['unresolved_architecture']}}
    text=json.dumps(document,separators=(',',':')).encode();text+=b' '*((-len(text))%4);binary+=b'\0'*((-len(binary))%4)
    return struct.pack('<4sII',b'glTF',2,12+8+len(text)+8+len(binary))+struct.pack('<I4s',len(text),b'JSON')+text+struct.pack('<I4s',len(binary),b'BIN\0')+binary
