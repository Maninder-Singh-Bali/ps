"""Source metadata retention; classification remains separate from CAD naming."""
def safe(value):
    if value is None or isinstance(value,(str,int,float,bool)):return value
    if isinstance(value,dict):return {str(k):safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [safe(v) for v in value]
    try:return [safe(v) for v in value]
    except TypeError:return str(value)

def dxf_manifest(doc,entities):
    from ezdxf.lldxf.tagwriter import TagCollector
    def record(entity):
        return {'id':entity.dxf.handle,'type':entity.dxftype(),'layer':entity.dxf.layer,
                'attributes':safe(entity.dxf.all_existing_dxf_attribs()),
                'native_tags':[[t.code,safe(t.value)] for t in TagCollector.dxftags(entity)]}
    names={e.dxf.name for e in entities if e.dxftype()=='INSERT'};blocks={};pending=list(names)
    while pending:
        name=pending.pop()
        if name in blocks:continue
        block=doc.blocks.get(name)
        if block is None:blocks[name]={'missing':True};continue
        contents=list(block);blocks[name]={'base_point':safe(block.block.dxf.base_point),'entities':[record(e) for e in contents]}
        pending.extend(e.dxf.name for e in contents if e.dxftype()=='INSERT' and e.dxf.name not in blocks)
    return {'schema_version':1,'entities':[record(e) for e in entities],'blocks':blocks,'units_declaration':doc.units,
            'classification_status':'Layer names and units require validation; native tags are source evidence.'}
