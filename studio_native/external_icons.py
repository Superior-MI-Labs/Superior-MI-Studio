"""Optional *external* Universal Icon Vocabulary resolver (no Qt dependency).

    The manifest remains authoritative. Studio never copies an icon pack into
    its Python application, scans arbitrary downloads, or requires it to run.
    Only explicitly installed locations are considered. Images load lazily in
    the existing Qt renderer; this module only resolves validated coordinates.
"""
from __future__ import annotations
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

PACK_ID='org.superior-mi.studio.universal-icons'


def default_icon_atlas_directory() -> Path:
    configured=os.environ.get('SMI_ICON_ATLAS_DIR')
    if configured:return Path(configured).expanduser()
    if sys.platform=='win32':
        root=os.environ.get('LOCALAPPDATA')
        if root:return Path(root)/'SuperiorMILabs'/'IconAtlas'
        return Path.home()/'AppData'/'Local'/'SuperiorMILabs'/'IconAtlas'
    return Path.home()/'.local'/'share'/'superior-mi'/'icon-atlas'


@dataclass(frozen=True)
class ExternalIconAtlas:
    root: Path
    entries: dict[str,tuple[Path,tuple[int,int,int,int]]]
    version: str

    @classmethod
    def discover(cls, location: Path | str) -> 'ExternalIconAtlas | None':
        base=Path(location).expanduser()
        candidates=[base]
        if base.is_dir():
            candidates += [p for p in base.iterdir()
                           if p.is_dir() and not p.is_symlink() and (p/'manifest.json').is_file()]
        for folder in candidates:
            try:return cls.from_directory(folder)
            except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError):continue
        return None

    @classmethod
    def from_directory(cls, folder: Path | str) -> 'ExternalIconAtlas':
        root=Path(folder).expanduser().resolve(strict=True)
        path=root/'manifest.json'
        if path.stat().st_size>16_000_000:raise ValueError('Icon manifest too large')
        data=json.loads(path.read_text(encoding='utf-8'))
        if data.get('pack_id')!=PACK_ID or not str(data.get('schema_version','')).startswith('4.'):
            raise ValueError('Unsupported icon manifest')
        entries={}
        for sheet in data.get('sheets',[]):
            rel=sheet['files']['rgba']
            asset_file=(root/rel).resolve()
            if not asset_file.is_relative_to(root) or not asset_file.is_file():
                raise ValueError('Atlas sheet outside installation')
            for asset in sheet.get('assets',[]):
                ident=asset['id'];r=asset['rect_px']
                rect=tuple(r[k] for k in ('x','y','w','h'))
                if (not isinstance(ident,str) or ident in entries or
                    not all(type(v) is int for v in rect) or
                    min(rect)<0 or rect[2]<=0 or rect[3]<=0 or
                    rect[0]+rect[2]>8192 or rect[1]+rect[3]>8192):
                    raise ValueError('Invalid icon coordinate or identity')
                entries[ident]=(asset_file,rect)
        if not entries:raise ValueError('Empty icon pack')
        return cls(root,entries,str(data['version']))

    def lookup(self, icon_id: str):
        return self.entries.get(icon_id)


def icon_id_for_resource(kind: str, suffix: str='') -> str:
    if kind=='directory':return 'icons.files.archives-disk-images-and-installers.folder'
    if suffix=='.py':return 'icons.files-formats.python-source'
    if suffix=='.md':return 'icons.files-formats.markdown'
    if suffix=='.json':return 'icons.files-formats.json-file'
    if suffix=='.sh':return 'icons.files-formats.bash-script'
    return 'icons.files-formats.plain-text'


def icon_id_for_source(kind: str) -> str:
    return {'function':'icons.programming.oop.function_definition',
            'if':'icons.programming.control.if',
            'loop':'icons.programming.control.while_loop',
            'class':'icons.programming.oop.class',
            'return':'icons.programming.structure.exit',
            }.get(kind,'icons.programming.structure.file')
