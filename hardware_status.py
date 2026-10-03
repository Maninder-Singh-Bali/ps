"""Label preparation-time memory samples; never invent a measurement timestamp."""
import re
from datetime import datetime, timezone


def sample(ram_gib, vram_gib):
    return describe({'name':'Hardware','ram_available_gib':ram_gib,
        'vram_free_gib':vram_gib,'measured_at':datetime.now(timezone.utc).isoformat()})


def describe(check):
    value=dict(check)
    if value.get('name')!='Hardware':return value
    ram=value.get('ram_available_gib');vram=value.get('vram_free_gib')
    if ram is None or vram is None:
        # Known v1 worker display divided MiB by 1024 but labelled the result GB.
        legacy=re.fullmatch(r'([\d.]+) GB RAM and ([\d.]+) GB VRAM currently free\.',value.get('detail',''))
        if legacy:
            ram,vram=map(float,legacy.groups())
            value.update(ram_available_gib=ram,vram_free_gib=vram)
    stamp=value.get('measured_at')
    timing='Measured '+stamp if stamp else 'Measurement time unavailable (older worker)'
    if isinstance(ram,(int,float)) and isinstance(vram,(int,float)):
        value['detail']=f'{ram:.1f} GiB RAM available; {vram:.1f} GiB VRAM free. {timing}. Saved preparation reading, not live.'
    else:
        value['detail']=f'Memory sample unavailable. {timing}. Saved preparation check, not live.'
    value['cached']=True
    return value
