"""Read one saved reference-project layout; never execute its production scripts."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ui', ROOT/'skill/game-ui-production/scripts/ui.py')
ui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ui)


def main(source, out):
    source = source.resolve()
    out.mkdir(parents=True, exist_ok=False)
    layout = source/'UI设计/探索HUD/成品UI/布局.json'
    page = ui.read(layout)['pages'][0]
    assets, layers = {}, []
    for i, old in enumerate(page['layers']):
        path = ui.inside(source, old['asset'])
        destination = out/path.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
        key = f'asset_{i}'
        assets[key] = {'path': path.relative_to(source).as_posix(), 'sha256': ui.digest(path),
                       'kind': 'ui' if old.get('state') else 'content', 'source': 'saved reference-project layout',
                       'license': 'unknown; reference only', 'status': 'pending_visual_review'}
        layer = {'id': f'layer_{i}', 'asset': key, 'rect': old['rect'], 'z': i, 'resize': 'stretch'}
        if old.get('source_crop'):
            layer['crop'] = old['source_crop']
        mode = old.get('mode')
        if mode == 'contain':
            layer['resize'] = 'contain'
        elif mode == 'sample_map_mask':
            layer.update(resize='cover', mask_ellipse=[.17, .10, .98, .95])
        elif mode is not None:
            raise ValueError(f'Unsupported saved mode: {mode}')
        layers.append(layer)
    reference = source/'UI设计'/page['reference']
    destination = out/reference.relative_to(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(reference, destination)
    documents = ['AGENTS.md', 'UI设计/AGENTS.md', 'UI设计/整体UI设计文档.md',
                 'UI设计/生图与素材生产规范.md', 'UI设计/探索HUD/设计稿.md']
    for name in documents + ['godot/reports/current-delivery.md']:
        path = ui.inside(source, name)
        destination = out/path.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
    config = {'schema_version': 1, 'source_root': '.', 'output_root': str(ROOT/'output'),
              'engine': 'godot4', 'documents': documents, 'status_source': 'godot/reports/current-delivery.md',
              'art_bible': 'UI设计/整体UI设计文档.md',
              'rules': {'mode': 'read-only reference; no project task resumed',
                        'production_scope': ['ui'], 'excluded_content': ['map', 'background'],
                        'artistic_retry_budget': 2}}
    manifest = {'schema_version': 1, 'canvas': page['canvas'], 'assets': assets, 'masters': {},
                'systems': [{'id': 'hud', 'name': '参考项目：地图饰框', 'pages': ['map-frame']}],
                'pages': [{'id': 'map-frame', 'name': page['name'], 'system': 'hud', 'status': 'candidate',
                           'reference': {'path': reference.relative_to(source).as_posix(), 'sha256': ui.digest(reference)},
                           'layers': layers, 'assessment': [[390, 85, 740, 650]],
                           'scope_mask': 'scope',
                           'notes': ['只读工具测试；没有继续参考项目制作或修改其状态。',
                                     '分析蒙版来自独立饰框 Alpha>16 的实际显示范围，排除背景与地图；仍须用户视觉审阅。']}]}
    frame_page = {'id': 'mask', 'layers': [layers[-1]]}
    frame, _ = ui.compose(manifest, frame_page, out.resolve(), 'normal')
    mask = frame.getchannel('A').point(lambda a: 255 if a > 16 else 0)
    mask.save(out/'scope.png')
    assets['scope'] = {'path': 'scope.png', 'sha256': ui.digest(out/'scope.png'), 'kind': 'content',
                       'source': 'derived from independent frame alpha>16 at saved layout geometry',
                       'license': 'derived inspection data', 'status': 'candidate'}
    for name, data in [('project', config), ('manifest', manifest)]:
        (out/f'{name}.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), 'utf-8')
    paths = list((source/'UI设计').rglob('*'))
    inventory = {'documents': {p: ui.digest(ui.inside(source, p)) for p in documents},
                 'status_source': config['status_source'], 'saved_layout': str(layout),
                 'saved_layout_sha256': ui.digest(layout), 'assets': assets,
                 'counts': {suffix: sum(p.is_file() and p.suffix.lower() == suffix for p in paths)
                            for suffix in ['.png', '.json', '.md', '.html']},
                 'confirmed_inputs': ['整体风格基线有文档依据；不表示本测试页面已确认'],
                 'missing': ['该页面逐页用户视觉批准', '资产许可确认', '引擎适配验证'],
                 'reference_project_written': False}
    inventory['read_only_source_hashes'] = {str(ui.inside(source, p)): ui.digest(ui.inside(source, p))
        for p in documents + ['godot/reports/current-delivery.md'] +
        [old['asset'] for old in page['layers']] + [str(reference.relative_to(source)), str(layout.relative_to(source))]}
    (out/'inventory.json').write_text(json.dumps(inventory, ensure_ascii=False, indent=2), 'utf-8')
    print(str(out))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    main(args.source, args.out)
