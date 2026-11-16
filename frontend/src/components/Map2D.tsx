import { useMemo, useState } from 'react';
import type { Layer, Reconstruction } from '../types';

type Props = { data: Reconstruction | null; layer: Layer; showRays: boolean };
const palette = (signal: number, isConfidence: boolean) => {
  const v = Math.max(0, Math.min(1, signal));
  if (isConfidence) return `rgba(34, 211, 238, ${0.06 + 0.88 * v})`;
  return `rgba(${Math.round(35 + 190 * v)}, ${Math.round(195 - 100 * v)}, ${Math.round(230 - 130 * v)}, ${0.09 + .86 * v})`;
};
export function Map2D({data, layer, showRays}: Props) {
  const [hover, setHover] = useState<{x:number,y:number} | null>(null);
  const demo = useMemo(() => data?.attenuation.flat().reduce((m,v)=>Math.max(m,v),4) ?? 4,[data]);
  if (!data) return <div className="empty-map"><div className="empty-orbit"><span>⌖</span></div><h3>No spatial data yet</h3><p>Validate your network and import measurements, or launch the clearly labeled simulation.</p></div>;
  const w = data.width_m, h = data.height_m;
  const cell = hover ? { attenuation:data.attenuation[hover.y][hover.x], confidence:data.confidence[hover.y][hover.x]}:null;
  return <div className="map-svg-wrap"><svg className="map-svg" viewBox={`-1.5 -1.5 ${w+3} ${h+3}`} role="img" aria-label={`${data.source} RF spatial reconstruction map`}>
    <defs><pattern id="minigrid" width="1" height="1" patternUnits="userSpaceOnUse"><path d="M 1 0 L 0 0 0 1" fill="none" stroke="#2e4661" strokeWidth=".022"/></pattern></defs>
    <rect x="0" y="0" width={w} height={h} fill="#0a1a29"/><rect x="0" y="0" width={w} height={h} fill="url(#minigrid)"/>
    {data.attenuation.flatMap((row,y)=>row.map((value,x)=> {
      const strength = layer === 'confidence' ? data.confidence[y][x] : Math.min(1,value/Math.max(2.2,demo*.6));
      return <rect key={`${x}-${y}`} x={x*data.cell_width_m} y={y*data.cell_height_m} width={data.cell_width_m+.008} height={data.cell_height_m+.008} fill={palette(strength,layer==='confidence')} onMouseEnter={()=>setHover({x,y})} onMouseLeave={()=>setHover(null)}/>;
    }))}
    {showRays && data.rays.map((r,i)=><line key={i} x1={r.tx_x} y1={r.tx_y} x2={r.rx_x} y2={r.rx_y} stroke="#8bdff2" strokeOpacity=".12" strokeWidth=".055"/>)}
    <rect x="0" y="0" width={w} height={h} fill="none" stroke="#6ad9f1" strokeWidth=".14"/>
    {Array.from(new Set(data.rays.map(r=>`${r.tx_x},${r.tx_y}`))).slice(0,20).map(pos=> { const [x,y]=pos.split(',').map(Number);return <g key={pos}><circle cx={x} cy={y} r=".24" fill="#4cf0e4" stroke="#05202d" strokeWidth=".08"/><circle cx={x} cy={y} r=".48" fill="none" stroke="#4cf0e4" strokeOpacity=".6" strokeWidth=".06"/></g> })}
    <g fontSize=".5" fontFamily="monospace" fill="#7693aa"><text x="0" y="-.5">0</text><text x={w} y="-.5" textAnchor="end">{w}m</text><text x="-.25" y={h+.65}>0</text><text x={w} y={h+.65} textAnchor="end">{h}m</text></g>
  </svg><div className="map-overlay-label"><span className="dot cyan"/> {layer==='confidence'?'MEASUREMENT SUPPORT':'INFERRED ATTENUATION'} <b>· {data.source === 'simulated' ? 'SIMULATION' : 'MEASURED INPUT'}</b></div>
    {cell && <div className="map-cell-tooltip">Grid {hover!.x},{hover!.y} · {cell.attenuation.toFixed(2)} dB/m · support {(cell.confidence*100).toFixed(0)}%</div>}
  </div>;
}
