"""Portable review/confirmation without library side effects; isolated fixtures only."""
import json
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_library
import asset_package as package
import library
import production as p
import ui


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.fixture=test_library.LibraryTests();self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.folder=self.fixture.folder;self.out=self.folder/'asset-package'
        cfg=ui.read(self.fixture.config);cfg['rules'].pop('asset_library')
        p.write(self.fixture.config,cfg,True)
        self.review=self.folder/'independent-review'
        ui.build(self.fixture.config,self.fixture.manifest,self.review)

    def prepare(self):
        return package.prepare(self.fixture.config,self.fixture.manifest,self.review,self.out,'项目A')

    def confirm(self):
        return package.confirm(self.out,self.fixture.evidence,'fixture','SYNTHETIC TEST ONLY',True)

    def test_standalone_package_and_confirmation_never_touch_library(self):
        with patch.dict(sys.modules,{'library':None}):
            self.prepare();self.confirm()
        record=package.validate(self.out,approved=True,allow_test=True)
        self.assertEqual(record['project'],'项目A');self.assertTrue((self.out/'assets').is_dir())
        self.assertTrue((self.out/'review/index.html').exists());self.assertFalse(self.fixture.lib.exists())
        for asset in record['assets']:
            self.assertIn('ui_type',asset);self.assertIn('usages',asset)
            self.assertEqual(Path(asset['path']).parent,Path('assets'))
        self.assertFalse(any(p.is_dir() for p in (self.out/'assets').iterdir()))

    def test_exact_categories_and_real_font_metadata(self):
        self.assertEqual(list(package.TYPES.values()),['底板','窗口框','按钮','页签','头像框','道具格','轨道','滑块','进度槽','进度填充','装饰','图标','字体'])
        self.prepare();record=package.validate(self.out,allow_test=True)
        fonts=[a for a in record['assets'] if a['ui_type']=='font']
        self.assertTrue(fonts)
        for font in fonts:
            self.assertEqual(font['kind'],'font');self.assertIsNone(font['size'])
            self.assertIsNone(font['visible_bounds']);self.assertTrue(font['path'].endswith('.ttf'))
            self.assertTrue(font['license']);self.assertTrue(font['usages'])

    def test_legacy_separator_is_decoration_without_changing_source(self):
        manifest=ui.read(self.fixture.manifest);manifest['assets']['panel']['ui_type']='separator'
        p.write(self.fixture.manifest,manifest,True)
        self.review=self.folder/'separator-review';ui.build(self.fixture.config,self.fixture.manifest,self.review)
        self.prepare();record=package.validate(self.out,allow_test=True)
        panel=next(a for a in record['assets'] if a['asset_id']=='panel')
        self.assertEqual(panel['ui_type'],'decoration')
        self.assertEqual(ui.read(self.fixture.manifest)['assets']['panel']['ui_type'],'separator')

    def test_unconfirmed_and_test_packages_cannot_enter_library(self):
        self.prepare()
        with self.assertRaisesRegex(ValueError,'confirmation'):
            package.validate(self.out,approved=True,allow_test=True)
        self.confirm()
        with self.assertRaisesRegex(ValueError,'Test packages'):
            library.add_package(self.out,self.fixture.lib)
        self.assertFalse(self.fixture.lib.exists())

    def test_changed_pixels_metadata_and_evidence_invalidate_confirmation(self):
        self.prepare();self.confirm();original=ui.read(self.out/'package.json')
        edited=json.loads(json.dumps(original));edited['assets'][0]['tags']=['changed']
        p.write(self.out/'package.json',edited,True)
        with self.assertRaisesRegex(ValueError,'metadata changed'):
            package.validate(self.out,approved=True,allow_test=True)
        p.write(self.out/'package.json',original,True)
        evidence=self.out/'approval.evidence';old=evidence.read_bytes();evidence.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'evidence changed'):
            package.validate(self.out,approved=True,allow_test=True)
        evidence.write_bytes(old)
        image=self.out/original['assets'][0]['path'];raw=image.read_bytes();image.write_bytes(raw+b'changed')
        with self.assertRaisesRegex(ValueError,'file changed'):
            package.validate(self.out,approved=True,allow_test=True)

    def test_relocated_package_import_uses_only_package_files(self):
        self.prepare();self.confirm();moved=self.folder/'moved-package';shutil.copytree(self.out,moved)
        real_validate=package.validate
        # Allow fixture publication only inside this temporary library; all integrity checks remain active.
        with patch('asset_package.validate',side_effect=lambda folder,approved: real_validate(folder,approved,allow_test=True)):
            with patch('ui.load',side_effect=AssertionError('Original project must not be loaded')):
                first=library.add_package(moved,self.fixture.lib)
                self.assertGreater(first['added'],0);self.assertEqual(library.add_package(moved,self.fixture.lib)['added'],0)
        self.assertTrue((self.fixture.lib/'项目A/index.json').exists())

    def test_confirmation_requires_evidence_and_correct_fixture_flag(self):
        self.prepare()
        with self.assertRaisesRegex(ValueError,'Explicit human'):
            package.confirm(self.out,self.folder/'missing.txt','fixture','test',True)
        with self.assertRaisesRegex(ValueError,'test_only'):
            package.confirm(self.out,self.fixture.evidence,'fixture','test')
        self.confirm()
        with self.assertRaisesRegex(ValueError,'already confirmed'):self.confirm()

    def test_stale_review_and_missing_type_rejected_before_package_creation(self):
        manifest=ui.read(self.fixture.manifest);manifest['assets']['panel'].pop('ui_type')
        p.write(self.fixture.manifest,manifest,True)
        with self.assertRaisesRegex(ValueError,'version changed'):self.prepare()
        ui.build(self.fixture.config,self.fixture.manifest,self.folder/'new-review');self.review=self.folder/'new-review'
        with self.assertRaisesRegex(ValueError,'Classify'):self.prepare()
        self.assertFalse(self.out.exists())


if __name__=='__main__':unittest.main()
