"""Robust line-of-sight RSSI path-loss calibration for authorized measurements."""
from __future__ import annotations
import numpy as np
from models import CalibrationRequest, CalibrationResponse

def calibrate(req: CalibrationRequest) -> CalibrationResponse:
    if not req.authorized:
        raise PermissionError("Calibration requires explicit authorization.")
    samples = [s for s in req.samples if s.line_of_sight]
    if len(samples) < 8:
        raise ValueError("Collect at least eight unobstructed reference measurements.")
    distance = np.array([s.distance_m for s in samples], dtype=float)
    if len(np.unique(np.round(distance, 2))) < 3 or distance.max()/distance.min() < 2:
        raise ValueError("Use at least three distinct distances across a 2x range.")
    observed = np.array([s.rssi_dbm for s in samples], dtype=float)
    design = np.column_stack([np.ones(len(samples)), -10*np.log10(distance)])
    coeff = np.linalg.lstsq(design, observed, rcond=None)[0]
    for _ in range(15):
        residual = observed - design @ coeff
        scale = max(.8, np.median(np.abs(residual-np.median(residual)))*1.4826)
        weight = np.minimum(1., 1.5*scale/np.maximum(np.abs(residual), 1.e-8))
        next_coeff = np.linalg.lstsq(design*np.sqrt(weight[:,None]), observed*np.sqrt(weight), rcond=None)[0]
        if np.max(np.abs(next_coeff-coeff)) < 1.e-5:
            coeff = next_coeff
            break
        coeff = next_coeff
    baseline, exponent = map(float, coeff)
    if not (-100 <= baseline <= 0 and 1 <= exponent <= 6):
        raise ValueError("Implausible path-loss calibration; check references.")
    mae = float(np.median(np.abs(observed-design@coeff)))
    warnings = ["Calibration is specific to hardware, frequency band and environment."]
    if mae > 3:
        warnings.append("Large residual variation; collect more stationary reference measurements.")
    return CalibrationResponse(baseline_dbm_at_1m=round(baseline,2),
        path_loss_exponent=round(exponent,3), samples_used=len(samples),
        median_abs_error_db=round(mae,2), warnings=warnings,
        model_description="Robust log-distance RSSI regression using line-of-sight measurements.")
