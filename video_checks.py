"""Technical and conservative visual diagnostics; never automatic approval."""
import av,numpy as np
from PIL import Image

def edge_energy(a):
    g=a.mean(axis=2)
    return float((np.abs(np.diff(g,axis=0)).mean()+np.abs(np.diff(g,axis=1)).mean())/2)

def inspect(path,source,seconds):
    with Image.open(source) as image:original=np.asarray(image.convert('RGB'),dtype=np.float32)
    count=0;luma=[];first_detail=None;previous_time=-1
    with av.open(str(path)) as container:
        stream=container.streams.video[0];fps=float(stream.average_rate or 0)
        if (stream.width,stream.height)!=(1920,1080) or abs(fps-24)>.01:raise ValueError('Video must be 1920 × 1080 at 24 fps. Output preserved for inspection.')
        for frame in container.decode(video=0):
            timestamp=float(frame.pts*frame.time_base)
            if timestamp<=previous_time:raise ValueError('Video has unordered frame timestamps. Output preserved for inspection.')
            previous_time=timestamp;pixels=frame.to_ndarray(format='rgb24').astype(np.float32)
            if count==0:first_detail=edge_energy(pixels)/max(edge_energy(original),.0001)
            luma.append(float(pixels.mean()));count+=1
    if count!=seconds*24:raise ValueError(f'Video is incomplete: {count} frames; expected {seconds*24}. Output preserved for inspection.')
    warnings=[]
    if first_detail<.90:warnings.append('The first decoded frame has less edge detail than the approved still. Check upholstery, rug and distant furniture for softness.')
    if max(luma)-min(luma)>5:warnings.append('Brightness varies across the clip. Check whether the exposure change is intended.')
    return {'technical_passed':True,'frames_decoded':count,'dimensions':[1920,1080],'fps':fps,'duration':count/fps,'first_frame_edge_ratio':round(first_detail,4),'brightness_range':round(max(luma)-min(luma),3),'warnings':warnings,'review_required':True,'note':'These are measured diagnostics, not proof of stable geometry, natural motion or exact product design. Watch the complete clip before approval.'}
