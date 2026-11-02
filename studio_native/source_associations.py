"""Bounded static local-file relationship candidates for the resource graph.

Never import, execute, or recursively crawl project code. Python's actual
import resolution is runtime dependent; each returned relationship is a
*syntactic local-file candidate*, not proof of runtime module loading.
"""
from __future__ import annotations
import ast
import io
import os
import stat
import tokenize
from dataclasses import dataclass
from pathlib import Path

MAX_ASSOCIATION_BYTES = 512_000
MAX_CANDIDATES_PER_FILE = 64


def _parse_existing_source(path: Path, source_texts=None):
    """One bounded parse from the live source owner or a safe regular file.

    A source session is the sole authority while open. For unopened files,
    read through a no-follow, non-blocking descriptor and validate fstat so
    symlink swaps, special files and oversized inputs cannot enter the AST
    evidence pipeline. This read never executes project code.
    """
    path=Path(path).absolute()
    try:
        if path.is_symlink():return None
        if source_texts is not None and path in source_texts:
            text=source_texts[path]
            if not isinstance(text,str) or len(text.encode('utf-8'))>MAX_ASSOCIATION_BYTES:
                return None
        else:
            flags=os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0)
            fd=os.open(path,flags)
            with os.fdopen(fd,'rb') as stream:
                info=os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size>MAX_ASSOCIATION_BYTES:
                    return None
                content=stream.read(MAX_ASSOCIATION_BYTES+1)
            if len(content)>MAX_ASSOCIATION_BYTES:return None
            encoding,_=tokenize.detect_encoding(io.BytesIO(content).readline)
            text=content.decode(encoding)
        return text,ast.parse(text,filename=str(path))
    except (OSError,UnicodeError,SyntaxError,ValueError,LookupError,OverflowError):
        return None



def verified_evidence_line(source_text: str, line: int, syntax: str) -> int | None:
    """Verify a resource edge's syntax against the *current* source revision.

    A line number alone is not a location contract after an unsaved edit.
    Match the exact Import/ImportFrom/Call AST source segment and starting
    line, without executing code or trusting a stale on-disk projection.
    Synthesized declaration annotations intentionally cannot qualify.
    """
    if (not isinstance(source_text,str) or type(line) is not int or line<1 or
            not isinstance(syntax,str) or not syntax or
            len(source_text.encode('utf-8'))>MAX_ASSOCIATION_BYTES):
        return None
    try:tree=ast.parse(source_text)
    except (SyntaxError,ValueError,TypeError,OverflowError):return None
    for node in ast.walk(tree):
        if (isinstance(node,(ast.Import,ast.ImportFrom,ast.Call)) and
                node.lineno==line and ast.get_source_segment(source_text,node)==syntax):
            return line
    return None


def _visible_module(source: Path, module: str, available: set[Path], *,
                    workspace_root: Path | None=None, relative=False) -> Path | None:
    """Syntactic module candidate in the visible set; never runtime resolution.

    A multi-segment absolute name is anchored to the explicitly browsed
    workspace root; a one-segment name remains sibling-local. Package paths
    require visible, regular __init__.py evidence at every intermediate level.
    No parent traversal, namespace-package guessing or disk index is used.
    """
    parts=module.split('.')
    if not 1<=len(parts)<=4 or any(not part.isidentifier() for part in parts):
        return None
    root=(Path(workspace_root).absolute() if workspace_root is not None else None)
    if root is None and len(parts)!=1:return None
    base=source.parent if relative or len(parts)==1 else root
    if root is not None:
        try:source.relative_to(root)
        except ValueError:return None
    cursor=base
    for part in parts[:-1]:
        cursor=cursor/part
        init=cursor/'__init__.py'
        if (cursor.is_symlink() or init not in available or init.is_symlink() or
                not init.is_file()):return None
    leaf=cursor/(parts[-1]+'.py')
    if leaf not in available:
        # A package import can resolve to the visible __init__.py, but it is
        # still just a static candidate and not proof of module loading.
        folder=cursor/parts[-1]
        leaf=folder/'__init__.py'
        if folder.is_symlink():return None
    if leaf==source or leaf not in available or leaf.is_symlink():return None
    if root is not None:
        try:leaf.relative_to(root)
        except ValueError:return None
    return leaf


@dataclass(frozen=True)
class ImportCandidate:
    source: Path
    target: Path
    line: int
    evidence: str
    certainty: str = 'local-file-candidate'


def local_python_imports(source: Path, available: set[Path], *, source_texts=None,
                         workspace_root: Path | None=None) -> list[ImportCandidate]:
    """Visible local module-name candidates, not import execution evidence.

    Standalone use preserves v2.87 sibling-only semantics. With an explicit
    workspace root, dotted packages are considered only when every segment
    and its __init__.py is already visible through explicit expansion.
    Relative imports support a single dot only in an existing package.
    """
    source=Path(source).absolute()
    if source.is_symlink() or source.suffix.lower()!='.py':return []
    parsed=_parse_existing_source(source,source_texts)
    if parsed is None:return []
    text,tree=parsed
    available={Path(p).absolute() for p in available if not Path(p).is_symlink()}
    result=[]
    package_init=source.parent/'__init__.py'
    relative_ok=package_init.is_file() and not package_init.is_symlink()
    for statement in ast.walk(tree):
        names=[]
        if isinstance(statement,ast.Import):
            names=[(alias.name,False) for alias in statement.names]
        elif isinstance(statement,ast.ImportFrom):
            if statement.level==0 and statement.module:
                names=[(statement.module,False)]
            elif statement.level==1 and relative_ok:
                names=([(statement.module,True)] if statement.module else
                       [(alias.name,True) for alias in statement.names])
        else:continue
        for name,relative in names:
            candidate=_visible_module(source,name,available,
                workspace_root=workspace_root,relative=relative)
            if candidate is None:continue
            evidence=ast.get_source_segment(text,statement) or ('import '+name)
            result.append(ImportCandidate(source,candidate,statement.lineno,evidence))
            if len(result)>=MAX_CANDIDATES_PER_FILE:return result
    return result

