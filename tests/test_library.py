"""Isolated library IO; publication tests mock the real-human approval gate."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skill/game-ui-production/scripts'))
sys.path.insert(0,str(ROOT/'tools'))
import library
import production as p
import ui
from make_demo import make


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name);self.source=self.folder/'project';self.lib=self.folder/'library'
        make(self.source,Path('C:/Windows/Fonts/arial.ttf'),[320,240])
        self.config=self.source/'project.json';self.manifest=self.source/'manifest.json'
        cfg=ui.read(self.config);cfg['rules'].update(test_fixture=True,asset_library={'root':str(self.lib),'project':'项目A'})
        p.write(self.config,cfg,True)
        manifest=ui.read(self.manifest)
        for asset in manifest['assets'].values():
            if asset['kind']=='ui':asset.update(ui_type='button',tags=['蓝色'],display_name='测试控件',
                classification={'status':'resolved','role':'Fixture control','basis':'Explicit isolated test specification','evidence':['test_library.py fixture']})
        p.write(self.manifest,manifest,True)
        self.review=self.folder/'review';ui.build(self.config,self.manifest,self.review)
        self.evidence=self.folder/'evidence.txt';self.evidence.write_text('SYNTHETIC TEST ONLY','utf-8')
        self.approval=self.folder/'approval.json'
        p.approval(self.config,self.manifest,self.review,self.evidence,'fixture','test',self.approval,True)

    def publish(self,project='项目A'):
        # No invented human approval is written. Mock gate only inside this temporary test library.
        _,manifest,source,_,resources=ui.load(self.config,self.manifest)
        context=(ui.read(self.config),source,self.lib,project,manifest,resources,ui.read(self.approval))
        with patch('library.approved_context',return_value=context):
            return library.add(self.config,self.manifest,self.review,self.approval)

    def test_project_index_dedup_and_rebuild(self):
        result=self.publish();self.assertGreater(result['added'],0)
        self.assertEqual(self.publish()['added'],0)
        original=ui.read(self.lib/'项目A/index.json')
        (self.lib/'项目A/index.json').write_text('{}','utf-8')
        library.reindex(self.lib,'项目A')
        self.assertEqual(ui.read(self.lib/'项目A/index.json'),original)
        self.assertFalse((self.lib/'index.json').exists())
        self.assertIn('项目A',(self.lib/'index.html').read_text('utf-8'))

    def test_search_isolation_and_explicit_cross_project(self):
        self.publish();self.publish('项目B')
        records=library.search(self.config,ui_type='button',query='蓝色',state='normal')
        self.assertTrue(records);self.assertTrue(all(r['project']=='项目A' for r in records))
        self.assertEqual(library.search(self.config,ui_type='frame'),[])
        with self.assertRaisesRegex(ValueError,'Cross-project'):library.search(self.config,'项目B')
        self.assertTrue(library.search(self.config,'项目B',True))

    def test_copy_reuse_keeps_source_and_tracks_origin(self):
        self.publish('项目B');record=library.search(self.config,'项目B',True,ui_type='button')[0]
        result=library.use(self.config,record['path'],'assets/reused.png','项目B',True)
        self.assertEqual(ui.digest(result['file']),record['sha256'])
        proof=ui.read(Path(result['file']).with_suffix('.provenance.json'))
        self.assertEqual(proof['library_project'],'项目B');self.assertTrue(proof['geometry_review_required'])
        with self.assertRaisesRegex(ValueError,'exists'):
            library.use(self.config,record['path'],'assets/reused.png','项目B',True)
        with self.assertRaisesRegex(ValueError,'below project'):
            library.use(self.config,record['path'],'../escape.png','项目B',True)

    def test_new_version_preserves_old_and_tampering_fails(self):
        self.publish();before=library.search(self.config);identity=next(r['asset_id'] for r in before if r['ui_type']=='button')
        manifest=ui.read(self.manifest);asset=manifest['assets'][identity]
        file=self.source/asset['path']
        with Image.open(file) as im:
            changed=im.convert('RGBA');changed.putpixel((0,0),(12,34,56,255));changed.save(file)
        asset['sha256']=ui.digest(file);p.write(self.manifest,manifest,True)
        self.publish();after=library.search(self.config)
        self.assertEqual(len(after),len(before)+1)
        (self.lib/'项目A'/before[0]['path']).write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError,'changed'):library.reindex(self.lib,'项目A')

    def test_real_gate_rejects_fixture_and_changed_approval_inputs(self):
        with self.assertRaisesRegex(ValueError,'genuine'):library.add(self.config,self.manifest,self.review,self.approval)
        # Simulate production evidence in memory solely to exercise stale-input validation.
        cfg=ui.read(self.config);cfg['rules']['test_fixture']=False
        approved=ui.read(self.approval);approved['test_only']=False
        original=ui.read
        with patch('library.location',return_value=(cfg,self.source,self.lib,'项目A')):
            with patch('ui.read',side_effect=lambda path: approved if Path(path)==self.approval else original(path)):
                approved['manifest_sha256']='0'*64
                with self.assertRaisesRegex(ValueError,'inputs changed'):
                    library.approved_context(self.config,self.manifest,self.review,self.approval)
                approved['manifest_sha256']=ui.digest(self.manifest)
                approved['build_sha256']='0'*64
                with self.assertRaisesRegex(ValueError,'build changed'):
                    library.approved_context(self.config,self.manifest,self.review,self.approval)
                approved['build_sha256']=ui.digest(self.review/'build.json');approved['evidence']['test_only']=False
                approved['evidence']['evidence_sha256']='0'*64
                with self.assertRaisesRegex(ValueError,'evidence changed'):
                    library.approved_context(self.config,self.manifest,self.review,self.approval)
        self.assertFalse(self.lib.exists())

    def test_classification_roundtrip_and_unclassified_rejection(self):
        task={'system':'inventory','assets':[{'id':'panel','kind':'ui','ui_type':'base','tags':['测试'],
              'classification':{'status':'resolved','role':'Panel base','basis':'Fixture panel background','evidence':['test specification']},
              'purpose':'panel','display_size':[100,70],'states':['normal'],'alpha':True,'allowed_changes':['panel']}]}
        request=self.folder/'request.json';p.plan(self.config,self.manifest,task,request)
        file=self.folder/'candidate.png';image=Image.new('RGBA',(100,70));image.paste('blue',(2,2,98,68));image.save(file)
        candidate=p.import_candidate(self.config,request,file,'panel','normal','test','CC0')
        out=self.folder/'attached.json';p.attach_candidate(self.config,self.manifest,candidate['path'],'panel',out)
        self.assertEqual(ui.read(out)['assets']['panel']['ui_type'],'base')
        self.assertEqual(ui.read(out)['assets']['panel']['tags'],['测试'])
        task['assets'][0].pop('ui_type')
        with self.assertRaisesRegex(ValueError,'explicit ui_type'):p.plan(self.config,self.manifest,task,self.folder/'bad.json')
        manifest=ui.read(self.manifest);manifest['assets']['panel'].pop('ui_type');p.write(self.manifest,manifest,True)
        with self.assertRaisesRegex(ValueError,'Classify'):self.publish()
        self.assertFalse(self.lib.exists())

    def test_project_approval_never_publishes_automatically(self):
        original_load=ui.load
        def simulated_production(*args):
            result=list(original_load(*args));result[0]=copy.deepcopy(result[0])
            result[0]['rules']['test_fixture']=False
            return tuple(result)
        # Approval is simulated only in memory; no invented production evidence is saved.
        with patch('ui.load',side_effect=simulated_production),patch('production.write') as save:
            with patch('library.add') as publish:
                result=p.approval(self.config,self.manifest,self.review,self.evidence,'test actor','MOCK ONLY',self.folder/'mock.json')
                publish.assert_not_called();save.assert_called_once()
                self.assertNotIn('library_result',result)
        self.assertFalse(self.lib.exists())


if __name__=='__main__':unittest.main()
