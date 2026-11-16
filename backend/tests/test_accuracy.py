"""Regression tests for calibration, duplicate robustness and uncertainty signals."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))

from fastapi.testclient import TestClient
from app import app
from calibration import calibrate
from demo import make_demo
from models import CalibrationRequest, ReconstructionRequest
from reconstruction import reconstruct

client = TestClient(app)


def test_calibration_recovers_known_propagation():
    import math
    samples = [{'distance_m':d,'rssi_dbm':-41-22*math.log10(d),'line_of_sight':True}
               for d in [1,1.5,2,2.5,3,4,6,8,10,13]]
    response = client.post('/api/calibrate', json={'identifier':'HomeNetwork','authorized':True,'samples':samples})
    assert response.status_code == 200, response.text
    result = response.json()
    assert abs(result['baseline_dbm_at_1m'] + 41) < .05
    assert abs(result['path_loss_exponent'] - 2.2) < .05
    assert result['median_abs_error_db'] < .05


def test_calibration_requires_distances_and_authorization():
    rows=[{'distance_m':2,'rssi_dbm':-52} for _ in range(8)]
    assert client.post('/api/calibrate',json={'identifier':'HomeNet','authorized':False,'samples':rows}).status_code==403
    response=client.post('/api/calibrate',json={'identifier':'HomeNet','authorized':True,'samples':rows})
    assert response.status_code==422


def test_grouping_deweights_repeats_and_rejects_rssi_outlier():
    request = make_demo()
    source=request.samples[0]
    normal=[source.model_copy(update={'rssi_dbm':source.rssi_dbm+n}) for n in [-.3,0,.4,.1]]
    bad=source.model_copy(update={'rssi_dbm':-122.})
    request.samples.extend(normal+[bad])
    result=reconstruct(request)
    assert result.unique_paths == len(make_demo().samples)
    assert result.measurements == len(make_demo().samples)+5
    assert result.outliers_rejected >= 1
    assert result.holdout_mae_db is not None
    assert len(result.angular_diversity)==result.ny
    assert all(0<=d<=6 for row in result.angular_diversity for d in row)
    assert len(result.survey_targets) >= 1
    assert all(t.support >= 0 for t in result.survey_targets)


def test_repeated_single_path_not_falsely_qualified():
    request=make_demo()
    request.samples=[request.samples[0].model_copy(update={'rssi_dbm':-50.}) for _ in range(30)]
    try:
        reconstruct(request)
        assert False, 'expected geometric diversity rejection'
    except ValueError as exc:
        assert 'geometrically distinct' in str(exc)


def test_negative_or_missing_real_permissions():
    demo=make_demo()
    demo.authorized=False
    assert client.post('/api/reconstruct',json=demo.model_dump()).status_code == 403
