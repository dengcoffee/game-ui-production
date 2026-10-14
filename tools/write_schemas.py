"""Generate the checked-in JSON schemas; no project-specific rules."""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / 'skill/game-ui-production/references'
STRING = {'type': 'string', 'minLength': 1}
ID = {'type': 'string', 'pattern': '^(?!.*--)[a-zA-Z0-9_-]+$'}
HASH = {'type': 'string', 'pattern': '^[a-f0-9]{64}$'}
NUM = {'type': 'number'}
POS = {'type': 'integer', 'minimum': 1}


def array(items, minimum=0):
    return {'type': 'array', 'items': items, 'minItems': minimum}


def tuple_of(*items):
    return {'type': 'array', 'prefixItems': list(items), 'items': False,
            'minItems': len(items), 'maxItems': len(items)}


def obj(properties, required):
    return {'type': 'object', 'properties': properties, 'required': required,
            'additionalProperties': False}


RECT = tuple_of({'type': 'integer'}, {'type': 'integer'}, POS, POS)
XY = tuple_of(NUM, NUM)
BOUNDS = tuple_of(*[{'type': 'integer', 'minimum': 0}]*4)
UNIT = {'type': 'number', 'minimum': 0, 'maximum': 1}
POINTS = array({'type': 'integer', 'minimum': 0}, 2)
classification = obj({'status': {'enum': ['resolved','pending']}, 'role': STRING,
                      'basis': STRING, 'evidence': array(STRING,1),
                      'candidates': array({'enum': ['base','frame','button','tab','avatar_frame','item_slot',
                          'scroll_track','scroll_thumb','progress_track','progress_fill','decoration','ui_icon','font']},2),
                      'question': STRING}, ['status','role','basis','evidence'])
classification['allOf']=[{'if': {'properties': {'status': {'const': 'pending'}}},
                         'then': {'required': ['candidates','question']}}]
grid = obj({k: POINTS for k in ['source_x', 'source_y', 'target_x', 'target_y']},
           ['source_x', 'source_y', 'target_x', 'target_y'])
fields = {'id': ID, 'z': {'type': 'integer'}, 'parent': ID, 'visible': {'type': 'boolean'},
          'opacity': UNIT, 'clip': RECT, 'asset': STRING, 'rect': RECT,
          'anchor': tuple_of(UNIT, UNIT), 'crop': BOUNDS, 'body': {'type': 'boolean'},
          'alpha_threshold': {'type': 'integer', 'minimum': 0, 'maximum': 254},
          'resize': {'enum': ['native', 'contain', 'cover', 'stretch', 'grid']}, 'grid': grid,
          'mask_ellipse': tuple_of(UNIT, UNIT, UNIT, UNIT),
          'text': {'type': 'string'}, 'font': STRING, 'size': POS, 'color': STRING, 'xy': XY,
          'text_anchor': STRING, 'stroke': {'type': 'integer', 'minimum': 0},
          'stroke_color': STRING, 'spacing': {'type': 'integer', 'minimum': 0}}
fields.update({'binding': STRING, 'max_width': POS, 'max_lines': POS,
               'overflow': {'enum': ['wrap', 'ellipsis', 'clip']}, 'letter_spacing': NUM,
               'shadow': obj({'offset': XY, 'color': STRING}, ['offset', 'color'])})
fields['typography_token'] = STRING
fields['fill_binding'] = STRING
layer = obj(fields, ['id', 'z'])
layer['oneOf'] = [{'required': ['asset', 'rect', 'resize'], 'not': {'required': ['text']}},
                  {'required': ['text', 'xy'], 'not': {'required': ['asset']}, 'anyOf': [
                      {'required': ['font','size','color']}, {'required': ['typography_token']}]}]
