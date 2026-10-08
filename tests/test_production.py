"""Production safety and portable delivery tests using isolated projects."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skill/game-ui-production/scripts'))
sys.path.insert(0,str(ROOT/'tools'))
import ui
import production as p
import godot_export
import assets
from make_demo import make


class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name);self.root=self.folder/'project'
        make(self.root,Path('C:/Windows/Fonts/arial.ttf'),[320,240])
        self.config=self.root/'project.json';self.manifest=self.root/'manifest.json'
        cfg=ui.read(self.config);cfg['rules'].update(test_fixture=True,artistic_retry_budget=2,production_scope=['ui'])
        p.write(self.config,cfg,True)
        self.task={'system':'inventory','assets':[{'id':'panel','kind':'ui','purpose':'panel','display_size':[100,70],
            'states':['normal'],'alpha':True,'allowed_changes':['panel only']}]}
        self.request=self.root/'request.json';p.plan(self.config,self.manifest,self.task,self.request)

    def candidate(self,color):
        file=self.folder/(color+'.png');im=Image.new('RGBA',(10,10));im.paste(color,(1,1,9,9));im.save(file)
        return p.import_candidate(self.config,self.request,file,'panel','normal','test','CC0')

    def review(self):
        review=self.folder/'review';ui.build(self.config,self.manifest,review)
        evidence=self.folder/'evidence.txt';evidence.write_text('SYNTHETIC TEST ONLY','utf-8')
        approval=self.folder/'approval.json'
        p.approval(self.config,self.manifest,review,evidence,'fixture','test',approval,True)
        return review,approval

    def test_scope_stale_and_budget(self):
        bad=copy.deepcopy(self.task);bad['assets'][0]['kind']='content'
        with self.assertRaisesRegex(ValueError,'scope'):p.plan(self.config,self.manifest,bad,self.folder/'bad.json')
        self.candidate('red');self.candidate('blue')
        with self.assertRaisesRegex(ValueError,'budget'):self.candidate('green')
        (self.root/'rules.md').write_text('changed','utf-8')
        with self.assertRaisesRegex(ValueError,'changed'):self.candidate('yellow')

    def test_provider_failure_consumes_budget(self):
        ticket=p.prepare_provider(self.config,self.request,'panel','normal','generate',[],self.folder/'call.json')
        p.provider_failure(self.config,ticket['ticket'],'verified provider failure')
        self.candidate('red')
        with self.assertRaisesRegex(ValueError,'budget'):self.candidate('blue')

    def test_alpha_required_and_edit_reference_required(self):
        file=self.folder/'opaque.png';Image.new('RGB',(10,10),'red').save(file)
        with self.assertRaisesRegex(ValueError,'transparency'):
            p.import_candidate(self.config,self.request,file,'panel','normal','test','CC0')
        with self.assertRaisesRegex(ValueError,'references|targets'):
            p.prepare_provider(self.config,self.request,'panel','normal','edit_with_reference',[],self.folder/'edit.json')

    def test_archive_restore_and_protected_latest(self):
        first=self.candidate('red');last=self.candidate('blue')
        plan=self.folder/'clean.json';p.clean_plan(self.config,self.manifest,plan)
        self.assertEqual(ui.read(plan)['files'],[{'path':first['path'],'sha256':first['sha256']}])
        result=p.clean_execute(self.config,self.manifest,plan,'.ui-production/archive/one')
        self.assertEqual(result['archived'],1);self.assertFalse((self.root/first['path']).exists())
        self.assertTrue((self.root/last['path']).exists())
        p.restore(self.config,'.ui-production/archive/one')
        self.assertEqual(ui.digest(self.root/first['path']),first['sha256'])
        bad=ui.read(plan);bad['files']=[{'path':last['path'],'sha256':last['sha256']}]
        p.write(self.folder/'bad-clean.json',bad)
        with self.assertRaisesRegex(ValueError,'protected'):
            p.clean_execute(self.config,self.manifest,self.folder/'bad-clean.json','.ui-production/archive/two')

    def test_cleanup_preserves_other_authoritative_manifest(self):
        first=self.candidate('red');self.candidate('blue')
        other=ui.read(self.manifest);other['assets']['panel'].update(path=first['path'],sha256=first['sha256'])
        p.write(self.root/'confirmed.json',other)
        cfg=ui.read(self.config);cfg['rules']['protected_manifests']=['confirmed.json'];p.write(self.config,cfg,True)
        plan=self.folder/'clean.json';p.clean_plan(self.config,self.manifest,plan)
        self.assertEqual(ui.read(plan)['files'],[])

    def test_exact_approval_and_frozen_tamper_refusal(self):
        review,approved=self.review()
        png=review/'inventory--normal.png';original=png.read_bytes();png.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'image changed'):
            p.freeze(self.config,self.manifest,review,approved,self.folder/'bad-delivery')
        png.write_bytes(original)
        frozen=self.folder/'delivery';p.freeze(self.config,self.manifest,review,approved,frozen)
        p.verify_delivery(frozen)
        ui.build(frozen/'project.json',frozen/'manifest.json',frozen/'reviews/portable')
        self.assertEqual(ui.digest(png),ui.digest(frozen/'reviews/portable/inventory--normal.png'))
        with self.assertRaisesRegex(ValueError,'production'):
            godot_export.export(frozen,self.folder/'engine',False)
        (frozen/'source/assets/panel.png').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'Frozen delivery changed'):p.verify_delivery(frozen)

    def test_approval_requires_full_review_and_fixture_marker(self):
        review=self.folder/'partial';ui.build(self.config,self.manifest,review,page_ids=['inventory'])
        evidence=self.folder/'evidence';evidence.write_text('test','utf-8')
        with self.assertRaisesRegex(ValueError,'every page'):
            p.approval(self.config,self.manifest,review,evidence,'fixture','test',self.folder/'a.json',True)
        with self.assertRaisesRegex(ValueError,'test_only'):
            p.approval(self.config,self.manifest,review,evidence,'fixture','test',self.folder/'b.json',False)

    def test_incremental_local_change_and_cache_hash(self):
        a=self.folder/'a';b=self.folder/'b';ui.build(self.config,self.manifest,a)
        ui.build(self.config,self.manifest,b,previous=a)
        self.assertTrue(all(e['reused'] for e in ui.read(b/'build.json')['pages']))
        changed=ui.read(self.manifest);changed['pages'][0]['layers'][0]['xy'][0]+=10
        path=self.folder/'changed.json';p.write(path,changed)
        c=self.folder/'c';ui.build(self.config,path,c,previous=a)
        for entry in ui.read(c/'build.json')['pages']:
            self.assertEqual(entry['reused'],entry['id']=='settings')
        (a/'settings--normal.png').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'changed|hash'):
            ui.build(self.config,self.manifest,self.folder/'d',previous=a)

    def test_crop_mask_and_migration_preserve_source(self):
        source=self.root/'assets/panel.png';hash=ui.digest(source)
        mask=self.folder/'mask.png';Image.new('L',(120,80),128).save(mask)
        result=assets.process(source,self.folder/'cut.png',[4,4,40,40],mask)
        self.assertEqual(result['info']['size'],[36,36]);self.assertEqual(ui.digest(source),hash)
        self.assertFalse(result['hidden_regions_reconstructed'])
        with self.assertRaises(ValueError):assets.process(source,self.folder/'bad.png',[0,0,200,200])
        original=ui.digest(self.manifest);migrated=self.folder/'v2.json';p.migrate(self.manifest,migrated)
        self.assertEqual(ui.digest(self.manifest),original);self.assertEqual(ui.read(migrated)['schema_version'],2)
        ui.load(self.config,migrated)

    def test_empty_new_project_and_existing_adoption(self):
        brief=self.folder/'brief.txt';brief.write_text('Warm paper panels; candidate direction.','utf-8')
        root=self.folder/'new';cfg=self.folder/'new.json'
        p.initialize(root,brief,[480,280],'godot4','C:/Windows/Fonts/arial.ttf',cfg)
        self.assertEqual(ui.read(root/'ui-status.json')['state'],'draft')
        with self.assertRaisesRegex(ValueError,'empty'):p.initialize(root,brief,[480,280],'godot4','C:/Windows/Fonts/arial.ttf',self.folder/'other.json')
        p.init_project(root,self.folder/'adopt.json','ArtBible.md',['ArtBible.md'],'ui-status.json','godot4')
        self.assertEqual(ui.read(root/'ui-status.json')['state'],'draft')

    def test_scroll_and_resource_fill_geometry(self):
        Image.new('RGBA',(10,10),'red').save(self.folder/'red.png')
        manifest={'canvas':[20,20],'assets':{'red':{'path':'red.png'}},'masters':{}}
        page={'id':'p','data':{'ratio':.5},'layers':[{'id':'bar','z':0,'asset':'red','rect':[0,5,10,10],
            'resize':'native','fill_binding':'ratio'}],'scroll_regions':[{'id':'s','rect':[0,0,10,10],
            'layers':['bar'],'offset':[0,5],'content_size':[10,20]}]}
        image,_=ui.compose(manifest,page,self.folder,'normal')
        self.assertEqual(image.getpixel((4,4)),(255,0,0,255));self.assertEqual(image.getpixel((5,4)),(0,0,0,0))
        self.assertEqual(image.getpixel((4,10)),(0,0,0,0))

    def test_authority_update_requires_evidence_frozen_version_and_snapshot(self):
        path=self.root/'ui-status.json'
        p.write(path,{'schema_version':1,'format':'game-ui-production-status','systems':{}})
        cfg=ui.read(self.config);cfg['status_source']='ui-status.json';p.write(self.config,cfg,True)
        evidence=self.folder/'status-evidence';evidence.write_text('SYNTHETIC evidence','utf-8')
        old=ui.digest(path)
        p.sync_status(self.config,self.manifest,'inventory','assets_verified',old,evidence,'fixture','test',test_only=True)
        self.assertEqual(ui.read(path)['systems']['inventory']['state'],'assets_verified')
        self.assertEqual(ui.digest(self.root/'.ui-production/state-backups'/(old+'.json')),old)
        with self.assertRaisesRegex(ValueError,'changed'):
            p.sync_status(self.config,self.manifest,'inventory','candidate',old,evidence,'fixture','test',test_only=True)
        with self.assertRaisesRegex(ValueError,'Frozen'):
            p.sync_status(self.config,self.manifest,'inventory','visual_approved',ui.digest(path),evidence,'fixture','test',test_only=True)

    def test_integrate_new_component_preserves_host_and_rebases_paths(self):
        review,approved=self.review();frozen=self.folder/'delivery'
        p.freeze(self.config,self.manifest,review,approved,frozen)
        export=self.folder/'export';godot_export.export(frozen,export,True)
        host=self.folder/'host';host.mkdir();(host/'project.godot').write_text('config_version=5','utf-8')
        hash=ui.digest(host/'project.godot')
        with self.assertRaisesRegex(ValueError,'test_only'):godot_export.integrate(export,host,'components/ui')
        result=godot_export.integrate(export,host,'components/ui',True)
        self.assertEqual(ui.digest(host/'project.godot'),hash)
        self.assertEqual(result['scene'],'res://components/ui/ui.tscn')
        self.assertIn('res://components/ui/ui-data.json',(host/'components/ui/ui_view.gd').read_text('utf-8'))
        with self.assertRaisesRegex(ValueError,'exists'):godot_export.integrate(export,host,'components/ui',True)


if __name__=='__main__':unittest.main()
