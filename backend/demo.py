"""Reproducible SYNTHETIC test geometry. Never claim this is a building scan."""
from math import hypot, log10
import numpy as np
from models import Measurement, ReconstructionRequest


def _crosses_wall(ax, ay, bx, by, wall):
    x1, y1, x2, y2 = wall
    if x1 == x2:
        if abs(bx - ax) < 1e-8: return False
        t = (x1 - ax) / (bx - ax)
        return 0 < t < 1 and min(y1, y2) <= ay + t * (by - ay) <= max(y1, y2)
    if abs(by - ay) < 1e-8: return False
    t = (y1 - ay) / (by - ay)
    return 0 < t < 1 and min(x1, x2) <= ax + t * (bx - ax) <= max(x1, x2)


def make_demo(router_identifier: str = "DEMO_NETWORK") -> ReconstructionRequest:
    rng = np.random.default_rng(2030)
    width, height = 24., 16.
    # A deliberately simple simulated building with doorway gaps.
    walls = [
        (8, 0, 8, 5), (8, 7, 8, 16),
        (16, 0, 16, 9), (16, 11, 16, 16),
        (0, 8, 3, 8), (5, 8, 12, 8), (14, 8, 24, 8),
    ]
    txs = [(2, 2), (12, 2), (22, 2), (2, 14), (12, 14), (22, 14)]
    rxs = [(float(x), float(y)) for x in [1, 4, 7, 10, 13, 16, 19, 23] for y in [1, 4, 7, 10, 13, 15]]
    samples = []
    for tx_x, tx_y in txs:
        for rx_x, rx_y in rxs:
            d = hypot(tx_x - rx_x, tx_y - rx_y)
            if d < 0.5: continue
            hits = sum(_crosses_wall(tx_x, tx_y, rx_x, rx_y, w) for w in walls)
            expected = -40 - 21 * log10(max(1, d))
            measured = expected - 5.5 * hits + rng.normal(0, 0.8)
            samples.append(Measurement(tx_x=tx_x, tx_y=tx_y, rx_x=rx_x, rx_y=rx_y,
                                       rssi_dbm=round(float(measured), 2), baseline_dbm_at_1m=-40,
                                       path_loss_exponent=2.1))
    return ReconstructionRequest(router_identifier=router_identifier, authorized=True,
                                 width_m=width, height_m=height, cell_size_m=.75,
                                 samples=samples, source="simulated")
