"""Portable review packages: extraction and confirmation never write a library."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

from PIL import Image
from fontTools.ttLib import TTFont, TTLibError
import ui

TYPES={'base':'底板','frame':'窗口框','button':'按钮','tab':'页签','avatar_frame':'头像框',
       'item_slot':'道具格','scroll_track':'轨道','scroll_thumb':'滑块',
       'progress_track':'进度槽','progress_fill':'进度填充',
       'decoration':'装饰','ui_icon':'图标','font':'字体'}


def asset_type(value):
    return 'decoration' if value=='separator' else value


def check_classification(record,required=False):
    if record is None:
        if required:raise ValueError('Classification evidence missing; inspect or ask user before extraction')
        return
    ui.validate_schema(record,'classification')
    if any(not record[k].strip() for k in ['role','basis']) or any(not e.strip() for e in record['evidence']):
        raise ValueError('Classification evidence must not be blank')
    if record['status']=='pending':raise ValueError('Classification unresolved; ask user: '+record['question'])


def file_info(path,kind):
    if kind=='font':
        if Path(path).suffix.lower() not in ('.ttf','.otf','.ttc'):raise ValueError('Unsupported font file format')
        try:
            with TTFont(path,fontNumber=0):pass
        except TTLibError as error:raise ValueError('Invalid font file') from error
        return {'size':None,'visible_bounds':None}
    with Image.open(path) as image:
        if image.format!='PNG':raise ValueError('Package images must be real PNG')
    return ui.image_info(path)


def project_name(value):
    if not isinstance(value,str) or not value or value in ('.','..') or re.search(r'[<>:"/\\|?*\x00-\x1f]',value) or value.endswith((' ','.')):
        raise ValueError('Invalid library project name')
    if value.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}:
        raise ValueError('Reserved library project name')
    return value


def content_hash(package):
    content={k:v for k,v in package.items() if k not in ('status','approval')}
    return hashlib.sha256(json.dumps(content,ensure_ascii=False,sort_keys=True).encode('utf-8')).hexdigest()


def validate(folder,approved=False,allow_test=False):
    folder=Path(folder).resolve();package=ui.read(folder/'package.json')
    if package['schema_version']!=1:raise ValueError('Unsupported asset package version')
    project_name(package['project'])
    if package['test_only'] and not allow_test:raise ValueError('Test packages cannot enter library')
    if not package['assets']:raise ValueError('Asset package is empty')
    ids=set()
    for asset in package['assets']:
        category=asset_type(asset['ui_type']);kind=asset.get('kind','ui')
        check_classification(asset.get('classification'))
        if category not in TYPES or (category=='font')!=(kind=='font') or not re.fullmatch(r'[A-Za-z0-9_-]+',asset['asset_id']) or asset['asset_id'] in ids or not re.fullmatch(r'[A-Za-z0-9_-]+',asset['asset_state']):
            raise ValueError('Invalid package asset identity or type')
        ids.add(asset['asset_id'])
        path=ui.inside(folder,asset['path'])
        if package['files'].get(asset['path'])!=asset['sha256']:raise ValueError('Asset hash differs from package inventory')
        info=file_info(path,kind)
        bounds=list(info['visible_bounds']) if info['visible_bounds'] else None
        if info['size']!=asset['size'] or bounds!=asset['visible_bounds']:
            raise ValueError('Package geometry changed')
    for path,digest in package['files'].items():
        if ui.digest(ui.inside(folder,path))!=digest:raise ValueError('Package file changed: '+path)
    if approved:
        if package['status']!='visual_approved':raise ValueError('Package needs explicit visual confirmation')
        evidence=package['approval']
        if evidence['content_sha256']!=content_hash(package):raise ValueError('Confirmed package metadata changed')
        if not evidence['actor'].strip() or not evidence['statement'].strip() or evidence['test_only']!=package['test_only']:
            raise ValueError('Invalid package approval')
        if ui.digest(ui.inside(folder,evidence['evidence_path']))!=evidence['evidence_sha256']:
            raise ValueError('Package approval evidence changed')
    return package


def prepare(config_path,manifest_path,build_path,out,project):
    import production
    config,manifest,source,inputs,resources=ui.load(config_path,manifest_path)
    build_path=Path(build_path).resolve();out=Path(out).resolve();project_name(project)
    if out.exists():raise ValueError('Package destination exists')
    if out.is_relative_to(build_path):raise ValueError('Package must be outside review directory')
    report=ui.read(build_path/'build.json')
    if report['manifest_hash']!=ui.digest(manifest_path) or report['config_hash']!=ui.digest(config_path) or report['inputs']!=inputs:
        raise ValueError('Review version changed; rebuild package inputs')
    expected={(p['id'],s) for p in manifest['pages'] for s in ['normal']+list(p.get('state_overrides',{}))}
    if {(p['id'],p['state']) for p in report['pages']}!=expected:raise ValueError('Package requires complete review')
    for p in report['pages']:
        if ui.digest(build_path/(p['id']+'--'+p['state']+'.png'))!=p['assembly_hash']:
            raise ValueError('Review image changed')
    if not production.quality(config_path,manifest_path)['passed']:raise ValueError('Asset quality gate failed')
    entries=[]
    for identity,asset in manifest['assets'].items():
        if asset['kind'] not in ('ui','font') or not resources[identity]['pages']:continue
        category='font' if asset['kind']=='font' else asset_type(asset.get('ui_type'))
        if category not in TYPES or (category=='font')!=(asset['kind']=='font'):raise ValueError('Classify UI asset before package: '+identity)
        classification=asset.get('classification')
        if asset['kind']=='font' and classification is None:
            classification={'status':'resolved','role':'Referenced font file','basis':'Real font file used by text layers',
                            'evidence':[asset['path']]}
        check_classification(classification,required=True)
        usages=[]
        for p in manifest['pages']:
            for state in ['normal']+list(p.get('state_overrides',{})):
                for layer in ui.expanded(manifest,p,state):
                    if layer.get('asset')==identity or layer.get('font')==identity:
                        usage={'page':p['id'],'state':state}
                        if asset['kind']=='font':usage.update(size=layer['size'],xy=layer['xy'])
                        else:usage.update(rect=layer['rect'],anchor=layer.get('anchor',[0,0]))
                        usages.append(usage)
        path=ui.inside(source,asset['path'])
        info=file_info(path,asset['kind'])
        suffix=path.suffix.lower() if asset['kind']=='font' else '.png'
        entries.append({'asset_id':identity,'name':asset.get('display_name',identity),'ui_type':category,'category':TYPES[category],'kind':asset['kind'],
            'classification':classification,
            'tags':asset.get('tags',[]),'asset_state':asset.get('asset_state','normal'),
            'path':'assets/'+identity+suffix,'sha256':asset['sha256'],'size':info['size'],
            'visible_bounds':info['visible_bounds'],'states':sorted({u['state'] for u in usages}),
            'usages':usages,'source':asset['source'],'license':asset['license']})
    if not entries:raise ValueError('No UI assets to package')
    out.mkdir(parents=True);(out/'assets').mkdir()
    for asset in entries:
        target=out/asset['path'];target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ui.inside(source,manifest['assets'][asset['asset_id']]['path']),target)
    shutil.copytree(build_path,out/'review')
    package={'schema_version':1,'project':project,'status':'candidate','test_only':bool(config['rules'].get('test_fixture')),
             'assets':entries,'source_manifest_sha256':ui.digest(manifest_path),
             'files':{p.relative_to(out).as_posix():ui.digest(p) for p in out.rglob('*') if p.is_file()}}
    production.write(out/'package.json',package)
    (out/'index.html').write_text('''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<title>待确认素材包</title><h1>素材包评审</h1><p>本包未自动入库。确认状态以 package.json 为准。</p>
<p><a href="review/index.html">组装对照</a> · <a href="package.json">标准素材清单</a></p>'''+
        ''.join('<p>'+a['category']+' · <a href="'+a['path']+'">'+a['asset_id']+'</a></p>' for a in entries),'utf-8')
    package['files']['index.html']=ui.digest(out/'index.html');production.write(out/'package.json',package,True)
    return {'package':str(out),'status':'candidate','assets':len(entries)}


def confirm(folder,evidence,actor,statement,test_only=False):
    import production
    folder=Path(folder).resolve();package=validate(folder,allow_test=True)
    if package['status']!='candidate':raise ValueError('Package is already confirmed; create a new version')
    evidence=Path(evidence).resolve()
    if not actor.strip() or not statement.strip() or not evidence.is_file():raise ValueError('Explicit human confirmation and evidence required')
    if test_only!=package['test_only']:raise ValueError('Test package approval must be marked test_only')
    target=folder/'approval.evidence'
    if target.exists():raise ValueError('Package evidence destination exists')
    shutil.copyfile(evidence,target)
    package['approval']={'actor':actor,'statement':statement,'test_only':test_only,
        'content_sha256':content_hash(package),'evidence_path':target.name,'evidence_sha256':ui.digest(target)}
    package['status']='visual_approved';production.write(folder/'package.json',package,True)
    return {'package':str(folder),'status':'visual_approved','library_written':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare')
    for field in ['config','manifest','build','out','project']:p.add_argument('--'+field,required=True)
    p=sub.add_parser('confirm')
    for field in ['package','evidence','actor','statement']:p.add_argument('--'+field,required=True)
    p.add_argument('--test-only',action='store_true');args=parser.parse_args()
    try:
        if args.command=='prepare':result=prepare(args.config,args.manifest,args.build,args.out,args.project)
        else:result=confirm(args.package,args.evidence,args.actor,args.statement,args.test_only)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (ValueError,OSError,KeyError,TypeError) as error:
        print(str(error),file=sys.stderr);sys.exit(1)
