"""Candidate layers from a reviewed region plan; no implicit resizing or AI calls."""
import argparse
from collections import Counter, deque
import json
from pathlib import Path
import re
import sys

from PIL import Image, ImageChops, ImageDraw
import ui
from asset_package import TYPES, asset_type, check_classification


def box(rect, size):
    if len(rect) != 4 or any(type(v) is not int for v in rect):
        raise ValueError('Rect requires four integer coordinates')
    x,y,w,h=rect
    if min(x,y)<0 or min(w,h)<=0 or x+w>size[0] or y+h>size[1]:
        raise ValueError('Rect exceeds canvas')
    return x,y,x+w,y+h


def border_mask(image, tolerance):
    """Remove only border-connected pixels close to the dominant border color."""
    if type(tolerance) is not int or not 0<=tolerance<=255:
        raise ValueError('Background tolerance must be an integer in 0..255')
    rgb=image.convert('RGB');w,h=rgb.size;pixels=rgb.load()
    border=set([(x,0) for x in range(w)]+[(x,h-1) for x in range(w)]+
               [(0,y) for y in range(h)]+[(w-1,y) for y in range(h)])
    color=Counter(pixels[x,y] for x,y in sorted(border)).most_common(1)[0][0]
    mask=Image.new('L',image.size,255);values=mask.load();queue=deque(sorted(border));seen=set()
    while queue:
        x,y=queue.popleft()
        if (x,y) in seen:continue
        seen.add((x,y))
        if max(abs(a-b) for a,b in zip(pixels[x,y],color))>tolerance:continue
        values[x,y]=0
        for nx,ny in [(x-1,y),(x+1,y),(x,y-1),(x,y+1)]:
            if 0<=nx<w and 0<=ny<h:queue.append((nx,ny))
    return mask,color


