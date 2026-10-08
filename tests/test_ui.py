"""Observable geometry, scope, schema and source-preservation regressions."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ui', ROOT/'skill/game-ui-production/scripts/ui.py')
ui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ui)


class CompositionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        image = Image.new('RGBA', (10, 10))
        for x in range(2, 8):
            for y in range(2, 8):
                image.putpixel((x, y), (255, 0, 0, 255))
        image.save(self.root/'red.png')
        Image.new('RGBA', (6, 6), 'blue').save(self.root/'blue.png')
        self.manifest = {'canvas': [40, 30], 'assets': {'red': {'path': 'red.png'}, 'blue': {'path': 'blue.png'}}, 'masters': {}}
        self.page = {'id': 'p', 'layers': [
            {'id': 'red', 'asset': 'red', 'body': True, 'rect': [20, 15, 6, 6],
             'anchor': [.5, .5], 'resize': 'native', 'z': 1},
            {'id': 'blue', 'asset': 'blue', 'parent': 'red', 'rect': [3, 3, 6, 6],
             'resize': 'native', 'clip': [20, 15, 2, 2], 'z': 2}],
            'state_overrides': {'disabled': {'blue': {'visible': False}}}}

    def test_visible_body_anchor_parent_clip_z_and_state(self):
        image, _ = ui.compose(self.manifest, self.page, self.root, 'normal')
        self.assertEqual(image.getpixel((17, 12)), (255, 0, 0, 255))
        self.assertEqual(image.getpixel((20, 15)), (0, 0, 255, 255))
        self.assertEqual(image.getpixel((22, 17)), (255, 0, 0, 255))
        self.assertEqual(image.getpixel((23, 18)), (0, 0, 0, 0))
        disabled, _ = ui.compose(self.manifest, self.page, self.root, 'disabled')
        self.assertEqual(disabled.getpixel((20, 15)), (255, 0, 0, 255))

    def test_assessment_excludes_only_declared_content(self):
        page = {'assessment': [[5, 5, 10, 10]], 'exclude': [[7, 7, 2, 2]]}
        mask = ui.assessment_mask(self.manifest, page)
        self.assertEqual(mask.histogram()[255], 96)
        self.assertEqual(mask.getpixel((6, 6)), 255)
        self.assertEqual(mask.getpixel((7, 7)), 0)
        self.assertEqual(mask.getpixel((4, 4)), 0)

    def test_alpha_scope_mask_keeps_irregular_frame(self):
        mask = Image.new('L', (40, 30))
        mask.putpixel((6, 6), 255)
        mask.putpixel((7, 7), 255)
        mask.save(self.root/'scope.png')
        self.manifest['assets']['scope'] = {'path': 'scope.png'}
        page = {'scope_mask': 'scope', 'exclude': [[7, 7, 1, 1]]}
        scope = ui.assessment_mask(self.manifest, page, self.root)
        self.assertEqual(scope.histogram()[255], 1)
        self.assertEqual(scope.getpixel((6, 6)), 255)

    def test_reject_cycle_unknown_parent_and_duplicate_layer(self):
        for change in ['cycle', 'missing', 'duplicate']:
            with self.subTest(change=change):
                page = copy.deepcopy(self.page)
                if change == 'cycle':
                    page['layers'][0]['parent'] = 'blue'
                elif change == 'missing':
                    page['layers'][0]['parent'] = 'missing'
                else:
                    page['layers'].append(page['layers'][0])
                with self.assertRaises(ValueError):
                    ui.compose(self.manifest, page, self.root, 'normal')

    def test_reject_unknown_geometry_or_implicit_scale(self):
        for field, value in [('blend', 'multiply'), ('resize', 'guess'), ('rect', [0, 0, 0, 10])]:
            with self.subTest(field=field):
                layer = dict(self.page['layers'][0], **{field: value})
                with self.assertRaises(ValueError):
                    ui.validate_schema(layer, 'layer')
        with self.assertRaises(ValueError):
            ui.resize(Image.new('RGBA', (10, 10)), {'resize': 'native', 'id': 'x'}, (20, 10))

    def test_grid_preserves_corner_pixels(self):
        image = Image.new('RGBA', (9, 9), 'green')
        image.putpixel((0, 0), (255, 0, 0, 255))
        image.putpixel((8, 8), (0, 0, 255, 255))
        result = ui.resize(image, {'id': 'frame', 'resize': 'grid', 'grid': {
            'source_x': [0, 3, 6, 9], 'source_y': [0, 3, 6, 9],
            'target_x': [0, 3, 17, 20], 'target_y': [0, 3, 12, 15]}}, (20, 15))
        self.assertEqual(result.getpixel((0, 0)), (255, 0, 0, 255))
        self.assertEqual(result.getpixel((19, 14)), (0, 0, 255, 255))

    def test_crop_and_opacity(self):
        page = {'id': 'p', 'layers': [{'id': 'x', 'asset': 'red', 'crop': [2, 2, 8, 8],
                 'rect': [0, 0, 6, 6], 'resize': 'native', 'opacity': .5, 'z': 0}]}
        image, _ = ui.compose(self.manifest, page, self.root, 'normal')
        self.assertEqual(image.getpixel((0, 0)), (255, 0, 0, 128))

    def test_hidden_parent_hides_child(self):
        page=copy.deepcopy(self.page);page['layers'][0]['visible']=False
        image,_=ui.compose(self.manifest,page,self.root,'normal')
        self.assertIsNone(image.getbbox())


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.config = ROOT/'output/fixtures/demo/project.json'
        self.manifest = ROOT/'output/fixtures/demo/manifest.json'

    def test_real_build_deterministic_sources_unchanged_and_no_overwrite(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'output') as tmp:
            folder = Path(tmp)
            _, _, _, inputs, _ = ui.load(self.config, self.manifest)
            a, b = folder/'a', folder/'b'
            ui.build(self.config, self.manifest, a)
            ui.build(self.config, self.manifest, b)
            self.assertEqual(ui.digest(a/'inventory--normal.png'), ui.digest(b/'inventory--normal.png'))
            self.assertTrue(all(ui.digest(p) == h for p, h in inputs.items()))
            report = ui.read(a/'build.json')
            self.assertFalse(report['visual_approved'])
            self.assertEqual(report['resources']['button']['pages'], ['inventory', 'settings'])
            with self.assertRaises(ValueError):
                ui.build(self.config, self.manifest, a)

    def test_input_hash_reference_size_and_path_traversal_fail(self):
        config, manifest, root, _, _ = ui.load(self.config, self.manifest)
        with self.assertRaises(ValueError):
            ui.inside(root, '../../outside.png')
        with tempfile.TemporaryDirectory(dir=root.parent) as tmp:
            path = Path(tmp)/'manifest.json'
            bad = copy.deepcopy(manifest)
            bad['assets']['button']['sha256'] = '0'*64
            path.write_text(json.dumps(bad), 'utf-8')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                ui.load(self.config, path)
            bad = copy.deepcopy(manifest)
            bad['canvas'] = [100, 100]
            path.write_text(json.dumps(bad), 'utf-8')
            with self.assertRaisesRegex(ValueError, 'logical canvas'):
                ui.load(self.config, path)

    def test_local_repair_affects_only_target_page(self):
        _, manifest, root, _, _ = ui.load(self.config, self.manifest)
        before = [ui.compose(manifest, page, root, 'normal')[0].tobytes() for page in manifest['pages']]
        repaired = copy.deepcopy(manifest)
        repaired['pages'][0]['layers'][0]['xy'][0] += 10
        after = [ui.compose(repaired, page, root, 'normal')[0].tobytes() for page in repaired['pages']]
        self.assertNotEqual(before[0], after[0])
        self.assertEqual(before[1], after[1])


if __name__ == '__main__':
    unittest.main(verbosity=2)
