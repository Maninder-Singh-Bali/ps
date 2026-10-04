"""Explicit copy-only draft migration; original workspace stays recoverable."""
import argparse,hashlib,json,shutil
from pathlib import Path

def migrate(source,destination):
    source=Path(source).resolve();destination=Path(destination).resolve()
    if not source.is_dir():raise ValueError('Source draft folder is missing.')
    if destination.exists():raise ValueError('Choose a NEW destination. Existing workspaces are never overwritten.')
    if source==destination or source in destination.parents:raise ValueError('Choose a separate destination.')
    files=[p for p in source.rglob('*') if p.is_file()]
    if any(p.is_symlink() for p in source.rglob('*')):raise ValueError('Resolve symlinks explicitly before copying a draft workspace.')
    manifest={str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    shutil.copytree(source,destination)
    for name,sha in manifest.items():
        if hashlib.sha256((destination/name).read_bytes()).hexdigest()!=sha:raise ValueError('Copy verification failed: '+name)
    report={'source':str(source),'destination':str(destination),'files':manifest,'mode':'copy; originals retained','rollback':'Stop the local dashboard and relaunch with --drafts pointing at the original source.'}
    (destination/'workspace-copy.json').write_text(json.dumps(report,indent=2));return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('destination');a=p.parse_args();r=migrate(a.source,a.destination);print('Verified',len(r['files']),'files. Original workspace unchanged.')
