"""Baseline regularized RF tomography using spatially located RSSI links.

Not architectural ground truth. Assumes calibrated, stationary power and a log-distance
path-loss model; inference should not be trusted where cross-link coverage is poor.
"""
from __future__ import annotations

from collections import defaultdict
from math import ceil, hypot, log10
import numpy as np
from scipy import sparse

from models import Measurement, ReconstructionRequest, ReconstructionResponse, SurveyTarget


def _ray_weights(x0: float, y0: float, x1: float, y1: float, nx: int, ny: int, cw: float, ch: float):
    """Approximate path lengths per cell using sub-cell midpoint quadrature."""
    d = hypot(x1 - x0, y1 - y0)
    if d < 0.01:
        return {}
    steps = max(1, ceil(d / (min(cw, ch) / 3)))
    length = d / steps
    result: dict[int, float] = {}
    for i in range(steps):
        t = (i + 0.5) / steps
        x, y = x0 + t * (x1 - x0), y0 + t * (y1 - y0)
        ix, iy = int(x / cw), int(y / ch)
        if 0 <= ix < nx and 0 <= iy < ny:
            cell = iy * nx + ix
            result[cell] = result.get(cell, 0) + length
    return result


def _system(req: ReconstructionRequest):
    nx = ceil(req.width_m / req.cell_size_m)
    ny = ceil(req.height_m / req.cell_size_m)
    if nx * ny > 6400:
        raise ValueError("Grid is too fine. Increase the cell size.")
    cw, ch = req.width_m / nx, req.height_m / ny
    rows, cols, vals, b = [], [], [], []
    for index, sample in enumerate(req.samples):
        positions = (sample.tx_x, sample.tx_y, sample.rx_x, sample.rx_y)
        if not (0 <= positions[0] <= req.width_m and 0 <= positions[2] <= req.width_m
                and 0 <= positions[1] <= req.height_m and 0 <= positions[3] <= req.height_m):
            raise ValueError(f"Measurement {index + 1} is outside the specified mapping area.")
        weights = _ray_weights(*positions, nx, ny, cw, ch)
        for cell, length in weights.items():
            rows.append(index)
            cols.append(cell)
            vals.append(length)
        distance = max(1.0, hypot(sample.tx_x - sample.rx_x, sample.tx_y - sample.rx_y))
        expected = sample.baseline_dbm_at_1m - 10 * sample.path_loss_exponent * log10(distance)
        b.append(max(0, expected - sample.rssi_dbm))
    A = sparse.coo_matrix((vals, (rows, cols)), shape=(len(req.samples), nx * ny)).tocsr()
    return A, np.array(b, dtype=float), nx, ny, cw, ch


def _laplacian(nx: int, ny: int):
    """First-order spatial smoothing via grid-neighbor differences."""
    r, c, v, idx = [], [], [], 0
    for y in range(ny):
        for x in range(nx):
            current = y * nx + x
            for other in ([current + 1] if x + 1 < nx else []) + ([current + nx] if y + 1 < ny else []):
                r.extend([idx, idx]); c.extend([current, other]); v.extend([1., -1.]); idx += 1
    return sparse.coo_matrix((v, (r, c)), shape=(idx, nx * ny)).tocsr()


def _fit(A: sparse.csr_matrix, b: np.ndarray, nx: int, ny: int, epochs: int = 180):
    """Projected accelerated-gradient minimization of a regularized least squares objective."""
    D = _laplacian(nx, ny)
    n = A.shape[1]
    lam_smooth, lam_ridge = 0.24, 0.12
    gram = (A.T @ A + lam_smooth * (D.T @ D) + lam_ridge * sparse.eye(n)).tocsr()
    target = np.asarray(A.T @ b).ravel()
    seed = np.ones(n, dtype=float) / np.sqrt(n)
    eigenvalue = 1.
    for _ in range(24):
        t = gram @ seed
        norm = np.linalg.norm(t)
        if norm == 0: break
        seed = t / norm
        eigenvalue = float(seed @ (gram @ seed))
    step = 0.9 / max(eigenvalue, 1e-8)
    x = np.zeros(n, dtype=float)
    y = x.copy()
    acceleration = 1.
    for _ in range(epochs):
        new_x = np.maximum(0, y - step * ((gram @ y) - target))
        new_acc = (1 + np.sqrt(1 + 4 * acceleration * acceleration)) / 2
        y = new_x + ((acceleration - 1) / new_acc) * (new_x - x)
        x, acceleration = new_x, new_acc
    return x




