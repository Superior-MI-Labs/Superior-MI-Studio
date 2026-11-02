"""Versioned user-owned graph presentation state (no Qt or language semantics).

This file records ONLY view preferences. It must never contain or overwrite
source text, resource content, graph edges, or hand-authored node values.
"""
from __future__ import annotations

import json
import math
import os
import tempfile
from pathlib import Path

VERSION = 1
MAX_BYTES = 4_000_000
MAX_RECORDS = 30_000
MAX_COORD = 2_000_000.0


def default_location() -> Path:
    override = os.environ.get('SMI_PRESENTATION_STATE_FILE')
    if override:
        return Path(override).expanduser()
    if os.name == 'nt':
        root = os.environ.get('LOCALAPPDATA')
        return Path(root).expanduser() / 'SuperiorMILabs' / 'Studio' / 'view-state.json' if root else Path.home() / 'AppData' / 'Local' / 'SuperiorMILabs' / 'Studio' / 'view-state.json'
    root = os.environ.get('XDG_CONFIG_HOME')
    return (Path(root).expanduser() if root else Path.home() / '.config') / 'superior-mi' / 'studio' / 'view-state.json'


def _number(value, *, positive=False) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > MAX_COORD:
        raise ValueError('Invalid presentation coordinate')
    if positive and value <= 0:
        raise ValueError('Invalid positive presentation dimension')
    return float(value)


def _string(value) -> str:
    if not isinstance(value, str) or not value or len(value) > 4096 or '\x00' in value:
        raise ValueError('Invalid presentation identity')
    return value


def _records(value, fields, numbers=(), *, positive=()):
    if not isinstance(value, list) or len(value) > MAX_RECORDS:
        raise ValueError('Invalid presentation records')
    result = []
    seen = set()
    for entry in value:
        if not isinstance(entry, dict):
            raise ValueError('Invalid presentation record')
        norm = {key: (_number(entry[key], positive=key in positive) if key in numbers
                      else _string(entry[key])) for key in fields}
        identity = tuple(norm[k] for k in fields if k not in numbers)
        if identity in seen:
            raise ValueError('Duplicate presentation record')
        seen.add(identity)
        result.append(norm)
    return result


def _string_list(value):
    if not isinstance(value, list) or len(value) > MAX_RECORDS:
        raise ValueError('Invalid presentation list')
    return sorted(set(_string(v) for v in value))


def _dock_modes(value):
    """Presentation-only dock regions; reject unknown states or arbitrary keys."""
    if not isinstance(value, dict) or set(value)-{'left','right'}:
        raise ValueError('Unknown docking region')
    if any(mode not in ('pinned','collapsed','auto-hide') for mode in value.values()):
        raise ValueError('Invalid dock visibility mode')
    return {'left':value.get('left','pinned'),'right':value.get('right','pinned')}


def validate(raw: dict) -> dict:
    if not isinstance(raw, dict) or raw.get('version') != VERSION:
        raise ValueError('Unsupported presentation state version')
    documents = raw.get('documents', {})
    if not isinstance(documents, dict) or len(documents) > 1000:
        raise ValueError('Invalid document preferences')
    normalized_docs = {}
    for path, prefs in documents.items():
        _string(path)
        if not isinstance(prefs, dict):
            raise ValueError('Invalid document preference')
        normalized_docs[path] = {
            'expanded': _string_list(prefs.get('expanded', [])),
            'collapsed': _string_list(prefs.get('collapsed', [])),
        }
    cameras=_records(raw.get('cameras', []), ('path','graph','x','y','zoom'), ('x','y','zoom'), positive=('zoom',))
    if any(not 0.01 <= item['zoom'] <= 2.5 for item in cameras):
        raise ValueError('Invalid presentation zoom')
    return {
        'version': VERSION,
        'source_positions': _records(raw.get('source_positions', []), ('path','view','node','x','y'), ('x','y')),
        'resource_positions': _records(raw.get('resource_positions', []), ('node','x','y'), ('x','y')),
        'setting_positions': _records(raw.get('setting_positions', []), ('node','x','y'), ('x','y')),
        'cameras': cameras,
        'sizes': _records(raw.get('sizes', []), ('path','graph','width','height'), ('width','height'), positive=('width','height')),
        'front': _records(raw.get('front', []), ('path','graph','node')),
        'documents': normalized_docs,
        'resource_expanded': _string_list(raw.get('resource_expanded', [])),
        'resource_path': _string(raw.get('resource_path') or str(Path.home())),
        'dock_modes': _dock_modes(raw.get('dock_modes', {})),
    }


def blank() -> dict:
    return validate({'version': VERSION})


class PresentationStore:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path is not None else default_location()
        self.error = None

    def load(self):
        self.error = None
        if not self.path.exists():
            return blank()
        try:
            if self.path.stat().st_size > MAX_BYTES:
                raise ValueError('Presentation state exceeds size limit')
            data = json.loads(self.path.read_text(encoding='utf-8'))
            return validate(data)
        except (OSError, ValueError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
            self.error = str(exc)
            return blank()

    def save(self, data: dict):
        clean = validate(data)
        payload = json.dumps(clean, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
        if len(payload) > MAX_BYTES:
            raise ValueError('Presentation state exceeds size limit')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp = tempfile.mkstemp(prefix='.view-state-', suffix='.tmp', dir=str(self.path.parent))
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, self.path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
