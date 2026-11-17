# MAPS · Wi-Fi Spatial Intelligence

**Version 0.3 — functioning synthetic demo + opt-in local hardware bridge**

A **local-first, authorization-required MVP** for RF attenuation tomography. Enter a private router IPv4 address, local hostname, or SSID; validate the identifier; import **spatially referenced and calibrated** Wi-Fi RSSI measurements; reconstruct and inspect a probabilistic obstruction heatmap in 2D/3D; export JSON/SVG. A separate, clearly labeled synthetic dataset lets you test the entire mapping pipeline.

> **Important:** Merely entering a router IP or SSID **cannot** reveal a building's actual floor plan. Browser JavaScript cannot retrieve CSI or low-level wireless samples from an arbitrary router. This MVP never probes router interfaces or third-party networks. It does not claim verified walls, doors, or room dimensions, and does not provide remote scanning or unauthorized access.

## Start here — try the demo without network access

1. Follow the instructions below to start FastAPI and Vite locally.
2. Open `http://127.0.0.1:5173`. The router input initially displays **`192.168.1.6` as an example identifier only**. No connection, authorization or network scan is implied.
3. Click **Run synthetic demo**. This calls `GET /api/demo/preview` with a separate `SYNTHETIC_DEMO_ONLY` identity. No router is contacted. Explore the 2D and 3D RF attenuation views, coverage, warnings, and survey targets.
4. Open **Signal Laboratory** for actual host hardware capability reporting and optional authorized captures. Open **Projects** to save/reopen reconstruction JSON locally; nothing auto-uploads to a cloud.

> The 3D model represents estimated radio attenuation, **not** literal walls or verified room boundaries. A router IP/SSID alone never yields a real floor plan.

## Preview features

- Responsive dark RF analysis dashboard with router input, explicit authorization, and honest status reporting.
- FastAPI identification and RF reconstruction endpoints.
- Calibrated-path RSSI attenuation baseline; sparse ray-grid intersection, nonnegative spatially regularized optimization.
- Measurement coverage, limited-observability checks, 20% holdout prediction error in dB, cell-level measurement support.
- 2D heatmap with sensor and ray overlays, 3D extruded attenuation grid with orbit camera.
- Real CSV/JSON measurement import; local SVG/JSON exports; included deterministic synthetic dataset.
- An opt-in Linux `iw` linked-AP RSSI **dBm capture adapter** (driver-dependent, manual coordinates and calibration), plus an `nmcli` diagnostic-only adapter. **CSI is not yet implemented.**
- Automated API/reconstruction tests.

## Start locally

**Prerequisites:** Python 3.11+, Node 20+, npm. From the repository root:

Terminal 1:

```bash
python -m venv .venv
source .venv/bin/activate # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
cd backend
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2:

```bash
cd frontend
npm install
npm run dev
```

Open **http://127.0.0.1:5173**. The frontend dev proxy forwards `/api` to `127.0.0.1:8000`. Do not expose the local MVP to the internet; it has no user authentication service or deployment hardening.

## Try the end-to-end demo

1. Enter `192.168.1.1` (only a **label** for this simulated session).
2. Check the authorization box for your own intended environment.
3. Click **Run synthetic demo**.
4. Explore simulated attenuation in 2D/3D, with support and quality metrics. It **does not** scan that address.

## Reconstruct an authorized measurement dataset

Prepare a CSV with columns:

```csv
tx_x,tx_y,rx_x,rx_y,rssi_dbm,baseline_dbm_at_1m,path_loss_exponent
2,2,10,6,-70,-40,2.1
```

- Coordinates are meters in the same surveyed coordinate system. For accuracy, positions need independent validation.
- Every row is an independently measured transmitter→receiver path. Do not paste fake RSSI values or use signal-strength percentage as dBm.
- `baseline_dbm_at_1m` and `path_loss_exponent` should be **calibrated per transmitter/environment**; the default values are placeholders.
- At least 24 paths are needed; considerably more, with multiple transmitters, spatially varied receivers, and crossing ray directions, are recommended.
- In the UI set the measurement area width/height, enable authorization, and import `.csv` or `.json` via **Import real measurements**.
- Missing coverage shows up as low measurement support. Holdout error measures how well the model predicts unseen link attenuation, **not architectural wall-position accuracy**.
- The mathematical inverse is underdetermined with sparse links, and the base model ignores frequency-dependent propagation, anisotropic materials, and time-varying interference. Validate predicted geometry with an actual survey.

### API

`POST /api/identify` validates a local identifier and returns `ready_to_map=false` because no compatible sensing agent is connected.

`POST /api/demo` generates an explicitly synthetic six-transmitter example, then runs the **same reconstruction engine** as real data.

`POST /api/reconstruct` accepts `{router_identifier, authorized, width_m, height_m, cell_size_m, samples, source:"measured"}`. View the full schema at `http://127.0.0.1:8000/docs`.

### Capture real RSSI on supported Linux hardware

With an already-associated Wi-Fi interface and `iw` installed, record a driver-reported RSSI measurement at a **physically surveyed** position:

```bash
python agent/iw_capture.py --interface wlan0 --ssid HomeNetwork \
  --tx-x 2 --tx-y 2 --rx-x 8 --rx-y 6 \
  --baseline-dbm-at-1m -40 --path-loss-exponent 2.1 \
  --output readings.csv
```

The agent prompts for authorization, reads the already-associated link without scanning, requires the exact SSID, and appends a measurement row. Position and calibration values must be measured independently. Repeat at many locations and, ideally, use multiple access points with known coordinates. This is an early capture adapter, not fully automatic mapping.

## Accuracy roadmap

