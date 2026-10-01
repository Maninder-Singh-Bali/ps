"""Compare save computation in an isolated fixture; never opens user data."""
import sys,tempfile,time,copy,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,sys.argv[1])
from PIL import Image
from store import Store
from engine import register_asset
import furniture_blocks,shared_floor

with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
    root=Path(folder);st=Store(root/'data');p=st.create_project('Benchmark')
    image=root/'plan.png';Image.new('RGB',(400,200),'white').save(image)
    a=register_asset(st,p['id'],image,'plan');p['floor_plans']=[a['id']]
    a['drawing']={'features':[],'revision':0};a['plan_reading']={'features':[],'revision':0}
    drafts=[]
    for i in range(12):
        r=st.add_room(p['id'],str(i),'Ground' if i<6 else 'First',a['id'],[0,0,1,1])
        items=[dict(id=str(j),kind='chair',preset_id='chair',label='Chair',x=.15+j*.07,y=.5,width=.025,depth=.05,angle=0,height_m=.85) for j in range(8)]
        r['block_layout']={'items':items};drafts.append(dict(room_id=r['id'],revision=r['revision'],items=items))
    snapshot=copy.deepcopy(st.db);st.save=lambda:None;times=[];calls=[]
    for _ in range(5):
        st.db=copy.deepcopy(snapshot)
        with patch('shared_floor.build',wraps=shared_floor.build) as build:
            start=time.perf_counter()
            furniture_blocks.save_plan(st,p['id'],drafts[0]['room_id'],dict(drafts=drafts))
            times.append(time.perf_counter()-start);calls.append(build.call_count)
    print(json.dumps(dict(sections=12,objects=96,floors=2,median_seconds=sorted(times)[2],preview_builds=calls[-1])))
