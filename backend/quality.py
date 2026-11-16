"""Spatial evidence quality: independent links, crossing directions, survey priority."""
from collections import defaultdict
from math import hypot
import numpy as np

def aggregate(samples, width, height):
    grouped=defaultdict(list)
    for i,s in enumerate(samples):
        if not (0<=s.tx_x<=width and 0<=s.rx_x<=width and 0<=s.tx_y<=height and 0<=s.rx_y<=height):
            raise ValueError(f"Measurement {i+1} is outside the specified mapping area.")
        key=(round(s.tx_x,1),round(s.tx_y,1),round(s.rx_x,1),round(s.rx_y,1),
             s.label or "",round(s.baseline_dbm_at_1m,2),round(s.path_loss_exponent,3))
        grouped[key].append(s)
    result=[]; rejected=0
    for group in grouped.values():
        values=np.array([s.rssi_dbm for s in group],dtype=float)
        if len(values)>=4:
            middle=float(np.median(values))
            mad=float(np.median(np.abs(values-middle)))
            ok=np.abs(values-middle)<=max(4.,3.5*mad*1.4826)
            rejected+=int((~ok).sum());values=values[ok]
        result.append(group[0].model_copy(update={"rssi_dbm":float(np.median(values))}))
    return result,rejected

def angles_by_cell(matrix, samples, count):
    bins=[set() for _ in range(count)]
    for row,s in enumerate(samples):
        theta=float(np.arctan2(s.rx_y-s.tx_y,s.rx_x-s.tx_x)%np.pi)
        sector=min(5,int(theta/np.pi*6))
        for cell in matrix.indices[matrix.indptr[row]:matrix.indptr[row+1]]:
            bins[cell].add(sector)
    return np.array([len(x) for x in bins],dtype=int)

def suggest(support, diversity, nx, ny, cell_w, cell_h, limit=5):
    chosen=[]
    cells=sorted(range(len(support)),key=lambda i:(int(support[i]),int(diversity[i]),i))
    for i in cells:
        x=(i%nx+.5)*cell_w;y=(i//nx+.5)*cell_h
        if any(hypot(x-z["x_m"],y-z["y_m"])<max(2.,3*max(cell_w,cell_h)) for z in chosen):
            continue
        chosen.append(dict(x_m=round(x,2),y_m=round(y,2),
          support=int(support[i]),angular_bins=int(diversity[i]),
          reason="Low-evidence survey region; verify the location is physically accessible."))
        if len(chosen)>=limit:break
    return chosen
