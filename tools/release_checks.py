"""Release evidence: real host candidates, new project, isolated integration."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skill/game-ui-production/scripts'))
import ui
import production as p
import godot_export

def run(out):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    generated=Path('C:/Users/DKF/.codex/generated_images/01a11a5f-6fcb-71b0-98ad-3ac8b6e73dd4')
    source=generated/'exec-f7b0dfc3-6823-4a34-9bdd-6cfe94d1b96a.png'
    edited=generated/'exec-729b5c11-bf17-45c0-a73f-1571b715ba2f.png'
    brief=out/'brief.txt'
    brief.write_text('Independent technical art trial, not user-approved direction. Navy sci-fi UI, teal/amber borders, restrained glow. Transparent independent panels. Live text uses a real font. No characters, item icons or scenery.','utf-8')
    project=out/'new-project';config=project/'project.json'
    p.initialize(project,brief,[800,450],'godot4','C:/Windows/Fonts/arial.ttf',config)
    cfg=ui.read(config);cfg['rules']['test_fixture']=True;p.write(config,cfg,True)
    asset_dir=project/'assets';shutil.copyfile(source,asset_dir/'panel.png')
    manifest={'schema_version':2,'canvas':[800,450],'assets':{},'masters':{},
        'systems':[{'id':'sample','name':'New sci-fi sample','pages':['sample']}],
        'pages':[{'id':'sample','name':'New project sample','system':'sample','status':'candidate',
            'reference':{'path':'candidate-reference.png','sha256':'0'*64},'layers':[
                {'id':'panel','z':0,'asset':'panel','rect':[40,30,720,390],'resize':'contain'},
                {'id':'title','z':1,'text':'New project / live typography','font':'font','size':22,'color':'#e5fbff','xy':[160,150]}]}]}
    for identity,path,kind in [('panel',asset_dir/'panel.png','ui'),('font',asset_dir/'arial.ttf','font')]:
        manifest['assets'][identity]={'path':path.relative_to(project).as_posix(),'sha256':ui.digest(path),'kind':kind,
            'source':'actual builtin_imagegen host result' if kind=='ui' else 'local OS font',
            'license':'host generated candidate; review usage terms' if kind=='ui' else 'local use only; OS font not distributed',
            'status':'candidate'}
    image,_=ui.compose(manifest,manifest['pages'][0],project,'normal');image.save(project/'candidate-reference.png')
    manifest['pages'][0]['reference']['sha256']=ui.digest(project/'candidate-reference.png')
    manifest_path=project/'manifest.json';p.write(manifest_path,manifest)
    task={'system':'sample','assets':[{'id':'edited_panel','kind':'ui','purpose':'reference edit color variant',
        'display_size':[720,390],'states':['normal'],'alpha':True,'allowed_changes':['change teal border to amber; preserve other design as a goal, without pixel lock']}]}
    request=project/'edit-request.json';p.plan(config,manifest_path,task,request)
    receipt=p.import_candidate(config,request,edited,'edited_panel','normal','actual host reference edit; original input '+ui.digest(source),
        'host generated candidate; review usage terms','builtin_imagegen')
    p.write(out/'provider-results.json',{'generate':{'input':'new transparent independent sci-fi panel','output_sha256':ui.digest(source),'info':ui.image_info(source)},
        'edit_with_reference':{'requested_change':'teal border to amber; preserve design','reference_sha256':ui.digest(source),
            'output_sha256':ui.digest(edited),'receipt':receipt},'transparent_asset_verified':True,'pixel_lock':False,
        'call_evidence':'Two actual image_gen.imagegen calls in this Codex session. These receipts do not claim the newly written request was the exact archived original tool prompt.',
        'visual_approved':False})
    ui.build(config,manifest_path,project/'.ui-production/reviews/sample')
    export=ROOT/'output/full-trial-final/godot-0'
    host=out/'existing-godot';host.mkdir()
    (host/'project.godot').write_text('config_version=5\n[application]\nconfig/name="Existing isolated host"\nrun/main_scene="res://main.tscn"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n','utf-8')
    (host/'main.tscn').write_text('[gd_scene format=3]\n\n[node name="ExistingUIOwner" type="Control"]\n','utf-8')
    existing_hash=ui.digest(host/'project.godot')
    integrated=godot_export.integrate(export,host,'components/game-ui',True)
    probe=(export/'probe.gd').read_text('utf-8').replace('res://ui.tscn',integrated['scene'])
    (host/'integration_probe.gd').write_text(probe,'utf-8')
    engine='E:/GodotGame/godot/godot_console.exe'
    for name,args in [('import',['--editor','--import']),('behavior',['--script','integration_probe.gd'])]:
        result=subprocess.run([engine,'--headless','--path',str(host),*args],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
        log=result.stdout+'\n'+result.stderr;(out/(name+'.log')).write_text(log,'utf-8')
        if result.returncode or 'ERROR:' in log:raise ValueError('Integrated Godot failed: '+log)
    assert ui.digest(host/'project.godot')==existing_hash
    inventory=ui.read(ROOT/'output/fixtures/reference-v2/inventory.json')
    checks={name:ui.digest(name)==hash for name,hash in inventory['read_only_source_hashes'].items()}
    assert all(checks.values())
    p.write(out/'results.json',{'new_project':str(project),'candidate_reference_is_self_composed_test_baseline':True,
        'integration':integrated,'integration_behavior':ui.read(host/'engine-tests.json'),'host_config_unchanged':True,
        'reference_inputs_unchanged':checks,'visual_approved':False})
    print(json.dumps({'new_project':str(project),'integration_passed':True,'reference_inputs_unchanged':len(checks)},indent=2))

if __name__=='__main__':run(sys.argv[1])
