"""Deterministic candidate crop/alpha processing; never claim hidden reconstruction."""
import argparse
import json
from pathlib import Path
import sys

from PIL import Image
import ui
import production


def process(source,out,crop=None,alpha_mask=None):
    source=Path(source).resolve();out=Path(out).resolve()
    if out.exists() or out.with_suffix('.provenance.json').exists():raise ValueError('Candidate destination exists')
    with Image.open(source) as im:image=im.convert('RGBA')
    if alpha_mask:
        with Image.open(alpha_mask) as mask:
            if mask.size!=image.size:raise ValueError('Alpha mask size differs from source canvas')
            from PIL import ImageChops
            image.putalpha(ImageChops.multiply(image.getchannel('A'),mask.convert('L')))
    if crop:
        if not (0<=crop[0]<crop[2]<=image.width and 0<=crop[1]<crop[3]<=image.height):raise ValueError('Crop exceeds source')
        image=image.crop(crop)
    out.parent.mkdir(parents=True,exist_ok=True);image.save(out)
    report={'source':str(source),'source_sha256':ui.digest(source),'candidate':str(out),'sha256':ui.digest(out),
        'crop':crop,'alpha_mask_sha256':ui.digest(alpha_mask) if alpha_mask else None,
        'info':ui.image_info(out),'status':'candidate','hidden_regions_reconstructed':False,
        'visual_review_required':True}
    production.write(out.with_suffix('.provenance.json'),report)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True);p.add_argument('--out',required=True)
    p.add_argument('--crop',nargs=4,type=int);p.add_argument('--alpha-mask')
    a=p.parse_args()
    try:print(json.dumps(process(a.source,a.out,a.crop,a.alpha_mask),ensure_ascii=False,indent=2))
    except (ValueError,OSError) as e:print(str(e),file=sys.stderr);sys.exit(1)
