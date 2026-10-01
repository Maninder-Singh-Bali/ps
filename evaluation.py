"""Offline evaluation against explicitly reviewed annotations, never model self-grading."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from detection_review import category, iou, reconcile


def evaluate(predictions, annotations, threshold=.5):
    if annotations.get('reviewed') is not True or not annotations.get('reviewer'):
        raise ValueError('Use manually reviewed annotations with a reviewer and source hash.')
    if not annotations.get('source_sha256') or annotations['source_sha256']!=predictions.get('source_sha256'):
        raise ValueError('Prediction and annotation source hashes must match.')
    expected=annotations['features'];observed=predictions['features']
    used=set();matched=set();pairs=[];metrics={}
    # Score-first greedy matching is deliberately not used: model confidence is uncalibrated.
    candidates=sorted(((iou(p['bbox'],g['bbox']),pi,gi) for pi,p in enumerate(observed)
                       for gi,g in enumerate(expected) if category(p)==category(g)),reverse=True)
    for overlap,pi,gi in candidates:
        if overlap<threshold or pi in used or gi in matched:continue
        used.add(pi);matched.add(gi);pairs.append((pi,gi,overlap))
    for name in sorted({category(f) for f in expected+observed}):
        tp=sum(category(observed[i])==name for i in used)
        fp=sum(category(f)==name for i,f in enumerate(observed) if i not in used)
        fn=sum(category(f)==name for i,f in enumerate(expected) if i not in matched)
        metrics[name]={'true_positive':tp,'false_positive':fp,'false_negative':fn,
                       'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None}
    orientations=[]
    for pi,gi,_ in pairs:
        p,g=observed[pi],expected[gi]
        if category(g) in ('door','window','sliding door') and all(type(v.get('orientation_degrees')) in (int,float) for v in (p,g)):
            delta=abs(p['orientation_degrees']-g['orientation_degrees'])%180;orientations.append(min(delta,180-delta))
    return {'sample_size_plans':1,'annotation_split':annotations.get('split','unspecified'),
            'source_sha256':annotations['source_sha256'],'matching':'category-normalized greedy maximum IoU, one-to-one',
            'iou_threshold':threshold,'predicted_instances':len(observed),'annotated_instances':len(expected),'per_category':metrics,
            'mean_matched_bbox_iou':sum(v[2] for v in pairs)/len(pairs) if pairs else None,
            'opening_orientation_error_degrees':sum(orientations)/len(orientations) if orientations else None,
            'opening_orientation_sample_size':len(orientations),
            'conflicting_locations':len(reconcile(predictions)['review_issues']),
            'coverage_complete':predictions.get('coverage_complete'),
            'wall_boundary_error':None,'room_polygon_iou':None,'room_connections':None,
            'manual_correction_seconds':annotations.get('manual_correction_seconds'),
            'limitations':['Box IoU is not wall boundary or room polygon accuracy. Unimplemented geometry metrics remain null.',
                           'One plan is not representative. Keep development and held-out sets separate.']}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--predictions',type=Path,required=True)
    parser.add_argument('--annotations',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=evaluate(json.loads(args.predictions.read_text(encoding='utf-8')),json.loads(args.annotations.read_text(encoding='utf-8')))
    args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
