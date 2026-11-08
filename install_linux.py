"""Safe, standard-library Linux installer for the versioned Node Lab ZIP.

Deployment is not graph/runtime state. This module is deliberately independent
from the Qt application, and it never uses sudo or broad process-name matching.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import zipfile

APP_NAME = 'Superior-MI-Python-Visual-Programming-Lab'
VERSION = 'v2.129'
BASENAME = f'{APP_NAME}-{VERSION}'
VERSION_DIRECTORY = re.compile(rf'{re.escape(APP_NAME)}-v\d+\.\d+(?:\.\d+)?\Z')
REPORT_NAME = re.compile(r'qualification-\d{8}-\d{6}-\d+\Z')


def run_qualification(dest: Path, *, headless: bool) -> int:
    """Bound the entire runner, not just its doctor/Qt children.

    In particular, nested test subprocesses must not survive an abandoned
    installation. A timeout fails closed and cannot trigger version pruning.
    Native Linux creates a private process group for this release runner.
    """
    timeout_text=os.environ.get('SMI_INSTALL_QUALIFICATION_TIMEOUT','520')
    try:
        deadline=float(timeout_text)
    except ValueError as exc:
        raise ValueError('Invalid SMI_INSTALL_QUALIFICATION_TIMEOUT') from exc
    if not (0 < deadline <= 3600):
        raise ValueError('Qualification timeout must be within (0, 3600] seconds')
    argv=['bash',str(dest/'RUN-ALL.sh')]+(['--headless'] if headless else [])
    child=subprocess.Popen(argv,cwd=dest,start_new_session=True)
    try:
        return child.wait(timeout=deadline)
    except subprocess.TimeoutExpired:
        print(f'QUALIFICATION TIMEOUT after {deadline:g}s. Prior installs preserved; '
              'inspect retained report logs.',file=sys.stderr,flush=True)
        # Kill the *private* test process group, never a Studio process found
        # through a loose name match. A child holding an inherited output pipe
        # is terminated as well.
        try:
            os.killpg(child.pid,signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            child.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()
        return 124


def installed_versions(projects: Path) -> list[Path]:
    """Only direct, real, version-named directories; never follow links."""
    return sorted((p for p in projects.iterdir()
                   if VERSION_DIRECTORY.fullmatch(p.name) and p.is_dir() and not p.is_symlink()),
                  key=lambda p: tuple(int(part) for part in
                                      p.name[len(APP_NAME)+2:].split('.')))


def validate_archive(zf: zipfile.ZipFile) -> None:
    """Refuse nonstandard roots, link entries and traversal before extraction."""
    members = zf.infolist()
    if not members:
        raise ValueError('Empty installation ZIP')
    for member in members:
        raw = PurePosixPath(member.filename)
        if (raw.is_absolute() or not raw.parts or raw.parts[0] != BASENAME
                or any(p in ('.', '..') for p in raw.parts)
                or '\\' in member.filename):
            raise ValueError(f'Unsafe ZIP entry: {member.filename!r}')
        if stat.S_ISLNK(member.external_attr >> 16):
            raise ValueError(f'ZIP symlink refused: {member.filename!r}')
    names = set(zf.namelist())
    for required in ('RUN-ALL.sh', 'launch-linux.sh', 'studio_native/navigation.py'):
        if f'{BASENAME}/{required}' not in names:
            raise ValueError(f'Missing release file: {required}')
    bad = zf.testzip()
    if bad:
        raise ValueError(f'ZIP integrity failed at {bad}')


def installed_matches_archive(zf: zipfile.ZipFile, target: Path) -> bool:
    """An existing install is reusable only when all shipped files match.

    Generated caches and user-created files are ignored, never overwritten.
    """
    if not target.is_dir() or target.is_symlink():
        return False
    for item in zf.infolist():
        relative=PurePosixPath(item.filename)
        path=target.joinpath(*relative.parts[1:])
        if item.is_dir():
            if not path.is_dir() or path.is_symlink():
                return False
            continue
        if not path.is_file() or path.is_symlink():
            return False
        expected=hashlib.sha256(zf.read(item)).digest()
        actual=hashlib.sha256(path.read_bytes()).digest()
        if expected != actual:
            return False
    return True


def matches_gui_process(args: list[str], cwd: Path, projects: Path) -> bool:
    """Only the exact Qt app invocation launched in a managed version folder."""
    if not (VERSION_DIRECTORY.fullmatch(cwd.name) and cwd.parent == projects):
        return False
    return any(args[i] == '-m' and args[i + 1] == 'studio_native'
               for i in range(len(args)-1))


def local_processes(projects: Path):
    """Yield own-user processes based on /proc; no grep or unrelated Python kills."""
    proc = Path('/proc')
    if not proc.is_dir():
        return
    for item in proc.iterdir():
        if not item.name.isdecimal() or int(item.name) == os.getpid():
            continue
        try:
            if item.stat().st_uid != os.getuid():
                continue
            cwd = Path(os.readlink(item/'cwd')).resolve()
            raw = (item/'cmdline').read_bytes()
            args = [a.decode('utf-8', errors='replace') for a in raw.split(b'\0') if a]
            yield int(item.name), cwd, args
        except (OSError, PermissionError, ProcessLookupError):
            continue


def stop_node_lab(projects: Path) -> None:
    targets = [(pid,cwd) for pid,cwd,args in local_processes(projects)
               if matches_gui_process(args,cwd,projects)]
    if not targets:
        print('No running Node Lab Qt editors found.')
        return
    for pid,cwd in targets:
        print(f'Closing Node Lab PID {pid} ({cwd.name}) with SIGTERM...')
        try:
            os.kill(pid,signal.SIGTERM)
        except ProcessLookupError:
            pass
    # Avoid SIGKILL. If the application cannot exit cleanly, preserve it and
    # abort rather than deleting resources under a running process.
    deadline=time.monotonic()+6
    while time.monotonic()<deadline:
        running={pid for pid,_,_ in local_processes(projects)}
        if all(pid not in running for pid,_ in targets):
            return
        time.sleep(.1)
    raise RuntimeError('Node Lab did not close cleanly. Close it manually and rerun; no folders were deleted.')


def occupied_versions(projects: Path) -> set[Path]:
    return {cwd for _,cwd,_ in local_processes(projects)
            if VERSION_DIRECTORY.fullmatch(cwd.name) and cwd.parent == projects}


def prune_versions(projects: Path, installed: Path) -> None:
    in_use=occupied_versions(projects)
    for folder in installed_versions(projects):
        if folder == installed:
            continue
        if folder in in_use:
            print(f'PRESERVED (another process is using it): {folder}')
            continue
        print(f'Removing old version: {folder}')
        shutil.rmtree(folder)


def prune_logs(downloads: Path, *, keep: Path | None) -> None:
    """Clean only application-owned reports; retain the latest qualification."""
    log_dir=downloads/'SMI-NodeLab-Logs'
    if log_dir.is_dir() and not log_dir.is_symlink():
        for entry in log_dir.iterdir():
            name=entry.name
            is_report = bool(REPORT_NAME.fullmatch(name) or
                             (name.endswith('.tar.gz') and REPORT_NAME.fullmatch(name[:-7])))
            is_launch = bool(re.fullmatch(r'launch-\d{8}-\d{6}-\d+\.log',name))
            if not (is_report or is_launch) or entry.is_symlink():
                continue
            if keep and (entry == keep or entry == Path(str(keep)+'.tar.gz')):
                continue
            if entry.is_dir():
                shutil.rmtree(entry)
            elif entry.is_file():
                entry.unlink()
            print(f'Removed old log: {entry.name}')
    # Older releases also placed doctor logs directly in Downloads.
    for entry in downloads.iterdir():
        if entry.is_symlink() or not entry.is_file():
            continue
        if re.fullmatch(r'SMI-v\d+\.\d+(?:\.\d+)?-[A-Za-z0-9-]+\.log',entry.name):
            entry.unlink()
            print(f'Removed old standalone log: {entry.name}')


def latest_report(downloads: Path) -> Path | None:
    root=downloads/'SMI-NodeLab-Logs'
    if not root.is_dir():
        return None
    reports=[x for x in root.iterdir() if x.is_dir() and not x.is_symlink()
             and REPORT_NAME.fullmatch(x.name)]
    return max(reports,key=lambda p:p.stat().st_mtime_ns) if reports else None


def install(archive: Path, *, launch: bool = True, headless: bool = False) -> int:
    home=Path.home()
    projects=(home/'Projects').resolve()
    downloads=(home/'Downloads').resolve()
    projects.mkdir(parents=True,exist_ok=True)
    downloads.mkdir(parents=True,exist_ok=True)
    dest=projects/BASENAME
    if not archive.is_file():
        print(f'ERROR: ZIP missing: {archive}',file=sys.stderr)
        return 3
    print(f'Verifying archive: {archive}',flush=True)
    with zipfile.ZipFile(archive) as zf:
        validate_archive(zf)
        print('Archive integrity: PASS',flush=True)
        reuse = dest.exists() or dest.is_symlink()
        if reuse and not installed_matches_archive(zf,dest):
            print(f'ERROR: Existing install differs from archive: {dest}\n'
                  'Preserved local files. Resolve differences manually before retry.',file=sys.stderr)
            return 3
        # Stop only Node Lab GUI processes, and only after validating ZIP.
        stop_node_lab(projects)
        if not reuse:
            stage=Path(tempfile.mkdtemp(prefix='.smi-nodelab-install-',dir=projects))
            try:
                zf.extractall(stage)
                # zipfile.extractall does not restore POSIX executable bits.
                # Preserve only executable shell-script permissions declared in
                # the validated archive; never copy suid/sgid or arbitrary modes.
                for member in zf.infolist():
                    if (member.filename.endswith('.sh') and
                            member.external_attr >> 16 & 0o111):
                        script=stage.joinpath(*PurePosixPath(member.filename).parts)
                        if script.is_file() and not script.is_symlink():
                            script.chmod(script.stat().st_mode | 0o111)
                source=stage/BASENAME
                if not source.is_dir():
                    raise RuntimeError('Release root directory absent after extraction')
                source.rename(dest)
            finally:
                shutil.rmtree(stage,ignore_errors=True)
        else:
            print(f'Identical {VERSION} already installed; re-running qualification without overwriting files.')
    print(f'Installed: {dest}',flush=True)
    print('Running release qualification (logs retained on any failure)...',flush=True)
    # If PyQt6 or real GUI checks fail, never remove the last working version.
    qualification_status=run_qualification(dest,headless=headless)
    if qualification_status:
        print('QUALIFICATION FAILED. Previous versions/logs preserved. Upload the printed report.',file=sys.stderr)
        return qualification_status
    if headless:
        print('HEADLESS-ONLY PASS: previous versions/logs preserved until native Qt passes.')
        return 0
    current=latest_report(downloads)
    # Existing desktop shortcut otherwise becomes a dead link after cleanup.
    shortcut=home/'.local/share/applications/superior-mi-python-visual-programming-lab.desktop'
    if shortcut.exists() and not shortcut.is_symlink():
        subprocess.run(['bash',str(dest/'install-desktop-shortcut.sh')],cwd=dest,check=True)
    prune_versions(projects,dest)
    prune_logs(downloads,keep=current)
    print(f'INSTALL & NATIVE QT PASS: {dest}\nLatest report preserved: {current}',flush=True)
    if launch:
        return subprocess.run(['bash',str(dest/'launch-linux.sh')],cwd=dest,check=False).returncode
    return 0


def main() -> int:
    parser=argparse.ArgumentParser(description='Node Lab versioned installer, safe scope cleanup')
    parser.add_argument('zip',type=Path,help=f'Exact {VERSION} ZIP path')
    parser.add_argument('--no-launch',action='store_true',help='Qualify and install without opening GUI afterward')
    parser.add_argument('--headless',action='store_true',help='Run doctor only; never prune old versions or logs')
    args=parser.parse_args()
    try:
        return install(args.zip.expanduser().resolve(),launch=not args.no_launch,headless=args.headless)
    except (OSError,ValueError,RuntimeError,zipfile.BadZipFile) as exc:
        print(f'INSTALL ABORTED: {exc}',file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
