"""Classification gates and evidence transport, using isolated fixtures."""
import copy
from pathlib import Path
import sys
import unittest
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_library
import asset_package
import layers
import production as p
import ui


class ClassificationTests(unittest.TestCase):
    def setUp(self):
        self.fixture=test_library.LibraryTests();self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups);self.folder=self.fixture.folder
        self.resolved={'status':'resolved','role':'Panel base','basis':'Explicit test panel specification',
                       'evidence':['isolated fixture region A']}
        self.pending={'status':'pending','role':'Unclear navigation control','basis':'Static image cannot distinguish behavior',
                      'evidence':['isolated fixture region B'],'candidates':['button','tab'],
                      'question':'Does this execute an action or switch content?'}
        self.task={'system':'inventory','assets':[{'id':'panel','kind':'ui','ui_type':'base',
            'classification':self.resolved,'purpose':'panel','display_size':[100,70],
            'states':['normal'],'alpha':True,'allowed_changes':['panel']}]}
        self.image=self.folder/'source.png'
        source=self.fixture.source/ui.read(self.fixture.manifest)['assets']['panel']['path']
        with Image.open(source) as image:
            self.size=list(image.size);image.save(self.image)
        self.task['assets'][0]['display_size']=self.size

    def extract(self,classification):
        plan={'canvas':self.size,'source_sha256':ui.digest(self.image),'regions':[
            {'id':'panel','purpose':'panel','rect':[0,0,*self.size],'method':'rect','ui_type':'base',
             'classification':classification}]}
        path=self.folder/'layers.json';p.write(path,plan)
        return layers.build(self.image,path,self.folder/'layers')

    def test_pending_plan_and_layer_are_blocked_before_outputs(self):
        self.task['assets'][0]['classification']=self.pending
        with self.assertRaisesRegex(ValueError,'ask user'):
            p.plan(self.fixture.config,self.fixture.manifest,self.task,self.folder/'request.json')
        with self.assertRaisesRegex(ValueError,'ask user'):self.extract(self.pending)
        self.assertFalse((self.folder/'layers').exists());self.assertFalse((self.folder/'request.json').exists())

    def test_missing_evidence_is_not_fabricated(self):
        self.task['assets'][0].pop('classification')
        with self.assertRaisesRegex(ValueError,'evidence missing'):
            p.plan(self.fixture.config,self.fixture.manifest,self.task,self.folder/'request.json')
        manifest=ui.read(self.fixture.manifest);manifest['assets']['panel'].pop('classification')
        p.write(self.fixture.manifest,manifest,True);review=self.folder/'review-new'
        ui.build(self.fixture.config,self.fixture.manifest,review)
        with self.assertRaisesRegex(ValueError,'evidence missing'):
            asset_package.prepare(self.fixture.config,self.fixture.manifest,review,self.folder/'package','项目A')
        self.assertFalse((self.folder/'package').exists())

    def test_full_plan_report_manifest_package_transport_and_mismatch_rejection(self):
        request=self.folder/'request.json';p.plan(self.fixture.config,self.fixture.manifest,self.task,request)
        report=self.extract(self.resolved);self.assertEqual(report['regions'][0]['classification'],self.resolved)
        report_path=self.folder/'layers/report.json';image=self.folder/'layers/panel.png'
        altered=copy.deepcopy(report);altered['regions'][0]['classification']['basis']='Different explanation'
        mismatch=self.folder/'mismatch.json';p.write(mismatch,altered)
        with self.assertRaisesRegex(ValueError,'differs from production plan'):
            p.import_candidate(self.fixture.config,request,image,'panel','normal','fixture','CC0','extraction',layer_report=mismatch)
        candidate=p.import_candidate(self.fixture.config,request,image,'panel','normal','fixture','CC0','extraction',layer_report=report_path)
        self.assertEqual(candidate['layer_report_sha256'],ui.digest(report_path))
        manifest=self.folder/'attached.json';p.attach_candidate(self.fixture.config,self.fixture.manifest,candidate['path'],'panel',manifest)
        self.assertEqual(ui.read(manifest)['assets']['panel']['classification'],self.resolved)
        review=self.folder/'review-new';ui.build(self.fixture.config,manifest,review)
        folder=self.folder/'package';asset_package.prepare(self.fixture.config,manifest,review,folder,'项目A')
        package=asset_package.validate(folder,allow_test=True)
        self.assertEqual(next(a for a in package['assets'] if a['asset_id']=='panel')['classification'],self.resolved)

    def test_pending_manifest_cannot_be_packaged(self):
        manifest=ui.read(self.fixture.manifest);manifest['assets']['panel']['classification']=self.pending
        p.write(self.fixture.manifest,manifest,True);review=self.folder/'review-new'
        ui.build(self.fixture.config,self.fixture.manifest,review)
        with self.assertRaisesRegex(ValueError,'ask user'):
            asset_package.prepare(self.fixture.config,self.fixture.manifest,review,self.folder/'package','项目A')
        self.assertFalse((self.folder/'package').exists())


if __name__=='__main__':unittest.main()
