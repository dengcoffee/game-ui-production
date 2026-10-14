"""Candidate segmentation and fixed geometry checks on isolated images."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skill/game-ui-production/scripts'))
import layers
import ui


class LayerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'source.png'
        image=Image.new('RGBA',(40,30),'#202030');draw=ImageDraw.Draw(image)
        draw.rectangle((12,8,27,21),fill='#509090')
        draw.rectangle((17,12,21,16),fill='#202030')
        image.save(self.source)
        self.plan={'canvas':[40,30],'source_sha256':ui.digest(self.source),'regions':[
            {'id':'panel','purpose':'panel','rect':[8,4,24,22],'method':'border',
             'tolerance':0,'subject_bounds':[4,4,20,18]}]}
        self.path=self.root/'plan.json';self.out=self.root/'out'

    def build(self):
        self.path.write_text(json.dumps(self.plan),'utf-8')
        return layers.build(self.source,self.path,self.out)

    def test_border_segmentation_preserves_enclosed_fill_and_coordinates(self):
        report=self.build()
        with Image.open(self.out/'panel.png') as image:
            self.assertEqual(image.size,(24,22))
            self.assertEqual(image.getpixel((0,0))[3],0)
            self.assertEqual(image.getpixel((10,10))[3],255)
        with Image.open(self.out/'assembly.png') as image:
            self.assertEqual(image.size,(40,30))
            self.assertEqual(image.getchannel('A').getbbox(),(12,8,28,22))
        self.assertTrue(report['fixed_rects_passed'])
        self.assertFalse(report['visual_approved'])

    def test_repair_only_changes_declared_region(self):
        spec=self.plan['regions'][0];spec['method']='rect';spec.pop('subject_bounds')
        spec.update(occlusions=[[7,8,4,3]],repair='repair.png')
        Image.new('RGBA',(24,22),'red').save(self.root/'repair.png');self.build()
        with Image.open(self.source) as source,Image.open(self.out/'panel.png') as result:
            original=source.crop((8,4,32,26))
            for y in range(22):
                for x in range(24):
                    if 7<=x<11 and 8<=y<11:self.assertEqual(result.getpixel((x,y)),(255,0,0,255))
                    else:self.assertEqual(result.getpixel((x,y)),original.getpixel((x,y)))

    def test_same_canvas_smaller_subject_is_rejected(self):
        spec=self.plan['regions'][0];spec.update(method='mask',mask='mask.png')
        mask=Image.new('L',(24,22));ImageDraw.Draw(mask).rectangle((5,5,18,16),fill=255)
        mask.save(self.root/'mask.png')
        with self.assertRaisesRegex(ValueError,'Subject geometry changed'):self.build()
        self.assertFalse(self.out.exists())

    def test_wrong_repair_dimensions_are_not_resized(self):
        self.plan['regions'][0].update(occlusions=[[7,8,4,3]],repair='repair.png')
        Image.new('RGBA',(25,22),'red').save(self.root/'repair.png')
        with self.assertRaisesRegex(ValueError,'resizing forbidden'):self.build()
        self.assertFalse(self.out.exists())

    def test_missing_repair_excludes_occluder_and_reports_pending(self):
        self.plan['regions'][0]['occlusions']=[[7,8,4,3]]
        report=self.build()
        self.assertTrue(report['regions'][0]['pending_reconstruction'])
        with Image.open(self.out/'panel.png') as image:self.assertEqual(image.getpixel((8,9))[3],0)

    def test_stale_reference_and_out_of_range_geometry_are_rejected(self):
        self.plan['canvas']=[41,30]
        with self.assertRaisesRegex(ValueError,'Canvas differs'):self.build()
        self.plan['canvas']=[40,30];self.plan['source_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'identity changed'):self.build()
        self.plan['source_sha256']=ui.digest(self.source);self.plan['regions'][0]['rect']=[8,4,40,22]
        with self.assertRaisesRegex(ValueError,'exceeds canvas'):self.build()


if __name__=='__main__':unittest.main()