def _aggregate_samples(req: ReconstructionRequest) -> tuple[list[Measurement], int]:
    """Prevent packet bursts on one geometry from counting as independent ray paths.

    Near-identical links are combined by median. Gross RSSI outliers are excluded
    only for groups with >= 4 repeats (otherwise evidence is insufficient).
    """
    groups: dict[tuple, list[Measurement]] = defaultdict(list)
    for i, sample in enumerate(req.samples):
        if not (0 <= sample.tx_x <= req.width_m and 0 <= sample.rx_x <= req.width_m
                and 0 <= sample.tx_y <= req.height_m and 0 <= sample.rx_y <= req.height_m):
            raise ValueError(f"Measurement {i + 1} is outside the specified mapping area.")
        key = (round(sample.tx_x, 1), round(sample.tx_y, 1),
               round(sample.rx_x, 1), round(sample.rx_y, 1), sample.label or '',
               round(sample.baseline_dbm_at_1m, 2), round(sample.path_loss_exponent, 3))
        groups[key].append(sample)
    unique, rejected = [], 0
    for samples in groups.values():
        levels = np.array([s.rssi_dbm for s in samples], dtype=float)
        if len(levels) >= 4:
            median = np.median(levels)
            mad = np.median(np.abs(levels - median))
            allowed = np.abs(levels - median) <= max(4., 3.5 * mad * 1.4826)
            rejected += int((~allowed).sum())
            levels = levels[allowed]
        item = samples[0].model_copy(update={'rssi_dbm': float(np.median(levels))})
        unique.append(item)
    return unique, rejected


def _angle_support(A: sparse.csr_matrix, samples: list[Measurement], cells: int) -> np.ndarray:
    """Independent crossing-angle bins per cell (six orientations over 180°)."""
    bins = [set() for _ in range(cells)]
    for i, sample in enumerate(samples):
        angle = float(np.arctan2(sample.rx_y-sample.tx_y, sample.rx_x-sample.tx_x) % np.pi)
        sector = min(5, int(angle / np.pi * 6))
        for cell in A.indices[A.indptr[i]:A.indptr[i+1]]:
            bins[cell].add(sector)
    return np.array([len(b) for b in bins], dtype=int)


