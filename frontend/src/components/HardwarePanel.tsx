import { useEffect, useState } from 'react';
import { Activity, AlertCircle, ArrowDownToLine, Cpu, Radio, RefreshCcw, ShieldCheck, Wifi } from 'lucide-react';
import type { Calibration, Measurement, Reconstruction } from '../types';

const API = import.meta.env.VITE_API_URL ?? '';

type Adapter = { id: string; supported: boolean; ready: boolean; measurement: string; description: string };
type CapabilityReport = {
  scope: string; capture_enabled: boolean; token_configured: boolean;
  adapters: Adapter[]; warning: string;
};
type Captured = {adapter: string; ssid: string; bssid: string | null; captured_at: string; measurement: Measurement; warnings: string[]};
type Props = {
  router: string;
  authorized: boolean;
  calibration: Calibration | null;
  width: number;
  height: number;
  samples: Measurement[];
  setSamples: (samples: Measurement[]) => void;
  onReconstructed: (result: Reconstruction) => void;
  onMessage: (message: string) => void;
  onError: (message: string) => void;
};

async function request<T>(path: string, body?: unknown, token?: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API}${path}`, body ? {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? {'X-MAPS-Hardware-Token': token} : {}),
      },
      body: JSON.stringify(body),
    } : {method: 'GET'});
  } catch {
    throw new Error('Local backend unreachable. Start FastAPI on 127.0.0.1:8000.');
  }
  const data: unknown = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = data as {detail?: string};
    throw new Error(typeof error.detail === 'string' ? error.detail : `Local hardware API returned ${response.status}.`);
  }
  return data as T;
}

function exportReadings(samples: Measurement[]) {
  const keys = ['tx_x','tx_y','rx_x','rx_y','rssi_dbm','baseline_dbm_at_1m','path_loss_exponent'] as const;
  const csv = [keys.join(','), ...samples.map(row=>keys.map(k=>row[k]).join(','))].join('\n')+'\n';
  const url = URL.createObjectURL(new Blob([csv], {type:'text/csv'}));
  const a = document.createElement('a'); a.href=url; a.download='maps-hardware-measurements.csv'; a.click();
  window.setTimeout(()=>URL.revokeObjectURL(url), 1000);
}

export function HardwarePanel({router, authorized, calibration, width, height, samples, setSamples, onReconstructed, onMessage, onError}: Props) {
  const [cap, setCap] = useState<CapabilityReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [hardwareToken, setHardwareToken] = useState('');
  const [interfaceName, setInterfaceName] = useState('wlan0');
  const [ssid, setSsid] = useState('');
  const [bssid, setBssid] = useState('');
  const [txX, setTxX] = useState('');
  const [txY, setTxY] = useState('');
  const [rxX, setRxX] = useState('');
  const [rxY, setRxY] = useState('');
  const [coordinatesVerified, setCoordinatesVerified] = useState(false);
  const [lastReading, setLastReading] = useState<Captured | null>(null);

  async function refresh() {
    setLoading(true);
    try {setCap(await request<CapabilityReport>('/api/hardware/capabilities'));}
    catch(err) {onError(err instanceof Error ? err.message : 'Hardware check failed.');}
    finally {setLoading(false);}
  }
  useEffect(() => { void refresh(); }, []); // Check capabilities, do not initiate any scan.

  async function capture() {
    setBusy(true);
    try {
      const coordinates = [txX, txY, rxX, rxY].map(v => v.trim()===''?NaN:Number(v));
      if (coordinates.some(x => !Number.isFinite(x) || x < 0 || x > 200)) {
        throw new Error('Enter verified transmitter and receiver coordinates in meters (0–200).');
      }
      if (!coordinatesVerified) throw new Error('Confirm the coordinates were measured, not inferred from the IP address.');
      const reading = await request<Captured>('/api/hardware/capture', {
        router_identifier: router, authorized,
        expected_ssid: ssid.trim(), expected_bssid: bssid.trim() || null, interface: interfaceName.trim(),
        tx_x: coordinates[0], tx_y: coordinates[1], rx_x: coordinates[2], rx_y: coordinates[3],
        baseline_dbm_at_1m: calibration?.baseline_dbm_at_1m ?? -40,
        path_loss_exponent: calibration?.path_loss_exponent ?? 2.1,
      }, hardwareToken);
      setSamples([...samples, reading.measurement]);
      setLastReading(reading);
      onMessage(`Collected ${reading.measurement.rssi_dbm} dBm from ${reading.ssid}. This is a measured wireless link, not a mapped room.`);
      setCoordinatesVerified(false);
    } catch (err) {onError(err instanceof Error ? err.message : 'Capture failed.');}
    finally {setBusy(false);}
  }

  async function reconstruct() {
    if (samples.length < 24) { onError('Collect at least 24 spatially distinct links before reconstruction.'); return; }
    setBusy(true);
    try {
      const result = await request<Reconstruction>('/api/reconstruct', {
        router_identifier: router, authorized, width_m: width, height_m: height,
        cell_size_m: 0.75, samples, source:'measured',
      });
      onReconstructed(result);
      onMessage(`Reconstructed ${result.unique_paths} distinct measured paths. This is an estimated RF attenuation map, not a verified floor plan.`);
    } catch (err) {onError(err instanceof Error ? err.message : 'Reconstruction failed.');}
    finally {setBusy(false);}
  }

  const ready = cap?.adapters.some(a=>a.id==='linux_iw_associated_link' && a.ready) ?? false;
  const distinct = new Set(samples.map(s=>[s.tx_x,s.tx_y,s.rx_x,s.rx_y].join('|'))).size;

  return <section className="panel hardware-panel" aria-label="Local hardware capture">
    <div className="hardware-head">
      <div><div className="section-kicker"><Cpu size={15}/> LOCAL HARDWARE BRIDGE</div>
        <h2>Live Wi-Fi measurements</h2>
        <p>Read one RSSI sample from the network already connected to the computer running the local backend.</p>
      </div>
      <button className="secondary-button" type="button" onClick={()=>void refresh()} disabled={loading}>
        <RefreshCcw size={15} className={loading?'spin':''}/> Check hardware
      </button>
    </div>
    <div className="hardware-adapters">
      {(cap?.adapters ?? []).map(adapter => <div className="hardware-adapter" key={adapter.id}>
        <span className="hardware-adapter-icon">{adapter.id==='csi_plugin'?<Activity size={19}/>:<Wifi size={19}/>}</span>
        <div><strong>{adapter.measurement}</strong><p>{adapter.description}</p></div>
        <span className={`hardware-status ${adapter.ready?'ready':''}`}>{adapter.ready?'READY':adapter.supported?'OPT-IN REQUIRED':'NOT AVAILABLE'}</span>
      </div>)}
      {!cap && <p className="hardware-note">Connect the local backend to check supported devices. No scan is performed by this check.</p>}
    </div>
    <div className="hardware-note"><ShieldCheck size={16}/> Device status refers to the FastAPI host, never the router at <code>{router}</code>. Entering that IP does not establish a connection.</div>
    {!ready && <div className="hardware-not-ready"><AlertCircle size={17}/><div><b>Live capture is off until explicitly configured.</b><p>On a Linux computer with an already-associated Wi-Fi interface and <code>iw</code> installed, start the backend with <code>MAPS_ENABLE_LOCAL_CAPTURE=1</code> and a strong <code>MAPS_HARDWARE_TOKEN</code>. Bind it to 127.0.0.1. No hardware readings are simulated here.</p></div></div>}
    <div className="hardware-fields">
      <label>Linux Wi-Fi interface<input value={interfaceName} onChange={e=>setInterfaceName(e.target.value)} placeholder="wlan0" autoComplete="off"/></label>
      <label>Currently connected SSID<input value={ssid} onChange={e=>setSsid(e.target.value)} placeholder="Your actual Wi-Fi name" autoComplete="off"/></label>
      <label>Expected AP BSSID (optional)<input value={bssid} onChange={e=>setBssid(e.target.value)} placeholder="aa:bb:cc:dd:ee:ff" autoComplete="off"/></label>
      <label>Local capture token<input type="password" value={hardwareToken} onChange={e=>setHardwareToken(e.target.value)} placeholder="Token configured in your backend" autoComplete="off"/></label>
    </div>
    <h3 className="hardware-subheading">Measured positions <span>meters, common coordinate frame</span></h3>
    <div className="hardware-fields coordinates">
      <label>Transmitter X<input type="number" min="0" max="200" value={txX} onChange={e=>{setTxX(e.target.value);setCoordinatesVerified(false);}} placeholder="e.g. 2.0"/></label>
      <label>Transmitter Y<input type="number" min="0" max="200" value={txY} onChange={e=>{setTxY(e.target.value);setCoordinatesVerified(false);}} placeholder="e.g. 4.0"/></label>
      <label>Receiver X<input type="number" min="0" max="200" value={rxX} onChange={e=>{setRxX(e.target.value);setCoordinatesVerified(false);}} placeholder="e.g. 6.0"/></label>
      <label>Receiver Y<input type="number" min="0" max="200" value={rxY} onChange={e=>{setRxY(e.target.value);setCoordinatesVerified(false);}} placeholder="e.g. 5.0"/></label>
    </div>
    <label className="hardware-confirm"><input type="checkbox" checked={coordinatesVerified} onChange={e=>setCoordinatesVerified(e.target.checked)}/> These coordinates come from an independently measured survey.</label>
    {!calibration && <p className="hardware-warning">No reference calibration loaded. Default propagation coefficients are placeholders; capture data will not yield reliable building geometry until calibrated.</p>}
    <div className="hardware-actions">
      <button className="primary-button" type="button" disabled={!ready || !authorized || !coordinatesVerified || !ssid.trim() || !hardwareToken || busy} onClick={()=>void capture()}><Radio size={16}/> Capture associated RSSI</button>
      <button className="secondary-button" disabled={samples.length<1 || busy} onClick={()=>exportReadings(samples)}><ArrowDownToLine size={16}/> Export CSV</button>
      <button className="secondary-button" disabled={samples.length<24 || !authorized || busy} onClick={()=>void reconstruct()}><Activity size={16}/> Reconstruct collected data</button>
      <button className="hardware-clear" disabled={samples.length<1 || busy} onClick={()=>{setSamples([]);setLastReading(null);}}>Clear survey</button>
    </div>
    <div className="hardware-progress">
      <div><strong>{samples.length}</strong><span>RSSI readings</span></div>
      <div><strong>{distinct}</strong><span>distinct surveyed links</span></div>
      <div><strong>{Math.max(0,24-distinct)}</strong><span>additional unique links to minimum</span></div>
      <div><strong>{lastReading?`${lastReading.measurement.rssi_dbm} dBm`:'—'}</strong><span>most recent signal</span></div>
    </div>
    <p className="hardware-footnote">Pin an AP BSSID when multiple access points broadcast the same SSID, or readings may be attributed to the wrong transmitter. The 24-link threshold is a minimum, not a guarantee of sufficient angular diversity. A single AP with one moving receiver generally has poor wall-location identifiability. Use multiple known transmitter locations and a verified floor outline where possible.</p>
  </section>;
}
