"""Verify transport against an existing completed job; never submit a render."""
import argparse
import hashlib
import io
import json
import platform
from pathlib import Path

import requests
from PIL import Image
from remote_processing import Client
from worker_protocol import contract


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--remote-config', required=True)
    parser.add_argument('--job', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    client = Client(args.remote_config)
    status = client.get('/v1/status')
    expected = contract(Path(__file__).parent)
    assert all(status[k] == expected[k] for k in ('protocol', 'workflow'))
    job = client.get('/v1/jobs/' + args.job)
    assert job['status'] == 'completed', 'Only a completed historical job is allowed'
    history = client.get('/v1/jobs/' + args.job + '/result')
    checks = {}
    anonymous = requests.Session()
    anonymous.trust_env = False
    anonymous.verify = client.session.verify
    for route in ('/v1/status', '/v1/nodes', '/v1/jobs/' + args.job,
                  '/v1/outputs/' + next(iter(job['outputs']))):
        code = anonymous.get(client.url + route, timeout=10).status_code
        assert code == 403, (route, code)
        checks[route] = code
    browser = client.session.get(client.url + '/v1/status',
                                 headers={'Origin': 'http://127.0.0.1:8777'}, timeout=10)
    assert browser.status_code == 403
    data = io.BytesIO()
    Image.new('RGB', (8, 8), (23, 47, 89)).save(data, format='PNG')
    raw = data.getvalue()
    uploads = [client.request('POST', '/v1/inputs', data=raw,
               headers={'Content-Type': 'application/octet-stream'}).json() for _ in range(2)]
    assert uploads[0] == uploads[1] == {'id': hashlib.sha256(raw).hexdigest()}
    outputs = {}
    for aid, info in job['outputs'].items():
        raw = client.request('GET', '/v1/outputs/' + aid).content
        assert hashlib.sha256(raw).hexdigest() == aid
        assert len(raw) == info['bytes']
        (out / (aid + '.png')).write_bytes(raw)
        outputs[aid] = {'bytes': len(raw), 'checksum_verified': True}
    fresh = Client(args.remote_config).get('/v1/jobs/' + args.job)
    assert (fresh['prompt_id'], fresh['attempts']) == (job['prompt_id'], job['attempts'])
    result = dict(platform=platform.platform(), python=platform.python_version(),
                  status=status, job=job, unauthenticated=checks,
                  browser_origin_rejected=True, input_transfer_deduplicated=True,
                  outputs=outputs, fresh_client_reconnected=True,
                  new_inference_submissions=0, live_progress_tested=False,
                  progress_scope='Persisted progress of the completed checkpoint job')
    (out / 'connection.json').write_text(json.dumps(result, indent=2))
    (out / 'history.json').write_text(json.dumps(history, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
