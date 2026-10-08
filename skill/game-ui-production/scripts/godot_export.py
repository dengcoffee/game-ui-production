"""Export a frozen manifest to an isolated Godot component and smoke project."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import sys

from PIL import Image, ImageDraw, ImageFont

import ui
import production


def export(delivery_path,out,test_only=False):
    delivery_path=Path(delivery_path).resolve()
    delivery=production.verify_delivery(delivery_path)
    if delivery['test_only']!=test_only:
        raise ValueError('Fixture delivery cannot be exported as production')
    config_path=delivery_path/'project.json';manifest_path=delivery_path/'manifest.json'
    _,manifest,root,_,_=ui.load(config_path,manifest_path)
    out=Path(out).resolve()
    if out.exists():raise ValueError('Godot export destination exists')
    out.mkdir(parents=True)
    (out/'assets').mkdir()
    fonts={}
    for key,a in manifest['assets'].items():
        if a['kind']=='font':
            source=ui.inside(root,a['path'])
            destination=out/'assets'/(key+source.suffix)
            shutil.copyfile(source,destination)
            fonts[key]='res://'+destination.relative_to(out).as_posix()
    pages=[];pending=[]
    for page in manifest['pages']:
        states={}
        for state in ['normal']+list(page.get('state_overrides',{})):
            layers=ui.expanded(manifest,page,state);coords=ui.positions(layers)
            output=[]
            for layer in sorted(layers,key=lambda v:v['z']):
                entry=copy.deepcopy(layer)
                entry['position']=coords[layer['id']][:2]
                if 'asset' in layer:
                    # Deterministic per-layer geometry preprocessing. Text remains live.
                    single=dict(layer)
                    single.pop('parent',None);single.pop('anchor',None)
                    single.pop('fill_binding',None)
                    single['rect']=coords[layer['id']]
                    scrolling=any(layer['id'] in r['layers'] for r in page.get('scroll_regions',[]))
                    if scrolling:
                        if single.get('clip'):raise ValueError('Scrolling images use region clipping; remove static layer clip')
                        single['rect']=[0,0,*coords[layer['id']][2:]]
                    sample=dict(manifest,canvas=coords[layer['id']][2:]) if scrolling else manifest
                    plane,_=ui.compose(sample,{'id':page['id'],'layers':[single]},root,'normal')
                    bounds=plane.getbbox()
                    if bounds:
                        file=f'{page["id"]}--{state}--{layer["id"]}.png'
                        plane.crop(bounds).save(out/'assets'/file)
                        entry['texture']='res://assets/'+file
                        entry['texture_offset']=list(bounds[:2]) if scrolling else [bounds[0]-entry['position'][0],bounds[1]-entry['position'][1]]
                    entry['control_size']=coords[layer['id']][2:]
                else:
                    font=ImageFont.truetype(str(ui.inside(root,manifest['assets'][layer['font']]['path'])),layer['size'])
                    dummy=ImageDraw.Draw(Image.new('RGBA',(1,1)))
                    value=str(ui.lookup(page.get('data',{}),layer.get('binding',''),layer['text']))
                    value=ui.layout_text(value,font,layer)
                    plain=dummy.textbbox((0,0),value,font=font)
                    anchored=dummy.textbbox((0,0),value,font=font,anchor=layer.get('text_anchor'))
                    entry.update(font_path=fonts[layer['font']],baseline=font.getmetrics()[0]+anchored[1]-plain[1],
                                 line_height=font.getbbox('A')[3]+layer.get('spacing',4),
                                 display_text=value,offset_x=anchored[0]-plain[0],control_size=[layer.get('max_width',manifest['canvas'][0]),manifest['canvas'][1]])
                    if layer.get('binding'):pending.append({'page':page['id'],'layer':layer['id'],'binding':layer['binding'],'owner':'game data source; UI exposes set_data'})
                output.append(entry)
            states[state]=output
        pages.append({'id':page['id'],'name':page['name'],'system':page['system'],'states':states,
                      'interactions':page.get('interactions',[]),'animations':page.get('animations',[]),'data':page.get('data',{})})
        pages[-1]['scroll_regions']=page.get('scroll_regions',[])
    payload={'schema_version':manifest['schema_version'],'canvas':manifest['canvas'],'pages':pages,
             'delivery_manifest_sha256':delivery['manifest_sha256'],'test_only':test_only}
    production.write(out/'ui-data.json',payload)
    for name in ['ui_view.gd','text_layer.gd','probe.gd','render_probe.gd']:
        shutil.copyfile(ui.HOME/'adapters/godot4'/name,out/name)
    (out/'ui.tscn').write_text('[gd_scene load_steps=2 format=3]\n\n[ext_resource type="Script" path="res://ui_view.gd" id="1"]\n\n[node name="GameUI" type="Control"]\nscript = ExtResource("1")\n', 'utf-8')
    w,h=manifest['canvas']
    (out/'project.godot').write_text(f'config_version=5\n[application]\nconfig/name="UI adapter validation"\nrun/main_scene="res://ui.tscn"\n[display]\nwindow/size/viewport_width={w}\nwindow/size/viewport_height={h}\nwindow/stretch/mode="canvas_items"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\ntextures/default_filters/use_nearest_mipmap_filter=false\n', 'utf-8')
    report={'adapter':'godot4','tool_version':ui.VERSION,'delivery_sha256':ui.digest(delivery_path/'delivery.json'),
            'test_only':test_only,'pending_bindings':pending,'engine_verified':False,
            'geometry_strategy':'same manifest; crop/contain/grid/alpha preprocessed per independent layer; dynamic text rendered by real FontFile',
            'font_rendering':'must compare engine screenshot; browser rasterization is not proof',
            'integration':'instance ui.tscn inside existing UI owner; connect action_requested; no game business/autoload/save modifications',
            'files':{p.relative_to(out).as_posix():ui.digest(p) for p in out.rglob('*') if p.is_file()}}
    production.write(out/'adapter.json',report)
    return {'project':str(out),'pages':len(pages),'pending_bindings':len(pending),'engine_verified':False}


def integrate(export_path,project_path,folder,test_only=False):
    source=Path(export_path).resolve();project=Path(project_path).resolve()
    if not (project/'project.godot').is_file():raise ValueError('Target is not an existing Godot project')
    target=production.managed(project,folder)
    if target.exists():raise ValueError('Component target exists; stage a new version and review callers before replacing')
    report=ui.read(source/'adapter.json')
    if report['test_only']!=test_only:raise ValueError('Fixture integration must be explicitly test_only')
    for name,hash in report['files'].items():
        if ui.digest(ui.inside(source,name))!=hash:raise ValueError('Staged adapter changed')
    prefix='res://'+target.relative_to(project).as_posix()+'/'
    target.mkdir(parents=True)
    copied={}
    for name in report['files']:
        if name in ['project.godot','probe.gd','render_probe.gd']:continue
        path=ui.inside(source,name);dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True)
        if path.suffix in ['.gd','.tscn','.json']:
            dest.write_text(path.read_text('utf-8').replace('res://',prefix),'utf-8')
        else:shutil.copyfile(path,dest)
        copied[name]=ui.digest(dest)
    production.write(target/'integration.json',{'source_adapter_sha256':ui.digest(source/'adapter.json'),
        'files':copied,'scene':prefix+'ui.tscn','pending_bindings':report['pending_bindings'],
        'engine_verified':False,'test_only':report['test_only'],
        'owner_actions':'Instance scene in existing UI owner; connect action_requested and supply set_data; retain game navigation/save/input lifecycle'})
    return {'scene':prefix+'ui.tscn','target':str(target),'business_modified':False}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--delivery');p.add_argument('--out');p.add_argument('--test-only',action='store_true')
    p.add_argument('--integrate');p.add_argument('--project');p.add_argument('--folder')
    a=p.parse_args()
    try:
        if a.integrate:
            if not a.project or not a.folder:p.error('integrate requires project and folder')
            result=integrate(a.integrate,a.project,a.folder,a.test_only)
        else:
            if not a.delivery or not a.out:p.error('export requires delivery and out')
            result=export(a.delivery,a.out,a.test_only)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (ValueError,OSError,KeyError) as e:print(str(e),file=sys.stderr);sys.exit(1)
