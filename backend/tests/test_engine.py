import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))

from fastapi.testclient import TestClient
from app import app
from demo import make_demo
from reconstruction import reconstruct

client = TestClient(app)


def test_authorization_required():
    r = client.post('/api/identify', json={'identifier': '192.168.1.1', 'authorized': False})
    assert r.status_code == 403


def test_no_ip_to_floorplan_claim():
    r = client.post('/api/identify', json={'identifier': '192.168.1.1', 'authorized': True})
    assert r.status_code == 200
    assert r.json()['ready_to_map'] is False
    assert r.json()['verified'] is False


def test_public_target_rejected():
    r = client.post('/api/identify', json={'identifier': '8.8.8.8', 'authorized': True})
    assert r.status_code == 422


def test_demo_is_explicitly_simulated():
    r = client.post('/api/demo', json={'identifier': '192.168.1.1', 'authorized': True})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j['source'] == 'simulated'
    assert j['measurements'] >= 200
    assert j['nx'] == len(j['attenuation'][0])
    assert j['ny'] == len(j['attenuation'])
    assert j['holdout_mae_db'] is not None
    assert 0 <= j['coverage_pct'] <= 100


def test_out_of_bounds_measurements():
    request = make_demo()
    request.samples[0].tx_x = 50
    try:
        reconstruct(request)
        assert False, 'expected rejection'
    except ValueError as exc:
        assert 'outside' in str(exc)


def test_ssid_and_local_hostname():
    for target in ['HomeNetwork', 'router.local']:
        assert client.post('/api/identify', json={'identifier': target, 'authorized': True}).status_code == 200


def test_single_transmitter_is_quality_flagged():
    request = make_demo()
    request.samples = [s for s in request.samples if s.tx_x == 2 and s.tx_y == 2]
    result = reconstruct(request)
    assert result.spatially_observable is False
    assert any('one transmitter' in w for w in result.warnings)


def test_no_reconstruction_without_authorization():
    request = make_demo()
    request.authorized = False
    try:
        reconstruct(request)
        assert False, 'expected denial'
    except PermissionError:
        pass
