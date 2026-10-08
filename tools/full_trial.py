"""End-to-end isolated fixtures; approval evidence is explicitly synthetic."""
import argparse
import copy
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skill/game-ui-production/scripts'))
import ui
import production
import godot_export
from make_demo import make


def run(out,font):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    results=[]
    for index,canvas in enumerate([[640,360],[480,280]]):
        project=out/f'project-{index}'
        make(project,Path(font),canvas)
        config=ui.read(project/'project.json')
        config['schema_version']=2
        config['output_root']=str(out)
        config['rules'].update(test_fixture=True,candidate_dir='.ui-production/candidates',
            production_scope=['ui'],artistic_retry_budget=2,max_upscale=3,
            state_groups=[['button','disabled']],asset_constraints={'button':{'alpha':True}})
        production.write(project/'project.json',config,True)
        manifest=ui.read(project/'manifest.json');manifest['schema_version']=2
        manifest['typography']={'body':{'font':'font','size':22,'color':'#ffffff','spacing':5}}
        for page in manifest['pages']:
            for state,opacity in [('hover',.9),('pressed',.75),('selected',1),('focus',.95)]:
                page['state_overrides'][state]={'action':{'opacity':opacity}}
            page['data']={'name':page['name'],'amount':3,'description':'Live data from game owner','ratio':.5}
            page['layers'][0]['binding']='name'
            page['layers'][0].update(max_width=canvas[0]-100,max_lines=1,overflow='ellipsis')
            page['layers'][1].update(typography_token='body',binding='description',max_width=canvas[0]-100,max_lines=3,overflow='wrap')
            page['interactions']=[{'id':'confirm','rect':[canvas[0]-160,canvas[1]-100,112,46],
                'action':'confirm','focus_order':0,'states':{state:state for state in ['normal','disabled','hover','pressed','selected','focus']}}]
            page['animations']=[{'layer':'title','property':'opacity','from':.65,'to':1,'duration':.2,'loop':False}]
            page['scroll_regions']=[{'id':'description_scroll','rect':[40,80,canvas[0]-80,80],
                'layers':[page['layers'][1]['id']],'content_size':[canvas[0]-80,800],'offset':[0,0]}]
            page['layers'].append({'id':'resource_fill','z':3,'asset':'button','rect':[50,canvas[1]-100,100,20],
                'resize':'stretch','fill_binding':'ratio'})
        if index==1:
            # Distinct project rules/art sample; no changes to universal core.
            from PIL import Image,ImageOps
            for key in ['panel','button','disabled']:
                path=project/manifest['assets'][key]['path']
                im=Image.open(path).convert('RGBA');alpha=im.getchannel('A')
                im=ImageOps.colorize(ImageOps.grayscale(im),'#522c17','#fff0cf').convert('RGBA');im.putalpha(alpha);im.save(path)
                manifest['assets'][key]['sha256']=ui.digest(path)
            (project/'rules.md').write_text('Synthetic amber-paper project. Warm sepia, plain paper panels. All sample art and approvals are test-only.', 'utf-8')
        production.write(project/'manifest.json',manifest,True)
        evidence=project/'fixture-evidence.txt'
        evidence.write_text('SYNTHETIC AUTOMATED TEST EVIDENCE. No real user visual approval. Exercise exact-version gate only.', 'utf-8')
        task={'system':'inventory','assets':[{'id':'new_panel','kind':'ui','purpose':'independent reusable panel sample',
            'display_size':[220,130],'states':['normal'],'alpha':True,
            'allowed_changes':['this independent panel only'],'effects':['material texture','complete border','subtle shadow']}]}
        request=project/'request.json'
        production.plan(project/'project.json',project/'manifest.json',task,request)
        candidate=production.import_candidate(project/'project.json',request,project/'assets/panel.png','new_panel','normal','deterministic trial candidate','CC0')
        staged=project/'staged.json'
        production.attach_candidate(project/'project.json',project/'manifest.json',candidate['path'],'panel',staged)
        review=project/'review'
        ui.build(project/'project.json',staged,review)
        approval=project/'approval.json'
        production.approval(project/'project.json',staged,review,evidence,'automated fixture','synthetic gate test',approval,True)
        frozen=project/'delivery'
        production.freeze(project/'project.json',staged,review,approval,frozen)
        engine=out/f'godot-{index}'
        godot_export.export(frozen,engine,True)
        case_data=[{'id':'empty','data':{'name':'','amount':0,'description':''}},
            {'id':'long','data':{'name':'Extremely long label '*20,'amount':999999999,'description':'Long description '*60}},
            {'id':'max-list','data':{'name':'Maximum list','description':'\n'.join(f'Item {i}: 999999999' for i in range(100))},
             'layers':{'description':{'max_lines':100}}},
            {'id':'missing-glyph','data':{'name':'Unsupported \U0001fae8','description':'glyph gate'}}]
        stress=production.stress(project/'project.json',staged,case_data,project/'stress')
        results.append({'project':str(project),'gate':production.quality(project/'project.json',staged),
                        'stress':[(v['case'],v['quality']['passed']) for v in stress],
                        'delivery':str(frozen),'engine':str(engine),'synthetic_approval':True})
    production.write(out/'results.json',results)
    print(json.dumps(results,ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--font',required=True)
    a=p.parse_args();run(a.out,a.font)
