"""Windowless PC entry point; configuration is outside the source deployment."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from background_runtime import logs
import json
c=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
sys.stdout=sys.stderr=logs(Path(c['private_dir'])/'logs')
from worker_service import serve
try:serve(sys.argv[1])
except Exception:
    import traceback
    traceback.print_exc()