def build(source, plan_path, out):
    source=Path(source).resolve();plan_path=Path(plan_path).resolve();out=Path(out).resolve()
    if out.exists():raise ValueError('Candidate destination exists')
    plan=ui.read(plan_path)
    with Image.open(source) as im:reference=im.convert('RGBA')
    if plan['source_sha256']!=ui.digest(source):raise ValueError('Source identity changed')
    if plan['canvas']!=list(reference.size):raise ValueError('Canvas differs from reference')
    if not plan['regions']:raise ValueError('Region plan is empty')
    prepared=[];ids=set()
    for spec in plan['regions']:
        identity=spec['id']
        if not re.fullmatch(r'[A-Za-z0-9_-]+',identity) or identity in ids:
            raise ValueError('Unsafe or duplicate region ID')
        ids.add(identity);rect=box(spec['rect'],reference.size);image=reference.crop(rect)
        classification=spec.get('classification')
        check_classification(classification,required=spec.get('ui_type') is not None)
        category=asset_type(spec.get('ui_type'))
        if category is not None and (category not in TYPES or category=='font'):raise ValueError('Invalid image layer category')
        method=spec['method'];inputs={};background=None
        if method=='rect':mask=Image.new('L',image.size,255)
        elif method=='border':mask,background=border_mask(image,spec.get('tolerance',12))
        elif method=='mask':
            path=(plan_path.parent/spec['mask']).resolve()
            with Image.open(path) as im:mask=im.convert('L')
            if mask.size!=image.size:raise ValueError('Mask size differs from fixed rect')
            inputs[str(path)]=ui.digest(path)
        else:raise ValueError('Unknown segmentation method')
        repair_mask=Image.new('L',image.size);draw=ImageDraw.Draw(repair_mask)
        for hidden in spec.get('occlusions',[]):
            left,top,right,bottom=box(hidden,image.size)
            draw.rectangle((left,top,right-1,bottom-1),fill=255)
        pending=repair_mask.getbbox() is not None
        if spec.get('repair'):
            if not pending:raise ValueError('Repair needs declared occlusions')
            path=(plan_path.parent/spec['repair']).resolve()
            with Image.open(path) as im:patch=im.convert('RGBA')
            if patch.size!=image.size:raise ValueError('Repair size differs from fixed rect; resizing forbidden')
            image=Image.composite(patch,image,repair_mask);inputs[str(path)]=ui.digest(path);pending=False
        elif pending:
            mask=ImageChops.subtract(mask,repair_mask)
        image.putalpha(ImageChops.multiply(image.getchannel('A'),mask))
        bounds=image.getchannel('A').getbbox()
        if bounds is None:raise ValueError('Empty region: '+identity)
        expected=spec.get('subject_bounds')
        if expected is not None:
            box([expected[0],expected[1],expected[2]-expected[0],expected[3]-expected[1]],image.size)
            if list(bounds)!=expected:raise ValueError('Subject geometry changed: '+identity)
        record={'id':identity,'purpose':spec['purpose'],'rect':spec['rect'],'method':method,
                'ui_type':category,'category':TYPES.get(category),'classification':classification,
                'visible_bounds':list(bounds),'subject_bounds_checked':expected is not None,
                'background_color':background,'inputs':inputs,'pending_reconstruction':pending,
                'status':'reference_crop' if method=='rect' else 'segmented_candidate',
                'internal_geometry_review_required':True}
        prepared.append((image,mask,repair_mask,record))
    # Validate all regions before writing; preserve coordinates, never fit to mask bounds.
    out.mkdir(parents=True);assembly=Image.new('RGBA',reference.size);preview=reference.copy()
    draw=ImageDraw.Draw(preview)
    for image,mask,repair_mask,record in prepared:
        identity=record['id'];x,y,w,h=record['rect']
        for suffix,artifact in [('',image),('--mask',mask),('--repair-mask',repair_mask)]:
            artifact.save(out/(identity+suffix+'.png'))
        record['sha256']=ui.digest(out/(identity+'.png'))
        record['mask_sha256']=ui.digest(out/(identity+'--mask.png'))
        record['repair_mask_sha256']=ui.digest(out/(identity+'--repair-mask.png'))
        assembly.alpha_composite(image,(x,y))
        draw.rectangle((x,y,x+w-1,y+h-1),outline='#ffcc00',width=1)
        draw.text((x+2,y+2),identity,fill='#ffcc00')
    assembly.save(out/'assembly.png');preview.save(out/'preview.png');reference.save(out/'reference.png')
    (out/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),'utf-8')
    cards=''.join('<figure><figcaption>'+record['id']+'</figcaption><img src="'+record['id']+
                  '.png"></figure>' for _,_,_,record in prepared)
    (out/'index.html').write_text('''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<title>候选分层对照</title><style>
body{background:#20232a;color:#eee;font:16px sans-serif;margin:24px}
section{display:flex;gap:20px;flex-wrap:wrap}figure{margin:0 0 20px}
img{display:block;max-width:100%;height:auto;background-color:#bbb;
background-image:conic-gradient(#eee 25%,transparent 0 50%,#eee 0 75%,transparent 0);
background-size:20px 20px}figcaption{padding:8px 0}
</style><h1>候选分层对照</h1><p>按原始坐标组装。仅为候选；主体尺寸及内部几何须结合报告检查，未视觉批准。</p>
<p><a href="report.json">检查报告</a> · <a href="plan.json">区域计划</a></p><section>
<figure><figcaption>参考原图</figcaption><img src="reference.png"></figure>
<figure><figcaption>固定区域标注</figcaption><img src="preview.png"></figure>
<figure><figcaption>候选组装</figcaption><img src="assembly.png"></figure>
</section><h2>独立图层</h2><section>'''+cards+'</section></html>','utf-8')
    report={'source':str(source),'source_sha256':ui.digest(source),'plan_sha256':ui.digest(plan_path),
            'canvas':plan['canvas'],'regions':[item[3] for item in prepared],
            'fixed_rects_passed':True,'visual_approved':False,
            'files':{p.name:ui.digest(p) for p in out.iterdir() if p.is_file()},
            'limitations':['No semantic segmentation model or alpha matting',
                           'Canvas/rect checks do not prove internal geometry is unchanged']}
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True);parser.add_argument('--plan',required=True)
    parser.add_argument('--out',required=True);args=parser.parse_args()
    try:print(json.dumps(build(args.source,args.plan,args.out),ensure_ascii=False,indent=2))
    except (ValueError,OSError,KeyError,TypeError) as error:
        print(str(error),file=sys.stderr);sys.exit(1)