def _survey_targets(support: np.ndarray, diversity: np.ndarray, nx: int, ny: int,
                    cw: float, ch: float, limit: int = 5) -> list[SurveyTarget]:
    """Candidate low-evidence zones, NOT guaranteed traversable receiver locations."""
    chosen = []
    # Bias toward missing paths and poor angular variety, then deterministic order.
    candidates = sorted(range(len(support)), key=lambda i:(int(support[i]), int(diversity[i]), i))
    for cell in candidates:
        x, y = (cell % nx + .5) * cw, (cell // nx + .5) * ch
        if any(hypot(x-t.x_m, y-t.y_m) < max(2., 3*max(cw,ch)) for t in chosen):
            continue
        chosen.append(SurveyTarget(x_m=round(x,2), y_m=round(y,2), support=int(support[cell]),
            angular_bins=int(diversity[cell]),
            reason='Target low-coverage zone from several different directions; verify access and coordinates.'))
        if len(chosen) >= limit:
            break
    return chosen

def reconstruct(req: ReconstructionRequest) -> ReconstructionResponse:
    if not req.authorized:
        raise PermissionError("Mapping requires explicit network and building authorization.")
    unique, rejected = _aggregate_samples(req)
    if len(unique) < 24:
        raise ValueError('At least 24 geometrically distinct radio paths are required; repeated packets do not count.')
    fit_req = req.model_copy(update={'samples': unique})
    A, b, nx, ny, cw, ch = _system(fit_req)
    if A.nnz == 0:
        raise ValueError("No valid radio paths are present.")
    tx = {(round(s.tx_x, 1), round(s.tx_y, 1)) for s in unique}
    rx = {(round(s.rx_x, 1), round(s.rx_y, 1)) for s in unique}
    # Distinct positions and crossing paths matter more than packet count alone.
    coverage = np.asarray((A > 0).sum(axis=0)).ravel()
    diversity = _angle_support(A, unique, nx * ny)
    coverage_pct = float((coverage >= 3).mean() * 100)
    angles = set()
    for s in unique:
        dx, dy = s.rx_x - s.tx_x, s.rx_y - s.tx_y
        angles.add(round((np.arctan2(dy, dx) % np.pi) / np.pi * 12))
    observable = len(tx) >= 2 and len(rx) >= 8 and len(angles) >= 4 and coverage_pct >= 30
    warnings = []
    if len(tx) < 2:
        warnings.append("Only one transmitter position: wall reconstruction is highly ambiguous.")
    if len(rx) < 8:
        warnings.append("Too few receiver locations; collect more spatially distributed readings.")
    if len(angles) < 4:
        warnings.append("Insufficient crossing angles; move receivers around different sides of the space.")
    if coverage_pct < 45:
        warnings.append("Low ray coverage; unobserved areas are not reliable.")
    if len(req.samples) > len(unique):
        warnings.append(f"Aggregated {len(req.samples)} readings into {len(unique)} distinct radio paths; repeats do not add spatial coverage.")
    if rejected:
        warnings.append(f"Rejected {rejected} anomalous RSSI readings within repeated-path groups.")
    if float((diversity >= 2).mean()) < .3:
        warnings.append('Limited crossing-angle diversity in most cells; proposed barriers are ambiguous.')
    if req.source == "measured":
        warnings.append("Results are RF attenuation estimates, not validated architectural walls. Calibrate radio path-loss parameters.")
    # Fixed holdout split for reproducibility. Avoid holdout on tiny datasets.
    indices = np.arange(len(b))
    hold = indices[::5] if len(b) >= 35 else np.array([], dtype=int)
    train_mask = np.ones(len(b), dtype=bool)
    train_mask[hold] = False
    x = _fit(A[train_mask], b[train_mask], nx, ny)
    mae = float(np.mean(np.abs(A[hold] @ x - b[hold]))) if len(hold) else None
    # Coverage alone is not statistically calibrated confidence; explicitly label as support.
    confidence = np.minimum(1., coverage / 12.) * np.minimum(1., diversity / 3.)
    if mae is not None:
        confidence *= np.exp(-mae / 22.0)
    confidence = np.minimum(1, confidence)
    # Remove numerical fuzz and suppress unsupported cells.
    x[coverage < 2] = 0.
    attenuation = np.round(x.reshape(ny, nx), 3).tolist()
    conf = np.round(confidence.reshape(ny, nx), 3).tolist()
    rays = [dict(tx_x=s.tx_x, tx_y=s.tx_y, rx_x=s.rx_x, rx_y=s.rx_y) for s in unique[:160]]
    return ReconstructionResponse(
        source=req.source, router_identifier=req.router_identifier, nx=nx, ny=ny,
        width_m=req.width_m, height_m=req.height_m, cell_width_m=cw, cell_height_m=ch,
        attenuation=attenuation, confidence=conf, angular_diversity=diversity.reshape(ny,nx).tolist(),
        obstruction_threshold=1.4,
        measurements=len(req.samples), unique_paths=len(unique), outliers_rejected=rejected, transmitter_positions=len(tx), receiver_positions=len(rx),
        coverage_pct=round(coverage_pct, 1), holdout_mae_db=round(mae, 2) if mae is not None else None,
        spatially_observable=observable, warnings=warnings,
        survey_targets=_survey_targets(coverage,diversity,nx,ny,cw,ch), rays=rays,
        model_description="Nonnegative, spatially regularized RSSI attenuation tomography; confidence visualizes unique-ray and crossing-angle support, not a calibrated accuracy probability."
    )
