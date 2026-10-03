"""Preset-specific technical diagnostics; never automatic approval."""
import av,numpy as np
from PIL import Image
from video_workflow import settings,NATIVE

def edge_energy(a):
    g=a.mean(axis=2)
    return float((np.abs(np.diff(g,axis=0)).mean()+np.abs(np.diff(g,axis=1)).mean())/2)

def inspect(path,source,seconds,preset=NATIVE):
    config=settings(preset,seconds);size=tuple(config['output'])
    with Image.open(source) as image:
        image=image.convert('RGB');resized=image.size!=size
        if resized:image=image.resize(size,Image.Resampling.LANCZOS)
        original=np.asarray(image,dtype=np.float32)
    count=0;luma=[];first_detail=None;previous_time=-1
    with av.open(str(path)) as container:
        stream=container.streams.video[0];fps=float(stream.average_rate or 0)
        if (stream.width,stream.height)!=size or abs(fps-24)>.01:
            raise ValueError(f'Video must match {size[0]} × {size[1]} at 24 fps for this preset. Output preserved for inspection.')
        for frame in container.decode(video=0):
            if frame.pts is None or frame.time_base is None:raise ValueError('Video timestamps missing; output preserved.')
            timestamp=float(frame.pts*frame.time_base)
            if timestamp<=previous_time:raise ValueError('Video has unordered frame timestamps. Output preserved for inspection.')
            previous_time=timestamp;pixels=frame.to_ndarray(format='rgb24').astype(np.float32)
            if count==0:first_detail=edge_energy(pixels)/max(edge_energy(original),.0001)
            luma.append(float(pixels.mean()));count+=1
    if count!=config['frames']:raise ValueError(f'Video is incomplete: {count} frames; expected {config["frames"]}. Output preserved for inspection.')
    warnings=[]
    if first_detail<.90:warnings.append('The first decoded frame has less edge detail than the resolution-matched source. Review material detail.')
    if max(luma)-min(luma)>5:warnings.append('Brightness varies across the clip. Check whether the exposure change is intended.')
    return {'technical_passed':True,'preset_id':preset,'frames_decoded':count,'dimensions':list(size),'fps':fps,'duration':count/fps,
        'first_frame_edge_ratio':round(first_detail,4),'edge_comparison_source':{'dimensions':list(size),'resized':resized,'method':'lanczos' if resized else None},
        'brightness_range':round(max(luma)-min(luma),3),'warnings':warnings,'review_required':True,
        'note':'Measured diagnostics, not proof of stable geometry, natural motion or exact product design. Edge comparison uses a source at the output resolution. Watch the complete clip before approval.'}
