"""Read the bundled atlas's existing pack.json for Qt icon previews.

This indexes pre-existing art; the manifest is not a semantic catalog and is
never permitted to point outside the bundled pack root.
"""
from __future__ import annotations
import json
from pathlib import Path


class AssetIndex:
    def __init__(self,root):
        self.root=Path(root).resolve()
        path=self.root/'pack.json'
        self.entries={}
        self.sheets={}
        if not path.is_file():return
        if path.stat().st_size>512_000:raise ValueError('Atlas manifest too large')
        data=json.loads(path.read_text(encoding='utf-8'))
        if data.get('schema_version')!=1:raise ValueError('Unsupported atlas manifest version')
        for sheet in data.get('sheets',[]):
            rel=sheet.get('image','')
            image_path=(self.root/rel).resolve()
            if not image_path.is_relative_to(self.root) or not image_path.is_file() or image_path.is_symlink():
                raise ValueError('Atlas sheet escapes the pack')
            cp=sheet['cell_px'];width=sheet['width_px'];height=sheet['height_px']
            if not all(type(x)==int for x in (cp,width,height)) or not (1<=cp<=1024 and 1<=width<=8192 and 1<=height<=8192):
                raise ValueError('Invalid sheet dimensions')
            self.sheets[rel]=image_path
            for asset in sheet.get('assets',[]):
                ident=asset.get('id');cell=asset.get('cells')
                if not isinstance(ident,str) or ident in self.entries or not isinstance(cell,dict):
                    raise ValueError('Invalid or repeated asset id')
                if not all(type(cell.get(k))==int for k in ('x','y','w','h')):
                    raise ValueError('Bad crop coordinates')
                x=cell['x']*cp;y=cell['y']*cp;w=cell['w']*cp;h=cell['h']*cp
                if x<0 or y<0 or w<=0 or h<=0 or x+w>width or y+h>height:
                    raise ValueError('Atlas crop outside sheet')
                self.entries[ident]={'id':ident,'slot':asset.get('slot',''),'sheet':rel,'rect':(x,y,w,h),'tags':asset.get('tags',[])}

    def find(self,slot='',search=''):
        q=search.strip().lower()
        return [e for e in self.entries.values() if (not slot or e['slot']==slot) and
                (not q or q in ' '.join([e['id'],e['slot'],*e['tags']]).lower())]
