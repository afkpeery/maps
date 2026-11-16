"""Robust clear-line-of-sight log-distance calibration (not wall estimation)."""
from __future__ import annotations
from math import log10
import numpy as np
from models import CalibrationRequest, CalibrationResponse


def calibrate(req: CalibrationRequest) -> CalibrationResponse:
    if not req.authorized:
        raise PermissionError('Calibration requires explicit authorization.')
    samples = [s for s in req.samples if s.line_of_sight]
    if len(samples) < 8:
        raise ValueError('Collect at least eight unobstructed reference measurements.')
    distances = np.asarray([s.distance_m for s in samples], dtype=float)
    if len(np.unique(np.round(distances, 2))) < 3 or distances.max() / distances.min() < 2:
        raise ValueError('Reference distances must include at least three values spanning a 2× range.')
    y = np.asarray([s.rssi_dbm for s in samples], dtype=float)
    X = np.column_stack((np.ones(len(samples)), -10 * np.log10(distances)))
    coefficients = np.linalg.lstsq(X, y, rcond=None)[0]
    for _ in range(15):
        residuals = y - X @ coefficients
        scale = max(0.8, float(np.median(np.abs(residuals - np.median(residuals)))) * 1.4826)
        weights = np.minimum(1.0, 1.5 * scale / np.maximum(np.abs(residuals), 1e-8))
        next_coefficients = np.linalg.lstsq(X * np.sqrt(weights[:, None]), y * np.sqrt(weights), rcond=None)[0]
        if np.max(np.abs(next_coefficients - coefficients)) < 1e-5:
            break
        coefficients = next_coefficients
    baseline, exponent = map(float, coefficients)
    if not (-100 <= baseline <= 0 and 1 <= exponent <= 6):
        raise ValueError('Fitted calibration is physically implausible; inspect measurements and reference conditions.')
    error = float(np.median(np.abs(y - X @ coefficients)))
    warnings = []
    if error > 3:
        warnings.append('High residual variation; repeat references while radios and surroundings are stationary.')
    if len(samples) < len(req.samples):
        warnings.append('Obstructed references were ignored; only line-of-sight samples were fitted.')
    warnings.append('Calibration is hardware, band and environment specific; repeat when these change.')
    return CalibrationResponse(baseline_dbm_at_1m=round(baseline, 2), path_loss_exponent=round(exponent, 3),
        samples_used=len(samples), median_abs_error_db=round(error, 2), warnings=warnings,
        model_description='Huber-style robust regression on line-of-sight RSSI = baseline - 10 n log10(distance).')
