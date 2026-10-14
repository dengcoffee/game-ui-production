"""Approved UI/font library, isolated by project; metadata files are authoritative."""
import argparse
import html
import json
from pathlib import Path
import re
import shutil
import sys
from urllib.parse import quote

import ui
from asset_package import TYPES, project_name, asset_type, file_info, check_classification
DEFAULT_ROOT=Path.home()/'Desktop/素材库'


def location(config_path):
    import production
    config,root=production.context(config_path)
    setting=config['rules'].get('asset_library')
    if not setting:raise ValueError('Configure rules.asset_library with project and root first')
    library=Path(setting.get('root',DEFAULT_ROOT)).expanduser()
    if not library.is_absolute():raise ValueError('Library root must be absolute')
    return config,root,library.resolve(),project_name(setting['project'])


def page(title,body):
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>'+html.escape(title)+'''</title>
<style>body{font:16px sans-serif;background:#20232a;color:#eee;margin:24px}a{color:#9cd8ed}
article{display:inline-block;vertical-align:top;width:260px;margin:8px;padding:12px;background:#30343d}
article[hidden]{display:none}
img{max-width:240px;max-height:180px;background:repeating-conic-gradient(#aaa 0% 25%,#eee 0% 50%) 0/20px 20px}
input,select{padding:8px;margin:8px}small{display:block;overflow-wrap:anywhere}</style>
<h1>'''+html.escape(title)+'</h1>'+body+'</html>'


def init_root(root):
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=True)
    links=''.join('<li><a href="'+quote(p.name)+'/index.html">'+html.escape(p.name)+'</a></li>'
                  for p in sorted(root.iterdir()) if p.is_dir() and (p/'index.json').is_file())
    (root/'index.html').write_text(page('项目素材库','<ul>'+links+'</ul>'),'utf-8')
    return {'root':str(root)}


def records(root,project):
    folder=Path(root).resolve()/project_name(project);result=[]
    for path in sorted(folder.glob('*/*.asset.json')):
        record=ui.read(path)
        record['ui_type']=asset_type(record['ui_type'])
        check_classification(record.get('classification'))
        if record['project']!=project or record['ui_type'] not in TYPES or record['status']!='visual_approved':
            raise ValueError('Invalid library metadata: '+str(path))
        for relative,hash_value in [(record['path'],record['sha256']),
                                    (record['approval_path'],record['approval_sha256']),
                                    (record['evidence_path'],record['evidence_sha256'])]:
            if ui.digest(ui.inside(folder,relative))!=hash_value:raise ValueError('Library file changed: '+relative)
        result.append(record)
    return result


def reindex(root,project):
    import production
    project=project_name(project);folder=Path(root).resolve()/project
    if not folder.is_dir():raise ValueError('Library project does not exist')
    entries=records(root,project)
    production.write(folder/'index.json',{'project':project,'assets':entries},True)
    cards=''
    for record in entries:
        text=' '.join([record['name'],record['asset_id'],TYPES[record['ui_type']],*record['tags'],*record['states']])
        cards+='<article data-type="'+record['ui_type']+'" data-search="'+html.escape(text.casefold(),quote=True)+'">'
        preview='字体文件' if record['ui_type']=='font' else '<img src="'+quote(record['path'])+'">'
        cards+='<a href="'+quote(record['path'])+'">'+preview+'</a><p>'+html.escape(record['name'])+'</p>'
        cards+='<small>'+html.escape(TYPES[record['ui_type']]+' · '+str(record['size'])+' · '+', '.join(record['states']))+'</small>'
        cards+='<small>'+html.escape(', '.join(record['tags']))+'</small></article>'
    options=''.join('<option value="'+key+'">'+value+'</option>' for key,value in TYPES.items())
    controls='<input id="query" placeholder="名称、标签或状态"><select id="type"><option value="">全部类型</option>'+options+'</select>'
    script='''<script>const q=document.getElementById('query'),t=document.getElementById('type');
function filter(){for(const c of document.querySelectorAll('article'))c.hidden=!!((t.value&&c.dataset.type!==t.value)||!c.dataset.search.includes(q.value.toLowerCase()));}
q.addEventListener('input',filter);t.addEventListener('change',filter);</script>'''
    (folder/'index.html').write_text(page(project+'素材',controls+cards+script),'utf-8')
    init_root(root)
    return {'project':project,'assets':len(entries)}


def approved_context(config_path,manifest_path,build_path,approval_path):
    config,source,root,project=location(config_path)
    _,manifest,_,inputs,resources=ui.load(config_path,manifest_path)
    approval=ui.read(approval_path);build_path=Path(build_path)
    if approval['state']!='visual_approved' or approval['test_only'] or config['rules'].get('test_fixture'):
        raise ValueError('Only genuine production visual approval may enter library')
    if approval['config_sha256']!=ui.digest(config_path) or approval['manifest_sha256']!=ui.digest(manifest_path) or approval['inputs']!=inputs:
        raise ValueError('Approved inputs changed')
    if approval['build_sha256']!=ui.digest(build_path/'build.json'):
        raise ValueError('Approved build changed')
    expected={(p['id'],s) for p in manifest['pages'] for s in ['normal']+list(p.get('state_overrides',{}))}
    if {(p['id'],p['state']) for p in approval['pages']}!=expected:
        raise ValueError('Approval must cover all page states')
    for entry in approval['pages']:
        if ui.digest(build_path/(entry['id']+'--'+entry['state']+'.png'))!=entry['assembly_sha256']:
            raise ValueError('Approved assembly changed')
    evidence=approval['evidence']
    if evidence['test_only'] or not evidence['actor'].strip() or not evidence['statement'].strip() or ui.digest(evidence['evidence_path'])!=evidence['evidence_sha256']:
        raise ValueError('Approval evidence changed or invalid')
    return config,source,root,project,manifest,resources,approval


def add(config_path,manifest_path,build_path,approval_path):
    import production
    config,source,root,project,manifest,resources,approval=approved_context(config_path,manifest_path,build_path,approval_path)
    evidence=approval['evidence']
    assets=[]
    for identity,asset in manifest['assets'].items():
        if asset['kind'] not in ('ui','font') or not resources[identity]['pages']:continue
        asset=dict(asset,ui_type='font' if asset['kind']=='font' else asset_type(asset.get('ui_type')))
        if asset.get('ui_type') not in TYPES:raise ValueError('Classify UI asset before library add: '+identity)
        check_classification(asset.get('classification'))
        if not re.fullmatch(r'[A-Za-z0-9_-]+',identity):raise ValueError('Unsafe asset ID')
        path=ui.inside(source,asset['path'])
        file_info(path,asset['kind'])
        usages=[]
        for p in manifest['pages']:
            for state in ['normal']+list(p.get('state_overrides',{})):
                for layer in ui.expanded(manifest,p,state):
                    if layer.get('asset')==identity or layer.get('font')==identity:
                        usage={'page':p['id'],'state':state}
                        if asset['kind']=='font':usage.update(size=layer['size'],xy=layer['xy'])
                        else:usage.update(rect=layer['rect'],anchor=layer.get('anchor',[0,0]))
                        usages.append(usage)
        assets.append((identity,asset,path,usages))
    return store(root,project,assets,approval_path,evidence)


def add_package(package_path,root=DEFAULT_ROOT):
    from asset_package import validate
    folder=Path(package_path).resolve();package=validate(folder,approved=True)
    assets=[]
    for record in package['assets']:
        asset=dict(record,display_name=record['name'],ui_type=asset_type(record['ui_type']))
        assets.append((record['asset_id'],asset,ui.inside(folder,record['path']),record['usages']))
    evidence=dict(package['approval'],evidence_path=str(ui.inside(folder,package['approval']['evidence_path'])))
    return store(Path(root).resolve(),package['project'],assets,folder/'package.json',evidence)


def store(root,project,assets,approval_path,evidence):
    import production
    folder=root/project;folder.mkdir(parents=True,exist_ok=True)
    proof=ui.digest(approval_path);proof_dir=folder/'证据';proof_dir.mkdir(exist_ok=True)
    for src,target in [(Path(approval_path),proof_dir/(proof+'.json')),
                       (Path(evidence['evidence_path']),proof_dir/(proof+'.evidence'))]:
        if target.exists() and ui.digest(target)!=ui.digest(src):raise ValueError('Stored approval changed')
        if not target.exists():shutil.copyfile(src,target)
    added=0
    for identity,asset,path,usages in assets:
        kind=asset.get('kind','ui');suffix=path.suffix.lower() if kind=='font' else '.png'
        relative=Path(TYPES[asset['ui_type']])/(identity+'--'+asset.get('asset_state','normal')+'--'+asset['sha256']+suffix)
        target=folder/relative;metadata=target.with_suffix('.asset.json')
        if metadata.exists():
            if ui.digest(target)!=asset['sha256']:raise ValueError('Stored asset changed')
            continue
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists() and ui.digest(target)!=asset['sha256']:raise ValueError('Stored asset changed')
        if not target.exists():shutil.copyfile(path,target)
        info=file_info(path,kind)
        record={'project':project,'kind':kind,'asset_id':identity,'name':asset.get('display_name',identity),
                'classification':asset.get('classification'),
                'ui_type':asset['ui_type'],'category':TYPES[asset['ui_type']],'tags':asset.get('tags',[]),'path':relative.as_posix(),
                'sha256':asset['sha256'],'size':info['size'],'visible_bounds':info['visible_bounds'],
                'states':sorted({u['state'] for u in usages}),'usages':usages,'source':asset['source'],
                'license':asset['license'],'status':'visual_approved',
                'approval_path':'证据/'+proof+'.json','approval_sha256':proof,
                'evidence_path':'证据/'+proof+'.evidence','evidence_sha256':evidence['evidence_sha256']}
        production.write(metadata,record);added+=1
    result=reindex(root,project);result['added']=added
    return result


def search(config_path,project=None,cross_project=False,ui_type=None,query='',state=None,size=None):
    _,_,root,current=location(config_path);project=project or current
    if project!=current and not cross_project:raise ValueError('Cross-project access requires explicit flag')
    entries=records(root,project)
    return [r for r in entries if (not ui_type or r['ui_type']==ui_type) and
            (not state or state in r['states']) and (not size or r['size']==list(size)) and
            query.casefold() in ' '.join([r['name'],r['asset_id'],*r['tags']]).casefold()]


def use(config_path,asset_path,out,project=None,cross_project=False):
    import production
    _,source,root,current=location(config_path);project=project or current
    record=next((r for r in search(config_path,project,cross_project) if r['path']==asset_path),None)
    if record is None:raise ValueError('Unknown library asset')
    destination=production.managed(source,out)
    if record['ui_type']=='font' and destination.suffix.lower()!=Path(record['path']).suffix.lower():raise ValueError('Preserve font file extension')
    if destination.exists() or destination.with_suffix('.provenance.json').exists():raise ValueError('Reuse destination exists')
    destination.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(ui.inside(root/project,record['path']),destination)
    production.write(destination.with_suffix('.provenance.json'),{'library_project':project,
        'library_asset':record,'sha256':ui.digest(destination),'status':'candidate','geometry_review_required':True})
    return {'file':str(destination),'status':'candidate','geometry_review_required':True}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('init');p.add_argument('--root',default=str(DEFAULT_ROOT))
    for name in ['add','search','reindex','use']:
        p=sub.add_parser(name);p.add_argument('--config',required=name!='add')
        if name=='add':
            p.add_argument('--package');p.add_argument('--root',default=str(DEFAULT_ROOT))
            for field in ['manifest','build','approval']:p.add_argument('--'+field)
        if name in ['search','use']:
            p.add_argument('--project');p.add_argument('--cross-project',action='store_true')
        if name=='search':
            p.add_argument('--type',choices=TYPES);p.add_argument('--query',default='');p.add_argument('--state');p.add_argument('--size',nargs=2,type=int)
        if name=='use':p.add_argument('--asset',required=True);p.add_argument('--out',required=True)
    args=parser.parse_args()
    try:
        if args.command=='init':result=init_root(args.root)
        elif args.command=='add':
            if args.package:
                if args.config or args.manifest or args.build or args.approval:raise ValueError('Package import is independent of project inputs')
                result=add_package(args.package,args.root)
            else:
                if not all([args.config,args.manifest,args.build,args.approval]):raise ValueError('Specify --package or all legacy approval inputs')
                result=add(args.config,args.manifest,args.build,args.approval)
        elif args.command=='search':result=search(args.config,args.project,args.cross_project,args.type,args.query,args.state,args.size)
        elif args.command=='use':result=use(args.config,args.asset,args.out,args.project,args.cross_project)
        else:
            _,_,root,project=location(args.config);result=reindex(root,project)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (ValueError,OSError,KeyError,TypeError) as error:
        print(str(error),file=sys.stderr);sys.exit(1)
