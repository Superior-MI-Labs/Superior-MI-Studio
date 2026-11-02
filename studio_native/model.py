"""Pure, UI-agnostic authoring model compatible with the browser Node Lab v0.1.

Everything here is prototype presentation data, NOT Studio runtime semantics.
"""
from __future__ import annotations
import copy
import json
import math
import uuid
from pathlib import Path

FORMAT = 'smi.dynamic-node-lab'
VERSION = 1
TYPES = ('u32','i32','f32','f64','bool','string','vector','image','audio','video','event','object','execution')
ROW_TYPES = ('slider','toggle','dropdown','number','text','color','label','button','preview','collection')
TYPE_COLORS = {'u32':'#eab05b','i32':'#f2787f','f32':'#25cce0','f64':'#6caaf4','bool':'#4bdca3','string':'#ce91f8','vector':'#8e95ff','image':'#5dc5ff','audio':'#e77cce','video':'#a994ff','event':'#ffd36c','object':'#b3c6d8','execution':'#ffffff',
 'py:int':'#eab05b','py:float':'#6caaf4','py:bool':'#4bdca3','py:str':'#ce91f8',
 'py:unknown':'#90aaba','py:object':'#aebeca','py:callable':'#8e95ff',
 'py:None':'#718ca1','py:bytes':'#d8ae6e','py:module':'#67c49e'}
DEFAULT_SETTINGS = {'port_label_mode':'contextual','show_grid':True,'default_visible_rows':5,'type_colors':copy.deepcopy(TYPE_COLORS)}
MAX_FILE_BYTES = 4_000_000


def uid(prefix):
    return f'{prefix}-{uuid.uuid4().hex[:13]}'


def port(label, kind='audio'):
    return {'id':uid('port'),'label':label,'type':kind}


def parse_input_default(type_id: str, text: str):
    """Interpret a *draft UI fallback* without executing or evaluating Python.

    This is not the language/runtime's notion of a function default parameter.
    Its value is only displayed while a prototype input has no incoming edge.
    """
    if type_id == 'string':
        if len(text) > 256: raise ValueError('String default exceeds 256 characters')
        return text
    if type_id == 'bool':
        if text.strip().lower() not in ('true', 'false'):
            raise ValueError('Boolean default must be true or false')
        return text.strip().lower() == 'true'
    if type_id in ('u32','i32'):
        try:
            value = int(text.strip(), 10)
        except (ValueError, TypeError) as exc:
            raise ValueError('Integer default must be a decimal integer') from exc
        in_range = (-2147483648 <= value <= 2147483647) if type_id == 'i32' else (0 <= value <= 4294967295)
        if not in_range:
            raise ValueError('Integer default is outside the declared range')
        return value
    if type_id in ('f32','f64'):
        try:
            value = float(text.strip())
        except (ValueError, TypeError) as exc:
            raise ValueError('Floating-point default must be a number') from exc
        if not math.isfinite(value):
            raise ValueError('Floating-point default must be finite')
        # A precision descriptor is not evidence of a correctly rounded
        # 32-bit runtime value. Keep this strictly a UI-only preview value.
        return value
    raise ValueError('This port type does not have a built-in scalar fallback editor')


def format_input_default(port_):
    if 'default' not in port_:
        return None
    if port_.get('binding_mode')=='source_literal' and port_.get('source_literal_text'):
        # Preserve the authored source spelling, especially quotes/escapes.
        # This is a presentation token, never evaluated as code.
        return str(port_['source_literal_text'])
    value = port_['default']
    if type(value) is bool:
        return 'true' if value else 'false'
    return str(value)


def row(kind='slider', label=None):
    if kind not in ROW_TYPES: raise ValueError('Unsupported control kind')
    result = {'id':uid('row'),'kind':kind,'label':label or kind.capitalize(),'tags':[]}
    if kind=='slider': result.update(value=.55,min=0,max=1,step=.01,unit='')
    elif kind=='toggle': result['value']=True
    elif kind=='dropdown': result.update(value='Studio',options=['Studio','Podcast','Broadcast'])
    elif kind=='number': result.update(value=32,min=0,max=4096,step=1)
    elif kind=='text': result['value']='Hello, Studio'
    elif kind=='color': result['value']='#26c7f5'
    elif kind=='label': result['value']='Read-only information'
    elif kind=='button': result['value']='Preview action'
    elif kind=='preview': result['value']='waveform'
    elif kind=='collection': result['items']=[f'dataset_{i:03d}.png' for i in range(1,101)]
    return result


def section(title='New section',rows=None):
    return {'id':uid('section'),'title':title,'collapsed':False,'page':0,'visible_rows':5,
            'rows':list(rows) if rows is not None else [row('slider')]}


