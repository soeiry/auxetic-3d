#!/usr/bin/env python3
"""JSON-driven editable CadQuery source; all physical inputs mm / degrees."""
import argparse
import csv
import json
import math
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import importlib.metadata
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent
KEYS = {'schema_version','L1_base','L2_base','D_base','Theta','Phi','ScaleFactor',
        'Nx','Ny','Nz','stl_tolerance_mm'}


def load_config(path):
    data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(data,dict) or set(data) != KEYS:
        raise ValueError(f'설정 키를 확인하세요. 필요한 키: {sorted(KEYS)}')
    for key,value in data.items():
        if type(value) not in (int,float) or not math.isfinite(value):
            raise ValueError(f'{key}: 유한한 숫자를 입력하세요.')
    if data['schema_version'] != 1:
        raise ValueError('지원하는 schema_version은 1입니다.')
    for key in ('L1_base','L2_base','D_base','ScaleFactor','stl_tolerance_mm'):
        if data[key] <= 0:
            raise ValueError(f'{key}: 0보다 커야 합니다.')
    for key in ('Nx','Ny','Nz'):
        if data[key] != int(data[key]) or not 1 <= data[key] <= 10:
            raise ValueError(f'{key}: 1~10 사이의 정수를 입력하세요.')
        data[key] = int(data[key])
    if data['Nx']*data['Ny']*data['Nz'] > 64:
        raise ValueError('이 버전은 최대 64셀까지 허용합니다. 전수 간섭 검사는 셀 수의 제곱에 비례합니다.')
    if not 0 < data['Theta'] < 35.264389 or not 0 < data['Phi'] < 54.735610:
        raise ValueError('각도 범위: 0 < Theta < 35.264389°, 0 < Phi < 54.735610°')
    return data


def geometry(data):
    import cad_core
    s=data['ScaleFactor']
    args=SimpleNamespace(theta=data['Theta'],phi=data['Phi'],b=None,l2=data['L2_base']*s,
                         l3=None,l1=data['L1_base']*s,l1_ratio=1.,cell_size=None,
                         mu=.1,radii=None,radius=data['D_base']*s/2,
                         repeat=[data[k] for k in ('Nx','Ny','Nz')],
                         stl_tolerance=data['stl_tolerance_mm'])
    return cad_core.parameters(args)


def write_user_table(data,p,folder):
    units={'L1_base':'mm','L2_base':'mm','D_base':'mm','Theta':'degree','Phi':'degree',
           'ScaleFactor':'unitless','Nx':'count','Ny':'count','Nz':'count'}
    rows=[(key,data[key],unit,'independent','config JSON / Inventor User Parameters') for key,unit in units.items()]
    derived=[('L1',p['l1_mm'],'L1_base * ScaleFactor'),('L2',p['l2_mm'],'L2_base * ScaleFactor'),
             ('StrutDiameter',2*p['radii_mm'][0],'D_base * ScaleFactor'),
             ('CubeHalf',p['b_mm'],'L2 * cos(Theta) / sqrt(2)'),
             ('L3',p['l3_mm'],'CubeHalf / cos(Phi)'),
             ('FaceInset',p['a_mm'],'CubeHalf - L2 * sin(Theta)'),
             ('EdgeCoord',p['c_mm'],'CubeHalf - L3 * sin(Phi) / sqrt(2)'),
             ('UnitPitch',p['cell_pitch_mm'],'2 * (L1 + FaceInset)')]
    rows.extend((key,value,'mm','dependent',formula) for key,value,formula in derived)
    with (folder/'user_parameters.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(['parameter','value','unit','role','expression_or_location']);writer.writerows(rows)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config',type=Path,default=ROOT/'config/paper_default.json')
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--replace',action='store_true',help='기존 결과를 .previous 폴더로 보존하고 교체')
    ap.add_argument('--no-preview',action='store_true')
    ap.add_argument('--check-only',action='store_true',help='파일 생성 없이 기하 및 전체 연결/간섭 검사')
    args=ap.parse_args()
    try:
        data=load_config(args.config)
        p=geometry(data)
        import cad_core
        nodes,edges=cad_core.cell_graph(p)
        cad_core.graph_checks(nodes,edges,p['radii_mm'])
        nn,ee,_=cad_core.repeat_graph(nodes,edges,p['repeat'],p['cell_pitch_mm'])
        cad_core.graph_checks(nn,ee,p['radii_mm'])
        if args.check_only:
            print('입력/연결/비접합 부재 간섭 검사 통과')
            print(json.dumps(p,indent=2));return
        target=args.output.resolve()
        if target.exists() and not args.replace:
            raise ValueError('출력 폴더가 있습니다. 다른 폴더를 지정하거나 --replace를 사용하세요.')
        target.parent.mkdir(parents=True,exist_ok=True)
        staging=Path(tempfile.mkdtemp(prefix=target.name+'.building-',dir=target.parent))
        command=[sys.executable,str(ROOT/'cad_core.py'),'--l1',str(p['l1_mm']),
                 '--l2',str(p['l2_mm']),'--radius',str(p['radii_mm'][0]),
                 '--theta',str(data['Theta']),'--phi',str(data['Phi']),
                 '--repeat',*(str(data[k]) for k in ('Nx','Ny','Nz')),
                 '--stl-tolerance',str(data['stl_tolerance_mm']),'--output',str(staging)]
        if args.no_preview: command.append('--no-preview')
        # Underlying builder exit status is preserved; partial results never replace
        # a previously successful output directory.
        subprocess.run(command,check=True)
        (staging/'input_parameters.json').write_text(json.dumps(data,indent=2)+'\n')
        write_user_table(data,p,staging)
        versions={'python':platform.python_version(),'platform':platform.platform(),
                  'inventor_executed':False,
                  'packages':{k:importlib.metadata.version(k) for k in
                              ('cadquery','cadquery-ocp','numpy','matplotlib','pillow')}}
        (staging/'environment.json').write_text(json.dumps(versions,indent=2)+'\n')
        if target.exists():
            i=1
            while target.with_name(target.name+f'.previous-{i}').exists(): i+=1
            backup=target.with_name(target.name+f'.previous-{i}')
            target.rename(backup);print('이전 결과 보존:',backup)
        staging.rename(target)
        print('생성 및 검증 완료:',target)
    except (ValueError,AssertionError,subprocess.CalledProcessError) as exc:
        print(f'생성 중단: {exc}',file=sys.stderr)
        sys.exit(1)


if __name__=='__main__': main()
