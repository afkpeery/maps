# MAPS reconstruction accuracy — evidence standards

MAPS v0.3 implements RF attenuation **hypotheses** via calibrated RSSI ray reconstruction. It is **not** a validated architectural floorplan detector. The 3D view extrudes inferred attenuation cells and is not proof of wall geometry, floor height or room dimensions.

## Required experimental protocol for higher accuracy

1. **Measure site geometry independently.** Survey physical bounds, transmitter (and ideally AP BSSID) positions, and receiver trajectories/positions, with uncertainty for each.
2. **Calibrate each device/environment.** Collect 8+ LOS distance–RSSI pairs over several distances; repeat across time/channel conditions. Record chipset/firmware, band, channel, antenna orientation and baseline drift.
3. **Prevent false evidence.** Aggregate repeated packets for the same Tx/Rx geometry, hold out independent geometry rather than only random packets, and reject obvious outliers. Repeated readings are not independent paths.
4. **Use crossing paths.** A collection of many paths from a single static AP does not uniquely localize walls. Use spatially separated APs/receivers and angular diversity. If geometry is insufficient, return observability warnings and survey suggestions, not a fabricated floorplan.
5. **Ground-truth benchmark.** Evaluate against multiple authorized buildings with known plans not used in training. Track surveyed-wall precision/recall and displacement in meters, room-area error, calibrated uncertainty coverage, and performance by building material/band/device.
6. **Detect distribution shifts.** Metal ducts, moving people, floor slabs, furniture, neighboring APs, multi-AP SSIDs, orientation, and hardware changes can alter RSSI substantially.
7. **Report confidence honestly.** Current cell-level 'confidence' denotes support/regularization heuristics, not a calibrated probability that a wall exists. Holdout RSSI mean absolute error is not a wall-location error metric.
8. **Only claim outcomes actually measured.** The synthetic demo's known layout is for illustrating the engine, not an estimate of an unknown building. CSI, Wi-Fi FTM/RTT, visual SLAM, depth cameras and LiDAR can be added when appropriate hardware and validation are available.

## Current gates and non-goals

- Hardware capture: opt-in, same-host, already-associated Linux `iw` RSSI **dBm** only.
- Reconstruction: at least 24 readings and sufficient distinct path geometry; status/coverage/angular support/holdout error included; several metadata limitations remain.
- No router-IP-only location inference, no unauthorized Wi-Fi discovery, no architectural confirmation, no verified wall/door recognition, no multi-floor reconstruction.

## Roadmap

- Device-specific calibration profiles, recording independent measurement errors and per-device drift.
- CSI plugin with calibrated amplitude/phase, band/MIMO capture and cross-device timing where supported.
- Verified ranging/positioning and sensor fusion using surveyed landmarks, robot or phone odometry with opt-in local sensors.
- RF / architectural cross-validation on held-out buildings with material- and device-specific uncertainty.
- Optional dimensional geometry editing with explicit **user-verified** vs **model-estimated** boundaries.
