import { useRef, useState } from 'react';
import { Activity, AlertCircle, ArrowDownToLine, ArrowRight, BadgeCheck, Box, Check, ChevronDown, ChevronRight, CircleHelp, Database, FileUp, Grid2X2, Layers3, LockKeyhole, Map, Menu, Radio, RadioTower, Radar, RefreshCcw, ScanLine, ShieldCheck, SlidersHorizontal, Sparkles, Waves, Wifi, X } from 'lucide-react';
import { Map2D } from './components/Map2D';
import { Map3D } from './components/Map3D';
import { HardwarePanel } from './components/HardwarePanel';
import { createProject, parseProject } from './project';
import type { Calibration, Layer, Measurement, Reconstruction, ViewMode } from './types';

const API = import.meta.env.VITE_API_URL ?? '';
type Page = 'studio' | 'signals' | 'projects' | 'guide';
async function postJson<T>(path:string, payload:unknown):Promise<T> {
  let response:Response;
  try { response = await fetch(`${API}${path}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}); }
  catch { throw new Error('Cannot reach the mapping API. Start FastAPI on localhost:8000.'); }
  const body = await response.json().catch(()=>({}));
  if(!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `Request failed (${response.status}).`);
  return body as T;
}
const download = (name:string,content:string,type='application/json') => {
  const blob = new Blob([content],{type}); const href=URL.createObjectURL(blob); const a=document.createElement('a');
  a.href=href; a.download=name; a.click(); window.setTimeout(()=>URL.revokeObjectURL(href),1500);
};
function parseRows(text:string, calibration:Calibration|null):Measurement[] {
  const lines = text.replace(/\r/g,'').split('\n').filter(l=>l.trim());
  if(lines.length<2)throw new Error('The CSV needs a header and at least 24 samples.');
  const headers=lines[0].split(',').map(x=>x.trim());
  const required=['tx_x','tx_y','rx_x','rx_y','rssi_dbm'];
  if(required.some(h=>!headers.includes(h)))throw new Error('Missing CSV columns: tx_x, tx_y, rx_x, rx_y, rssi_dbm.');
  return lines.slice(1).map((line,i)=>{
    const values=line.split(',').map(v=>v.trim());
    const get=(key:string,def?:number)=>{const j=headers.indexOf(key);return j<0 ? def! : Number(values[j]);};
    const sample:Measurement={tx_x:get('tx_x'),tx_y:get('tx_y'),rx_x:get('rx_x'),rx_y:get('rx_y'),rssi_dbm:get('rssi_dbm'),baseline_dbm_at_1m:get('baseline_dbm_at_1m',calibration?.baseline_dbm_at_1m??-40),path_loss_exponent:get('path_loss_exponent',calibration?.path_loss_exponent??2.1)};
    if(Object.values(sample).some(x=>!Number.isFinite(x))) throw new Error(`Invalid number on CSV row ${i+2}.`);
    return sample;
  });
}
function parseReferenceRows(text:string) {
  const lines=text.replace(/\r/g,'').split('\n').filter(s=>s.trim());
  if (lines.length<9) throw new Error('Reference CSV needs at least eight measurements.');
  const columns=lines[0].split(',').map(s=>s.trim());
  if (!columns.includes('distance_m') || !columns.includes('rssi_dbm')) throw new Error('Reference CSV must contain distance_m,rssi_dbm.');
  return lines.slice(1).map((line,index)=>{
    const values=line.split(',').map(s=>s.trim());
    const dist=Number(values[columns.indexOf('distance_m')]);
    const rssi=Number(values[columns.indexOf('rssi_dbm')]);
    if (!Number.isFinite(dist) || !Number.isFinite(rssi)) throw new Error(`Invalid reference value on row ${index+2}`);
    const flag=columns.indexOf('line_of_sight');
    return {distance_m:dist,rssi_dbm:rssi,line_of_sight:flag<0 || !['false','0','no'].includes(values[flag]?.toLowerCase())};
  });
}
function App() {
  const [page,setPage]=useState<Page>('studio');
  const [router,setRouter]=useState('192.168.1.6'); // Example only; never an established connection.
  const [authorized,setAuthorized]=useState(false);
  const [data,setData]=useState<Reconstruction|null>(null);
  const [view,setView]=useState<ViewMode>('2d');
  const [layer,setLayer]=useState<Layer>('attenuation');
  const [showRays,setShowRays]=useState(false);
  const [showTargets,setShowTargets]=useState(true);
  const [calibration,setCalibration]=useState<Calibration|null>(null);
  const [hardwareSamples,setHardwareSamples]=useState<Measurement[]>([]);
  const [message,setMessage]=useState('192.168.1.6 is an example identifier only. No router is connected, authorized or scanned. Launch a separate synthetic demo below.');
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  const [width,setWidth]=useState(24);
  const [height,setHeight]=useState(16);
  const fileInput=useRef<HTMLInputElement>(null);
  const projectInput=useRef<HTMLInputElement>(null);
  const calibrationInput=useRef<HTMLInputElement>(null);
  const [menuOpen,setMenuOpen]=useState(false);
  const identification=async()=>{
    setError('');setBusy(true);setData(null);
    try { const response=await postJson<{message:string,kind:string}>('/api/identify',{identifier:router,authorized});setMessage(response.message); }
    catch(e) { setError(e instanceof Error?e.message:'Unable to validate identifier.'); }
    finally {setBusy(false);}
  };
  const simulate=async()=>{
    setBusy(true);setError('');
    try { const response=await fetch(`${API}/api/demo/preview`); if(!response.ok)throw new Error('Unable to load the synthetic demo.'); const result=await response.json() as Reconstruction;setData(result);setPage('studio');setMessage('Synthetic demonstration loaded from SYNTHETIC_DEMO_ONLY. It has no relationship to 192.168.1.6 or any physical router.'); }
    catch(e){setError(e instanceof Error?e.message:'Simulation failed.');}
    finally{setBusy(false);}
  };
  const loadMeasurements=async(e:React.ChangeEvent<HTMLInputElement>)=>{
    const file=e.currentTarget.files?.[0]; if(!file)return;
    e.currentTarget.value='';setBusy(true);setError('');
    try {const txt=await file.text();const samples=file.name.toLowerCase().endsWith('.json')?JSON.parse(txt) as Measurement[]:parseRows(txt,calibration);
      if(!Array.isArray(samples)) throw new Error('JSON must be an array of measurements.');
      const result=await postJson<Reconstruction>('/api/reconstruct',{router_identifier:router,authorized,width_m:width,height_m:height,cell_size_m:.75,samples,source:'measured'});
      setData(result);setMessage(`${result.unique_paths} unique links reconstructed from ${samples.length} readings. ${calibration?'Reference calibration applied where missing.':'Default propagation coefficients are placeholders unless supplied in the file.'}`);setPage('studio');
    }catch(e){setError(e instanceof Error?e.message:'Upload failed.');}
    finally{setBusy(false);}
  };
  const loadCalibration=async(e:React.ChangeEvent<HTMLInputElement>)=>{
    const file=e.currentTarget.files?.[0];if(!file)return;
    e.currentTarget.value='';setBusy(true);setError('');
    try {const samples=parseReferenceRows(await file.text());
      const result=await postJson<Calibration>('/api/calibrate',{identifier:router,authorized,samples});
      setCalibration(result);setMessage(`Calibrated from ${result.samples_used} reference readings: baseline ${result.baseline_dbm_at_1m} dBm at 1 m, exponent ${result.path_loss_exponent}. Use same radio and environment.`);
    }catch(e){setError(e instanceof Error?e.message:'Calibration failed.');}
    finally{setBusy(false);}
  };
  const loadProject=async(event:React.ChangeEvent<HTMLInputElement>)=>{
    const file=event.currentTarget.files?.[0];if(!file)return;
    event.currentTarget.value='';setError('');
    try {
      if(file.size>4_000_000)throw new Error('Project exceeds the 4 MB import limit.');
      const project=parseProject(await file.text());
      setData(project.reconstruction);
      setCalibration(project.calibration ?? null);
      setRouter(project.reconstruction.router_identifier);
      setMessage(`Opened ${project.reconstruction.source} project saved ${project.saved_at}. Confirm measurements before interpreting geometry.`);
      setPage('studio');
    }catch(e){setError(e instanceof Error?e.message:'Cannot load project.');}
  };
  const saveProject=()=>{
    if(!data)return;
    download('maps-project.json',JSON.stringify(createProject(data,calibration),null,2));
    setMessage('Project saved to your device. MAPS does not automatically sync it to a server.');
  };
  const exportSvg=()=>{
    if(!data)return;
    const sq=13;const w=data.nx*sq,h=data.ny*sq;
    const cells=data.attenuation.flatMap((row,y)=>row.map((v,x)=>{
      const a=Math.min(1,v/12); const r=Math.round(35+190*a),g=Math.round(195-100*a),b=Math.round(230-130*a);
      return `<rect x="${x*sq}" y="${y*sq}" width="${sq}" height="${sq}" fill="rgb(${r},${g},${b})" fill-opacity="${.09+.86*a}"/>`;
    })).join('');
    download('maps-attenuation.svg',`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><rect width="${w}" height="${h}" fill="#101d30"/>${cells}</svg>`,'image/svg+xml');
  };
  const activeNav=(p:Page)=>{setPage(p);setMenuOpen(false)};
  return <div className="app-shell">
    <aside className={`sidebar ${menuOpen?'mobile-open':''}`}>
      <div className="brand"><div className="brand-mark"><ScanLine size={21} strokeWidth={2.2}/></div><div><strong>MAPS<span className="brand-period">.</span></strong><small>SPATIAL INTELLIGENCE</small></div></div>
      <div className="nav-overline">WORKSPACE</div>
      <nav aria-label="Main navigation"><button onClick={()=>activeNav('studio')} className={`nav-item ${page==='studio'?'active':''}`}><Grid2X2 size={18}/> Mapping Studio <ChevronRight size={16} className="right-arrow"/></button><button onClick={()=>activeNav('signals')} className={`nav-item ${page==='signals'?'active':''}`}><Waves size={18}/> Signal Laboratory</button><button onClick={()=>activeNav('projects')} className={`nav-item ${page==='projects'?'active':''}`}><Database size={18}/> Projects</button><button onClick={()=>activeNav('guide')} className={`nav-item ${page==='guide'?'active':''}`}><CircleHelp size={18}/> Setup Guide</button></nav>
      <div className="side-spacer"/><div className="side-info"><div className="side-info-icon"><ShieldCheck size={17}/></div><strong>Privacy-first mapping</strong><span>No remote router probing. Data stays in your local API environment.</span></div><div className="side-footer"><span className="status-pulse"/> LOCAL MVP <span className="side-version">v0.3.0</span></div>
    </aside>
    {menuOpen && <div className="mobile-scrim" onClick={()=>setMenuOpen(false)} />}
    <main className="workspace"><header className="topbar"><button className="mobile-menu" aria-label="Toggle navigation" onClick={()=>setMenuOpen(!menuOpen)}><Menu size={20}/></button><div className="breadcrumb"><span>Workspace</span><ChevronRight size={15}/><b>{page==='studio'?'Mapping Studio':page==='signals'?'Signal Laboratory':page==='projects'?'Projects':'Setup Guide'}</b></div><div className="topbar-end"><span className="secure-pill"><LockKeyhole size={13}/> LOCAL PROCESSING</span><div className="avatar">M</div></div></header>
      <div className="content">
        <div className="page-head"><div><div className="eyebrow"><span className="small-square"/> INTELLIGENT ENVIRONMENT ANALYSIS</div><h1>{page==='studio'?'Mapping Studio':page==='signals'?'Signal Laboratory':page==='projects'?'Saved Projects':'Setup & Requirements'}<span className="heading-dot">.</span></h1><p>{page==='studio'?'Transform authorized wireless observations into spatial hypotheses.':page==='signals'?'Understand coverage, uncertainty, and the limitations of your measurements.':page==='projects'?'Export and reopen local mapping sessions without automatic cloud storage.':'Get calibrated spatial measurements before reconstructing an environment.'}</p></div><div className="head-status"><span className={`head-light ${data?'lit':''}`}/>{data?'Reconstruction loaded':'Awaiting input'}<ChevronDown size={14}/></div></div>
        {page==='projects' ? <section className="panel projects-panel">
          <div className="section-kicker"><Database size={16}/> PROJECT ARCHIVE</div>
          <h2>Save and reopen your map</h2>
          <p>Projects are exported as JSON to your device. No cloud sync or silent storage is performed. Only reconstructed data and calibration are included, not router credentials or capture tokens.</p>
          <div className="project-summary"><div><small>CURRENT PROJECT</small><strong>{data ? data.router_identifier : 'None loaded'}</strong></div><div><small>DATA SOURCE</small><strong>{data ? data.source.toUpperCase() : '—'}</strong></div><div><small>LINKS</small><strong>{data ? data.unique_paths : '—'}</strong></div></div>
          <div className="project-actions"><button type="button" className="primary-button" disabled={!data} onClick={saveProject}><ArrowDownToLine size={16}/> Save project JSON</button><button type="button" className="secondary-button" onClick={()=>projectInput.current?.click()}><FileUp size={16}/> Open a saved project</button><input ref={projectInput} type="file" accept=".json,application/json" hidden onChange={loadProject}/></div>
          {(error || message) && <div className={`alert-bar ${error?'error':''}`} role="status">{error||message}</div>}
          <p className="project-privacy"><ShieldCheck size={15}/> Imported projects are visualization artifacts—not authenticated architectural records. Never interpret synthetic RF data as a measurement of a real building.</p>
        </section> : page==='guide' ? <section className="guide-grid">
          <div className="panel guide-card"><span className="guide-number">01</span><h2>Identify the network</h2><p>Enter a private router IP, local hostname or Wi-Fi SSID. This only labels the mapping project; it cannot reveal the building from the identifier alone.</p></div>
          <div className="panel guide-card"><span className="guide-number">02</span><h2>Collect calibrated data</h2><p>For a real survey, use the Signal Laboratory hardware bridge on a Linux computer with a connected Wi-Fi radio, or import measurements. Known x/y coordinates and cross-link geometry are essential.</p></div>
          <div className="panel guide-card"><span className="guide-number">03</span><h2>Import and reconstruct</h2><p>Import a CSV or JSON measurement dataset. The local Python engine infers an attenuation grid with regularization, measurement support, and holdout prediction error.</p></div>
          <div className="panel guide-card"><span className="guide-number">04</span><h2>Validate the result</h2><p>Compare inferred obstruction areas with physical measurements or a verified survey. No geometry should be interpreted as a reliable architectural wall without validation.</p></div>
          <div className="panel guide-wide"><h3>Expected CSV columns</h3><code>tx_x,tx_y,rx_x,rx_y,rssi_dbm,baseline_dbm_at_1m,path_loss_exponent</code><p>Coordinates in meters, RSSI in dBm. Optional calibration fields default to -40 dBm at 1 m and path-loss exponent 2.1. At least 24 distinct paths are required. For reference calibration, record 8+ clear-line-of-sight readings at surveyed distances in a CSV with <code>distance_m,rssi_dbm,line_of_sight</code>. A single radio/environment calibration is not transferable to other radios.</p><button className="secondary-button" onClick={()=>download('maps-measurements-template.csv','tx_x,tx_y,rx_x,rx_y,rssi_dbm,baseline_dbm_at_1m,path_loss_exponent\n2,2,10,6,-70,-40,2.1\n','text/csv')}><ArrowDownToLine size={16}/> Download CSV template</button> <button className="secondary-button" onClick={()=>download('maps-calibration-template.csv','distance_m,rssi_dbm,line_of_sight\n1,-40,true\n2,-46,true\n3,-50,true\n4,-53,true\n5,-55,true\n6,-57,true\n8,-59,true\n10,-61,true\n','text/csv')}><ArrowDownToLine size={16}/> Reference template (example numbers only)</button></div>
        </section> : <>
          <section className="scan-panel panel"><div className="scan-left"><div className="section-kicker"><Radar size={14}/> NETWORK RECONSTRUCTION</div><h2>Map your environment<span>.</span></h2><p>Explore the simulated map instantly, or connect compatible sensing hardware to collect authorized spatial measurements.</p><div className="example-label">EXAMPLE IDENTIFIER · NOT CONNECTED · NOT AUTHORIZED</div><label className="form-label" htmlFor="router">NETWORK NAME OR LOCAL ROUTER IP</label><div className="input-row"><div className="input-wrap"><Wifi size={19}/><input id="router" value={router} onChange={e=>setRouter(e.target.value)} placeholder="e.g. 192.168.1.6 or Office_WiFi"/></div><button className="primary-button" disabled={busy || !authorized || !router.trim()} onClick={identification}>{busy?<RefreshCcw size={17} className="spin"/>:<ScanLine size={17}/>} Analyze <ArrowRight size={17}/></button></div><label className="consent"><input type="checkbox" checked={authorized} onChange={e=>setAuthorized(e.target.checked)}/><span>I own or have permission to map this building and network.</span></label><div className="scan-actions"><button onClick={simulate} disabled={busy} className="text-action"><Sparkles size={16}/> Run synthetic demo <ChevronRight size={16}/></button><div className="divider-v"/><button className="text-action" disabled={!authorized || busy} onClick={()=>calibrationInput.current?.click()}><SlidersHorizontal size={16}/> Calibrate reference RSSI <ChevronRight size={16}/></button><input ref={calibrationInput} type="file" accept=".csv,text/csv" onChange={loadCalibration} hidden/><div className="divider-v"/><button className="text-action" disabled={!authorized || busy} onClick={()=>fileInput.current?.click()}><FileUp size={16}/> Import real measurements <ChevronRight size={16}/></button><input ref={fileInput} type="file" accept=".csv,.json,text/csv,application/json" onChange={loadMeasurements} hidden/></div></div><div className="scan-visual" aria-hidden="true"><div className="signal-orbit orbit-outer"/><div className="signal-orbit orbit-mid"/><div className="signal-orbit orbit-inner"/><div className="core-glow"><RadioTower size={50}/></div><div className="floating-pill p1"><Activity size={12}/> RF ANALYSIS</div><div className="floating-pill p2"><BadgeCheck size={12}/> SPATIAL ENGINE</div><div className="scan-grid-overlay"/></div></section>
          {(error || message) && <div className={`alert-bar ${error?'error':''}`} role="status">{error?<AlertCircle size={17}/>:<CircleHelp size={17}/>}<span>{error||message}</span>{error && <button aria-label="Dismiss error" onClick={()=>setError('')}><X size={15}/></button>}</div>}
          <div className="metrics-grid"><div className="metric panel"><div className="metric-top"><span>DATA POINTS</span><Database size={17}/></div><div className="metric-number">{data?.unique_paths.toLocaleString()??'—'}<small>{data?`unique of ${data.measurements}`:'no dataset'}</small></div><div className="metric-bottom"><span className="metric-bullet"/> {data?'Spatially referenced links':'Awaiting measurement input'}</div></div><div className="metric panel"><div className="metric-top"><span>GRID COVERAGE</span><Layers3 size={17}/></div><div className="metric-number">{data?`${data.coverage_pct.toFixed(1)}%`:'—'}<small>{data?'3+ paths/cell':'not sampled'}</small></div><div className="metric-bottom"><span className="metric-bullet"/> {data?'Support, not accuracy':'No coverage estimate'}</div></div><div className="metric panel"><div className="metric-top"><span>HOLDOUT ERROR</span><Activity size={17}/></div><div className="metric-number">{data?.holdout_mae_db!=null?data.holdout_mae_db.toFixed(2):'—'}<small>{data?'dB MAE':'unavailable'}</small></div><div className="metric-bottom"><span className="metric-bullet"/> Prediction error, not wall error</div></div><div className="metric panel"><div className="metric-top"><span>OBSERVABILITY</span><ShieldCheck size={17}/></div><div className="metric-number metric-text">{data?(data.spatially_observable?'Qualified':'Limited'):'—'}</div><div className="metric-bottom"><span className={`metric-bullet ${data?.spatially_observable?'good':''}`}/> {data?'Heuristic geometry sufficiency':'Not evaluated'}</div></div></div>
          {page==='studio'? <section className="map-panel panel"><div className="map-top"><div><div className="section-kicker"><Map size={14}/> SPATIAL RECONSTRUCTION</div><h2>Environment overview</h2><p>{data?'Inferred spatial attenuation; not a surveyed architectural floor plan.':'Your mapping visualization will appear here.'}</p></div><div className="map-controls"><div className="segmented"><button className={view==='2d'?'selected':''} onClick={()=>setView('2d')}><Map size={15}/> 2D</button><button className={view==='3d'?'selected':''} onClick={()=>setView('3d')}><Box size={15}/> 3D</button></div><button className="icon-button" disabled={!data} onClick={()=>data&&download('maps-reconstruction.json',JSON.stringify(data,null,2))} title="Export reconstruction JSON" aria-label="Export JSON"><ArrowDownToLine size={18}/></button></div></div><div className="map-main">{view==='2d'?<Map2D data={data} layer={layer} showRays={showRays} showTargets={showTargets}/>:<Map3D data={data}/>}</div><div className="map-bottom"><div className="layer-buttons"><button className={layer==='attenuation'?'sel':''} onClick={()=>setLayer('attenuation')}><span className="layer-icon warm"/> Attenuation</button><button className={layer==='diversity'?'sel':''} onClick={()=>setLayer('diversity')}><span className="layer-icon blue"/> Crossing angles</button><button className={layer==='confidence'?'sel':''} onClick={()=>setLayer('confidence')}><span className="layer-icon blue"/> Measurement support</button><label className="ray-toggle"><input type="checkbox" checked={showRays} onChange={e=>setShowRays(e.target.checked)}/> Show rays</label><label className="ray-toggle"><input type="checkbox" checked={showTargets} onChange={e=>setShowTargets(e.target.checked)}/> Survey targets (S1–S5)</label></div><div className="map-exports"><button disabled={!data} onClick={exportSvg}><ArrowDownToLine size={14}/> Export SVG</button></div></div></section> : <><HardwarePanel router={router} authorized={authorized} calibration={calibration} width={width} height={height} samples={hardwareSamples} setSamples={setHardwareSamples} onReconstructed={(result)=>{setData(result);setPage('studio');}} onMessage={setMessage} onError={setError}/><section className="panel lab-panel"><div className="section-kicker"><Radio size={14}/> SIGNAL QUALITY LAB</div><h2>Measurement diagnostics</h2><p>Understand whether the data actually supports reconstruction.</p><div className="lab-stats"><div><small>TRANSMITTER POSITIONS</small><strong>{data?.transmitter_positions??'—'}</strong></div><div><small>RECEIVER POSITIONS</small><strong>{data?.receiver_positions??'—'}</strong></div><div><small>MEASUREMENT SOURCE</small><strong>{data?data.source.toUpperCase():'NONE'}</strong></div><div><small>REPEATED/REJECTED RSSI</small><strong>{data?`${data.measurements-data.unique_paths}/${data.outliers_rejected}`:'—'}</strong></div><div><small>REFERENCE CALIBRATION</small><strong>{calibration?`${calibration.median_abs_error_db} dB`:'NONE'}</strong></div><div><small>SUGGESTED ZONES</small><strong>{data?.survey_targets.length??'—'}</strong></div></div><div className="lab-advice"><SlidersHorizontal size={20}/><div><b>Increasing accuracy</b><p>Use known transmitter coordinates, calibrated path-loss models, multiple crossing angles and independently verified reference dimensions. Prefer CSI and precise ranging only when compatible hardware is available and calibrated.</p></div></div>{data&&<div className="lab-advice"><Map size={20}/><div><b>Candidate collection zones (not verified walkable)</b><p>{data.survey_targets.map((t,i)=>`S${i+1} (${t.x_m}, ${t.y_m}) m — ${t.support} links, ${t.angular_bins} directions`).join(' · ')}</p></div></div>}</section></>}
          <section className="bottom-grid"><div className="panel details-card"><div className="card-head"><div><span className="section-kicker"><SlidersHorizontal size={14}/> RECONSTRUCTION SETTINGS</span><h3>Survey dimensions</h3></div><span className="subtle-badge">METERS</span></div><div className="settings-fields"><label>Width (m)<input type="number" min={4} max={70} value={width} onChange={e=>setWidth(Number(e.target.value))}/></label><label>Length (m)<input type="number" min={4} max={70} value={height} onChange={e=>setHeight(Number(e.target.value))}/></label></div><p>Applied when you import real readings. Verify physical bounds independently for accurate scaling.</p></div><div className="panel details-card"><div className="card-head"><div><span className="section-kicker"><AlertCircle size={14}/> MEASUREMENT QUALITY</span><h3>Interpretation & limitations</h3></div><span className="subtle-badge">{data?.warnings.length??0} NOTES</span></div><div className="warnings">{data?data.warnings.length?data.warnings.slice(0,3).map((w,i)=><p key={i}><span className="warning-mark"/> {w}</p>):<p><Check size={14}/> No automated quality flags; verify physical geometry independently.</p>:<p>Any inferred room layout requires multiple spatially diverse readings and independent verification. Router IP alone is insufficient.</p>}</div></div></section>
        </>}
        <footer className="page-footer"><span>MAPS / Wi-Fi SPATIAL INTELLIGENCE</span><span><ShieldCheck size={13}/> Authorization required · Local-first prototype</span></footer>
      </div></main>
  </div>;
}
export default App;
