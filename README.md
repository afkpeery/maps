# MAPS · Wi-Fi Spatial Intelligence

A **local-first, authorization-required MVP** for RF attenuation tomography. Enter a private router IPv4 address, local hostname, or SSID; validate the identifier; import **spatially referenced and calibrated** Wi-Fi RSSI measurements; reconstruct and inspect a probabilistic obstruction heatmap in 2D/3D; export JSON/SVG. A separate, clearly labeled synthetic dataset lets you test the entire mapping pipeline.

> **Important:** Merely entering a router IP or SSID **cannot** reveal a building's actual floor plan. Browser JavaScript cannot retrieve CSI or low-level wireless samples from an arbitrary router. This MVP never probes router interfaces or third-party networks. It does not claim verified walls, doors, or room dimensions, and does not provide remote scanning or unauthorized access.

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

## Push into the new GitHub repo named `maps`

Create an **empty** repository named `maps` in GitHub first (do not initialize it with a README). Then run from the extracted `maps/` directory:

```bash
git init -b main
git add .
git commit -m "Initial MAPS RF reconstruction MVP"
git remote add origin https://github.com/YOUR_USERNAME/maps.git
git push -u origin main
```

If your GitHub account uses HTTPS authentication, configure Git Credential Manager or use SSH. Replace `YOUR_USERNAME` with your account login.

## License

MIT, see `LICENSE`.


## Accuracy phase 2 (implemented on GitHub)

- `POST /api/calibrate` performs robust log-distance path-loss calibration using 8+ line-of-sight reference measurements at three or more distinct distances spanning at least 2×. Calibration is device and environment specific.
- Repeated packets on the same measured radio geometry are aggregated by their median, with gross outliers suppressed. Repeats do **not** count as independent rays.
- Every result now includes `unique_paths`, `outliers_rejected`, `angular_diversity`, and `survey_targets`. Suggested targets are low-evidence regions; they are **not** verified accessible rooms.
- RF predictions and support scores are not architectural ground truth or statistically calibrated wall-detection probabilities.
- Low-level CSI capture, verified wall extraction and automatic mapping from one stationary router remain unimplemented.
