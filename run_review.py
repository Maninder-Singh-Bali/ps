"""Synthetic-only review workspace; never reads client data."""
from pathlib import Path
from server import make_server
from review_fixtures import seed_geometry
ROOT=Path(__file__).resolve().parent
http=make_server(ROOT/'validation-artifacts/review-data',8789,start_worker=False)
seed_geometry(http.store,ROOT/'validation-artifacts/geometry-demo')
import threading
threading.Thread(target=http.engine.worker,daemon=True,name='Studio review jobs').start()
print('Synthetic review at http://127.0.0.1:8789',flush=True)
try:http.serve_forever()
finally:http.engine.stop.set();http.server_close()