def make_node(kind='custom', x=150, y=150):
    node={'id':uid('node'),'kind':kind,'title':'NEW NODE','subtitle':'Custom presentation draft',
          'accent':'#2ad0ea','x':x,'y':y,'draft_ports':{'inputs':[dict(port('Input','f32'), default=0.5)],'outputs':[port('Result','f32')]},
          'containers':[section('CONTROLS')]}
    if kind=='audio':
        node.update(title='AUDIO MIX',subtitle='Sound · mixing · output',accent='#27cbed',
                    draft_ports={'inputs':[port(n,'audio') for n in ('Audio','Music','Voice','SFX')],
                                 'outputs':[port('Mix','audio'),port('Stems','audio'),port('Analysis','object')]},
                    containers=[section('WAVEFORM',[row('preview','Waveform preview')]),
                       section('MIX CHANNELS',[dict(row('slider',n),value=v,min=0,max=1,step=.01,unit=' dB') for n,v in zip(('Music','Voice','SFX','Master'),(.66,.53,.42,.77))]),
                       section('OUTPUT SETUP',[row('toggle','Enhance'),row('dropdown','Profile'),row('text','Export name')])])
    elif kind=='fx':
        node.update(title='SIGNAL PROCESSOR',subtitle='Equalizer · audio effects',accent='#8b98ff',
                    draft_ports={'inputs':[port('Source','audio'),port('Sidechain','audio'),port('Amount','f32')],
                                 'outputs':[port('Processed','audio'),port('Envelope','f32')]},
                    containers=[section('EQUALIZER',[dict(row('slider',n),unit=' dB') for n in ('Low','Mid','High')]),
                                section('PROCESSING',[row('toggle','Limiter'),row('dropdown','Quality')])])
    elif kind=='folder':
        node.update(title='ASSET COLLECTION',subtitle='100 files · bounded listing',accent='#d7a967',
                    draft_ports={'inputs':[],'outputs':[port('Files','object'),port('Count','u32')]},
                    containers=[section('FILES',[row('collection','Texture files')]),section('OPTIONS',[row('toggle','Recursive'),row('dropdown','Sort by')])])
    elif kind=='string':
        node.update(title='STRING CONSTANT',subtitle='Text · literal draft',accent='#bd84ee',
                    draft_ports={'inputs':[],'outputs':[port('Value','string')]},
                    containers=[section('TEXT VALUE',[dict(row('text','Value'),value='Hello, World!')])])
    return node


def new_state():
    a,b,c=make_node('audio',170,100),make_node('fx',770,175),make_node('folder',180,850)
    return {'format':FORMAT,'version':VERSION,'nodes':[a,b,c],
            'edges':[{'id':uid('edge'),'source':a['id'],'sourcePort':a['draft_ports']['outputs'][0]['id'],
                     'target':b['id'],'targetPort':b['draft_ports']['inputs'][0]['id']}],
            'settings':copy.deepcopy(DEFAULT_SETTINGS)}


def find_node(state, ident):
    return next((n for n in state['nodes'] if n['id']==ident),None)


def find_port(n, direction, ident):
    if n is None: return None
    return next((p for p in n['draft_ports'][direction] if p['id']==ident),None)


def connection_error(state, src, output, dst, input_id):
    a,b=find_node(state,src),find_node(state,dst)
    if not a or not b:return 'Missing node'
    out=find_port(a,'outputs',output); pin=find_port(b,'inputs',input_id)
    if not out or not pin:return 'Missing port'
    if src==dst:return 'Self connections are disabled'
    if out['type']!=pin['type']:return f'Type mismatch: {out["type"]} → {pin["type"]}'
    if any(e['target']==dst and e['targetPort']==input_id for e in state['edges']):return 'Input already connected'
    return ''


def connect(state, src, out, dst, inp):
    error=connection_error(state,src,out,dst,inp)
    if error:raise ValueError(error)
    e={'id':uid('edge'),'source':src,'sourcePort':out,'target':dst,'targetPort':inp}
    state['edges'].append(e)
    return e


def remove_node(state, id_):
    state['nodes'][:]=[n for n in state['nodes'] if n['id']!=id_]
    state['edges'][:]=[e for e in state['edges'] if e['source']!=id_ and e['target']!=id_]


def remove_port(state,node_id,port_id):
    n=find_node(state,node_id)
    if n:
        for side in ('inputs','outputs'):
            n['draft_ports'][side][:]=[p for p in n['draft_ports'][side] if p['id']!=port_id]
        state['edges'][:]=[e for e in state['edges'] if e['sourcePort']!=port_id and e['targetPort']!=port_id]


def matches(row_, query):
    q=query.strip().lower()
    if not q:return True
    return any(q in str(value).lower() for value in [row_.get('kind',''),row_.get('label',''),row_.get('value',''),*(row_.get('tags',[]) or []),*(row_.get('items',[]) or [])])


def paged_rows(sec, query=''):
    rows=[r for r in sec['rows'] if matches(r,query)]
    limit=max(1,min(50,int(sec.get('visible_rows',5))))
    pages=max(1,math.ceil(len(rows)/limit))
    page=max(0,min(pages-1,int(sec.get('page',0))))
    return rows[page*limit:(page+1)*limit],page,pages,len(rows)