1. **Hardware:** expand supported RSSI dBm driver adapters and add CSI adapters with reliable TX/RX position metadata. The included `iw` adapter reads real dBm from a currently associated link but still requires surveyed coordinates and calibrated propagation parameters; the `nmcli` diagnostic agent exposes percentage only.
2. **Ranging:** import supported RTT/Fine Timing Measurement, calibrated multi-antenna / Angle of Arrival inputs, or depth/visual-inertial data, when available.
3. **Calibration:** estimate path-loss model parameters from surveyed references; capture error distributions and phase stability where CSI exists.
4. **Geometry:** add physically justified priors, uncertain wall extraction and doorway hypothesis tools; visibly separate estimates from confirmed survey annotations.
5. **Validation:** evaluate reconstruction against ground-truth plans using held-out buildings, wall-intersection metrics, room-area error, and calibrated uncertainty, rather than prediction MAE alone.
6. **Productization:** encrypted local project storage, client authorization and hardware pairing, per-user permissions, audit trails, explicit retention settings, deployment security, hardware matrix and multi-floor workflows.

## Tests

```bash
pip install pytest httpx
cd backend
python -m pytest -q
cd ../frontend
npm run build
```

## Privacy & scope

- Only assess wireless infrastructure and buildings you own or have explicit permission to map.
- The API does not initiate IP scans, Wi-Fi association, credential guessing, router exploits, or packet interception.
- All inference remains an *attenuation hypothesis*. The 3D viewer displays extruded RF estimates, **not actual architecture**.
- Live CI or deployment does not demonstrate sensing capability; actual hardware integration remains future work.

## Repository

The project is maintained at https://github.com/afkpeery/maps. The frontend/backend test workflow is in `.github/workflows/check.yml`.

## License

MIT, see `LICENSE`.

## v0.2: calibration and measurement-quality improvements

- `POST /api/calibrate`: fits baseline dBm at 1 meter and the path-loss exponent using robust regression over **8+ clear-line-of-sight** reference readings. Reference CSV format: `distance_m,rssi_dbm,line_of_sight`. Readings must span at least three distances over a 2× range; calibration stays specific to hardware, frequency band and environment. This is not an automatic router-only capability.
- In `/api/reconstruct`, measurements from approximately the same physical ray are combined with a median instead of inflating spatial evidence. Large RSSI deviations in repeated groups (>=4 readings) can be rejected. Fewer than 24 distinct rays are rejected.
- A crossing-angle layer (0–6 orientation bins per grid cell) and spatial coverage candidates show where additional authorized measurements would improve evidence. Target coordinates are **suggested regions, not verified accessible rooms**.
- The signal laboratory now shows total vs. unique paths, outlier count, reference calibration residuals, angular diversity, and proposed low-evidence survey regions.
- Holdout prediction error continues to quantify RF-path fit only, not accuracy against architectural ground truth. Repeated packets from one path do not leak into training and validation sets as independent links.

### Calibrate via API

```bash
curl -X POST http://127.0.0.1:8000/api/calibrate \
  -H 'Content-Type: application/json' \
  -d '{"identifier":"HomeNetwork","authorized":true,"samples":[{"distance_m":1,"rssi_dbm":-40},{"distance_m":1.5,"rssi_dbm":-44},{"distance_m":2,"rssi_dbm":-46},{"distance_m":3,"rssi_dbm":-50},{"distance_m":4,"rssi_dbm":-52},{"distance_m":6,"rssi_dbm":-56},{"distance_m":8,"rssi_dbm":-58},{"distance_m":10,"rssi_dbm":-60}]}'
```

The returned coefficients can be used for missing values in imported readings via the frontend calibration action; supplied per-row coefficients take precedence. Use genuine reference measurements, not the example values above.


## Phase 3 — functioning hardware integration architecture

- `GET /api/demo/preview` offers an authorization-free **synthetic** demo, entirely isolated from any real router identifier or sensor.
- `GET /api/hardware/capabilities` reports whether the **local backend host** can run the Linux `iw` associated-link adapter. CSI is explicitly marked unimplemented.
- `POST /api/hardware/capture` reads the current Linux associated Wi-Fi link RSSI in dBm, with explicit authorization, an opt-in environment flag and a 20+ character local token; optionally checks the specific BSSID to guard against mesh/AP roaming.
- **Signal Laboratory** now has adapter status, surveyed-coordinate entry, token-protected capture, locally accumulated readings, CSV export and measurement-based reconstruction.
- **Projects** supports explicit local JSON save/reopen; no background cloud sync or storage of capture tokens.
- The initial router field now displays `192.168.1.6` solely as a **non-connected example**, while the one-click synthetic demo always uses `SYNTHETIC_DEMO_ONLY`.

See [Hardware integration](docs/HARDWARE_INTEGRATION.md) for setup, security boundaries and REST API, and [Accuracy & validation](docs/ACCURACY_VALIDATION.md) for what can/cannot be claimed from RSSI.

### Hardware quickstart (Linux, local only)

```bash
# Set these on the computer with an already-connected supported Wi-Fi interface:
export MAPS_ENABLE_LOCAL_CAPTURE=1
export MAPS_HARDWARE_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
# Keep this token secret; paste it only in your own local MAPS Signal Laboratory.
cd backend
uvicorn app:app --host 127.0.0.1 --port 8000
```

Run the Vite frontend separately as above. Do not expose this API publicly. The existing CLI `agent/iw_capture.py` remains an alternative workflow.

**This is a testable research MVP, not a fully deployed device-agnostic Wi-Fi tomography product.** 3D architectural wall recognition, CSI integration, automated router login, multi-floor mapping and verified dimension estimates are still outstanding.