layer['allOf'] = [
    {'not': {'required': ['crop', 'body']}},
    {'if': {'required': ['resize'], 'properties': {'resize': {'const': 'grid'}}},
     'then': {'required': ['grid']}}
]
patch = obj({k: v for k, v in fields.items() if k != 'id'}, [])
asset = obj({'path': STRING, 'sha256': HASH, 'kind': {'enum': ['ui', 'content', 'font']},
             'source': STRING, 'license': STRING, 'status': STRING,
             'ui_type': {'enum': ['base','frame','button','tab','avatar_frame','item_slot',
                                  'scroll_track','scroll_thumb','progress_track','progress_fill',
                                  'separator','decoration','ui_icon','font']},
             'tags': array(STRING), 'display_name': STRING, 'asset_state': ID,
             'classification': classification},
            ['path', 'sha256', 'kind', 'source', 'license', 'status'])
page = obj({'id': ID, 'name': STRING, 'system': ID, 'master': ID, 'status': STRING,
            'reference': obj({'path': STRING, 'sha256': HASH}, ['path', 'sha256']),
            'layers': array(layer), 'assessment': array(RECT, 1), 'exclude': array(RECT), 'scope_mask': STRING,
            'notes': array(STRING), 'state_overrides': {'type': 'object',
                'propertyNames': {'allOf': [ID, {'not': {'const': 'normal'}}]},
                'additionalProperties': {'type': 'object', 'additionalProperties': patch}}},
           ['id', 'name', 'system', 'status', 'reference', 'layers'])
page['properties'].update({
    'data': {'type': 'object'},
    'scroll_regions': array(obj({'id': ID, 'rect': RECT, 'layers': array(ID,1),
        'content_size': tuple_of(POS,POS), 'offset': tuple_of({'type':'integer','minimum':0},{'type':'integer','minimum':0})},
        ['id','rect','layers','content_size','offset'])),
    'interactions': array(obj({'id': ID, 'rect': RECT, 'action': STRING,
        'disabled': {'type': 'boolean'}, 'focus_order': {'type': 'integer', 'minimum': 0},
        'states': {'type': 'object', 'propertyNames': {'enum': ['normal','hover','pressed','selected','disabled','focus']},
                   'additionalProperties': ID}}, ['id', 'rect', 'action'])),
    'animations': array(obj({'layer': ID, 'property': {'enum': ['opacity','x','y','rotation','scale']},
        'from': NUM, 'to': NUM, 'duration': {'type': 'number', 'exclusiveMinimum': 0},
        'loop': {'type': 'boolean'}}, ['layer','property','from','to','duration']))})
manifest = obj({'schema_version': {'enum': [1, 2]}, 'canvas': tuple_of(POS, POS),
                'assets': {'type': 'object', 'propertyNames': ID, 'additionalProperties': asset},
                'masters': {'type': 'object', 'propertyNames': ID, 'additionalProperties': array(layer)},
                'systems': array(obj({'id': ID, 'name': STRING, 'pages': array(ID, 1)},
                                     ['id', 'name', 'pages']), 1), 'pages': array(page, 1)},
               ['schema_version', 'canvas', 'assets', 'masters', 'systems', 'pages'])
manifest['properties']['typography'] = {'type': 'object', 'additionalProperties': obj({
    'font': STRING, 'size': POS, 'color': STRING, 'stroke': {'type':'integer','minimum':0},
    'spacing': {'type':'integer','minimum':0}}, ['font','size','color'])}
project = obj({'schema_version': {'enum': [1, 2]}, 'source_root': STRING, 'output_root': STRING,
               'engine': STRING, 'documents': array(STRING), 'status_source': STRING,
               'rules': {'type': 'object'}, 'art_bible': STRING},
              ['schema_version', 'source_root', 'output_root', 'engine', 'documents', 'status_source', 'rules', 'art_bible'])
for name, schema in [('layer', layer), ('manifest', manifest), ('project', project), ('classification',classification)]:
    schema['$schema'] = 'https://json-schema.org/draft/2020-12/schema'
    (OUT / (name + '.schema.json')).write_text(json.dumps(schema, indent=2), 'utf-8')
