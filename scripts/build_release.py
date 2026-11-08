#!/usr/bin/env python3
"""Build one deterministic, integrity-verified Studio source release ZIP.

Version, archive root and installer requirements come from the existing
install_linux.py contract. This script replaces ad-hoc external ZIP assembly.
No project source outside the release manifest is installed or executed.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from install_linux import BASENAME, VERSION, validate_archive  # noqa: E402

OMIT_DIRS={'.git','.agent-artifacts','__pycache__','.mypy_cache','.pytest_cache','.venv'}
OMIT_NAMES={'REPOSITORY-SHA256SUMS.txt'}


def source_files(root: Path) -> list[Path]:
    result=[]
    for path in root.rglob('*'):
        relative=path.relative_to(root)
        if any(part in OMIT_DIRS for part in relative.parts):
            continue
        if path.is_symlink():
            raise ValueError('Release source contains symlink: '+relative.as_posix())
        if (not path.is_file() or path.name in OMIT_NAMES or path.suffix in ('.pyc','.pyo')
                or path.name.endswith(('.smi-lock', '.smi-previous'))):
            continue
        result.append(path)
    return sorted(result,key=lambda path:path.relative_to(root).as_posix())


def build(target: Path, root: Path = ROOT) -> tuple[int, str]:
    target=target.expanduser().absolute()
    if target.exists() or target.is_symlink():
        raise FileExistsError('Refusing to replace an existing release: '+str(target))
    # A Git checkout may be named `Superior-MI-Studio` or anything else.
    # Only the archive's *internal root* is versioned, never the source folder.
    # Read the candidate's own installer declaration without executing it,
    # and compare against the version imported from the canonical installer.
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Release source must be a real directory')
    try:
        source_tree=ast.parse((root/'install_linux.py').read_text(encoding='utf-8'))
    except (OSError,UnicodeError,SyntaxError) as exc:
        raise ValueError('Release source has no readable installer declaration') from exc
    declared=[node.value.value for node in source_tree.body
              if isinstance(node,ast.Assign) and len(node.targets)==1
              and isinstance(node.targets[0],ast.Name)
              and node.targets[0].id=='VERSION' and isinstance(node.value,ast.Constant)
              and type(node.value.value) is str]
    if declared != [VERSION]:
        raise ValueError('Release source installer version differs from authoritative version')
    files=source_files(root)
    manifest=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+
                     p.relative_to(root).as_posix()+'\n' for p in files).encode('utf-8')
    # Manifest is itself shipped but not recursively listed inside itself.
    entries=[(p.relative_to(root).as_posix(),p.read_bytes()) for p in files]
    entries.append(('REPOSITORY-SHA256SUMS.txt',manifest))
    entries.sort(key=lambda row:row[0])
    target.parent.mkdir(parents=True,exist_ok=True)
    fd,temporary=tempfile.mkstemp(dir=target.parent,prefix='.smi-release-',suffix='.zip')
    os.close(fd)
    try:
        with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=8) as archive:
            for name,data in entries:
                metadata=zipfile.ZipInfo(BASENAME+'/'+name,date_time=(1980,1,1,0,0,0))
                metadata.create_system=3
                mode=stat.S_IFREG | (0o755 if name.endswith('.sh') else 0o644)
                metadata.external_attr=mode<<16
                metadata.compress_type=zipfile.ZIP_DEFLATED
                archive.writestr(metadata,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=8)
        with zipfile.ZipFile(temporary) as archive:
            validate_archive(archive)
            for line in manifest.decode('utf-8').splitlines():
                expected,name=line.split('  ',1)
                if hashlib.sha256(archive.read(BASENAME+'/'+name)).hexdigest()!=expected:
                    raise ValueError('Manifest digest mismatch: '+name)
        # Hard-link publication is atomic and fails if another agent created
        # the destination after our initial check. os.replace would clobber it.
        os.link(temporary,target)
        return len(entries),hashlib.sha256(target.read_bytes()).hexdigest()
    finally:
        if os.path.exists(temporary):os.unlink(temporary)


def qualify_headless(root: Path = ROOT) -> None:
    """Reuse the existing agent gate before publishing a release archive.

    This does not replace native Qt host qualification or add a second test
    runner. Errors stop publication; the deterministic ZIP builder retains
    its no-overwrite and per-file hash validation contracts.
    """
    subprocess.run(['bash', 'scripts/agent-verify.sh', '--headless'],
                   cwd=root, check=True)


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True,help='New exact versioned ZIP path')
    parser.add_argument('--qualify-headless',action='store_true',
                        help='Run existing complete headless agent gate before building')
    args=parser.parse_args()
    try:
        if args.qualify_headless:
            qualify_headless()
        count,digest=build(args.output)
    except (OSError,ValueError,zipfile.BadZipFile,subprocess.CalledProcessError) as exc:
        print('RELEASE BUILD REFUSED:',exc,file=sys.stderr)
        return 1
    print('RELEASE_BUILD_PASS',count,'files',args.output,'sha256',digest)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
