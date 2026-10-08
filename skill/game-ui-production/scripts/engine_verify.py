"""Run isolated Godot checks and capture actual GPU output; no visual approval."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
from PIL import Image, ImageChops, ImageDraw
import ui
import production


def verify(export,godot,out,delivery):
    export=Path(export).resolve();out=Path(out).resolve()
    if out.exists():raise ValueError('Verification destination exists')
    report=ui.read(export/'adapter.json')
    for name,hash in report['files'].items():
        if ui.digest(ui.inside(export,name))!=hash:raise ValueError('Adapter input changed')
    frozen=Path(delivery).resolve()
    production.verify_delivery(frozen)
    if ui.digest(frozen/'delivery.json')!=report['delivery_sha256']:raise ValueError('Wrong source delivery')
    out.mkdir(parents=True)
    # Run in a copy so imports/test artifacts cannot modify the staged component.
    work=out/'project';shutil.copytree(export,work,ignore=shutil.ignore_patterns('.godot','*.import','*--engine.png','engine-tests.json'))
    steps=[('import',['--headless','--editor','--import']),('behavior',['--headless','--script','probe.gd']),
           ('render',['--position','-10000,-10000','--rendering-method','gl_compatibility','--script','render_probe.gd'])]
    logs={}
    for name,args in steps:
        result=subprocess.run([str(godot),'--path',str(work),*args],capture_output=True,text=True,
            encoding='utf-8',errors='replace',timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        log=result.stdout+'\n'+result.stderr
        (out/(name+'.log')).write_text(log,'utf-8');logs[name]=result.returncode
        if result.returncode or 'SCRIPT ERROR:' in log or 'ERROR:' in log:
            raise ValueError(f'Godot {name} failed; inspect {out/(name+".log")}')
    behavior=ui.read(work/'engine-tests.json')
    if not behavior['passed']:raise ValueError('Engine behavior checks failed')
    comparisons=[]
    for entry in ui.read(frozen/'review/build.json')['pages']:
        base=entry['id']+'--'+entry['state']
        source=work/(base+'--engine.png');reference=frozen/'review'/(base+'.png')
        a=Image.open(reference).convert('RGBA');b=Image.open(source).convert('RGBA')
        if a.size!=b.size:raise ValueError('Engine canvas mismatch')
        diff=ImageChops.difference(a,b)
        # getbbox(alpha) alone hides RGB differences when both alphas are equal.
        changed=sum(max(pixel)>8 for pixel in diff.get_flattened_data())
        text_mask=Image.new('L',a.size)
        draw=ImageDraw.Draw(text_mask)
        for layer in entry['layers']:
            if layer.get('text_bounds'):
                x0,y0,x1,y1=layer['text_bounds']
                draw.rectangle((x0-3,y0-3,x1+3,y1+3),fill=255)
        outside=sum(max(pixel)>8 and not text for pixel,text in zip(diff.get_flattened_data(),text_mask.get_flattened_data()))
        diff.convert('RGB').save(out/(base+'--difference.png'))
        comparisons.append({'page':entry['id'],'state':entry['state'],'assembly_sha256':ui.digest(reference),
            'engine_sha256':ui.digest(source),'changed_pixels_tolerance_8':changed,
            'outside_text_changed_pixels':outside,'text_regions_padding':3,'total_pixels':a.width*a.height})
    value={'adapter_sha256':ui.digest(export/'adapter.json'),'delivery_sha256':ui.digest(frozen/'delivery.json'),
        'behavior':behavior,'comparisons':comparisons,'steps':logs,'test_only':report['test_only'],
        'technical_passed':True,'visual_approved':False,'engine_verified':False,
        'next':'Human compares captures and plays the integrated UI; numerical difference is not approval'}
    production.write(out/'verification.json',value)
    return value


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['export','godot','out','delivery']:p.add_argument('--'+key,required=True)
    a=p.parse_args()
    try:
        import json
        print(json.dumps(verify(a.export,a.godot,a.out,a.delivery),ensure_ascii=False,indent=2))
    except (ValueError,OSError,subprocess.TimeoutExpired) as e:print(str(e),file=sys.stderr);sys.exit(1)