def validate(state):
    problems=[]
    if not isinstance(state,dict) or state.get('format')!=FORMAT or state.get('version')!=VERSION:
        return ['Unrecognized dynamic-node-lab document format']
    if not isinstance(state.get('nodes'),list) or not isinstance(state.get('edges'),list) or not isinstance(state.get('settings'),dict):
        return ['Missing graph members']
    if len(state['nodes'])>150 or len(state['edges'])>1200:problems.append('Graph exceeds prototype bounds')
    seen_nodes=set(); seen_ports=set()
    for n in state['nodes']:
        if not isinstance(n,dict):problems.append('Invalid node');continue
        if not isinstance(n.get('id'),str) or n['id'] in seen_nodes:problems.append('Duplicate/missing node id')
        seen_nodes.add(n.get('id'))
        if not isinstance(n.get('title'),str) or len(n['title'])>100:problems.append('Invalid title')
        if not isinstance(n.get('accent'),str) or len(n['accent'])!=7 or not n['accent'].startswith('#'):
            problems.append('Invalid accent')
        try:
            if not all(math.isfinite(n[k]) and abs(n[k])<=20000 for k in ('x','y')):problems.append('Invalid node position')
        except (KeyError,TypeError):problems.append('Missing node position')
        ports=n.get('draft_ports')
        if not isinstance(ports,dict) or not isinstance(n.get('containers'),list):problems.append('Invalid node structure');continue
        for direction in ('inputs','outputs'):
            for p in ports.get(direction,[]):
                if not isinstance(p,dict) or p.get('id') in seen_ports or not isinstance(p.get('id'),str):problems.append('Invalid or duplicate port');continue
                seen_ports.add(p['id'])
                if p.get('type') not in TYPES or not isinstance(p.get('label'),str):problems.append('Invalid port')
                if 'default' in p:
                    if direction!='inputs': problems.append('Output port cannot have an inline default')
                    elif p.get('type') == 'string' and type(p['default']) is str and len(p['default'])<=256:pass
                    elif p.get('type') == 'bool' and type(p['default']) is bool:pass
                    elif p.get('type') in ('i32','u32') and type(p['default']) is int:
                        try:parse_input_default(p['type'],str(p['default']))
                        except ValueError:problems.append('Invalid integer input default')
                    elif p.get('type') in ('f32','f64') and type(p['default']) in (int,float) and math.isfinite(p['default']):pass
                    else:problems.append('Invalid input default/type combination')
        if len(n['containers'])>32:problems.append('Too many containers')
        sec_ids=set()
        for s in n['containers']:
            if not isinstance(s,dict):problems.append('Invalid container');continue
            if s.get('id') in sec_ids:problems.append('Duplicate container')
            sec_ids.add(s.get('id'))
            rows=s.get('rows')
            limit=s.get('visible_rows')
            if not isinstance(rows,list) or len(rows)>200 or type(limit)!=int or not (1<=limit<=50):problems.append('Invalid container rows');continue
            for r in rows:
                if not isinstance(r,dict) or r.get('kind') not in ROW_TYPES:problems.append('Unsupported row control')
    occupied_inputs=set()
    for e in state['edges']:
        if not isinstance(e,dict):problems.append('Invalid edge');continue
        out=find_port(find_node(state,e.get('source')),'outputs',e.get('sourcePort'))
        inp=find_port(find_node(state,e.get('target')),'inputs',e.get('targetPort'))
        if not out or not inp:
            problems.append('Broken edge');continue
        if out['type']!=inp['type']:
            problems.append('Connected port type mismatch')
        destination=(e['target'],e['targetPort'])
        if destination in occupied_inputs:
            problems.append('Input already connected')
        occupied_inputs.add(destination)
    if state['settings'].get('port_label_mode') not in ('hidden','contextual','always'):problems.append('Invalid port label mode')
    return problems


def transaction(state, change):
    """Validate a candidate draft edit before publishing it.

    The existing draft state is the only writable authority; this produces a
    replacement state, not an independent graph/port registry. The same shared
    semantic descriptor used by source/resource consumers gates all changes.
    """
    candidate=copy.deepcopy(state)
    change(candidate)
    errors=validate(candidate)
    if errors:
        raise ValueError('; '.join(errors[:6]))
    from .semantic_contract import describe_graph, ContractError
    try:
        describe_graph(candidate,origin='draft')
    except ContractError as exc:
        raise ValueError(str(exc)) from exc
    return candidate


def read_state(path):
    source=Path(path)
    if source.stat().st_size>MAX_FILE_BYTES:raise ValueError('Graph file exceeds 4 MB limit')
    data=json.loads(source.read_text(encoding='utf-8'))
    errors=validate(data)
    if errors:raise ValueError('; '.join(errors[:6]))
    for key,value in DEFAULT_SETTINGS.items():data['settings'].setdefault(key,copy.deepcopy(value))
    return data


def write_state(path,state):
    errors=validate(state)
    if errors:raise ValueError('; '.join(errors[:6]))
    content=json.dumps(state,ensure_ascii=False,indent=2)+'\n'
    if len(content.encode('utf-8'))>MAX_FILE_BYTES:raise ValueError('Graph exceeds 4 MB limit')
    Path(path).write_text(content,encoding='utf-8')
