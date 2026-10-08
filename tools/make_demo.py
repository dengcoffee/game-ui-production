"""Create deterministic technical fixtures, not game production artwork."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ui', ROOT/'skill/game-ui-production/scripts/ui.py')
ui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ui)


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), 'utf-8')


def make(out, font, canvas):
    out.mkdir(parents=True, exist_ok=False)
    (out/'assets').mkdir()
    (out/'rules.md').write_text('技术测试样例；全部为候选，无用户美术确认。几何资产仅用于验证工具，不作为游戏美术。', 'utf-8')
    shutil.copyfile(font, out/'assets/font.ttf')
    panel = Image.new('RGBA', (120, 80))
    d = ImageDraw.Draw(panel)
    d.rounded_rectangle((4, 4, 115, 75), radius=12, fill='#253955', outline='#72c8ce', width=3)
    panel.save(out/'assets/panel.png')
    for name, color in [('button', '#468689'), ('disabled', '#667080')]:
        im = Image.new('RGBA', (100, 50))
        ImageDraw.Draw(im).rounded_rectangle((8, 8, 91, 41), radius=6, fill=color)
        im.save(out/f'assets/{name}.png')
    assets = {p.stem: {'path': p.relative_to(out).as_posix(), 'sha256': ui.digest(p),
                      'kind': 'font' if p.suffix == '.ttf' else 'ui',
                      'source': 'local OS font' if p.suffix == '.ttf' else 'deterministic test fixture',
                      'license': 'local-use-only; OS font not distributed' if p.suffix == '.ttf' else 'CC0',
                      'status': 'candidate'} for p in (out/'assets').iterdir()}
    w, h = canvas
    master = [
        {'id': 'window', 'asset': 'panel', 'rect': [20, 20, w-40, h-40], 'resize': 'grid', 'z': 0,
         'grid': {'source_x': [0, 20, 100, 120], 'source_y': [0, 20, 60, 80],
                  'target_x': [0, 20, w-60, w-40], 'target_y': [0, 20, h-60, h-40]}},
        {'id': 'action', 'parent': 'window', 'asset': 'button', 'body': True,
         'rect': [w-180, h-120, 112, 46], 'resize': 'contain', 'z': 2},
        {'id': 'label', 'parent': 'action', 'text': 'Confirm', 'font': 'font',
         'xy': [16, 12], 'size': 20, 'color': '#ffffff', 'text_anchor': 'lt', 'z': 3}]
    pages = []
    for name in ['inventory', 'settings']:
        page = {'id': name, 'name': name.title(), 'system': name, 'master': 'common', 'status': 'candidate',
                'reference': {'path': f'{name}-reference.png', 'sha256': '0'*64},
                'layers': [{'id': 'title', 'text': name.title(), 'font': 'font', 'xy': [48, 42],
                            'size': 30, 'color': '#c8eff0', 'text_anchor': 'lt', 'z': 4},
                           {'id': 'description', 'text': 'Shared master / independent PNGs\nOffline visual review',
                            'font': 'font', 'xy': [48, 100], 'size': 22, 'color': '#ffffff', 'z': 4}],
                'assessment': [[20, 20, w-40, h-40]], 'exclude': [[40, h-85, 70, 30]],
                'state_overrides': {'disabled': {'action': {'asset': 'disabled'}}},
                'notes': ['技术样例；非游戏美术交付。两个系统引用同一个母版与按钮状态资产。']}
        pages.append(page)
    manifest = {'schema_version': 1, 'canvas': canvas, 'assets': assets, 'masters': {'common': master},
                'systems': [{'id': p['system'], 'name': p['name'], 'pages': [p['id']]} for p in pages], 'pages': pages}
    for page in pages:
        reference, _ = ui.compose(manifest, page, out.resolve(), 'normal')
        # Known reference mismatch exercises threshold/mask; deliberately not a design target.
        ImageDraw.Draw(reference).rectangle((55, 170, 85, 195), fill='#d59055')
        reference.save(out/page['reference']['path'])
        page['reference']['sha256'] = ui.digest(out/page['reference']['path'])
    config = {'schema_version': 1, 'source_root': '.', 'output_root': '../..', 'engine': 'none',
              'documents': ['rules.md'], 'status_source': 'rules.md', 'art_bible': 'rules.md',
              'rules': {'production_scope': ['ui'], 'artistic_retry_budget': 2}}
    save(out/'project.json', config)
    save(out/'manifest.json', manifest)
    print(str(out))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--font', required=True, type=Path)
    parser.add_argument('--canvas', nargs=2, type=int, default=[640, 360])
    args = parser.parse_args()
    make(args.out, args.font, args.canvas)
