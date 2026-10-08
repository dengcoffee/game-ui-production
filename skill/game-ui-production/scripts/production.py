"""Project discovery, scoped production requests, candidates, gates and deliveries."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys

from fontTools.ttLib import TTFont
from PIL import Image

import ui


def write(path, value, replace=False):
    path = Path(path)
    if path.exists() and not replace:
        raise ValueError(f'Refusing overwrite: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix+'.tmp')
    if temporary.exists():
        raise ValueError(f'Pending write exists: {temporary}')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), 'utf-8')
    temporary.replace(path)


def context(config_path):
    path = Path(config_path).resolve()
    config = ui.read(path)
    ui.validate_schema(config, 'project')
    root = (path.parent/config['source_root']).resolve()
    return config, root


def managed(root, relative):
    path = (root/relative).resolve()
    if path == root or not path.is_relative_to(root):
        raise ValueError('Managed path must be below project root')
    return path


def discover(root):
    root = Path(root).resolve()
    excluded = {'.git','.venv','node_modules','.godot','__pycache__','Original_Backup','archive'}
    files = [p for p in root.rglob('*') if p.is_file() and not set(p.relative_to(root).parts)&excluded]
    docs = [p.relative_to(root).as_posix() for p in files if p.suffix.lower() in ['.md','.json']]
    images = []
    for path in files:
        if path.suffix.lower() in ['.png','.jpg','.webp']:
            images.append({'path': path.relative_to(root).as_posix(), 'sha256': ui.digest(path),
                           **ui.image_info(path), 'confirmation': 'unknown; consult project authority'})
    engines = [p.relative_to(root).as_posix() for p in files if p.name == 'project.godot']
    return {'root': str(root), 'documents': docs, 'images': images, 'godot_projects': engines,
            'fonts': [p.relative_to(root).as_posix() for p in files if p.suffix.lower() in ['.ttf','.otf','.ttc']],
            'confirmed_by_discovery': False}


def initialize(root,brief,canvas,engine,font,out):
    root=Path(root).resolve()
    if root.exists() and any(root.iterdir()):raise ValueError('Initialize only an empty new project; adopt existing projects')
    brief=Path(brief).read_text('utf-8-sig')
    if not brief.strip():raise ValueError('An explicit project art brief is required')
    root.mkdir(parents=True,exist_ok=True)
    (root/'ArtBible.md').write_text('# Project Art Bible — candidate\n\n'+brief+'\n\nVisual direction and representative samples require explicit user confirmation.\n','utf-8')
    write(root/'ui-status.json',{'schema_version':1,'format':'game-ui-production-status','state':'draft','systems':{},'visual_approved':False})
    source=Path(font).resolve()
    with TTFont(source,fontNumber=0):pass
    target=root/'assets'/source.name;target.parent.mkdir();shutil.copyfile(source,target)
    config={'schema_version':2,'source_root':str(root),'output_root':str(root/'.ui-production/reviews'),
        'engine':engine,'documents':['ArtBible.md'],'status_source':'ui-status.json','art_bible':'ArtBible.md',
        'rules':{'logical_canvas':canvas,'production_scope':['ui'],'candidate_dir':'.ui-production/candidates','artistic_retry_budget':2}}
    write(out,config)
    return {'config':str(out),'art_bible':str(root/'ArtBible.md'),'font':{'path':target.relative_to(root).as_posix(),'sha256':ui.digest(target)},
            'state':'draft','next':'Codex plans system/master/page geometry and representative sample assets from this brief; no visual approval inferred'}


def init_project(root, out, art_bible, documents, status_source, engine, new=False, canvas=None):
    root = Path(root).resolve()
    if new:
        root.mkdir(parents=True, exist_ok=True)
        bible = managed(root, art_bible)
        if bible.exists():
            raise ValueError('New project Art Bible already exists; adopt instead')
        raise ValueError('Create the user-reviewed Art Bible file first; then adopt it. No default art direction.')
    for name in documents + [art_bible, status_source]:
        ui.inside(root, name)
    result = {'schema_version': 2, 'source_root': str(root),
              'output_root': str(managed(root, '.ui-production/reviews')), 'engine': engine,
              'documents': documents, 'art_bible': art_bible, 'status_source': status_source,
              'rules': {'candidate_dir': '.ui-production/candidates', 'production_scope': ['ui'],
                        'artistic_retry_budget': 2}}
    if canvas:
        result['rules']['logical_canvas'] = canvas
    write(out, result)
    return {'config': str(Path(out).resolve()), 'inventory': discover(root)}


def plan(config_path, manifest_path, task, out):
    config, manifest, root, inputs, resources = ui.load(config_path, manifest_path)
    system = task['system']
    pages = [p for p in manifest['pages'] if p['system'] == system]
    if not pages:
        raise ValueError('Unknown task system')
    whitelist = set(config['rules'].get('production_scope', ['ui']))
    requests = task.get('assets', [])
    if len({a['id'] for a in requests}) != len(requests):
        raise ValueError('Duplicate requested assets')
    for asset in requests:
        if asset['kind'] not in whitelist:
            raise ValueError(f'Asset category outside project production scope: {asset["kind"]}')
        if not all(k in asset for k in ['purpose','display_size','states','alpha','allowed_changes']):
            raise ValueError('Asset request lacks purpose, geometry, states, alpha or edit scope')
        if asset['kind'] != 'ui' and asset['kind'] not in task.get('explicit_content_authorization', []):
            raise ValueError('Content production requires explicit task authorization')
    bible = ui.inside(root, config['art_bible']).read_text('utf-8-sig')
    request = {'schema_version': 1, 'system': system, 'config_sha256': ui.digest(config_path),
        'manifest_sha256': ui.digest(manifest_path), 'inputs': inputs,
        'references': [p['reference'] for p in pages], 'pages': [p['id'] for p in pages],
        'shared_masters': sorted({p['master'] for p in pages if p.get('master')}),
        'reused_assets': {k:v['pages'] for k,v in resources.items() if set(v['pages'])&{p['id'] for p in pages}},
        'assets': requests, 'art_bible': bible, 'rules': config['rules'],
        'retry_budget': config['rules'].get('artistic_retry_budget', 2), 'status': 'candidate',
        'prompts': {a['id']: '\n'.join([
            'Project Art Bible:\n'+bible, 'System context: '+system,
            'Shared layers are immutable except explicitly allowed regions.',
            'Asset specification: '+json.dumps(a, ensure_ascii=False),
            'Project rules: '+json.dumps(config['rules'], ensure_ascii=False),
            'Exclude dynamic text, character portraits, item icons, maps and scene backgrounds unless explicitly authorized.',
            'Generate only this independent asset. Preserve complete edges, shadows and required effects.']) for a in requests}}
    write(out, request)
    return {'request': str(out), 'assets': len(requests), 'pages': request['pages']}


def capabilities():
    return {'builtin_imagegen': {'execution': 'Codex host tool; not callable from Python',
        'operations': ['generate','edit_with_reference','transparent_asset'],
        'availability': 'host must inspect current tool schema', 'pixel_lock': False,
        'verified_calls': 'consult provider-results.json; never infer success from tool availability'},
        'external': {'operations': ['import_external_result'], 'verified': True,
                     'formats': ['PNG'], 'requires_api_key': False}}


def ledger_path(config, root):
    return managed(root, config['rules'].get('candidate_dir', '.ui-production/candidates'))/'index.json'


def import_candidate(config_path, request_path, file, identity, state, origin, license, method='external', attempt=None):
    config, root = context(config_path)
    request = ui.read(request_path)
    if request['config_sha256'] != ui.digest(config_path):
        raise ValueError('Production request is stale for project config')
    if any(ui.digest(p) != h for p,h in request['inputs'].items()):
        raise ValueError('Production request inputs changed; replan before producing')
    spec = next((a for a in request['assets'] if a['id'] == identity), None)
    if spec is None or state not in spec['states']:
        raise ValueError('Asset or state is outside production request')
    if spec['kind'] not in config['rules'].get('production_scope', ['ui']):
        raise ValueError('Production category no longer allowed')
    if not identity.replace('-','').replace('_','').isalnum() or not state.replace('-','').replace('_','').isalnum():
        raise ValueError('Unsafe asset/state ID')
    file = Path(file).resolve()
    with Image.open(file) as source:
        if source.format != 'PNG':
            raise ValueError('Import must be a real PNG')
    info = ui.image_info(file, spec.get('alpha_threshold', 0))
    if spec['alpha'] and (not info['has_alpha_channel'] or info['alpha_extrema'][0] == 255):
        raise ValueError('Required genuine transparency is absent')
    if info['visible_bounds'] is None:
        raise ValueError('Empty image')
    base = ledger_path(config, root)
    ledger = ui.read(base) if base.exists() else {'schema_version': 1, 'candidates': [], 'attempts': []}
    attempts = [a for a in ledger['attempts'] if a['id'] == identity and a['state'] == state and a['request']==ui.digest(request_path)]
    ticket = next((a for a in attempts if a.get('ticket')==attempt and a['outcome']=='prepared'),None) if attempt else None
    if attempt and ticket is None:
        raise ValueError('Unknown or already completed provider attempt')
    if not ticket and len(attempts) >= request['retry_budget']:
        raise ValueError('Artistic retry budget exhausted; diagnose or obtain a revised production request')
    hash = ui.digest(file)
    relative = (base.parent/identity/state/(hash+'.png')).relative_to(root).as_posix()
    destination = managed(root, relative)
    if destination.exists():
        raise ValueError('This exact candidate already exists')
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(file, destination)
    record = {'id': identity, 'state': state, 'path': relative, 'sha256': hash,
              'source': origin, 'license': license, 'method': method, 'status': 'candidate',
              'request_sha256': ui.digest(request_path), 'spec': spec, 'info': info,
              'created_at': datetime.now(timezone.utc).isoformat()}
    ledger['candidates'].append(record)
    if ticket:
        ticket.update(outcome='imported',output_sha256=hash)
    else:
        ledger['attempts'].append({'id': identity, 'state': state, 'request': ui.digest(request_path), 'outcome': 'imported'})
    write(base, ledger, True)
    return record


def prepare_provider(config_path,request_path,identity,state,operation,references,out):
    config,root=context(config_path)
    request=ui.read(request_path)
    if request['config_sha256']!=ui.digest(config_path) or any(ui.digest(p)!=h for p,h in request['inputs'].items()):
        raise ValueError('Production request is stale')
    spec=next((v for v in request['assets'] if v['id']==identity),None)
    if not spec or state not in spec['states']:raise ValueError('Asset/state outside production plan')
    if operation=='edit_with_reference' and not references:raise ValueError('Reference editing needs explicit local targets')
    paths=[str(ui.inside(root,p)) for p in references]
    args={'prompt':request['prompts'][identity]+'\nTarget state: '+state+
          '\nOperation: '+operation+'; preserve only declared invariants; no pixel-lock guarantee.',
          'transparent_background':bool(spec['alpha'])}
    if paths:args['referenced_image_paths']=paths
    base=ledger_path(config,root)
    ledger=ui.read(base) if base.exists() else {'schema_version':1,'candidates':[],'attempts':[]}
    used=[v for v in ledger['attempts'] if v['id']==identity and v['state']==state and v['request']==ui.digest(request_path)]
    if len(used)>=request['retry_budget']:raise ValueError('Provider retry budget exhausted')
    ticket=hashlib.sha256((ui.digest(request_path)+identity+state+str(len(used))).encode()).hexdigest()
    result={'provider':'builtin_imagegen','tool':'image_gen.imagegen','arguments':args,'ticket':ticket,
            'requires_view_image_first':paths,'external_fallback':'production.py import',
            'reference_hashes':{p:ui.digest(p) for p in paths},'claim':'tool request; not generated output'}
    write(out,result)
    ledger['attempts'].append({'id':identity,'state':state,'request':ui.digest(request_path),
                               'ticket':ticket,'operation':operation,'outcome':'prepared'})
    write(base,ledger,True)
    return result


def provider_failure(config_path,ticket,reason):
    config,root=context(config_path)
    base=ledger_path(config,root);ledger=ui.read(base)
    record=next((v for v in ledger['attempts'] if v.get('ticket')==ticket and v['outcome']=='prepared'),None)
    if record is None:raise ValueError('Unknown provider attempt')
    record.update(outcome='failed',reason=reason)
    write(base,ledger,True)
    return {'recorded':True,'fallback':'external import remains available under a revised plan'}


def attach_candidate(config_path, manifest_path, candidate_path, asset_id, out):
    config, manifest, root, _, resources = ui.load(config_path, manifest_path)
    ledger = ui.read(ledger_path(config, root))
    record = next((v for v in ledger['candidates'] if v['path'] == candidate_path), None)
    if record is None or ui.digest(ui.inside(root, record['path'])) != record['sha256']:
        raise ValueError('Unknown or changed candidate')
    new = copy.deepcopy(manifest)
    new['assets'][asset_id] = {k:record[k] for k in ['path','sha256','source','license','status']}
    new['assets'][asset_id]['kind'] = record['spec']['kind']
    write(out, new)
    return {'manifest': str(out), 'affected_pages': resources.get(asset_id, {}).get('pages', []), 'status': 'candidate'}


def quality(config_path, manifest_path):
    config, manifest, root, _, resources = ui.load(config_path, manifest_path)
    errors, warnings = [], []
    for identity, data in resources.items():
        if data['license'].lower().startswith('unknown'):
            warnings.append({'asset': identity, 'issue': 'license_unknown'})
        if data['kind'] == 'font':
            continue
        if data['visible_bounds'] is None:
            errors.append({'asset': identity, 'issue': 'empty_alpha'})
    constraints = config['rules'].get('asset_constraints', {})
    for identity, rule in constraints.items():
        if identity not in resources:
            errors.append({'asset': identity, 'issue': 'required_asset_missing'})
            continue
        data = resources[identity]
        if rule.get('alpha') and (not data['has_alpha_channel'] or data['alpha_extrema'][0] == 255):
            errors.append({'asset': identity, 'issue': 'missing_transparency'})
        if rule.get('size') and data.get('size') != rule['size']:
            errors.append({'asset': identity, 'issue': 'source_canvas_mismatch'})
    for group in config['rules'].get('state_groups', []):
        entries = [resources[k] for k in group if k in resources]
        if len(entries) != len(group) or len({tuple(v.get('size', [])) for v in entries}) != 1:
            errors.append({'group': group, 'issue': 'state_geometry_mismatch'})
    font_maps = {}
    for page in manifest['pages']:
        for state in ['normal']+list(page.get('state_overrides', {})):
            layers = ui.expanded(manifest, page, state)
            for layer in layers:
                if 'font' in layer:
                    key = layer['font']
                    if key not in font_maps:
                        with TTFont(ui.inside(root, manifest['assets'][key]['path']), fontNumber=0) as font:
                            font_maps[key] = font.getBestCmap() or {}
                    value = str(ui.lookup(page.get('data', {}), layer['binding'], layer['text'])) if layer.get('binding') else layer['text']
                    missing = sorted({c for c in value if not c.isspace() and ord(c) not in font_maps[key]})
                    if missing:
                        errors.append({'page': page['id'], 'layer': layer['id'], 'issue': 'missing_glyphs', 'characters': missing})
                if 'asset' in layer:
                    data = resources[layer['asset']]
                    bounds = layer.get('crop') or data['visible_bounds'] if layer.get('body') else layer.get('crop')
                    size = [bounds[2]-bounds[0], bounds[3]-bounds[1]] if bounds else data['size']
                    if max(layer['rect'][2]/size[0], layer['rect'][3]/size[1]) > config['rules'].get('max_upscale', 2):
                        warnings.append({'page': page['id'], 'layer': layer['id'], 'issue': 'upscale_precision'})
                    if layer['resize'] == 'stretch' and abs(size[0]/size[1]-layer['rect'][2]/layer['rect'][3]) > .05:
                        warnings.append({'page': page['id'], 'layer': layer['id'], 'issue': 'nonuniform_stretch_declared'})
                if layer.get('binding') and ui.lookup(page.get('data', {}), layer['binding']) is None:
                    warnings.append({'page': page['id'], 'layer': layer['id'], 'issue': 'binding_uses_placeholder', 'binding': layer['binding']})
    return {'passed': not errors, 'errors': errors, 'warnings': warnings, 'visual_approved': False}


def approval(config_path, manifest_path, build_path, evidence, actor, statement, out, test_only=False):
    config, manifest, root, inputs, _ = ui.load(config_path, manifest_path)
    report = ui.read(Path(build_path)/'build.json')
    if report['manifest_hash'] != ui.digest(manifest_path) or report['config_hash'] != ui.digest(config_path):
        raise ValueError('Approval does not match built version')
    evidence = Path(evidence).resolve()
    if not actor.strip() or not statement.strip() or not evidence.is_file():
        raise ValueError('Explicit human approval statement and evidence are required')
    if test_only != bool(config['rules'].get('test_fixture', False)):
        raise ValueError('Fixture approvals must be marked test_only; production cannot use them')
    gate = quality(config_path, manifest_path)
    if not gate['passed']:
        raise ValueError('Asset gate failed')
    expected={(p['id'],s) for p in manifest['pages'] for s in ['normal']+list(p.get('state_overrides',{}))}
    if {(p['id'],p['state']) for p in report['pages']}!=expected:
        raise ValueError('Approval must cover every page/state in this delivery manifest')
    if any(ui.digest(p)!=h for p,h in report['inputs'].items()):
        raise ValueError('Review inputs changed; rebuild before approval')
    for entry in report['pages']:
        file = Path(build_path)/(entry['id']+'--'+entry['state']+'.png')
        if ui.digest(file) != entry['assembly_hash']:
            raise ValueError('Review image changed since build')
    evidence_record = {'actor': actor, 'statement': statement, 'evidence_sha256': ui.digest(evidence),
                       'evidence_path': str(evidence), 'test_only': test_only}
    record = {'schema_version': 1, 'state': 'visual_approved', 'test_only': test_only,
              'manifest_sha256': ui.digest(manifest_path), 'config_sha256': ui.digest(config_path),
              'build_sha256': ui.digest(Path(build_path)/'build.json'), 'inputs': inputs,
              'pages': [dict(id=p['id'], state=p['state'], reference_sha256=p['reference_hash'],
                            assembly_sha256=p['assembly_hash']) for p in report['pages']],
              'evidence': evidence_record}
    write(out, record)
    return record


def freeze(config_path, manifest_path, build_path, approval_path, out):
    config, manifest, root, inputs, _ = ui.load(config_path, manifest_path)
    approved = ui.read(approval_path)
    if approved['state'] != 'visual_approved' or approved['manifest_sha256'] != ui.digest(manifest_path):
        raise ValueError('Exact visual approval is required before freezing')
    if approved['config_sha256'] != ui.digest(config_path) or approved['inputs'] != inputs:
        raise ValueError('Approved inputs changed; re-review required')
    if approved['build_sha256'] != ui.digest(Path(build_path)/'build.json'):
        raise ValueError('Approved build report changed')
    for page in approved['pages']:
        if ui.digest(Path(build_path)/(page['id']+'--'+page['state']+'.png')) != page['assembly_sha256']:
            raise ValueError('Approved review image changed')
    evidence = approved['evidence']
    if ui.digest(evidence['evidence_path']) != evidence['evidence_sha256']:
        raise ValueError('Approval evidence changed')
    out = Path(out).resolve()
    if out.exists():
        raise ValueError('Delivery destination exists')
    out.mkdir(parents=True)
    for file in inputs:
        source = Path(file)
        if source.is_relative_to(root):
            target = out/'source'/source.relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    portable = dict(config, source_root='source', output_root='reviews')
    write(out/'project.json', portable)
    write(out/'manifest.json', manifest)
    write(out/'approval.json', approved)
    shutil.copyfile(evidence['evidence_path'], out/'approval-evidence.txt')
    shutil.copytree(build_path, out/'review')
    files = {p.relative_to(out).as_posix():ui.digest(p) for p in out.rglob('*') if p.is_file()}
    delivery = {'schema_version': 1, 'state': 'visual_approved', 'test_only': approved['test_only'],
                'tool_version': ui.VERSION, 'manifest_sha256': ui.digest(out/'manifest.json'),
                'source_manifest_sha256': ui.digest(manifest_path), 'art_bible_sha256': ui.digest(ui.inside(root, config['art_bible'])),
                'schema': manifest['schema_version'], 'files': files, 'engine_verified': False}
    write(out/'delivery.json', delivery)
    return {'delivery': str(out), 'test_only': approved['test_only'], 'files': len(files)}


def verify_delivery(path):
    path = Path(path).resolve()
    delivery = ui.read(path/'delivery.json')
    for name, hash in delivery['files'].items():
        if ui.digest(ui.inside(path, name)) != hash:
            raise ValueError(f'Frozen delivery changed: {name}')
    return delivery


def protected_assets(config,root,manifest_path):
    protected=set()
    files=[Path(manifest_path)]+[ui.inside(root,p) for p in config['rules'].get('protected_manifests',[])]
    for file in files:
        manifest=ui.read(file);ui.validate_schema(manifest,'manifest')
        protected.update(ui.inside(root,a['path']) for a in manifest['assets'].values())
    return protected


def clean_plan(config_path, manifest_path, out):
    config, _, root, _, _ = ui.load(config_path, manifest_path)
    base = ledger_path(config, root)
    ledger = ui.read(base) if base.exists() else {'candidates': []}
    manifest = ui.read(manifest_path)
    protected = protected_assets(config,root,manifest_path)
    latest = {}
    for record in ledger['candidates']:
        latest[(record['id'],record['state'])] = record['path']
    files = [r for r in ledger['candidates'] if r['path'] not in latest.values()
             and managed(root, r['path']).is_file() and managed(root,r['path']) not in protected]
    plan = {'schema_version': 1, 'manifest_sha256': ui.digest(manifest_path),
            'config_sha256': ui.digest(config_path), 'files': [{'path':r['path'],'sha256':r['sha256']} for r in files],
            'operation': 'archive; reversible; no permanent deletion'}
    write(out, plan)
    return plan


def clean_execute(config_path, manifest_path, plan_path, archive):
    config, _, root, _, _ = ui.load(config_path, manifest_path)
    plan = ui.read(plan_path)
    if plan['manifest_sha256'] != ui.digest(manifest_path) or plan['config_sha256'] != ui.digest(config_path):
        raise ValueError('Cleanup plan is stale')
    protected = protected_assets(config,root,manifest_path)
    candidate_root = ledger_path(config,root).parent
    ledger=ui.read(ledger_path(config,root))
    registered={r['path']:r['sha256'] for r in ledger['candidates']}
    latest={}
    for r in ledger['candidates']:latest[(r['id'],r['state'])]=r['path']
    archive = managed(root,archive)
    if archive.exists() or archive.is_relative_to(candidate_root) or candidate_root.is_relative_to(archive):
        raise ValueError('Archive must be a new independent directory below project root')
    sources = []
    if len({e['path'] for e in plan['files']})!=len(plan['files']):raise ValueError('Duplicate cleanup targets')
    for entry in plan['files']:
        path = ui.inside(root,entry['path'])
        if (not path.is_relative_to(candidate_root) or path in protected or ui.digest(path) != entry['sha256']
                or registered.get(entry['path'])!=entry['sha256'] or entry['path'] in latest.values()):
            raise ValueError('Cleanup target is changed, protected or outside candidate directory')
        sources.append((entry,path))
    archive.mkdir(parents=True)
    journal = {'root':str(root),'files':[],'restored':False}
    write(archive/'restore.json',journal)
    for entry,path in sources:
        target = archive/'files'/entry['path']
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.move(str(path),str(target))
        journal['files'].append(entry)
        write(archive/'restore.json',journal,True)
    return {'archived':len(sources),'restore':str(archive/'restore.json')}


def restore(config_path, archive):
    _, root = context(config_path)
    archive = managed(root,archive)
    journal = ui.read(archive/'restore.json')
    if journal['root'] != str(root) or journal['restored']:
        raise ValueError('Wrong project or already restored')
    for entry in journal['files']:
        source = ui.inside(archive,'files/'+entry['path'])
        if ui.digest(source) != entry['sha256'] or managed(root,entry['path']).exists():
            raise ValueError('Restore source changed or destination exists')
    for entry in journal['files']:
        target = managed(root,entry['path'])
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.move(str(archive/'files'/entry['path']),str(target))
    journal['restored'] = True
    write(archive/'restore.json',journal,True)
    return {'restored':len(journal['files'])}


def stress(config_path, manifest_path, cases, out):
    _, manifest, _, _, _ = ui.load(config_path,manifest_path)
    out = Path(out)
    if out.exists():
        raise ValueError('Stress destination exists')
    out.mkdir(parents=True)
    results = []
    for case in cases:
        if not case['id'].replace('-','').replace('_','').isalnum():
            raise ValueError('Unsafe stress ID')
        sample = copy.deepcopy(manifest)
        for page in sample['pages']:
            page['data'] = case.get('data',{})
            for layer in page['layers']:
                if layer['id'] in case.get('text',{}):
                    layer['text'] = case['text'][layer['id']]
                layer.update(case.get('layers',{}).get(layer['id'],{}))
        file = out/(case['id']+'.json')
        write(file,sample)
        results.append({'case':case['id'],'quality':quality(config_path,file),
                        'build':ui.build(config_path,file,out/case['id'])})
    write(out/'results.json',results)
    return results


def migrate(manifest_path,out):
    manifest = ui.read(manifest_path)
    ui.validate_schema(manifest,'manifest')
    if manifest['schema_version'] != 1:
        raise ValueError('Only schema 1 to 2 migration is supported')
    manifest['schema_version'] = 2
    manifest.setdefault('typography',{})
    write(out,manifest)
    return {'from':1,'to':2,'output':str(out),'source_unchanged':True}


def sync_status(config_path,manifest_path,system,state,expected_sha,evidence,actor,statement,
                delivery=None,verification=None,test_only=False):
    config,manifest,root,_,_=ui.load(config_path,manifest_path)
    path=ui.inside(root,config['status_source'])
    if ui.digest(path)!=expected_sha:raise ValueError('Authority index changed; reread before updating')
    index=ui.read(path)
    if index.get('format')!='game-ui-production-status':
        raise ValueError('Existing authority has a different format; update that document in place after reviewing its conventions')
    if system not in {s['id'] for s in manifest['systems']}:raise ValueError('Unknown system')
    states=['draft','candidate','approved_reference','assets_verified','visual_approved','engine_verified']
    if state not in states:raise ValueError('Unknown production state')
    if test_only!=bool(config['rules'].get('test_fixture',False)):raise ValueError('Fixture status must be marked test_only')
    evidence=Path(evidence).resolve()
    if not evidence.is_file() or not actor.strip() or not statement.strip():raise ValueError('Explicit evidence and responsible actor required')
    if state=='assets_verified' and not quality(config_path,manifest_path)['passed']:raise ValueError('Asset gate failed')
    frozen=None
    if state in ['visual_approved','engine_verified']:
        if not delivery:raise ValueError('Frozen exact-version approval required')
        frozen=verify_delivery(delivery)
        if frozen['source_manifest_sha256']!=ui.digest(manifest_path) or frozen['test_only']!=test_only:
            raise ValueError('Frozen version or confirmation type mismatch')
    if state=='engine_verified':
        if not verification:raise ValueError('Engine technical verification plus human play evidence required')
        verified=ui.read(verification)
        if (not verified['technical_passed'] or verified['delivery_sha256']!=ui.digest(Path(delivery)/'delivery.json')
                or verified['test_only']!=test_only):raise ValueError('Wrong engine verification')
    snapshots=managed(root,'.ui-production/state-backups')
    if snapshots.exists() and len(list(snapshots.glob('*.json')))>=config['rules'].get('status_snapshot_limit',8):
        raise ValueError('Status snapshot budget exhausted; review recoverable snapshots before continuing')
    snapshots.mkdir(parents=True,exist_ok=True)
    backup=snapshots/(expected_sha+'.json')
    if not backup.exists():shutil.copyfile(path,backup)
    index['systems'][system]={'state':state,'manifest_sha256':ui.digest(manifest_path),
        'test_only':test_only,'actor':actor,'statement':statement,'evidence_path':str(evidence),
        'evidence_sha256':ui.digest(evidence),'delivery':str(Path(delivery).resolve()) if delivery else None,
        'verification':str(Path(verification).resolve()) if verification else None}
    write(path,index,True)
    return {'authority':str(path),'system':system,'state':state,'backup':str(backup),
        'next':'Rebuild after authority changes; existing frozen packages remain immutable'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command',required=True)
    p = subs.add_parser('discover'); p.add_argument('--root',required=True)
    p = subs.add_parser('adopt')
    for field in ['root','out','art-bible','status-source','engine']: p.add_argument('--'+field,required=True)
    p.add_argument('--documents',nargs='+',required=True);p.add_argument('--canvas',nargs=2,type=int)
    p=subs.add_parser('init')
    for key in ['root','brief','engine','font','out']:p.add_argument('--'+key,required=True)
    p.add_argument('--canvas',nargs=2,type=int,required=True)
    subs.add_parser('capabilities')
    p = subs.add_parser('verify-delivery'); p.add_argument('--delivery',required=True)
    p = subs.add_parser('migrate');p.add_argument('--manifest',required=True);p.add_argument('--out',required=True)
    p=subs.add_parser('sync-status')
    for key in ['config','manifest','system','state','expected-sha','evidence','actor','statement']:p.add_argument('--'+key,required=True)
    p.add_argument('--delivery');p.add_argument('--verification');p.add_argument('--test-only',action='store_true')
    for command in ['plan','quality','import','attach','approve','freeze','clean-plan','clean','restore','stress','prepare-provider','provider-failure']:
        p = subs.add_parser(command);p.add_argument('--config',required=True)
        if command not in ['import','restore','prepare-provider','provider-failure']:p.add_argument('--manifest',required=True)
        if command in ['plan','attach','approve','freeze','clean-plan','stress','prepare-provider']:p.add_argument('--out',required=True)
        if command == 'plan':p.add_argument('--task',required=True)
        if command == 'import':
            for key in ['request','file','id','state','source','license']:p.add_argument('--'+key,required=True)
            p.add_argument('--method',default='external',choices=['external','builtin_imagegen','extraction','repair'])
            p.add_argument('--attempt')
        if command=='prepare-provider':
            for key in ['request','id','state']:p.add_argument('--'+key,required=True)
            p.add_argument('--operation',choices=['generate','edit_with_reference','transparent_asset'],required=True)
            p.add_argument('--references',nargs='*',default=[])
        if command=='provider-failure':p.add_argument('--ticket',required=True);p.add_argument('--reason',required=True)
        if command == 'attach':p.add_argument('--candidate',required=True);p.add_argument('--id',required=True)
        if command in ['approve','freeze']:p.add_argument('--build',required=True)
        if command == 'approve':
            for key in ['evidence','actor','statement']:p.add_argument('--'+key,required=True)
            p.add_argument('--test-only',action='store_true')
        if command == 'freeze':p.add_argument('--approval',required=True)
        if command == 'clean':p.add_argument('--plan',required=True);p.add_argument('--archive',required=True)
        if command == 'restore':p.add_argument('--archive',required=True)
        if command == 'stress':p.add_argument('--cases',required=True)
    a = parser.parse_args()
    try:
        c = a.command
        if c == 'discover':r=discover(a.root)
        elif c=='init':r=initialize(a.root,a.brief,a.canvas,a.engine,a.font,a.out)
        elif c == 'adopt':r=init_project(a.root,a.out,a.art_bible,a.documents,a.status_source,a.engine,canvas=a.canvas)
        elif c == 'capabilities':r=capabilities()
        elif c == 'plan':r=plan(a.config,a.manifest,ui.read(a.task),a.out)
        elif c == 'quality':r=quality(a.config,a.manifest)
        elif c == 'import':r=import_candidate(a.config,a.request,a.file,a.id,a.state,a.source,a.license,a.method,a.attempt)
        elif c == 'prepare-provider':r=prepare_provider(a.config,a.request,a.id,a.state,a.operation,a.references,a.out)
        elif c == 'provider-failure':r=provider_failure(a.config,a.ticket,a.reason)
        elif c == 'attach':r=attach_candidate(a.config,a.manifest,a.candidate,a.id,a.out)
        elif c == 'approve':r=approval(a.config,a.manifest,a.build,a.evidence,a.actor,a.statement,a.out,a.test_only)
        elif c == 'freeze':r=freeze(a.config,a.manifest,a.build,a.approval,a.out)
        elif c == 'verify-delivery':r=verify_delivery(a.delivery)
        elif c == 'clean-plan':r=clean_plan(a.config,a.manifest,a.out)
        elif c == 'clean':r=clean_execute(a.config,a.manifest,a.plan,a.archive)
        elif c == 'restore':r=restore(a.config,a.archive)
        elif c == 'stress':r=stress(a.config,a.manifest,ui.read(a.cases),a.out)
        elif c=='sync-status':r=sync_status(a.config,a.manifest,a.system,a.state,a.expected_sha,a.evidence,a.actor,a.statement,a.delivery,a.verification,a.test_only)
        else:r=migrate(a.manifest,a.out)
        print(json.dumps(r,ensure_ascii=False,indent=2))
        return 1 if c=='quality' and not r['passed'] else 0
    except (ValueError,OSError,KeyError) as e:
        print(str(e),file=sys.stderr);return 1


if __name__ == '__main__':
    sys.exit(main())
