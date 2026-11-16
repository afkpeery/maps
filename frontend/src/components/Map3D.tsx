import { Canvas } from '@react-three/fiber';
import { OrbitControls, Grid } from '@react-three/drei';
import { Suspense, useMemo } from 'react';
import type { Reconstruction } from '../types';

type Block = {x:number;z:number;height:number;color:string};
function Model({data}: {data:Reconstruction}) {
  const blocks = useMemo(()=>{
    const result:Block[]=[];
    const mx=Math.max(6,...data.attenuation.flat());
    data.attenuation.forEach((row,y)=>row.forEach((val,x)=>{
      const confidence=data.confidence[y][x];
      if(val > data.obstruction_threshold && confidence>.15) result.push({
        x:(x+.5)*data.cell_width_m - data.width_m/2,
        z:(y+.5)*data.cell_height_m - data.height_m/2,
        height: Math.max(.15, Math.min(3,2.4*val/mx)),
        color:confidence > .45 ? '#36d9e8' : '#c28f6b'
      });
    }));
    return result;
  },[data]);
  return <group><mesh rotation={[-Math.PI/2,0,0]} position={[0,-.04,0]}><planeGeometry args={[data.width_m,data.height_m]}/><meshStandardMaterial color="#112338" roughness={.82}/></mesh>
    <mesh position={[0,.15,-data.height_m/2]}><boxGeometry args={[data.width_m,.3,.12]}/><meshStandardMaterial color="#3b6980"/></mesh>
    <mesh position={[0,.15,data.height_m/2]}><boxGeometry args={[data.width_m,.3,.12]}/><meshStandardMaterial color="#3b6980"/></mesh>
    <mesh position={[-data.width_m/2,.15,0]}><boxGeometry args={[.12,.3,data.height_m]}/><meshStandardMaterial color="#3b6980"/></mesh>
    <mesh position={[data.width_m/2,.15,0]}><boxGeometry args={[.12,.3,data.height_m]}/><meshStandardMaterial color="#3b6980"/></mesh>
    {blocks.map((b,i)=><mesh key={i} position={[b.x,b.height/2,b.z]}><boxGeometry args={[data.cell_width_m*.92,b.height,data.cell_height_m*.92]}/><meshStandardMaterial color={b.color} transparent opacity={.8} roughness={.4} metalness={.15}/></mesh>)}
    {Array.from(new Set(data.rays.map(r=>`${r.tx_x},${r.tx_y}`))).slice(0,20).map(pos=>{const [x,y]=pos.split(',').map(Number);return <mesh key={pos} position={[x-data.width_m/2,.2,y-data.height_m/2]}><sphereGeometry args={[.26,12,8]}/><meshBasicMaterial color="#4df1d2"/></mesh>})}
  </group>
}
export function Map3D({data}: {data:Reconstruction | null}) {
  if(!data) return <div className="empty-map"><h3>3D reconstruction unavailable</h3><p>Generate a reconstruction to view estimated attenuation as 3D volumes.</p></div>;
  return <div className="map-3d"><Canvas camera={{position:[21,24,25],fov:42,near:.1,far:400}} gl={{antialias:true}}><color attach="background" args={['#091524']}/><ambientLight intensity={1.4}/><directionalLight position={[7,18,7]} intensity={2.1}/><pointLight position={[-10,12,-8]} color="#5dbfe8" intensity={90}/><Suspense fallback={null}><Model data={data}/></Suspense><Grid position={[0,-.08,0]} args={[100,100]} sectionSize={5} cellSize={1} cellColor="#254057" sectionColor="#3c6078" fadeDistance={65} infiniteGrid/><OrbitControls makeDefault target={[0,0,0]} minDistance={8} maxDistance={90} maxPolarAngle={Math.PI/2.07}/></Canvas><div className="map-overlay-label"><span className="dot cyan"/> 3D ATTENUATION VOLUMES <b>· NOT VERIFIED WALLS</b></div></div>;
}