@dataclass(frozen=True)
class SymbolCandidate:
    """Source-backed declaration match; NOT proof of a runtime binding."""
    source: Path
    target: Path
    symbol: str
    import_line: int
    declaration_line: int
    declaration_kind: str
    certainty: str = 'syntactic-name-match'


def local_python_symbol_candidates(source: Path, available: set[Path], *,
                                   source_texts=None,
                                   workspace_root: Path | None=None) -> list[SymbolCandidate]:
    """Match imported names against visible top-level Python declarations.

    No call-dispatch, sys.path, conditional execution, or rebinding claims.
    Both files use the same bounded source reader, including live drafts.
    """
    source=Path(source).absolute()
    available={Path(p).absolute() for p in available if not Path(p).is_symlink()}
    if source.is_symlink() or source not in available:return []
    parsed=_parse_existing_source(source,source_texts)
    if parsed is None:return []
    _,tree=parsed
    out=[];cache={}
    relative_ok=(source.parent/'__init__.py').is_file() and not (source.parent/'__init__.py').is_symlink()
    for item in tree.body:
        if not isinstance(item,ast.ImportFrom) or not item.module or item.level>1:
            continue
        if item.level==1 and not relative_ok:continue
        target=_visible_module(source,item.module,available,workspace_root=workspace_root,
                               relative=item.level==1)
        if target is None:continue
        if target not in cache:cache[target]=_parse_existing_source(target,source_texts)
        target_parse=cache[target]
        if target_parse is None:continue
        _,other=target_parse
        declarations={}
        for stmt in other.body:
            if isinstance(stmt,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                declarations.setdefault(stmt.name,(stmt.lineno,type(stmt).__name__))
            elif isinstance(stmt,(ast.Assign,ast.AnnAssign)):
                targets=(stmt.targets if isinstance(stmt,ast.Assign) else [stmt.target])
                for target_expr in targets:
                    if isinstance(target_expr,ast.Name):
                        declarations.setdefault(target_expr.id,(stmt.lineno,'assignment'))
        for alias in item.names:
            if alias.name not in declarations:continue
            line,kind=declarations[alias.name]
            out.append(SymbolCandidate(source,target,alias.name,item.lineno,line,kind))
            if len(out)>=MAX_CANDIDATES_PER_FILE:return out
    return out

@dataclass(frozen=True)
class LiteralFileCandidate:
    """A literal filename expression, NOT proof of a successful runtime read."""
    source: Path
    target: Path
    line: int
    evidence: str
    certainty: str = 'literal-path-candidate'


def local_python_literal_files(source: Path, available: set[Path], *, source_texts=None,
                               workspace_root: Path | None=None) -> list[LiteralFileCandidate]:
    """Only explicit filename arguments to known resource-oriented expressions.

    `Path('x')`, `open('x')`, `Image.open('x')`, and `Path('x').open()`
    are syntactic candidates. Dynamic strings, traversal, symlinks, paths
    outside the visible directory, and unrelated string constants are ignored.
    When supplied the explicit workspace root, forward child paths such as
    `assets/icon.png` can connect to files *already visible* in explicitly
    expanded directories. Never traverse parents or symlinks, scan hidden
    children, or infer runtime path resolution. Standalone callers retain the
    original sibling-only behavior.
    """
    source=Path(source).absolute()
    available={Path(p).absolute() for p in available if not Path(p).is_symlink()}
    if source.is_symlink() or source.suffix.lower()!='.py' or source not in available:
        return []
    parsed=_parse_existing_source(source,source_texts)
    if parsed is None:return []
    text,tree=parsed
    results=[]
    for node in ast.walk(tree):
        if not isinstance(node,ast.Call) or not node.args:continue
        func=node.func
        recognized=(isinstance(func,ast.Name) and func.id in ('open','Path')) or (
            isinstance(func,ast.Attribute) and func.attr=='open' and (
                isinstance(func.value,ast.Name) and func.value.id=='Image'))
        if not recognized:continue
        arg=node.args[0]
        if not isinstance(arg,ast.Constant) or type(arg.value) is not str:continue
        raw=arg.value
        # A literal reference is not proof of a runtime file access. Relate
        # only exact visible file cards. Child paths are opt-in for the
        # workspace graph and cannot traverse parents or symlink directories.
        if (not raw or len(raw)>240 or raw.startswith('/') or '\\' in raw or
                '\x00' in raw or ':' in raw):continue
        pieces=raw.split('/')
        if (len(pieces)>4 or any(part in ('','.','..') for part in pieces) or
                (workspace_root is None and len(pieces)!=1)):continue
        target=source.parent.joinpath(*pieces)
        if workspace_root is not None:
            root=Path(workspace_root).absolute()
            try:
                source.relative_to(root)
                target.relative_to(root)
            except ValueError:continue
        cursor=source.parent
        unsafe=False
        for segment in pieces[:-1]:
            cursor=cursor/segment
            if cursor.is_symlink():unsafe=True;break
        if unsafe or target==source or target not in available or target.is_symlink() or not target.is_file():continue
        results.append(LiteralFileCandidate(source,target,node.lineno,
                                           ast.get_source_segment(text,node) or raw))
        if len(results)>=MAX_CANDIDATES_PER_FILE:break
    return results
