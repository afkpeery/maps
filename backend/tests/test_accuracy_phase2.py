"""Regression checks for calibration and independent wireless path support."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from fastapi.testclient import TestClient
from app import app
from demo import make_demo
from reconstruction import reconstruct

client=TestClient(app)

def test_calibration_regression():
    from math import log10
    rows=[{"distance_m":d,"rssi_dbm":-41-22*log10(d)} for d in [1,1.5,2,2.5,3,4,6,8,10,13]]
    response=client.post("/api/calibrate",json={"identifier":"HomeNetwork","authorized":True,"samples":rows})
    assert response.status_code==200,response.text
    obj=response.json()
    assert abs(obj["baseline_dbm_at_1m"]+41)<.05
    assert abs(obj["path_loss_exponent"]-2.2)<.05

def test_calibration_authorization_and_range():
    rows=[{"distance_m":2,"rssi_dbm":-50} for _ in range(8)]
    assert client.post("/api/calibrate",json={"identifier":"HomeNetwork","authorized":False,"samples":rows}).status_code==403
    assert client.post("/api/calibrate",json={"identifier":"HomeNetwork","authorized":True,"samples":rows}).status_code==422

def test_repeats_do_not_increase_independent_links():
    request=make_demo()
    original=len(request.samples)
    first=request.samples[0]
    request.samples.extend([first.model_copy(update={"rssi_dbm":first.rssi_dbm+x}) for x in [0,.2,-.2,.3]])
    request.samples.append(first.model_copy(update={"rssi_dbm":-123}))
    result=reconstruct(request)
    assert result.measurements==original+5
    assert result.unique_paths==original
    assert result.outliers_rejected>=1
    assert len(result.survey_targets)>0
    assert len(result.angular_diversity)==result.ny

def test_repeated_single_ray_rejected():
    request=make_demo()
    request.samples=[request.samples[0]]*30
    try:
        reconstruct(request)
        assert False, "should reject duplicate geometry"
    except ValueError as ex:
        assert "geometrically distinct" in str(ex)
