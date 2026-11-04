#!/usr/bin/env python3
"""General 3D re-entrant cell, Ghavidelnia et al., Materials 14 (2021) 993.

All dimensions are mm. Reference: Fig. 2, Eq. (1), sections 2.1.1, 2.2,
3.1, and supplementary Fig. S1-S4. This program performs geometry checks,
not a mechanical simulation. See GEOMETRY_REFERENCE_KO.md and GUIDE_KO.md.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import itertools
import json
import math
import os
from pathlib import Path
import struct
import time
import tempfile

os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir())/'auxetic-matplotlib'))
os.environ.setdefault('XDG_CACHE_HOME', str(Path(tempfile.gettempdir())/'auxetic-cache'))
import cadquery as cq
import numpy as np


def parameters(args):
    theta, phi = map(math.radians, (args.theta, args.phi))
    if not (0 < args.theta < 35.264389 and 0 < args.phi < 54.735610):
        raise ValueError('Supported re-entrant range: 0 < theta < 35.264389, 0 < phi < 54.735610 degrees.')
    k = 1 - math.sqrt(2) * math.tan(theta)  # inner face radius / b
    if args.l1_ratio <= 0:
        raise ValueError('l1-ratio must be positive')
    if args.b is not None:
        b = args.b
    elif args.l2 is not None:
        b = args.l2 * math.cos(theta) / math.sqrt(2)
    elif args.l3 is not None:
        b = args.l3 * math.cos(phi)
    else:
        side = args.cell_size if args.cell_size is not None else 77.1
        b = ((side / 2 - args.l1) / k if args.l1 is not None
             else side / (2 * (args.l1_ratio + k)))
    l1 = args.l1 if args.l1 is not None else args.l1_ratio * b
    a = b * k
    h = a + l1
    c = b * (1 - math.tan(phi) / math.sqrt(2))
    l2, l3 = math.sqrt(2) * b / math.cos(theta), b / math.cos(phi)
    if min(b, l1, a, c) <= 0 or h <= b:
        raise ValueError('Require positive lengths and a+l1 > b so the cell fits inside its periodic cube.')
    L = 2 * h
    if not 0 < args.mu < 1:
        raise ValueError('mu must be between zero and one')
    r_nom = math.sqrt(args.mu * L**3 / (math.pi * (6*l1 + 24*l2 + 24*l3)))
    radii = list(args.radii) if args.radii else [args.radius if args.radius is not None else r_nom] * 3
    if min(radii) <= 0 or max(radii) >= min(l1, l2, l3)/2:
        raise ValueError('Radii must be positive and less than half the shortest strut.')
    if b + max(radii) >= h:
        raise ValueError('Strut envelope may cross unintended cell boundaries; increase l1 or reduce radii.')
    if min(args.repeat) < 1:
        raise ValueError('Repeat counts must be positive')
    return dict(theta_deg=args.theta, phi_deg=args.phi, b_mm=b, a_mm=a,
                c_mm=c, half_pitch_mm=h, cell_pitch_mm=L,
                l1_mm=l1, l2_mm=l2, l3_mm=l3, radii_mm=radii,
                nominal_mu=sum(n*math.pi*r*r*l for n,r,l in zip((6,24,24),radii,(l1,l2,l3)))/L**3,
                repeat=list(args.repeat), stl_tolerance_mm=args.stl_tolerance)


def cell_graph(p):
    """8 cube vertices, 6 inner faces, 6 terminals, 12 recessed edge midpoints.

    D=(+-b,+-b,+-b); inner face B/E=+-a*axis; outer A/F=+-h*axis;
    C/G is a permutation of (0,+-c,+-c). No central node or solid faces.
    """
    b, a, c, h = (p[k] for k in ('b_mm','a_mm','c_mm','half_pitch_mm'))
    nodes, edges = {}, []
    for signs in itertools.product((-1,1), repeat=3):
        nodes['D'+''.join('p' if s>0 else 'm' for s in signs)] = tuple(s*b for s in signs)
    for axis in range(3):
        for sign in (-1,1):
            suffix = 'xyz'[axis] + ('p' if sign>0 else 'm')
            for prefix,dist in [('I',a),('T',h)]:
                v = [0.,0.,0.]; v[axis] = sign*dist
                nodes[prefix+suffix] = tuple(v)
            edges.append(('I'+suffix,'T'+suffix,1))
            for key,v in list(nodes.items()):
                if key.startswith('D') and sign*v[axis] > 0:
                    edges.append((key,'I'+suffix,2))
    for zero_axis in range(3):
        other = [i for i in range(3) if i != zero_axis]
        for signs in itertools.product((-1,1),repeat=2):
            v = [0.,0.,0.]
            for i,s in zip(other,signs): v[i] = s*c
            key = 'M'+'xyz'[zero_axis]+''.join('p' if s>0 else 'm' for s in signs)
            nodes[key] = tuple(v)
            for corner,pos in list(nodes.items()):
                if corner.startswith('D') and all(pos[i]*s > 0 for i,s in zip(other,signs)):
                    edges.append((corner,key,3))
    assert len(nodes) == 32 and Counter(t for _,_,t in edges) == {1:6,2:24,3:24}
    for u,v,t in edges:
        assert abs(math.dist(nodes[u],nodes[v]) - p[f'l{t}_mm']) < 1e-8
    return nodes, edges


def repeat_graph(nodes, edges, repeat, pitch):
    result, result_edges, lookup, interfaces = {}, [], {}, []
    terminal_owners = defaultdict(list)
    for cell in itertools.product(*(range(n) for n in repeat)):
        names = {}
        for name,pos in nodes.items():
            shifted = tuple(pos[i]+cell[i]*pitch for i in range(3))
            key = tuple(round(x,8) for x in shifted)
            if key not in lookup:
                lookup[key] = f'N{len(result):04d}'; result[lookup[key]] = shifted
            names[name] = lookup[key]
            if name.startswith('T'): terminal_owners[lookup[key]].append(list(cell))
        result_edges.extend((names[u],names[v],t) for u,v,t in edges)
    for node,owners in terminal_owners.items():
        if len(owners) == 2: interfaces.append(dict(node=node,position_mm=result[node],cells=owners))
        else: assert len(owners)==1
    expected = sum((repeat[i]-1)*math.prod(repeat[j] for j in range(3) if j!=i) for i in range(3))
    assert len(interfaces)==expected
    return result,result_edges,interfaces


def segment_distance(p0,p1,q0,q1):
    """Minimum distance of two finite centerlines (including endpoints)."""
    u,v,w = p1-p0,q1-q0,p0-q0
    aa,bb,cc,dd,ee = np.dot(u,u),np.dot(u,v),np.dot(v,v),np.dot(u,w),np.dot(v,w)
    det = aa*cc-bb*bb
    candidates = []
    if det > 1e-12*aa*cc:
        s,t = (bb*ee-cc*dd)/det,(aa*ee-bb*dd)/det
        if 0 <= s <= 1 and 0 <= t <= 1: candidates.append(np.linalg.norm(w+s*u-t*v))
    for s in (0.,1.):
        t = np.clip((ee+s*bb)/cc,0,1); candidates.append(np.linalg.norm(w+s*u-t*v))
    for t in (0.,1.):
        s = np.clip((t*bb-dd)/aa,0,1); candidates.append(np.linalg.norm(w+s*u-t*v))
    return float(min(candidates))


def graph_checks(nodes,edges,radii):
    neighbors = defaultdict(set)
    for u,v,_ in edges: neighbors[u].add(v); neighbors[v].add(u)
    visited, stack = set(),[next(iter(nodes))]
    while stack:
        u=stack.pop()
        if u not in visited: visited.add(u); stack.extend(neighbors[u]-visited)
    assert len(visited)==len(nodes), 'Disconnected centerline graph'
    pairs,minimum = 0,float('inf')
    coords = {k:np.array(v) for k,v in nodes.items()}
    # Capsule bounds enclose each flat-ended cylinder. Positive clearance proves
    # disjointness; negative clearance is conservatively rejected, not ignored.
    for i,(u,v,t) in enumerate(edges):
        for x,y,s in edges[i+1:]:
            if {u,v} & {x,y}: continue  # intended common joint
            gap = segment_distance(coords[u],coords[v],coords[x],coords[y])-radii[t-1]-radii[s-1]
            pairs += 1; minimum=min(minimum,gap)
            if gap <= 1e-7:
                raise ValueError(f'Nonincident struts may collide: {u}-{v}, {x}-{y}; capsule clearance {gap:g} mm')
    return dict(nodes=len(nodes),struts=len(edges),strut_types=dict(Counter(t for _,_,t in edges)),
                connected_components=1,node_degree_counts=dict(Counter(map(len,neighbors.values()))),
                nonincident_pairs_checked=pairs,minimum_nonincident_capsule_clearance_mm=minimum)


def cylinder(a,b,r):
    vec=cq.Vector(*b)-cq.Vector(*a)
    return cq.Solid.makeCylinder(r,vec.Length,cq.Vector(*a),vec.normalized())


def solid_check(shape):
    bb=shape.BoundingBox()
    result=dict(valid=shape.isValid(),solids=len(shape.Solids()),volume_mm3=shape.Volume(),
                bbox_mm=[bb.xlen,bb.ylen,bb.zlen],faces=len(shape.Faces()))
    if not result['valid'] or result['solids'] != 1 or result['volume_mm3'] <= 0:
        raise RuntimeError(f'Invalid or disconnected BRep: {result}')
    return result


def read_stl(path):
    data=path.read_bytes(); n=struct.unpack_from('<I',data,80)[0]
    dtype=np.dtype([('normal','<f4',(3,)),('points','<f4',(3,3)),('attribute','<u2')])
    assert len(data)==84+50*n, 'Expected binary STL'
    return np.frombuffer(data, dtype=dtype, count=n, offset=84)['points'].astype(float)


def mesh_check(path):
    triangles=read_stl(path)
    verts,idx=np.unique(np.round(triangles.reshape(-1,3),5),axis=0,return_inverse=True)
    faces=idx.reshape(-1,3)
    edges=np.concatenate([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]])
    directed_sign=np.where(edges[:,0]<edges[:,1],1,-1)
    _,inverse,counts=np.unique(np.sort(edges,axis=1),axis=0,return_inverse=True,return_counts=True)
    balance=np.bincount(inverse,weights=directed_sign)
    volume=np.einsum('ij,ij->i',triangles[:,0],np.cross(triangles[:,1],triangles[:,2])).sum()/6
    degenerate=int(np.count_nonzero(np.linalg.norm(np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0]),axis=1)<1e-10))
    result=dict(triangles=len(faces),vertices=len(verts),boundary_edges=int(np.count_nonzero(counts==1)),
                nonmanifold_edges=int(np.count_nonzero(counts>2)),orientation_errors=int(np.count_nonzero(balance)),
                degenerate_triangles=degenerate,signed_volume_mm3=float(volume),weld_tolerance_mm=1e-5)
    assert all(result[k]==0 for k in ('boundary_edges','nonmanifold_edges','orientation_errors','degenerate_triangles')),result
    assert volume>0
    return result


def export_check(shape,stem,out,p):
    before=solid_check(shape)
    step,stl=out/f'{stem}.step',out/f'{stem}.stl'
    cq.exporters.export(shape,str(step),exportType='STEP')
    shape.exportStl(str(stl),tolerance=p['stl_tolerance_mm'],angularTolerance=0.15,ascii=False,relative=False,parallel=False)
    after=solid_check(cq.importers.importStep(str(step)).val())
    delta=abs(after['volume_mm3']-before['volume_mm3'])/before['volume_mm3']
    assert delta<1e-7,(before,after)
    assert max(abs(a-b) for a,b in zip(before['bbox_mm'],after['bbox_mm']))<1e-6
    mesh=mesh_check(stl)
    mesh_error=abs(mesh['signed_volume_mm3']-before['volume_mm3'])/before['volume_mm3']
    assert mesh_error<0.01,mesh_error
    return dict(brep=before,step_reimport=after,step_relative_volume_error=delta,
                stl=mesh,stl_relative_volume_error=mesh_error)


def write_graph(nodes,edges,stem,out,p):
    with (out/f'{stem}_nodes.csv').open('w') as f:
        w=csv.writer(f); w.writerow(['node','x_mm','y_mm','z_mm']); w.writerows((n,*v) for n,v in nodes.items())
    with (out/f'{stem}_struts.csv').open('w') as f:
        w=csv.writer(f); w.writerow(['start','end','type','length_mm','radius_mm'])
        w.writerows((u,v,t,math.dist(nodes[u],nodes[v]),p['radii_mm'][t-1]) for u,v,t in edges)


def write_design_table(p,report,out):
    rows=[('theta',p['theta_deg'],'degree','논문 기본값 22.5; 사용자 변경 가능'),
          ('phi',p['phi_deg'],'degree','논문 기본값 22.5; 사용자 변경 가능'),
          ('L',p['cell_pitch_mm'],'mm','논문 기본값 77.1; 선택한 기준 길이로 결정'),
          ('l1/b',p['l1_mm']/p['b_mm'],'1','논문 기본값 1; 사용자 변경 가능'),
          ('mu_nominal',p['nominal_mu'],'1','식 (1), 접합부 중복을 포함한 공칭값')]
    for key in ('b_mm','l1_mm','l2_mm','l3_mm','a_mm','c_mm'):
        rows.append((key,p[key],'mm','입력값 및 기하 관계로 결정'))
    for i,r in enumerate(p['radii_mm'],1):
        rows.append((f'r{i}',r,'mm','반지름 입력 또는 식 (1)에서 역산; 직접 보고된 반지름 아님'))
    rows.extend([('repeat',' x '.join(map(str,p['repeat'])),'cells','사용자 입력'),
                 ('stl_tolerance',p['stl_tolerance_mm'],'mm','출력용 모델링 선택'),
                 ('actual_density',report['unit_cell']['actual_relative_density'],'1','CAD union 체적 / L^3')])
    with (out/'design_variables.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['variable','value','unit','provenance']);w.writerows(rows)
    # Independent relation from the paper: angle between Type II and Type III
    # at a common cube corner, Eq. (27).
    b,a,c=p['b_mm'],p['a_mm'],p['c_mm']
    v=np.array([-b,a-b,-b]); w=np.array([-b,c-b,c-b])
    actual=float(np.dot(v,w)/np.linalg.norm(v)/np.linalg.norm(w))
    theta,phi=map(math.radians,(p['theta_deg'],p['phi_deg']))
    l2,l3=p['l2_mm'],p['l3_mm']
    expected=(2*l3*math.cos(phi)**2+math.sqrt(2)*l3*math.cos(phi)*math.sin(phi)
              +math.sqrt(2)*l2*math.sin(phi)*math.sin(theta))/(2*l2)
    assert abs(actual-expected)<1e-12
    check=dict(equation_27_dot_product=actual,equation_27_expected=expected,
               alpha1_deg=math.degrees(math.acos(np.clip(actual,-1,1))),absolute_error=abs(actual-expected))
    (out/'paper_angle_crosscheck.json').write_text(json.dumps(check,indent=2)+'\n')


def preview(shape,stem,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    # Mesh the actual fused BRep for display, separate from export tolerance.
    vertices,faces=shape.tessellate(0.18,0.30)
    v=np.array([x.toTuple() for x in vertices]); tri=v[np.array(faces)]
    center=(v.max(axis=0)+v.min(axis=0))/2; tri=tri-center
    specs=[('isometric','Isometric',np.array([1.,1.,1.])),
           ('front','Front: XY / view from +Z',np.array([0.,0.,1.])),
           ('side','Side: ZY / view from +X',np.array([1.,0.,0.])),
           ('top','Top: XZ / view from +Y',np.array([0.,1.,0.]))]
    panels=[]
    for suffix,title,eye in specs:
        eye/=np.linalg.norm(eye)
        up=np.array([0.,0.,-1.]) if suffix=='top' else np.array([0.,1.,0.])
        right=np.cross(up,eye); right/=np.linalg.norm(right); up=np.cross(eye,right)
        basis=np.array([right,up,eye]); projected=tri@basis.T
        normals=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
        normals/=np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-15)
        light=eye+up*0.7-right*0.5; light/=np.linalg.norm(light)
        brightness=0.40+0.55*np.maximum(normals@light,0)
        color=np.array([.28,.65,.78])[None,:]*brightness[:,None]
        span=np.ptp(projected[:,:,:2].reshape(-1,2),axis=0).max()/2*1.14
        # Per-pixel depth testing avoids painter-order artifacts where long,
        # narrow triangles from intersecting strut directions overlap in view.
        resolution=1050
        raster=np.empty((resolution,resolution,3),dtype=np.uint8);raster[:]=[247,249,252]
        depth=np.full((resolution,resolution),-np.inf)
        pixels=(projected[:,:,:2]+span)/(2*span)*(resolution-1)
        for index in np.flatnonzero(normals@eye > 1e-10):
            xy=pixels[index]; z=projected[index,:,2]
            lo=np.maximum(np.floor(xy.min(axis=0)).astype(int),0)
            hi=np.minimum(np.ceil(xy.max(axis=0)).astype(int),resolution-1)
            if np.any(hi<lo): continue
            x,y=np.meshgrid(np.arange(lo[0],hi[0]+1),np.arange(lo[1],hi[1]+1))
            x0,y0=xy[0];x1,y1=xy[1];x2,y2=xy[2]
            denom=(y1-y2)*(x0-x2)+(x2-x1)*(y0-y2)
            if abs(denom)<1e-12: continue
            u=((y1-y2)*(x-x2)+(x2-x1)*(y-y2))/denom
            v=((y2-y0)*(x-x2)+(x0-x2)*(y-y2))/denom
            w=1-u-v;zz=u*z[0]+v*z[1]+w*z[2]
            sub=depth[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
            mask=(u>=-1e-8)&(v>=-1e-8)&(w>=-1e-8)&(zz>sub)
            sub[mask]=zz[mask]
            raster[lo[1]:hi[1]+1,lo[0]:hi[0]+1][mask]=np.uint8(np.clip(color[index]*255,0,255))
        fig,ax=plt.subplots(figsize=(7,7),dpi=150)
        ax.imshow(raster,origin='lower',extent=(-span,span,-span,span),interpolation='bilinear',zorder=1)
        ax.set(xlim=(-span,span),ylim=(-span,span),aspect='equal',title=title,xlabel='mm',ylabel='mm')
        ax.set_facecolor('#f7f9fc'); ax.grid(alpha=.12); ax.set_axisbelow(True)
        for i,label in enumerate('XYZ'):
            direction=basis[:2,i]
            if np.linalg.norm(direction)>.1:
                start=np.array([-span*.70,-span*.62]); end=start+direction*span*.23
                ax.annotate('',xy=end,xytext=start,arrowprops=dict(arrowstyle='->',color=['#c94a43','#348c54','#3654ad'][i]))
                ax.text(*(end+0.025*span),label,fontsize=9)
        fig.tight_layout(); path=out/f'{stem}_{suffix}.png';fig.savefig(path);plt.close(fig)
        panels.append(path)
    from PIL import Image
    canvas=Image.new('RGB',(2100,2100),'white')
    for i,path in enumerate(panels):
        canvas.paste(Image.open(path).convert('RGB'),((i%2)*1050,(i//2)*1050))
    canvas.save(out/f'{stem}_views.png')


def main():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    scale=parser.add_mutually_exclusive_group()
    for flag in ('cell-size','b','l2','l3'): scale.add_argument('--'+flag,type=float)
    type1=parser.add_mutually_exclusive_group()
    type1.add_argument('--l1',type=float)
    type1.add_argument('--l1-ratio',type=float,default=1.0)
    parser.add_argument('--theta',type=float,default=22.5);parser.add_argument('--phi',type=float,default=22.5)
    radial=parser.add_mutually_exclusive_group()
    radial.add_argument('--radius',type=float);radial.add_argument('--radii',type=float,nargs=3)
    parser.add_argument('--mu',type=float,default=.10)
    parser.add_argument('--repeat',type=int,nargs=3,default=(2,2,2),metavar=('NX','NY','NZ'))
    parser.add_argument('--stl-tolerance',type=float,default=.05)
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parent/'outputs')
    parser.add_argument('--no-preview',action='store_true')
    args=parser.parse_args();p=parameters(args);out=args.output;out.mkdir(parents=True,exist_ok=True)
    if args.stl_tolerance<=0: raise ValueError('STL tolerance must be positive')
    print(json.dumps(p,indent=2),flush=True)
    nodes,edges=cell_graph(p);start=time.time()
    graph=graph_checks(nodes,edges,p['radii_mm']); print('Unit graph verified',graph,flush=True)
    rods=[cylinder(nodes[u],nodes[v],p['radii_mm'][t-1]) for u,v,t in edges]
    print('Fusing 54 cylindrical struts...',flush=True)
    cell=rods[0].fuse(*rods[1:]).clean();solid_check(cell)
    unit_report=export_check(cell,'unit_cell',out,p)
    write_graph(nodes,edges,'unit_cell',out,p)
    print('Unit STEP and STL validated',unit_report,flush=True)
    nn,ee,interfaces=repeat_graph(nodes,edges,args.repeat,p['cell_pitch_mm'])
    lattice_graph=graph_checks(nn,ee,p['radii_mm']); print('Lattice graph verified',lattice_graph,flush=True)
    # A boundary joint is a full circular end face of two coaxial Type-I rods.
    degree=Counter(x for u,v,_ in ee for x in (u,v))
    for item in interfaces:
        node=item['node'];incident=[(u,v,t) for u,v,t in ee if node in (u,v)]
        assert degree[node]==2 and all(t==1 for _,_,t in incident)
        dirs=[np.array(nn[v if u==node else u])-nn[node] for u,v,_ in incident]
        dot=float(np.dot(dirs[0],dirs[1])/(np.linalg.norm(dirs[0])*np.linalg.norm(dirs[1])))
        assert abs(dot+1)<1e-10
        item.update(opposed_axis_dot=dot,shared_disk_area_mm2=math.pi*p['radii_mm'][0]**2)
    copies=[cell.translate(tuple(i*p['cell_pitch_mm'] for i in xyz)) for xyz in itertools.product(*(range(n) for n in args.repeat))]
    print(f'Fusing {len(copies)} unit cells at {len(interfaces)} periodic joints...',flush=True)
    lattice=copies[0].fuse(*copies[1:]).clean() if len(copies)>1 else copies[0]
    stem='lattice_'+'x'.join(map(str,args.repeat))
    lattice_report=export_check(lattice,stem,out,p)
    write_graph(nn,ee,stem,out,p)
    ratio=lattice.Volume()/(len(copies)*cell.Volume())
    assert abs(ratio-1)<1e-7, 'Unexpected cross-cell volume overlap or loss'
    unit_report['actual_relative_density']=cell.Volume()/p['cell_pitch_mm']**3
    report=dict(parameters=p,unit_cell=dict(graph=graph,**unit_report),lattice=dict(graph=lattice_graph,**lattice_report),
                boundary_joints=interfaces,lattice_to_sum_cell_volume_ratio=ratio,
                elapsed_before_preview_seconds=time.time()-start,
                material='Geometry only; TPU not assigned or simulated',cadquery_version=cq.__version__)
    (out/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'parameters.json').write_text(json.dumps(p,indent=2)+'\n')
    write_design_table(p,report,out)
    print('All CAD and mesh validations passed',flush=True)
    if not args.no_preview:
        preview(cell,'unit_cell',out);preview(lattice,stem,out)
    print(f'Completed in {time.time()-start:.1f}s: {out}',flush=True)


if __name__=='__main__': main()
