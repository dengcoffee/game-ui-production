"""Deterministic, read-only-input UI composition and offline review packaging."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import sys

from jsonschema import Draft202012Validator
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

HOME = Path(__file__).resolve().parents[1]
VERSION = '1.0.0'
RESAMPLE = Image.Resampling.LANCZOS


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text('utf-8-sig'))


def validate_schema(value, name):
    schema = read(HOME / 'references' / (name + '.schema.json'))
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda e: str(e.path))
    if errors:
        raise ValueError('\n'.join(f'{list(e.path)}: {e.message}' for e in errors))


def inside(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError(f'Input missing or outside source_root: {relative}')
    return path


def image_info(path, threshold=0):
    with Image.open(path) as source:
        im = source.convert('RGBA')
        alpha = im.getchannel('A')
        return {'size': list(im.size), 'alpha_extrema': list(alpha.getextrema()),
                'visible_bounds': alpha.point(lambda a: 255 if a > threshold else 0).getbbox(),
                'has_alpha_channel': 'A' in source.getbands() or 'transparency' in source.info}


def expanded(manifest, page, state='normal'):
    layers = [dict(v) for v in manifest['masters'].get(page.get('master'), []) + page['layers']]
    changes = page.get('state_overrides', {}).get(state, {})
    ids = [v['id'] for v in layers]
    if len(ids) != len(set(ids)) or set(changes) - set(ids):
        raise ValueError(f'Duplicate layer IDs or unknown state targets: {page["id"]}')
    for index, layer in enumerate(layers):
        layer.update(changes.get(layer['id'], {}))
        if layer.get('typography_token'):
            token = manifest.get('typography', {}).get(layer['typography_token'])
            if token is None:
                raise ValueError(f'Unknown typography token: {layer["typography_token"]}')
            layer = dict(token, **layer)
        validate_schema(layer, 'layer')
        layers[index] = layer
    return layers


def lookup(data, key, fallback=None):
    value = data
    for part in key.split('.'):
        if not isinstance(value, dict) or part not in value:
            return fallback
        value = value[part]
    return value


def layout_text(value, font, layer):
    value = str(value)
    width = layer.get('max_width')
    tracking = layer.get('letter_spacing', 0)
    length = lambda s: font.getlength(s) + max(0, len(s)-1)*tracking
    if not width or layer.get('overflow', 'wrap') == 'clip':
        return value
    lines = []
    for paragraph in value.split('\n'):
        if layer.get('overflow', 'wrap') == 'ellipsis':
            while paragraph and length(paragraph) > width:
                paragraph = paragraph[:-1]
            if paragraph != value and paragraph:
                while paragraph and length(paragraph + '…') > width:
                    paragraph = paragraph[:-1]
                paragraph += '…'
            lines.append(paragraph)
        else:
            line = ''
            for char in paragraph:
                if line and length(line+char) > width:
                    lines.append(line)
                    line = ''
                line += char
            lines.append(line)
    maximum = layer.get('max_lines')
    if maximum and len(lines) > maximum:
        lines = lines[:maximum]
        while lines[-1] and length(lines[-1]+'…') > width:
            lines[-1] = lines[-1][:-1]
        lines[-1] += '…'
    return '\n'.join(lines)


def load(config_path, manifest_path):
    config_path, manifest_path = Path(config_path).resolve(), Path(manifest_path).resolve()
    config, manifest = read(config_path), read(manifest_path)
    validate_schema(config, 'project')
    validate_schema(manifest, 'manifest')
    root = (config_path.parent / config['source_root']).resolve()
    inputs = {str(config_path): digest(config_path), str(manifest_path): digest(manifest_path)}
    for name in config['documents'] + [config['art_bible'], config['status_source']]:
        path = inside(root, name)
        inputs[str(path)] = digest(path)
    resources = {}
    for identity, asset in manifest['assets'].items():
        path = inside(root, asset['path'])
        actual = digest(path)
        if actual != asset['sha256']:
            raise ValueError(f'Asset hash mismatch: {identity}')
        inputs[str(path)] = actual
        resources[identity] = {'path': asset['path'], 'sha256': actual,
                               'kind': asset['kind'], 'status': asset['status'],
                               'source': asset['source'], 'license': asset['license'], 'pages': []}
        if asset['kind'] != 'font':
            resources[identity].update(image_info(path))
    page_ids = [p['id'] for p in manifest['pages']]
    if len(page_ids) != len(set(page_ids)):
        raise ValueError('Duplicate page IDs')
    system_ids = [s['id'] for s in manifest['systems']]
    if len(system_ids) != len(set(system_ids)):
        raise ValueError('Duplicate system IDs')
    for system in manifest['systems']:
        expected = {p['id'] for p in manifest['pages'] if p['system'] == system['id']}
        if set(system['pages']) != expected or len(system['pages']) != len(expected):
            raise ValueError(f'System page membership mismatch: {system["id"]}')
    for page in manifest['pages']:
        if page['system'] not in system_ids:
            raise ValueError(f'Unknown system: {page["system"]}')
        if page.get('master') and page['master'] not in manifest['masters']:
            raise ValueError(f'Unknown master: {page["master"]}')
        reference = inside(root, page['reference']['path'])
        if digest(reference) != page['reference']['sha256']:
            raise ValueError(f'Reference hash mismatch: {page["id"]}')
        if image_info(reference)['size'] != manifest['canvas']:
            raise ValueError(f'Reference must match logical canvas: {page["id"]}')
        inputs[str(reference)] = digest(reference)
        layer_ids = {v['id'] for v in expanded(manifest, page)}
        states = {'normal', *page.get('state_overrides', {})}
        interactions = page.get('interactions', [])
        if len({v['id'] for v in interactions}) != len(interactions):
            raise ValueError('Duplicate interaction IDs')
        for control in interactions:
            if set(control.get('states', {}).values()) - states:
                raise ValueError(f'Unknown interaction state: {control["id"]}')
        for animation in page.get('animations', []):
            if animation['layer'] not in layer_ids:
                raise ValueError(f'Unknown animation layer: {animation["layer"]}')
        scroll_ids = set()
        scrolling_layers = set()
        for region in page.get('scroll_regions', []):
            if region['id'] in scroll_ids or set(region['layers']) - layer_ids:
                raise ValueError('Duplicate scroll region or unknown scroll layer')
            scroll_ids.add(region['id'])
            if scrolling_layers & set(region['layers']):
                raise ValueError('Layer cannot belong to multiple scroll regions')
            scrolling_layers.update(region['layers'])
            for layer in expanded(manifest,page):
                if layer['id'] in region['layers'] and layer.get('parent'):
                    raise ValueError('Scroll region layers use absolute geometry; parent motion must be outside the region')
            for axis in range(2):
                if region['offset'][axis] > max(0,region['content_size'][axis]-region['rect'][axis+2]):
                    raise ValueError('Scroll offset exceeds content')
        if page.get('scope_mask'):
            key = page['scope_mask']
            if key not in resources or manifest['assets'][key]['kind'] == 'font':
                raise ValueError(f'Unknown image scope mask: {key}')
            if resources[key]['size'] != manifest['canvas']:
                raise ValueError(f'Scope mask must match logical canvas: {page["id"]}')
            resources[key]['pages'].append(page['id'])
        for state in ['normal'] + list(page.get('state_overrides', {})):
            layers = expanded(manifest, page, state)
            positions(layers)
            for layer in layers:
                for field in ['asset', 'font']:
                    if field not in layer:
                        continue
                    key = layer[field]
                    if key not in resources:
                        raise ValueError(f'Unknown resource: {key}')
                    asset = manifest['assets'][key]
                    if (field == 'font') != (asset['kind'] == 'font'):
                        raise ValueError(f'Resource kind mismatch: {key}')
                    if field == 'asset' and inside(root, asset['path']) == reference:
                        raise ValueError('Reference image cannot be an assembly layer')
                    if page['id'] not in resources[key]['pages']:
                        resources[key]['pages'].append(page['id'])
    return config, manifest, root, inputs, resources


def positions(layers):
    by_id = {v['id']: v for v in layers}
    result = {}

    def resolve(key, trail):
        if key in result:
            return result[key]
        if key in trail or key not in by_id:
            raise ValueError(f'Invalid layer parent graph: {key}')
        layer = by_id[key]
        rect = layer.get('rect', [*layer.get('xy', [0, 0]), 0, 0])
        x, y, w, h = rect
        ax, ay = layer.get('anchor', [0, 0]) if 'rect' in layer else [0, 0]
        x, y = x - w * ax, y - h * ay
        if layer.get('parent'):
            px, py, _, _ = resolve(layer['parent'], trail + [key])
            x, y = x + px, y + py
        result[key] = [round(x), round(y), w, h]
        return result[key]

    for key in by_id:
        resolve(key, [])
    return result


def resize(im, layer, size):
    mode = layer['resize']
    if mode == 'native':
        if im.size != size:
            raise ValueError(f'Native image size mismatch: {layer["id"]}')
        return im
    if mode == 'contain':
        return ImageOps.contain(im, size, RESAMPLE)
    if mode == 'cover':
        return ImageOps.fit(im, size, RESAMPLE)
    if mode == 'stretch':
        return im.resize(size, RESAMPLE)
    grid = layer['grid']
    sx, sy, tx, ty = [grid[k] for k in ['source_x', 'source_y', 'target_x', 'target_y']]
    for source, target, original, dest in [(sx, tx, im.width, size[0]), (sy, ty, im.height, size[1])]:
        if (len(source) != len(target) or source[0] != 0 or target[0] != 0
                or source[-1] != original or target[-1] != dest
                or any(b <= a for a, b in zip(source, source[1:]))
                or any(b <= a for a, b in zip(target, target[1:]))):
            raise ValueError(f'Invalid slice grid: {layer["id"]}')
    result = Image.new('RGBA', size)
    for i in range(len(sx) - 1):
        for j in range(len(sy) - 1):
            tile = im.crop((sx[i], sy[j], sx[i+1], sy[j+1]))
            tile = tile.resize((tx[i+1]-tx[i], ty[j+1]-ty[j]), RESAMPLE)
            result.alpha_composite(tile, (tx[i], ty[j]))
    return result


def compose(manifest, page, root, state):
    canvas = Image.new('RGBA', tuple(manifest['canvas']))
    layers = expanded(manifest, page, state)
    coords = positions(layers)
    records = []
    by_id = {layer['id']:layer for layer in layers}
    def visible(layer):
        return layer.get('visible',True) and (not layer.get('parent') or visible(by_id[layer['parent']]))
    for layer in sorted(layers, key=lambda v: v['z']):
        if not visible(layer):
            continue
        plane = Image.new('RGBA', canvas.size)
        x, y, w, h = coords[layer['id']]
        regions = [r for r in page.get('scroll_regions', []) if layer['id'] in r['layers']]
        for region in regions:
            x -= region['offset'][0]
            y -= region['offset'][1]
        record = {'id': layer['id'], 'rect': [x, y, w, h], 'z': layer['z']}
        if 'asset' in layer:
            path = inside(root, manifest['assets'][layer['asset']]['path'])
            with Image.open(path) as source:
                im = source.convert('RGBA')
            crop = layer.get('crop')
            if layer.get('body'):
                crop = im.getchannel('A').point(lambda a: 255 if a > layer.get('alpha_threshold', 0) else 0).getbbox()
                if crop is None:
                    raise ValueError(f'Empty visible body: {layer["id"]}')
            if crop:
                if not (0 <= crop[0] < crop[2] <= im.width and 0 <= crop[1] < crop[3] <= im.height):
                    raise ValueError(f'Crop outside source: {layer["id"]}')
                im = im.crop(crop)
            im = resize(im, layer, (w, h))
            x += (w-im.width)//2
            y += (h-im.height)//2
            if layer.get('mask_ellipse'):
                mask = Image.new('L', im.size)
                r = layer['mask_ellipse']
                ImageDraw.Draw(mask).ellipse(tuple([r[0]*im.width, r[1]*im.height,
                                                  r[2]*im.width, r[3]*im.height]), fill=255)
                im.putalpha(ImageChops.multiply(im.getchannel('A'), mask))
            plane.alpha_composite(im, (x, y))
            bounds = im.getchannel('A').getbbox()
            record.update(asset=layer['asset'], crop=crop, drawn_rect=[x, y, *im.size],
                          visible_bounds=[x+bounds[0], y+bounds[1], x+bounds[2], y+bounds[3]] if bounds else None)
        else:
            path = inside(root, manifest['assets'][layer['font']]['path'])
            font = ImageFont.truetype(str(path), layer['size'])
            options = {'font': font, 'fill': layer['color'], 'stroke_width': layer.get('stroke', 0),
                       'stroke_fill': layer.get('stroke_color', layer['color']),
                       'spacing': layer.get('spacing', 4)}
            if layer.get('text_anchor'):
                options['anchor'] = layer['text_anchor']
            draw = ImageDraw.Draw(plane)
            value = lookup(page.get('data', {}), layer['binding'], layer['text']) if layer.get('binding') else layer['text']
            value = layout_text(value, font, layer)
            if layer.get('shadow'):
                shadow = dict(options, fill=layer['shadow']['color'], stroke_fill=layer['shadow']['color'])
                dx, dy = layer['shadow']['offset']
                draw.text((x+dx, y+dy), value, **shadow)
            if layer.get('letter_spacing', 0):
                for row, line in enumerate(value.split('\n')):
                    px = x
                    for char in line:
                        draw.text((px, y+row*(layer['size']+layer.get('spacing', 4))), char, **options)
                        px += font.getlength(char)+layer['letter_spacing']
            else:
                draw.text((x, y), value, **options)
            bounds_options = {k: v for k, v in options.items() if k not in ['fill', 'stroke_fill']}
            record['text_bounds'] = plane.getbbox()
            record['rendered_text'] = value
            if layer.get('max_width') and layer.get('overflow') == 'clip':
                clip = Image.new('L', canvas.size)
                ImageDraw.Draw(clip).rectangle((x,y,x+layer['max_width']-1,canvas.height), fill=255)
                plane.putalpha(ImageChops.multiply(plane.getchannel('A'),clip))
        if 'clip' in layer:
            clip = Image.new('L', canvas.size)
            cx, cy, cw, ch = layer['clip']
            ImageDraw.Draw(clip).rectangle((cx, cy, cx+cw-1, cy+ch-1), fill=255)
            plane.putalpha(ImageChops.multiply(plane.getchannel('A'), clip))
        for region in regions:
            clip = Image.new('L', canvas.size)
            cx,cy,cw,ch = region['rect']
            ImageDraw.Draw(clip).rectangle((cx,cy,cx+cw-1,cy+ch-1),fill=255)
            plane.putalpha(ImageChops.multiply(plane.getchannel('A'),clip))
        if layer.get('fill_binding'):
            fill = min(1,max(0,float(lookup(page.get('data',{}),layer['fill_binding'],1))))
            clip = Image.new('L', canvas.size)
            if fill > 0:
                ImageDraw.Draw(clip).rectangle((x,y,x+round(w*fill)-1,y+h-1),fill=255)
            plane.putalpha(ImageChops.multiply(plane.getchannel('A'),clip))
        if layer.get('opacity', 1) != 1:
            plane.putalpha(plane.getchannel('A').point(lambda a: round(a*layer['opacity'])))
        canvas.alpha_composite(plane)
        records.append(record)
    return canvas, records


def assessment_mask(manifest, page, root=None):
    mask = Image.new('L', tuple(manifest['canvas']))
    draw = ImageDraw.Draw(mask)
    for color, boxes in [(255, page.get('assessment', [[0, 0, *manifest['canvas']]])),
                         (0, page.get('exclude', []))]:
        for x, y, w, h in boxes:
            draw.rectangle((x, y, x+w-1, y+h-1), fill=color)
    if page.get('scope_mask'):
        with Image.open(inside(root, manifest['assets'][page['scope_mask']]['path'])) as source:
            mask = ImageChops.multiply(mask, source.convert('L').point(lambda a: 255 if a > 0 else 0))
    return mask


def data_uri(image):
    stream = io.BytesIO()
    image.save(stream, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(stream.getvalue()).decode('ascii')


def build(config_path, manifest_path, out, previous=None, page_ids=None):
    config, manifest, root, inputs, resources = load(config_path, manifest_path)
    out = Path(out).resolve()
    allowed = (Path(config_path).resolve().parent / config['output_root']).resolve()
    if not out.is_relative_to(allowed) or out == allowed:
        raise ValueError('Output must be a child of configured output_root')
    if out.exists() and any(out.iterdir()):
        raise ValueError('Output directory is not empty; use a new candidate directory')
    if any(Path(p).is_relative_to(out) for p in inputs):
        raise ValueError('Output overlaps inputs')
    previous = Path(previous).resolve() if previous else None
    old_report = read(previous/'build.json') if previous else {'pages': []}
    old_views = {(p['id'],p['state']):p for p in old_report['pages']}
    if page_ids and set(page_ids)-{p['id'] for p in manifest['pages']}:
        raise ValueError('Unknown page filter')
    tool_files = [p for p in HOME.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    tool_hashes = {str(p.relative_to(HOME)):digest(p) for p in tool_files}
    # Complete all rendering before writing any output; unsupported data fails visibly.
    rendered = []
    for page in manifest['pages']:
        if page_ids and page['id'] not in page_ids:
            continue
        for state in ['normal'] + list(page.get('state_overrides', {})):
            layers = expanded(manifest,page,state)
            used = {l[k] for l in layers for k in ['asset','font'] if k in l}
            if page.get('scope_mask'):used.add(page['scope_mask'])
            identity = {'canvas':manifest['canvas'],'page':page,'layers':layers,
                'assets':{k:manifest['assets'][k] for k in sorted(used)},
                'tools':tool_hashes, 'rules':config['rules']}
            fingerprint = hashlib.sha256(json.dumps(identity,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            old = old_views.get((page['id'],state))
            reused = False
            if old and old.get('fingerprint') == fingerprint:
                file = previous/(page['id']+'--'+state+'.png')
                if digest(file) != old['assembly_hash']:
                    raise ValueError('Incremental cache image changed')
                with Image.open(file) as source:image = source.convert('RGBA')
                records = old['layers']
                reused = True
            else:
                image, records = compose(manifest, page, root, state)
            mask = assessment_mask(manifest, page, root)
            included = mask.histogram()[255]
            if included == 0:
                raise ValueError(f'Empty assessment scope: {page["id"]}')
            with Image.open(inside(root, page['reference']['path'])) as source:
                reference = source.convert('RGBA')
            rendered.append((page, state, image, records, mask, reference, included,fingerprint,reused))
    out.mkdir(parents=True, exist_ok=True)
    views, layout_records = [], []
    for page, state, image, records, mask, reference, included,fingerprint,reused in rendered:
        key = page['id'] + '--' + state
        image.save(out / (key + '.png'))
        mask.save(out / (key + '--mask.png'))
        view = {'id': page['id'], 'name': page['name'], 'system': page['system'], 'state': state,
                'status': page['status'], 'reference_hash': page['reference']['sha256'],
                'assembly_hash': digest(out / (key + '.png')), 'image': data_uri(image),
                'reference': data_uri(reference), 'mask': data_uri(mask), 'included': included,
                'layers': records, 'notes': page.get('notes', []), 'fingerprint':fingerprint,'reused':reused}
        views.append(view)
        layout_records.append({k: v for k, v in view.items() if k not in ['image', 'reference', 'mask']})
    selected = {p['id'] for p in views}
    systems = [dict(s,pages=[p for p in s['pages'] if p in selected]) for s in manifest['systems'] if set(s['pages'])&selected]
    package = {'tool_version': VERSION, 'canvas': manifest['canvas'], 'systems': systems,
               'manifest_hash': digest(manifest_path), 'views': views}
    template = (HOME / 'assets/viewer.html').read_text('utf-8')
    pixelmatch = (HOME / 'assets/vendor/pixelmatch.js').read_text('utf-8')
    payload = json.dumps(package, ensure_ascii=False).replace('<', '\\u003c')
    html = template.replace('/*__PIXELMATCH__*/', pixelmatch).replace('/*__DATA__*/', payload)
    (out / 'index.html').write_text(html, 'utf-8')
    report = {'tool_version': VERSION, 'schema_version': manifest['schema_version'],
              'manifest_hash': digest(manifest_path), 'config_hash': digest(config_path),
              'status': 'candidate', 'visual_approved': False, 'engine_verified': False,
              'inputs': inputs, 'tools': tool_hashes,
              'resources': resources, 'pages': layout_records}
    if any(digest(p) != h for p, h in inputs.items()):
        raise ValueError('Inputs changed during build; candidate is invalid')
    (out / 'build.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf-8')
    return {'html': str(out / 'index.html'), 'views': len(views), 'status': 'candidate',
            'reused':sum(v['reused'] for v in views)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['inspect', 'build'])
    parser.add_argument('--config', required=True)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--out')
    parser.add_argument('--previous')
    parser.add_argument('--pages',nargs='+')
    args = parser.parse_args()
    try:
        if args.command == 'build':
            if not args.out:
                parser.error('build requires --out')
            result = build(args.config, args.manifest, args.out,args.previous,args.pages)
        else:
            _, manifest, _, inputs, resources = load(args.config, args.manifest)
            result = {'canvas': manifest['canvas'], 'inputs': inputs, 'resources': resources,
                      'unreferenced_assets': [k for k, v in resources.items() if not v['pages']]}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
